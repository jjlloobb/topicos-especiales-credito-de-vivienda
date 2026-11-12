"""Ingesta y alta manual (Paso 9; BR-U8-01..04; NFR-U8-01, 44; US-101, US-102, US-109).

- `free_text` se guarda tal cual, siempre con parametros (`Jsonb`), nunca interpolado ni escapado.
- Idempotencia (BR-U8-02): la llave, el caso y su trabajo de evaluacion van en **una** transaccion; un cerrojo consultivo por
  (alcance, llave) serializa los reenvios concurrentes. Alcance: `client_id` (`azp`) en la ingesta, `user_id` en el alta manual.
- `X-Test-Scenario` (BR-U8-03): solo con `azp = channel-simulator` y `allow_test_scenarios = true`; si no, 422. Se guarda como
  `test_scenario_id` y no sale a scoring, al registro ni a los logs de negocio.
"""

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Final

from psycopg.types.json import Jsonb
from vectra_common.errors import ConflictState, ValidationFailed
from vectra_contracts.catalog import CaseState
from vectra_contracts.models.api import InvalidParam, Principal
from vectra_contracts.models.application import ApplicationIn, CaseIdentifierGroup, CaseRef

from vectra_case.db import Database

SIMULATOR: Final = "channel-simulator"
MANUAL_CHANNEL: Final = "manual"
IDENTIFICATION: Final = tuple(CaseIdentifierGroup.model_fields)
KEY_PATTERN: Final = re.compile(r"^[\x21-\x7e]{1,128}$")
SCENARIO_PATTERN: Final = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")


def _invalid(name: str, reason: str) -> ValidationFailed:
    return ValidationFailed(invalid_params=[InvalidParam(name=name, reason_code=reason)])


def check_idempotency_key(key: str | None) -> str:
    if key is None or not KEY_PATTERN.match(key):
        raise _invalid("Idempotency-Key", "invalid_or_missing")
    return key


def check_test_scenario(client_id: str | None, header: str | None, allow: bool) -> str | None:
    """`None` si no hay cabecera; el valor si se acepta; 422 si no se permite o es invalida (BR-U8-03)."""
    if header is None:
        return None
    if client_id != SIMULATOR or not allow:
        raise _invalid("X-Test-Scenario", "not_allowed")
    if not SCENARIO_PATTERN.match(header):
        raise _invalid("X-Test-Scenario", "invalid")
    return header


def body_sha256(body: ApplicationIn) -> str:
    canonical = json.dumps(
        body.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def scope_of(principal: Principal, manual: bool) -> str:
    if manual:
        return f"user:{principal.subject}"
    return f"client:{principal.client_id or principal.subject}"


def split(body: ApplicationIn, *, manual: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """(identificadores, `cases.application`): la solicitud sin el grupo de identificacion y con `sex` y estrato."""
    data = body.model_dump(mode="json")
    identifiers = {k: data[k] for k in IDENTIFICATION}
    rest = {k: v for k, v in data.items() if k not in IDENTIFICATION}
    if manual:
        rest["channel"] = MANUAL_CHANNEL
    return identifiers, rest


async def submit(
    db: Database,
    principal: Principal,
    body: ApplicationIn,
    key: str,
    test_scenario_id: str | None,
    *,
    manual: bool,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> CaseRef:
    scope = scope_of(principal, manual)
    sha = body_sha256(body)
    identifiers, application = split(body, manual=manual)
    created_by = {
        "kind": "user" if manual else "service",
        "id": principal.subject if manual else scope_of(principal, False)[7:],
    }
    channel = MANUAL_CHANNEL if manual else body.channel
    now = clock()
    async with db.tx() as conn:
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"intake:{scope}|{key}",)
        )
        cur = await conn.execute(
            "SELECT k.body_sha256, k.case_id, c.state FROM intake_keys k JOIN cases c ON c.case_id = k.case_id "
            "WHERE k.scope = %s AND k.idempotency_key = %s",
            (scope, key),
        )
        existing = await cur.fetchone()
        if existing is not None:
            if existing["body_sha256"] != sha:
                raise ConflictState()
            return CaseRef(case_id=existing["case_id"], state=CaseState(existing["state"]))
        case_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO cases (case_id, state, channel, created_by, created_at, updated_at, application, test_scenario_id) "
            "VALUES (%s, 'en_evaluacion', %s, %s, %s, %s, %s, %s)",
            (case_id, channel, Jsonb(created_by), now, now, Jsonb(application), test_scenario_id),
        )
        await conn.execute(
            "INSERT INTO case_identifiers (case_id, full_name, document_type, document_number, birth_date, phone, email, "
            "address, municipality_code) VALUES (%(case_id)s, %(full_name)s, %(document_type)s, %(document_number)s, "
            "%(birth_date)s, %(phone)s, %(email)s, %(address)s, %(municipality_code)s)",
            {"case_id": case_id, **identifiers},
        )
        await conn.execute(
            "INSERT INTO intake_keys (scope, idempotency_key, body_sha256, case_id, created_at) VALUES (%s, %s, %s, %s, %s)",
            (scope, key, sha, case_id, now),
        )
        await conn.execute(
            "INSERT INTO evaluation_jobs (case_id, attempt, run_at) VALUES (%s, 0, %s)", (case_id, now)
        )
    return CaseRef(case_id=case_id, state=CaseState.EN_EVALUACION)
