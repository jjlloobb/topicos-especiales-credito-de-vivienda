"""Gauges calculados de la base (Paso 11; P-U8-04, 08; NFR-U8-13): cola atrasada, `no_disponible` y evidencia pendiente.

Cada 30 s, en todas las replicas (por eso las alertas usan `max()`). Las metricas de retencion se difieren por la demo.
"""

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime

from vectra_case import metrics
from vectra_case.config import GAUGE_INTERVAL, JOBS_OVERDUE_AFTER
from vectra_case.db import Database


class DbGauges:
    def __init__(self, db: Database, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.db = db
        self.clock = clock
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def refresh(self) -> None:
        now = self.clock()
        async with self.db.tx() as conn:
            cur = await conn.execute(
                "SELECT count(*) AS n FROM evaluation_jobs WHERE run_at < %s - make_interval(secs => %s) "
                "AND (locked_until IS NULL OR locked_until < %s)",
                (now, JOBS_OVERDUE_AFTER, now),
            )
            overdue = (await cur.fetchone() or {"n": 0})["n"]
            cur = await conn.execute("SELECT count(*) AS n FROM cases WHERE state = 'no_disponible'")
            persistent = (await cur.fetchone() or {"n": 0})["n"]
            cur = await conn.execute(
                "SELECT entry_type, extract(epoch FROM (%s - min(created_at))) AS age FROM evidence_outbox "
                "WHERE state = 'pendiente_registro' GROUP BY entry_type",
                (now,),
            )
            ages = {r["entry_type"]: float(r["age"]) for r in await cur.fetchall()}
        metrics.JOBS_OVERDUE.set(overdue)
        metrics.FAILCLOSED_PERSISTENT.set(persistent)
        for entry_type in metrics.ENTRY_TYPES:
            metrics.EVIDENCE_PENDING_OLDEST.labels(entry_type=entry_type).set(
                max(ages.get(entry_type, 0.0), 0.0)
            )

    async def run_forever(self, interval: float = GAUGE_INTERVAL) -> None:
        while not self._stop.is_set():
            with suppress(Exception):
                await self.refresh()
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), interval)
