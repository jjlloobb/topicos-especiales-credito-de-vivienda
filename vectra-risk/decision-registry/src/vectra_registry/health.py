"""Readiness y metricas periodicas (Paso 9 y Paso 8; P-U3-01; BR-U3-17; NFR-U3-11).

`Health`: el servicio esta listo solo si la primaria responde y hay al menos un standby sincrono transmitiendo
(`sync_state IN ('sync', 'quorum')`: con `minSyncReplicas = 1` y `maxSyncReplicas = 2` CloudNativePG configura `ANY 1 (...)` y
PostgreSQL informa `quorum`, no `sync`). El resultado se cachea **5 s**: un refresco en segundo plano mantiene el valor, y uno
mas viejo que 5 s cuenta como no listo (si el refresco se cuelga, el pod sale del balanceo). Se consulta con el rol
`registry_health` (`pg_monitor`, sin acceso a `registry_entries`).

`Gauges`: cada 60 s, con el pool `projections`, el atraso del agregador (`vectra_registry_monitoring_lag_seconds`) y las metricas
de la verificacion bajo demanda (P-U3-09).
"""

import asyncio
import contextlib
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final, cast

from prometheus_client import Gauge
from vectra_common.metrics import REGISTRY

from vectra_registry.pools import Pool, Pools
from vectra_registry.queries import monitoring_lag, start_read

#: P-U1-04: el resultado de la sonda vale 5 s.
CACHE_SECONDS: Final = 5.0
#: El refresco corre a la mitad de la vigencia: el peor caso para notar una caida es ~2,5 s mas lo que tarda la consulta.
REFRESH_SECONDS: Final = CACHE_SECONDS / 2
GAUGE_SECONDS: Final = 60.0
SYNC_STANDBYS: Final = (
    "SELECT count(*) FROM pg_stat_replication WHERE state = 'streaming' AND sync_state IN ('sync', 'quorum')"
)

MONITORING_LAG: Final = Gauge(
    "vectra_registry_monitoring_lag_seconds", "Atraso del agregador de monitoreo (BR-U3-17)", registry=REGISTRY
)
PENDING_AGE: Final = Gauge(
    "vectra_registry_integrity_check_pending_age_seconds",
    "Edad de la verificacion pendiente mas antigua; 0 si no hay (BR-U3-13b)",
    registry=REGISTRY,
)
FULL_AGE: Final = Gauge(
    "vectra_registry_last_full_verification_age_seconds",
    "Edad de la ultima verificacion full terminada (BR-U3-13b)",
    registry=REGISTRY,
)
CHECKS_FAILED: Final = Gauge(
    "vectra_registry_integrity_checks_failed_total",
    "Verificaciones en estado fallida; solo crece porque las filas no se borran (BR-U3-13b)",
    registry=REGISTRY,
)


async def probe(pool: Pool) -> bool:
    """P-U3-01: `SELECT 1` y al menos un standby sincrono transmitiendo."""
    try:
        async with pool.connection() as conn:
            await conn.execute("SELECT 1")
            cursor = await conn.execute(SYNC_STANDBYS)
            row = await cursor.fetchone()
    except Exception:  # noqa: BLE001 - cualquier fallo significa no listo
        return False
    return row is not None and int(row[0]) >= 1  # type: ignore[call-overload]


class Health:
    """La sonda de readiness con cache de 5 s. `is_ready` es sincrona (la llama `/readyz` del puerto 8081)."""

    def __init__(
        self,
        pool: Pool,
        *,
        cache_seconds: float = CACHE_SECONDS,
        refresh_seconds: float = REFRESH_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._pool = pool
        self._cache_seconds = cache_seconds
        self._refresh_seconds = refresh_seconds
        self._monotonic = monotonic
        self._ready = False
        self._checked_at: float | None = None
        self._task: asyncio.Task[None] | None = None

    def is_ready(self) -> bool:
        """El ultimo resultado si tiene menos de 5 s; uno mas viejo (o ninguno) es no listo."""
        return (
            self._checked_at is not None
            and self._monotonic() - self._checked_at < self._cache_seconds
            and self._ready
        )

    async def refresh(self) -> bool:
        self._ready = await probe(self._pool)
        self._checked_at = self._monotonic()
        return self._ready

    async def _run(self) -> None:
        while True:
            await self.refresh()
            await asyncio.sleep(self._refresh_seconds)

    async def start(self) -> None:
        """Hace la primera comprobacion antes de aceptar trafico y deja el refresco en segundo plano."""
        await self.refresh()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task


class Gauges:
    """El atraso del agregador y las metricas de la verificacion bajo demanda, cada 60 s con el pool `projections`."""

    def __init__(self, pools: Pools, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._pools = pools
        self._clock = clock
        self._task: asyncio.Task[None] | None = None

    async def refresh(self) -> None:
        now = self._clock()
        try:
            async with self._pools.projections.connection() as conn, conn.transaction():
                await start_read(conn)
                _, lag = await monitoring_lag(conn, now)
                cursor = await conn.execute(
                    "SELECT min(requested_at), "
                    "(SELECT max(finished_at) FROM integrity_checks WHERE mode = 'full' AND status = 'terminada'), "
                    "(SELECT count(*) FROM integrity_checks WHERE status = 'fallida'), "
                    "(SELECT recorded_at FROM registry_entries WHERE seq = 0) "
                    "FROM integrity_checks WHERE status = 'pendiente'"
                )
                row = await cursor.fetchone()
        except Exception:  # noqa: BLE001 - sin lectura la serie queda sin actualizar (la alerta mira `absent()`)
            return
        assert row is not None  # noqa: S101
        pending, last_full, failed, genesis = cast(tuple[datetime | None, datetime | None, int, datetime | None], row)
        MONITORING_LAG.set(lag)
        PENDING_AGE.set(max(0.0, (now - pending).total_seconds()) if pending else 0.0)
        # Sin ninguna `full` terminada, la edad se cuenta desde la genesis del registro.
        reference = last_full or genesis
        FULL_AGE.set(max(0.0, (now - reference).total_seconds()) if reference else 0.0)
        CHECKS_FAILED.set(int(failed))

    async def _run(self) -> None:
        while True:
            await self.refresh()
            await asyncio.sleep(GAUGE_SECONDS)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
