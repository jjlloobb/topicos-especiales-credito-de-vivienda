"""Estado en memoria y lectura por `seq` (BR-U11-11; P-U11-01, 02, 04; NFR-U11-01, 02, 09..12).

- **Pasada completa** (al arrancar y una vez al dia): una sola lectura desde el dia 1 del sexto mes cerrado menos 1 dia. Cada
  pagina se pliega (`compute.absorb`) en los contadores de su mes y solo las decisiones de 35 dias se guardan. El estado nuevo se
  arma aparte, reemplaza al vigente en una sola asignacion y, con el candado todavia tomado, una lectura incremental desde su
  `last_seq` lo pone al dia.
- **Incremental** (cada 5 min): solo `seq` mayor que `last_seq`; si el candado esta tomado, devuelve «omitida» sin leer.
- `last_seq` nunca pasa de la ultima pagina confirmada: una pagina que falla no se aplica.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Final, Literal

from vectra_common.logging import log_access

from vectra_product import config
from vectra_product.compute import absorb, discard_old, first_relevant_month
from vectra_product.model import Counts, Decision, InvalidEntry, Snapshot, parse_entry
from vectra_product.reader import RawPage, Reader, ReadError

Result = Literal["done", "skipped"]
DONE: Final[Result] = "done"
SKIPPED: Final[Result] = "skipped"

#: Tipo de lectura que se cuenta en `vectra_product_entries_read_total{kind}` (NFR-U11-40).
Kind = Literal["incremental", "full"]
#: Punto de parada entre paginas (SIGTERM y plazo de la pasada, P-U11-02; INF-U11-01): lanza `Stopped` o `PassDeadline` y nunca
#: interrumpe una pagina en vuelo.
Checkpoint = Callable[[], None]
#: Se llama despues de cada pagina leida, con el tipo de lectura y el numero de entradas (items) de esa pagina.
ReadCallback = Callable[[Kind, int], None]


class NoBaseline(ReadError):
    """No hay pasada completa exitosa: una lectura incremental no tiene desde donde seguir."""


class PassDeadline(ReadError):
    """La pasada completa vencio su plazo (`config.FULL_PASS_DEADLINE_SECONDS`): falla y el estado vigente queda intacto."""


class Stopped(Exception):  # noqa: N818 - no es un error: SIGTERM pidio parar
    """`SIGTERM`: la lectura se interrumpe entre paginas. Una pasada a medias se descarta."""


def full_pass_start(now: datetime) -> datetime:
    """`recorded_from` de la pasada completa: dia 1 del mes de hace 6 meses, menos 1 dia (margen de la ventana de `occurred_at`)."""
    index = first_relevant_month(now.astimezone(UTC).date())
    first = date(index // 12, index % 12 + 1, 1)
    return datetime.combine(
        first - timedelta(days=config.FULL_PASS_MARGIN_DAYS), datetime.min.time(), tzinfo=UTC
    )


class _Data:
    """Los datos que se publican como una unidad: decisiones de 35 dias, contadores de meses y `last_seq`."""

    def __init__(self) -> None:
        self.entries: dict[int, Decision | InvalidEntry] = {}
        self.months: dict[int, Counts] = {}
        self.last_seq: int | None = None

    def apply(self, page: RawPage, today: date) -> None:
        for raw in page.items:
            seq = raw["seq"]
            if self.last_seq is not None and seq <= self.last_seq:
                continue  # leida antes: nunca se pliega dos veces
            entry = parse_entry(seq, raw)
            if isinstance(entry, InvalidEntry):
                # el `seq` solo va al log, nunca a una etiqueta (BR-U11-10); `log_access` lo deja pasar por el filtro de U0
                log_access(seq=seq)
            absorb(self.entries, self.months, entry, today)
        if page.items:
            self.last_seq = page.items[-1]["seq"]


class ProductState:
    def __init__(
        self,
        reader: Reader,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        on_read: ReadCallback | None = None,
    ) -> None:
        self._reader = reader
        self._clock = clock
        self._on_read = on_read
        self._data: _Data | None = None
        self.last_full_recompute_at: datetime | None = None
        self.last_success_at: datetime | None = None

    @property
    def last_seq(self) -> int | None:
        return None if self._data is None else self._data.last_seq

    def snapshot(self) -> Snapshot | None:
        """La instantanea para `compute`; `None` mientras no haya pasada completa. `compute` es sincrono: nadie la modifica a mitad."""
        return None if self._data is None else Snapshot(self._data.entries, self._data.months)

    def _read(self, kind: Kind, page: RawPage) -> None:
        if self._on_read is not None:
            self._on_read(kind, len(page.items))

    async def full_pass(self, checkpoint: Checkpoint | None = None) -> None:
        """Lee los 6 meses cerrados y el mes en curso. Espera el candado. Si falla, vence o se para, el estado vigente queda intacto.

        `checkpoint` se llama antes de la primera pagina y entre paginas (no tras la ultima: una pasada completa no se descarta por
        eso), nunca con una pagina en vuelo.
        """
        async with self._reader.exclusive():
            started = self._clock()
            data = _Data()
            if checkpoint is not None:
                checkpoint()
            async for page in self._reader.pages(None, full_pass_start(started)):
                self._read("full", page)
                data.apply(page, started.date())
                if checkpoint is not None and page.next_seq_after is not None:
                    checkpoint()
            discard_old(data.entries, data.months, self._clock().date())
            self._data = data  # reemplazo atomico: decisiones, contadores y `last_seq` cambian juntos
            self.last_full_recompute_at = self.last_success_at = self._clock()
            try:
                # con el candado todavia tomado, desde el `last_seq` de la pasada
                await self._incremental_locked(checkpoint)
            except ReadError:
                # la pasada si termino: el proximo ciclo sigue desde `last_seq`
                log_access(error_code="incremental_after_full_failed")

    async def incremental(self, checkpoint: Checkpoint | None = None) -> Result:
        """Una lectura de `seq > last_seq`. Si el candado esta tomado (pasada en curso o ciclo anterior), se omite sin leer."""
        async with self._reader.try_exclusive() as acquired:
            if not acquired:
                return SKIPPED
            await self._incremental_locked(checkpoint)
            return DONE

    async def _incremental_locked(self, checkpoint: Checkpoint | None) -> None:
        data = self._data
        if data is None:
            raise NoBaseline("sin pasada completa")
        if checkpoint is not None:
            checkpoint()
        async for page in self._reader.pages(data.last_seq, None):
            self._read("incremental", page)
            data.apply(page, self._clock().date())
            if checkpoint is not None and page.next_seq_after is not None:
                checkpoint()
        discard_old(data.entries, data.months, self._clock().date())
        self.last_success_at = self._clock()
