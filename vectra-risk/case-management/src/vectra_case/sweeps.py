"""Barrido de `modelo_congelado` y de la marca `model_frozen_after_recommendation` (Paso 11; BR-U8-10, 14; P-U8-04, 07).

Cada 5 min lee `serving-config`. Con governance caido o una respuesta invalida (forma vieja) se salta el ciclo: no mueve casos.
Con la version `activo`, los `modelo_congelado` pasan a `en_evaluacion` con `attempts = 0` y un trabajo nuevo (`attempt = 0`, un
`INSERT` simple: P-2 (a); si choca con una fila viva se revierte ese caso). Lotes de 100 con `SKIP LOCKED`: dos replicas no procesan
el mismo caso.
"""

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from typing import Final, Literal

from psycopg import errors
from vectra_common.errors import VectraError

from vectra_case.config import BATCH_SIZE
from vectra_case.db import Database
from vectra_case.governance_client import ServingConfigClient, ServingConfigInvalid

SWEEP_INTERVAL: Final[float] = 300.0


class Sweeper:
    def __init__(
        self,
        db: Database,
        governance: ServingConfigClient,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.db = db
        self.governance = governance
        self.clock = clock
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_once(self) -> Literal["skipped", "done"]:
        if self._stop.is_set():
            return "skipped"
        try:
            config = await self.governance.get()
        except (VectraError, ServingConfigInvalid):
            return "skipped"
        if config.state == "activo":
            while not self._stop.is_set() and await self._reactivate_batch() == BATCH_SIZE:
                pass
        frozen = config.model_version_id if config.state == "congelado" else None
        await self._marks(frozen)
        return "done"

    async def _reactivate_batch(self) -> int:
        """Devuelve cuantos casos movio; un lote incompleto (o con choques) termina el ciclo."""
        moved = 0
        now = self.clock()
        async with self.db.tx() as conn:
            cur = await conn.execute(
                "SELECT case_id FROM cases WHERE state = 'modelo_congelado' ORDER BY created_at LIMIT %s FOR UPDATE SKIP LOCKED",
                (BATCH_SIZE,),
            )
            ids = [r["case_id"] for r in await cur.fetchall()]
            for case_id in ids:
                try:
                    async with conn.transaction():  # SAVEPOINT por caso
                        await conn.execute(
                            "UPDATE cases SET state = 'en_evaluacion', attempts = 0, updated_at = %s "
                            "WHERE case_id = %s AND state = 'modelo_congelado'",
                            (now, case_id),
                        )
                        await conn.execute(
                            "INSERT INTO evaluation_jobs (case_id, attempt, run_at) VALUES (%s, 0, %s)",
                            (case_id, now),
                        )
                    moved += 1
                except errors.UniqueViolation:
                    continue
        return moved if moved == len(ids) else 0

    async def _marks(self, frozen_version: str | None) -> None:
        now = self.clock()
        async with self.db.tx() as conn:
            if frozen_version is not None:
                await conn.execute(
                    "UPDATE cases SET model_frozen_after_recommendation = true, updated_at = %s WHERE state = 'listo' "
                    "AND NOT model_frozen_after_recommendation AND recommendation->>'model_version_id' = %s",
                    (now, frozen_version),
                )
            await conn.execute(
                "UPDATE cases SET model_frozen_after_recommendation = false, updated_at = %s "
                "WHERE model_frozen_after_recommendation AND recommendation->>'model_version_id' IS DISTINCT FROM %s",
                (now, frozen_version),
            )

    async def run_forever(self, interval: float = SWEEP_INTERVAL) -> None:
        while not self._stop.is_set():
            with suppress(Exception):  # un ciclo fallido (base caida) no mata el bucle
                await self.run_once()
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), interval)
