"""Planificador del ciclo (BR-U11-11; P-U11-02; NFR-U11-04, 09). Dos bucles que comparten el candado del `reader`:

- **Pasadas completas** (`_pass_loop`): una al arrancar y una al dia, a las 02:30 UTC mas un desfase uniforme en
  [0, `config.FULL_PASS_JITTER_MAX_SECONDS`] s por dia, sorteado con un `random.Random` inyectable (P-3, opcion a: la diaria corre en
  el primer instante posterior al arranque, haya corrido o no la del arranque). Plazo `config.FULL_PASS_DEADLINE_SECONDS` por pasada;
  una fallida se reintenta cada `config.FULL_PASS_RETRY_SECONDS`, hasta `config.FULL_PASS_RETRIES` veces y despues ninguno hasta la
  diaria. Mientras **nunca** haya habido una pasada exitosa, el reintento no tiene tope (P-2, opcion b).
- **Ciclos incrementales** (`_cycle_loop`): cada `config.CYCLE_SECONDS`. Con el candado tomado (pasada en curso) se omiten y se cuentan
  en `vectra_product_cycles_skipped_total`; sin pasada exitosa no leen, no cuentan y no publican.

Tras cada lectura exitosa se calcula `compute(snapshot, params, now)` y se reemplaza la referencia publicada, una sola vez. Una
lectura fallida conserva lo publicado y no mueve `last_success` (BR-U11-11). `SIGTERM` (`stop`) detiene los bucles sin tomar ciclos
nuevos; la pagina en vuelo termina y una pasada a medias se descarta (el estado vigente queda intacto).

Reloj de pared, reloj monotono, espera y generador son parametros: ninguna prueba duerme minutos reales.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta

from vectra_common.logging import log_access

from vectra_product import config
from vectra_product.collector import Holder, Operations, Published
from vectra_product.compute import compute
from vectra_product.model import Params
from vectra_product.reader import ReadError
from vectra_product.state import (
    SKIPPED,
    Checkpoint,
    NoBaseline,
    PassDeadline,
    ProductState,
    Stopped,
)


def draw_jitter(rng: random.Random) -> float:
    """El desfase de un dia: uniforme en [0, `FULL_PASS_JITTER_MAX_SECONDS`] s (NFR-U11-04)."""
    return rng.uniform(0.0, float(config.FULL_PASS_JITTER_MAX_SECONDS))


def daily_start_on(day: date, rng: random.Random) -> datetime:
    """`02:30 UTC + desfase` de ese dia. Un sorteo por llamada."""
    return datetime.combine(day, config.FULL_PASS_AT_UTC, tzinfo=UTC) + timedelta(seconds=draw_jitter(rng))


def next_daily_start(after: datetime, rng: random.Random) -> datetime:
    """El primer instante `02:30 UTC + desfase` estrictamente posterior a `after`. Un sorteo por llamada."""
    moment = after.astimezone(UTC)
    start = daily_start_on(moment.date(), rng)
    return start if start > moment else start + timedelta(days=1)


class Scheduler:
    def __init__(
        self,
        state: ProductState,
        params: Params,
        holder: Holder,
        operations: Operations,
        *,
        wall: Callable[[], datetime],
        monotonic: Callable[[], float],
        sleep: Callable[[float], Awaitable[None]],
        rng: random.Random,
        stop: asyncio.Event,
    ) -> None:
        self._state = state
        self._params = params
        self._holder = holder
        self._ops = operations
        self._wall = wall
        self._mono = monotonic
        self._sleep = sleep
        self._rng = rng
        self._stop = stop
        self._next_daily = next_daily_start(wall(), rng)
        self._retry_at: float | None = None
        self._retries = 0

    @property
    def next_daily(self) -> datetime:
        return self._next_daily

    async def run(self) -> None:
        """Hasta que `stop` se activa; las excepciones inesperadas de un bucle detienen el otro y salen."""
        async with asyncio.TaskGroup() as group:
            group.create_task(self._pass_loop())
            group.create_task(self._cycle_loop())

    # -- espera ----------------------------------------------------------------------------------------------------------

    async def _wait(self, seconds: float) -> None:
        """Espera `seconds` o hasta que `stop` se activa, lo primero que ocurra."""
        if self._stop.is_set():
            return
        sleeper = asyncio.ensure_future(self._sleep(max(0.0, seconds)))
        stopper = asyncio.ensure_future(self._stop.wait())
        try:
            await asyncio.wait({sleeper, stopper}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (sleeper, stopper):
                task.cancel()
            await asyncio.gather(sleeper, stopper, return_exceptions=True)

    def _checkpoint(self, deadline: float | None) -> Checkpoint:
        def check() -> None:
            if self._stop.is_set():
                raise Stopped
            if deadline is not None and self._mono() > deadline:
                raise PassDeadline("full_pass_deadline")

        return check

    # -- publicacion -----------------------------------------------------------------------------------------------------

    def _publish(self) -> None:
        """`compute` sobre la instantanea del estado y un solo reemplazo de la referencia publicada (P-U11-03)."""
        snapshot = self._state.snapshot()
        last_success = self._state.last_success_at
        if snapshot is None or last_success is None:
            return
        now = self._wall()
        self._holder.replace(
            Published(
                compute(snapshot, self._params, now),
                self._params,
                now,
                last_success,
                self._state.last_full_recompute_at,
            )
        )

    # -- pasadas completas -----------------------------------------------------------------------------------------------

    async def _full_attempt(self) -> bool:
        """Una pasada completa con su plazo. `True` si terminó y se publicó; `False` si falló, venció o se descartó."""
        self._ops.full_pass_in_progress.set(1)
        started = self._mono()
        try:
            await self._state.full_pass(self._checkpoint(started + config.FULL_PASS_DEADLINE_SECONDS))
        except Stopped:
            return False  # SIGTERM: pasada descartada, sin contarla como fallo
        except ReadError as error:
            self._ops.observe("full", self._mono() - started)
            log_access(
                status="fallida",
                error_code=str(error) or type(error).__name__,
                attempt=self._retries + 1,
                duration_ms=int((self._mono() - started) * 1000),
            )
            return False
        else:
            self._ops.observe("full", self._mono() - started)
            self._publish()
            return True
        finally:
            self._ops.full_pass_in_progress.set(0)

    def _after_attempt(self, ok: bool) -> None:
        if ok:
            self._retries, self._retry_at = 0, None
            return
        never_succeeded = self._state.snapshot() is None
        if never_succeeded or self._retries < config.FULL_PASS_RETRIES:
            self._retries += 1
            self._retry_at = self._mono() + config.FULL_PASS_RETRY_SECONDS
        else:
            self._retry_at = None  # sin mas reintentos hasta la diaria; el estado incremental sigue intacto

    def _schedule_next_daily(self) -> None:
        """La del dia siguiente, con su propio desfase (una por dia: ni dos la misma noche, ni una de mas por el desfase nuevo)."""
        following = daily_start_on(self._next_daily.date() + timedelta(days=1), self._rng)
        self._next_daily = (
            following if following > self._wall() else next_daily_start(self._wall(), self._rng)
        )

    def _seconds_to_next_pass(self) -> float:
        waits = [(self._next_daily - self._wall()).total_seconds()]
        if self._retry_at is not None:
            waits.append(self._retry_at - self._mono())
        return max(0.0, min(waits))

    async def _pass_loop(self) -> None:
        self._after_attempt(await self._full_attempt())  # al arrancar
        while not self._stop.is_set():
            await self._wait(self._seconds_to_next_pass())
            if self._stop.is_set():
                return
            if self._wall() >= self._next_daily:
                self._schedule_next_daily()
                self._retries, self._retry_at = 0, None
            elif self._retry_at is None or self._mono() < self._retry_at:
                continue
            self._after_attempt(await self._full_attempt())

    # -- ciclos incrementales --------------------------------------------------------------------------------------------

    async def _cycle(self) -> None:
        started = self._mono()
        try:
            result = await self._state.incremental(self._checkpoint(None))
        except (NoBaseline, Stopped):
            return  # sin baseline no se lee, no se cuenta como omitido y no se publica; con SIGTERM no hay mas ciclos
        except ReadError as error:
            self._ops.observe("incremental", self._mono() - started)
            log_access(
                status="fallida",
                error_code=str(error) or type(error).__name__,
                duration_ms=int((self._mono() - started) * 1000),
            )
            return  # conserva lo publicado y `last_success` no se mueve (BR-U11-11)
        if result == SKIPPED:
            self._ops.cycles_skipped.inc()
            return
        self._ops.observe("incremental", self._mono() - started)
        self._publish()  # tambien sin lecturas nuevas: `now` cambia el dia

    async def _cycle_loop(self) -> None:
        next_tick = self._mono() + config.CYCLE_SECONDS
        while not self._stop.is_set():
            await self._wait(next_tick - self._mono())
            if self._stop.is_set():
                return
            await self._cycle()
            next_tick = max(next_tick + config.CYCLE_SECONDS, self._mono())
