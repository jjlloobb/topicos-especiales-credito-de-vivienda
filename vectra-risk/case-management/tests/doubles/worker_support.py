"""Soporte de las pruebas de `case-worker` (U08-T04): un mundo con PostgreSQL real (rol `case_worker`), los dobles de governance, scoring y
registro, y el reloj simulado de `u8_support`; encima del `harness` de `case-service` (reconciliador y barrido con el rol `case_app`).

`worker_world` no abre un cuarto PostgreSQL: usa el `Db` de `case_pg` (la base de la prueba) como los demas. Las lecturas de vuelta
(`case_row`, `job_count`, `outbox`) las hace el superusuario de la prueba, nunca la funcion bajo prueba.
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from random import Random
from typing import Any

import httpx
from case_pg import Db, url
from case_strategies import split_application
from scoring_double import ScoringDouble
from u8_support import APPLICATION, FakeClock, GovernanceDouble, Harness, harness
from vectra_case.config import GOVERNANCE_WORKER_POOL
from vectra_case.db import Database
from vectra_case.evaluation import Evaluator, ScoringClient, Taken, build_request
from vectra_case.governance_client import ServingConfigClient
from vectra_case.job_queue import JobQueue
from vectra_case.worker import Worker
from vectra_contracts.catalog import CaseState
from vectra_contracts.models.api import ScoringRequest
from vectra_contracts.models.features import FeatureSpec

from vectra_case import metrics


class FakeToken:
    """`TokenSource` de la prueba: `t1`, y tras `invalidate()` `t2`, `t3`... (para el reintento por 401)."""

    def __init__(self) -> None:
        self.n = 1
        self.invalidated = 0

    async def token(self) -> str:
        return f"t{self.n}"

    def invalidate(self) -> None:
        self.invalidated += 1
        self.n += 1


@dataclass
class World:
    h: Harness
    db: Db
    worker_db: Database
    governance: ServingConfigClient
    scoring: ScoringDouble
    scoring_client: ScoringClient
    token: FakeToken
    queue: JobQueue
    evaluator: Evaluator
    worker: Worker
    clock: FakeClock

    async def take(self) -> Taken | None:
        return await self.queue.take()

    async def step(self) -> Taken | None:
        """Una toma y su intento, sin pasar por el bucle (determinista): devuelve lo tomado, o `None` si no habia trabajo."""
        taken = await self.queue.take()
        if taken is not None:
            await self.evaluator.run(taken)
        return taken


@asynccontextmanager
async def worker_world(
    db: Db, *, pool: int = 5, scoring_timeout: float = 7.0, concurrency: int = 16, seed: int = 7
) -> AsyncIterator[World]:
    logging.getLogger("httpx").setLevel(
        logging.WARNING
    )  # el INFO por solicitud de httpx llena la salida de las pruebas largas
    async with harness(db) as h:
        worker_db = Database(url(db.pg, db.name, "case_worker", "case_worker"), size=pool)
        scoring = ScoringDouble()
        token = FakeToken()
        governance = ServingConfigClient(
            "http://governance",
            None,
            pool=GOVERNANCE_WORKER_POOL,
            transport=httpx.MockTransport(h.governance_handler.handler),
            clock=lambda: h.clock().timestamp(),
        )
        scoring_client = ScoringClient(
            "http://scoring", token, transport=scoring.transport(), timeout=scoring_timeout
        )
        queue = JobQueue(worker_db, h.clock)
        evaluator = Evaluator(worker_db, governance, scoring_client, h.clock, Random(seed))
        worker = Worker(queue, evaluator, concurrency=concurrency, rng=Random(seed))
        try:
            yield World(
                h,
                db,
                worker_db,
                governance,
                scoring,
                scoring_client,
                token,
                queue,
                evaluator,
                worker,
                h.clock,
            )
        finally:
            await scoring_client.aclose()
            await governance.aclose()
            await worker_db.close()


# --- Lecturas de vuelta (el superusuario de la prueba) -----------------------------------------------------------------------


def case_row(db: Db, case_id: uuid.UUID) -> dict[str, Any]:
    rows = db.query(
        "SELECT state, attempts, last_cause, ever_degraded, escalation_count, recommendation_entry_id FROM cases WHERE case_id = %s",
        case_id,
    )
    keys = ("state", "attempts", "last_cause", "ever_degraded", "escalation_count", "recommendation_entry_id")
    return dict(zip(keys, rows[0], strict=True))


def job_count(db: Db, case_id: uuid.UUID) -> int:
    return int(db.query("SELECT count(*) FROM evaluation_jobs WHERE case_id = %s", case_id)[0][0])  # type: ignore[call-overload]


def job_row(db: Db, case_id: uuid.UUID) -> dict[str, Any] | None:
    rows = db.query("SELECT attempt, run_at, locked_until FROM evaluation_jobs WHERE case_id = %s", case_id)
    return dict(zip(("attempt", "run_at", "locked_until"), rows[0], strict=True)) if rows else None


def outbox(db: Db, case_id: uuid.UUID) -> list[tuple[Any, ...]]:
    return db.query(
        "SELECT entry_type, idempotency_key, payload FROM evidence_outbox WHERE case_id = %s ORDER BY created_at",
        case_id,
    )


# --- Muestras ----------------------------------------------------------------------------------------------------------------


def default_spec() -> FeatureSpec:
    return FeatureSpec.model_validate_json(json.dumps(GovernanceDouble.spec("mv-1")))


def sample_taken(
    *,
    attempt: int = 1,
    ever_degraded: bool = False,
    case_id: uuid.UUID | None = None,
    application: dict[str, Any] | None = None,
) -> Taken:
    identifiers, rest = split_application(application or APPLICATION)
    return Taken(
        case_id or uuid.uuid4(),
        attempt,
        CaseState.EN_EVALUACION,
        datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        ever_degraded,
        rest,
        identifiers.model_dump(mode="json"),
    )


def sample_request(**kwargs: Any) -> ScoringRequest:
    return build_request(
        sample_taken(**kwargs), default_spec(), "mv-1", datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
    )


def attempts_total(result: str, attempt: int) -> float:
    return float(metrics.CASE_ATTEMPTS.labels(result=result, attempt=str(attempt))._value.get())  # type: ignore[attr-defined]


# --- Escenarios -------------------------------------------------------------------------------------------------------------


def new_case(
    db: Db, *, state: str = "en_evaluacion", attempts: int = 0, job_attempt: int | None = 0, **kwargs: Any
) -> uuid.UUID:
    """Un caso con su trabajo vivo (`job_attempt=None`: sin trabajo)."""
    from u8_support import seed_case, seed_job

    case_id = seed_case(db, state=state, attempts=attempts, **kwargs)
    if job_attempt is not None:
        seed_job(db, case_id, attempt=job_attempt)
    return case_id


def bulk_cases(db: Db, n: int, *, state: str = "en_evaluacion", jobs: bool = True) -> list[uuid.UUID]:
    """`n` casos (por omision `en_evaluacion`, con trabajo) con identificadores, en una sola conexion (sin triggers: solo prepara el escenario)."""
    from u8_support import APPLICATION

    _, rest = split_application(APPLICATION)
    ids: list[uuid.UUID] = []
    with db.admin() as conn:
        conn.execute("SET session_replication_role = replica")
        for _ in range(n):
            ids.append(uuid.uuid4())
        conn.cursor().executemany(
            "INSERT INTO cases (case_id, state, channel, created_by, application) VALUES (%s, %s, 'web', %s::jsonb, %s::jsonb)",
            [(i, state, json.dumps({"kind": "service", "id": "channel-web"}), json.dumps(rest)) for i in ids],
        )
        conn.cursor().executemany(
            "INSERT INTO case_identifiers (case_id, full_name, document_type, document_number, birth_date, phone, email, address, municipality_code) "
            "VALUES (%s, 'Ana Gomez', 'CC', '1020304050', '1985-01-01', '3001234567', 'a@example.com', 'Cra 7', '11001')",
            [(i,) for i in ids],
        )
        if jobs:
            conn.cursor().executemany(
                "INSERT INTO evaluation_jobs (case_id, attempt, run_at) VALUES (%s, 0, now() - interval '1 second')",
                [(i,) for i in ids],
            )
    return ids


def expire_case(db: Db, case_id: uuid.UUID) -> None:
    """P-5 (a) de U08-T04: el vencimiento de la retencion lo aplica un apoyo de la prueba con el rol `case_retention` real.

    Envejece `created_at` con el superusuario (`guard_vencido` lee la fecha) y, como `case_retention`, pasa el caso a `vencido` y borra su
    trabajo, igual que lo hara la CLI del Paso 16 (diferida). Los triggers `guard_transition` y `guard_vencido` siguen activos.
    """
    db.execute("UPDATE cases SET created_at = created_at - interval '3 years' WHERE case_id = %s", case_id)
    with db.as_role("case_retention") as conn:
        conn.execute("UPDATE cases SET state = 'vencido' WHERE case_id = %s", (case_id,))
        conn.execute("DELETE FROM evaluation_jobs WHERE case_id = %s", (case_id,))
