"""Soporte de las pruebas de `case-service` (U8): reloj simulado, principales, app con el autenticador falso y semillas de casos.

Cada prueba corre contra PostgreSQL real (Testcontainers) con el rol `case_app`; el superusuario solo prepara escenarios.
"""

import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from case_pg import Db, url
from case_strategies import SHA, recommendation_from_wire
from psycopg.types.json import Jsonb
from registry_double import RegistryDouble
from vectra_case.api import Services
from vectra_case.app import Settings, build_app
from vectra_case.credit import CreditReader
from vectra_case.db import Database
from vectra_case.evidence import Evidence, Reconciler, RegistryClient
from vectra_case.governance_client import ServingConfigClient
from vectra_case.sweeps import Sweeper
from vectra_common import process
from vectra_common.errors import Unauthenticated
from vectra_contracts.catalog import Outcome, Role, Scope
from vectra_contracts.models.api import Principal

__all__ = ["SHA"]


class FakeClock:
    """Reloj real mas un desplazamiento: `advance` simula horas y dias sin esperar."""

    def __init__(self) -> None:
        self.offset = timedelta(0)

    def __call__(self) -> datetime:
        return datetime.now(UTC) + self.offset

    def advance(self, **kwargs: float) -> None:
        self.offset += timedelta(**kwargs)


def principal(
    name: str, role: Role | None, *, scopes: frozenset[Scope] = frozenset(), client_id: str | None = None
) -> Principal:
    now = datetime.now(UTC)
    return Principal(
        subject=name,
        kind="user" if role else "service",
        roles=frozenset({role}) if role else frozenset(),
        scopes=scopes,
        acr="1" if role else None,
        auth_time=now - timedelta(minutes=5) if role else None,
        token_expiry=now + timedelta(hours=1),
        client_id=client_id,
    )


PRINCIPALS: dict[str, Principal] = {
    "analista": principal("analista-1", Role.ANALISTA),
    "analista2": principal("analista-2", Role.ANALISTA),
    "cro": principal("cro-1", Role.CRO),
    "cumplimiento": principal("cumplimiento-1", Role.CUMPLIMIENTO),
    "ingeniero": principal("ingeniero-1", Role.INGENIERO_RIESGO),
    "simulator": principal(
        "sim", None, scopes=frozenset({Scope.INTAKE_SUBMIT}), client_id="channel-simulator"
    ),
    "channel": principal("web", None, scopes=frozenset({Scope.INTAKE_SUBMIT}), client_id="channel-web"),
    "channel2": principal("web2", None, scopes=frozenset({Scope.INTAKE_SUBMIT}), client_id="channel-web-2"),
    "noscope": principal("svc", None, scopes=frozenset(), client_id="otro"),
}


class FakeAuthenticator:
    async def authenticate(self, authorization: str | None) -> Principal:
        name = (authorization or "").removeprefix("Bearer ").strip()
        if name not in PRINCIPALS:
            raise Unauthenticated()
        return PRINCIPALS[name]


