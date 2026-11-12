"""Estado en memoria y lectura por `seq` (BR-U11-11; P-U11-01, 02, 04; NFR-U11-01, 02, 09..12).

- **Pasada completa** (al arrancar y una vez al dia): una sola lectura desde el dia 1 del sexto mes cerrado menos 1 dia. Cada
  pagina se pliega (`compute.absorb`) en los contadores de su mes y solo las decisiones de 35 dias se guardan. El estado nuevo se
  arma aparte, reemplaza al vigente en una sola asignacion y, con el candado todavia tomado, una lectura incremental desde su
  `last_seq` lo pone al dia.
- **Incremental** (cada 5 min): solo `seq` mayor que `last_seq`; si el candado esta tomado, devuelve «omitida» sin leer.
- `last_seq` nunca pasa de la ultima pagina confirmada: una pagina que falla no se aplica.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Final, Literal

from vectra_product import config
from vectra_product.compute import absorb, discard_old, first_relevant_month
from vectra_product.model import Counts, Decision, InvalidEntry, Snapshot, parse_entry
from vectra_product.reader import RawPage, Reader, ReadError

log = logging.getLogger("vectra_product.state")

Result = Literal["done", "skipped"]
DONE: Final[Result] = "done"
SKIPPED: Final[Result] = "skipped"


class NoBaseline(ReadError):
    """No hay pasada completa exitosa: una lectura incremental no tiene desde donde seguir."""


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
                log.warning(
                    "entry_excluded seq=%d", seq
                )  # el `seq` solo va al log, nunca a una etiqueta (BR-U11-10)
            absorb(self.entries, self.months, entry, today)
        if page.items:
            self.last_seq = page.items[-1]["seq"]


class ProductState:
    def __init__(self, reader: Reader, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._reader = reader
        self._clock = clock
        self._data: _Data | None = None
        self.last_full_recompute_at: datetime | None = None
        self.last_success_at: datetime | None = None

    @property
    def last_seq(self) -> int | None:
        return None if self._data is None else self._data.last_seq

    def snapshot(self) -> Snapshot | None:
        """La instantanea para `compute`; `None` mientras no haya pasada completa. `compute` es sincrono: nadie la modifica a mitad."""
        return None if self._data is None else Snapshot(self._data.entries, self._data.months)

    async def full_pass(self) -> None:
        """Lee los 6 meses cerrados y el mes en curso. Espera el candado. Si falla, el estado vigente queda intacto."""
        async with self._reader.exclusive():
            started = self._clock()
            data = _Data()
            async for page in self._reader.pages(None, full_pass_start(started)):
                data.apply(page, started.date())
            discard_old(data.entries, data.months, self._clock().date())
            self._data = data  # reemplazo atomico: decisiones, contadores y `last_seq` cambian juntos
            self.last_full_recompute_at = self.last_success_at = self._clock()
            try:
                await (
                    self._incremental_locked()
                )  # con el candado todavia tomado, desde el `last_seq` de la pasada
            except ReadError:
                log.warning(
                    "incremental_after_full_failed"
                )  # la pasada si termino: el proximo ciclo sigue desde `last_seq`

    async def incremental(self) -> Result:
        """Una lectura de `seq > last_seq`. Si el candado esta tomado (pasada en curso o ciclo anterior), se omite sin leer."""
        async with self._reader.try_exclusive() as acquired:
            if not acquired:
                return SKIPPED
            await self._incremental_locked()
            return DONE

    async def _incremental_locked(self) -> None:
        data = self._data
        if data is None:
            raise NoBaseline("sin pasada completa")
        async for page in self._reader.pages(data.last_seq, None):
            data.apply(page, self._clock().date())
        discard_old(data.entries, data.months, self._clock().date())
        self.last_success_at = self._clock()