def auth(name: str, **headers: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {name}", **headers}


APPLICATION: dict[str, Any] = {
    "full_name": "Ana María Gómez",
    "document_type": "CC",
    "document_number": "1020304050",
    "birth_date": (date.today() - timedelta(days=40 * 365)).isoformat(),
    "phone": "3001234567",
    "email": "ana.gomez@example.com",
    "address": "Cra 7 # 45-10",
    "department_code": "11",
    "municipality_code": "11001",
    "monthly_income": 8_000_000,
    "other_income": 0,
    "employment_type": "asalariado",
    "employment_months": 48,
    "monthly_obligations": 500_000,
    "max_days_past_due_12m": 0,
    "property_value": 300_000_000,
    "requested_amount": 150_000_000,
    "term_months": 180,
    "proposed_rate_ea": "0.1200",
    "property_condition": "usada",
    "channel": "web",
    "sex": "F",
    "socioeconomic_stratum": "3",
}


def application(**over: Any) -> dict[str, Any]:
    return {**APPLICATION, **over}


def seed_case(
    db: Db,
    *,
    state: str = "en_evaluacion",
    outcome: Outcome = Outcome.FAVORABLE,
    model_version: str = "mv-1",
    app_data: dict[str, Any] | None = None,
    created_at: datetime | None = None,
    anonymized: bool = False,
    frozen_mark: bool = False,
    last_cause: str | None = None,
    attempts: int = 0,
    channel: str = "web",
    ever_degraded: bool = False,
) -> uuid.UUID:
    """Un caso real: nace como `case_app` (`guard_transition`), lo demas lo deja el superusuario sin triggers."""
    case_id = uuid.uuid4()
    data = app_data or application()
    keep = {
        k: v
        for k, v in data.items()
        if k
        not in (
            "full_name",
            "document_type",
            "document_number",
            "birth_date",
            "phone",
            "email",
            "address",
            "municipality_code",
        )
    }
    with db.as_role("case_app") as conn:
        conn.execute(
            "INSERT INTO cases (case_id, state, channel, created_by, application) VALUES (%s, 'en_evaluacion', %s, %s, %s)",
            (case_id, channel, Jsonb({"kind": "service", "id": "channel-web"}), Jsonb(keep)),
        )
    rec = None
    entry_id = None
    if state in ("listo", "decidido") or frozen_mark:
        rec = recommendation_from_wire(outcome, case_id=case_id).model_dump_json()
        rec = json.dumps(
            {
                **json.loads(rec),
                "model_version_id": model_version,
                "explanation": {**json.loads(rec)["explanation"], "model_version_id": model_version},
            }
        )
        entry_id = "7"
    db.execute(
        "UPDATE cases SET state = %s, recommendation = %s::jsonb, recommendation_entry_id = %s, attempts = %s, last_cause = %s, "
        "model_frozen_after_recommendation = %s, anonymized_at = %s, created_at = COALESCE(%s, created_at), updated_at = COALESCE(%s, updated_at), "
        "ever_degraded = %s "
        "WHERE case_id = %s",
        state,
        rec,
        entry_id,
        attempts,
        last_cause,
        frozen_mark,
        datetime.now(UTC) if anonymized else None,
        created_at,
        created_at,
        ever_degraded,
        case_id,
    )
    if not anonymized:
        db.execute(
            "INSERT INTO case_identifiers (case_id, full_name, document_type, document_number, birth_date, phone, email, address, municipality_code) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            case_id,
            data["full_name"],
            data["document_type"],
            data["document_number"],
            data["birth_date"],
            data["phone"],
            data["email"],
            data["address"],
            data["municipality_code"],
        )
    return case_id


@dataclass
class Harness:
    client: httpx.AsyncClient
    app: Any
    database: Database
    services: Services
    evidence: Evidence
    reconciler: Reconciler
    sweeper: Sweeper
    registry: RegistryDouble
    clock: FakeClock
    governance_handler: "GovernanceDouble"
    core_calls: list[str]


class GovernanceDouble:
    """`GET /v1/serving-config` con la forma nueva de U04-T09 y ETag, y `GET /v1/models/{id}/feature-spec`; `down` y `old_shape` fallan."""

    def __init__(self) -> None:
        self.state = "activo"
        self.model_version_id = "mv-1"
        self.down = False
        self.old_shape = False
        self.calls = 0
        self.spec_calls: list[str] = []  # una entrada por `feature-spec` pedido (la version)
        self.spec_status = 200
        self.spec_override: dict[str, Any] | None = (
            None  # sirve este cuerpo en lugar del `FeatureSpec` por omision
        )

    def config(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "model_version_id": self.model_version_id,
            "state": self.state,
            "policy_version_id": "p1",
            "cutoff": "0.5000",
            "low_confidence_threshold": "0.6000",
            "channel_rules": [],
            "feature_dictionary_version": "d1",
            "effective_from": "2026-11-01T00:00:00+00:00",
            "inference_service": "isvc-0a1b2c3d",
            "etag": f"{self.state}-{self.model_version_id}",
        }
        if self.old_shape:
            for k in ("cutoff", "low_confidence_threshold", "channel_rules"):
                del data[k]
        return data

    @staticmethod
    def spec(model_version_id: str) -> dict[str, Any]:
        """El `feature_spec` de U5: tres derivadas, un campo permitido y una busqueda."""
        return {
            "model_version_id": model_version_id,
            "features": [
                {"feature_id": "installment_to_income", "origin": "derived"},
                {"feature_id": "loan_to_value", "origin": "derived"},
                {"feature_id": "age_years", "origin": "derived"},
                {"feature_id": "employment_type", "origin": "field", "source_fields": ["employment_type"]},
                {
                    "feature_id": "channel_group",
                    "origin": "lookup",
                    "source_fields": ["channel"],
                    "table": {"web": "digital", "manual": "asistido"},
                    "default": "otro",
                },
            ],
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.down:
            return httpx.Response(503, json={})
        if request.url.path.endswith("/feature-spec"):
            version = request.url.path.split("/")[-2]
            self.spec_calls.append(version)
            if self.spec_status != 200:
                return httpx.Response(self.spec_status, json={})
            return httpx.Response(200, json=self.spec_override or self.spec(version))
        cfg = self.config()
        if request.headers.get("if-none-match") == f'"{cfg["etag"]}"':
            return httpx.Response(304, headers={"ETag": f'"{cfg["etag"]}"'})
        return httpx.Response(200, json=cfg, headers={"ETag": f'"{cfg["etag"]}"'})


@asynccontextmanager
async def harness(
    db: Db,
    *,
    allow_test_scenarios: bool = False,
    core_enabled: bool = False,
    core_handler: Callable[[httpx.Request], httpx.Response] | None = None,
    registry: RegistryDouble | None = None,
    clock: FakeClock | None = None,
    settings: Settings | None = None,
) -> AsyncIterator[Harness]:
    process.ensure_service()  # `create_app` lo hace despues; los clientes de `deps` lo necesitan antes
    clock = clock or FakeClock()
    registry = registry or RegistryDouble(clock=clock)
    dsn = url(db.pg, db.name, "case_app", "case_app")
    database = Database(dsn)
    registry_client = RegistryClient(
        "http://registry",
        None,
        transport=registry.transport(),
        monotonic=lambda: time.monotonic() + clock.offset.total_seconds(),
    )
    governance = GovernanceDouble()
    sc_client = ServingConfigClient(
        "http://governance", None, transport=httpx.MockTransport(governance.handler)
    )
    core_calls: list[str] = []

    def core(request: httpx.Request) -> httpx.Response:
        core_calls.append(str(request.url))
        if core_handler is None:
            return httpx.Response(404, json={})
        return core_handler(request)

    credit = CreditReader(
        core_enabled, "http://core" if core_enabled else None, None, transport=httpx.MockTransport(core)
    )
    evidence = Evidence(database, registry_client, clock)
    services = Services(database, evidence, credit, allow_test_scenarios)
    app = build_app(settings, authenticator=FakeAuthenticator(), services=services, clock=clock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://case") as client:
        try:
            yield Harness(
                client,
                app,
                database,
                services,
                evidence,
                Reconciler(evidence),
                Sweeper(database, sc_client, clock),
                registry,
                clock,
                governance,
                core_calls,
            )
        finally:
            await database.close()
            await registry_client.aclose()
            await sc_client.aclose()
            await credit.aclose()


def scalar(db: Db, statement: str, *params: object) -> Any:
    rows = db.query(statement, *params)
    return rows[0][0] if rows else None


def decision_body(**over: Any) -> dict[str, Any]:
    return {
        "decision": "sigue",
        "final_outcome": "favorable",
        "used_factors": ["ninguno"],
        "justification": "",
        **over,
    }


def insert_fail_closed(db: Db, case_id: uuid.UUID, n: int = 1, *, start: int = 1) -> list[uuid.UUID]:
    """Entradas `fail_closed` como las inserta `case-worker` (U08-T04): con el rol `case_worker`, sin `SELECT` ni `RETURNING`."""
    keys = []
    now = datetime.now(UTC)
    with db.as_role("case_worker") as conn:
        for i in range(start, start + n):
            key = uuid.uuid5(case_id, f"fail_closed:{i}")
            entry = {
                "entry_type": "fail_closed",
                "case_id": str(case_id),
                "actor": {"kind": "service", "id": "case-worker"},
                "occurred_at": now.isoformat(),
                "correlation_id": uuid.uuid4().hex,
                "idempotency_key": str(key),
                "payload": {
                    "local_cause": "scoring_unreachable",
                    "retryable": True,
                    "attempt": 6,
                    "escalated_at": now.isoformat(),
                },
            }
            conn.execute(
                "INSERT INTO evidence_outbox (evidence_id, case_id, entry_type, idempotency_key, payload) "
                "VALUES (%s, %s, 'fail_closed', %s, %s)",
                (uuid.uuid4(), case_id, key, Jsonb(entry)),
            )
            keys.append(key)
    return keys


def seed_job(db: Db, case_id: uuid.UUID, *, attempt: int = 0, run_at: datetime | None = None) -> None:
    """El trabajo vivo de un caso (lo crean la ingesta, `retry` y el barrido en `case-service`)."""
    db.execute(
        "INSERT INTO evaluation_jobs (case_id, attempt, run_at) VALUES (%s, %s, COALESCE(%s, now() - interval '1 second'))",
        case_id,
        attempt,
        run_at,
    )
