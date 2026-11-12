"""API de case-service (Paso 13; BR-U8-13, 13b; P-U8-03, 06; INF-U8-04, 06): las 9 rutas de F04 y F10.

`handlers(...)` devuelve el mapa que `create_app` exige (ni uno de mas ni de menos). Las consultas leen la base con el rol
`case_app`; `views` arma las vistas. Logs `case.viewed` y `case.retry_requested` solo con la allowlist de U0.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from psycopg import errors
from pydantic import BaseModel, RootModel
from vectra_common import logging as vlog
from vectra_common.app_factory import Handler, HandlerKey, RequestContext
from vectra_common.errors import ConflictState, NotFound
from vectra_contracts.catalog import CaseState, Decision, FinalOutcome, LogEvent
from vectra_contracts.models.api import DecisionIn, DecisionView, Page, Principal
from vectra_contracts.models.application import (
    ApplicationIn,
    CaseFilter,
    CaseIdentifierGroup,
    CaseIdentifiers,
    CaseRef,
    CaseSummary,
    PersistentFailure,
)
from vectra_contracts.outcome import Recommendation, read_wire

from vectra_case import intake, metrics, views
from vectra_case.credit import CreditReader
from vectra_case.db import Conn, Database
from vectra_case.evidence import Evidence
from vectra_case.views import CaseRow

PERSISTENT_FAILURES = RootModel[list[PersistentFailure]]
_CASE_COLUMNS = (
    "c.case_id, c.state, c.channel, c.created_at, c.updated_at, c.application, c.attempts, c.last_cause, "
    "c.model_frozen_after_recommendation, (c.anonymized_at IS NOT NULL) AS anonymized, c.recommendation_entry_id, "
    "CASE WHEN c.state IN ('listo', 'decidido') THEN c.recommendation::text END AS rec, "
    "i.full_name, i.document_type, i.document_number, i.birth_date, coalesce(i.phone, '') AS phone, "
    "coalesce(i.email, '') AS email, coalesce(i.address, '') AS address, i.municipality_code"
)
_FROM = "FROM cases c LEFT JOIN case_identifiers i ON i.case_id = c.case_id"


@dataclass
class Services:
    db: Database
    evidence: Evidence
    credit: CreditReader
    allow_test_scenarios: bool


def _services(ctx: RequestContext) -> Services:
    services: Services | None = ctx.request.app.state.services
    if services is None:
        raise RuntimeError("servicios sin iniciar")
    return services


def _role(principal: Principal) -> str:
    return sorted(r.value for r in principal.roles)[0] if principal.roles else ""


def _case_id(ctx: RequestContext) -> uuid.UUID:
    try:
        return uuid.UUID(ctx.path_params["id"])
    except ValueError as exc:
        raise NotFound() from exc


def _identifiers(row: dict[str, Any]) -> CaseIdentifierGroup | None:
    if row["full_name"] is None:
        return None
    keys = (
        "full_name",
        "document_type",
        "document_number",
        "birth_date",
        "phone",
        "email",
        "address",
        "municipality_code",
    )
    return CaseIdentifierGroup.model_validate({k: row[k] for k in keys})


def _case_row(row: dict[str, Any]) -> CaseRow:
    return CaseRow(
        case_id=row["case_id"],
        state=CaseState(row["state"]),
        channel=row["channel"],
        created_at=row["created_at"],
        application=row["application"],
        attempts=row["attempts"],
        last_cause=row["last_cause"],
        model_frozen_after_recommendation=row["model_frozen_after_recommendation"],
        anonymized=row["anonymized"],
        identifiers=_identifiers(row),
        recommendation=None if row["rec"] is None else read_wire(Recommendation, row["rec"]),
        recommendation_entry_id=row["recommendation_entry_id"],
        no_disponible_since=row["updated_at"],
    )


async def _decision_view(conn: Conn, case_id: uuid.UUID) -> DecisionView | None:
    cur = await conn.execute(
        "SELECT decision, final_outcome, used_factors, justification, decided_at, decided_by->>'id' AS by "
        "FROM decisions WHERE case_id = %s AND state = 'confirmada'",
        (case_id,),
    )
    d = await cur.fetchone()
    if d is None:
        return None
    return DecisionView(
        decision=Decision(d["decision"]),
        final_outcome=FinalOutcome(d["final_outcome"]),
        used_factors=d["used_factors"],
        justification=d["justification"],
        decided_at=d["decided_at"],
        decided_by=d["by"],
    )


def handlers() -> dict[HandlerKey, Handler]:
    async def submit_application(ctx: RequestContext) -> BaseModel:
        return await _submit(ctx, manual=False)

    async def create_case(ctx: RequestContext) -> BaseModel:
        return await _submit(ctx, manual=True)

    async def _submit(ctx: RequestContext, *, manual: bool) -> BaseModel:
        s = _services(ctx)
        body = ctx.body
        assert isinstance(body, ApplicationIn)  # noqa: S101
        key = intake.check_idempotency_key(ctx.request.headers.get("idempotency-key"))
        scenario = intake.check_test_scenario(
            ctx.principal.client_id, ctx.request.headers.get("x-test-scenario"), s.allow_test_scenarios
        )
        return await intake.submit(s.db, ctx.principal, body, key, scenario, manual=manual)

    async def list_cases(ctx: RequestContext) -> BaseModel:
        s = _services(ctx)
        f = ctx.query
        assert isinstance(f, CaseFilter)  # noqa: S101
        where: list[str] = []
        params: list[Any] = []
        if f.state:
            where.append("c.state = ANY(%s)")
            params.append([st.value for st in f.state])
        else:
            where.append("c.state <> 'vencido'")
        if f.channel is not None:
            where.append("c.channel = %s")
            params.append(f.channel)
        if f.created_from is not None:
            where.append("c.created_at >= %s")
            params.append(f.created_from)
        if f.created_to is not None:
            where.append("c.created_at <= %s")
            params.append(f.created_to)
        if f.model_frozen_after_recommendation is not None:
            where.append("c.model_frozen_after_recommendation = %s")
            params.append(f.model_frozen_after_recommendation)
        clause = " WHERE " + " AND ".join(where)
        async with s.db.tx() as conn:
            cur = await conn.execute(f"SELECT count(*) AS n FROM cases c{clause}", params)  # noqa: S608
            total = (await cur.fetchone() or {"n": 0})["n"]
            cur = await conn.execute(
                f"SELECT {_CASE_COLUMNS} {_FROM}{clause} ORDER BY c.created_at DESC, c.case_id LIMIT %s OFFSET %s",  # noqa: S608
                [*params, f.page_size, (f.page - 1) * f.page_size],
            )
            rows = await cur.fetchall()
        items = [views.case_summary(_case_row(r)) for r in rows]
        return Page[CaseSummary](items=items, page=f.page, total=total)

    async def list_persistent_failures(ctx: RequestContext) -> BaseModel:
        s = _services(ctx)
        async with s.db.tx() as conn:
            cur = await conn.execute(
                f"SELECT {_CASE_COLUMNS} {_FROM} WHERE c.state = 'no_disponible' ORDER BY c.updated_at, c.case_id"  # noqa: S608
            )
            rows = await cur.fetchall()
        return PERSISTENT_FAILURES([views.persistent_failure(_case_row(r)) for r in rows])

    async def get_case(ctx: RequestContext) -> BaseModel:
        s = _services(ctx)
        case_id = _case_id(ctx)
        async with s.db.tx() as conn:
            cur = await conn.execute(f"SELECT {_CASE_COLUMNS} {_FROM} WHERE c.case_id = %s", (case_id,))  # noqa: S608
            raw = await cur.fetchone()
            if raw is None:
                raise NotFound()
            decision = await _decision_view(conn, case_id) if raw["state"] == CaseState.DECIDIDO else None
        row = _case_row(raw)
        if row.state is CaseState.DECIDIDO:
            row = CaseRow(
                **{**row.__dict__, "decision": decision, "credit_status": await s.credit.status(case_id)}
            )
        vlog.log_event(
            LogEvent.CASE_VIEWED,
            principal_subject=ctx.principal.subject,
            principal_role=_role(ctx.principal),
            case_id=str(case_id),
        )
        return views.case_detail(row)

    async def get_case_identifiers(ctx: RequestContext) -> BaseModel:
        s = _services(ctx)
        case_id = _case_id(ctx)
        async with s.db.tx() as conn:
            cur = await conn.execute(f"SELECT {_CASE_COLUMNS} {_FROM} WHERE c.case_id = %s", (case_id,))  # noqa: S608
            raw = await cur.fetchone()
        if raw is None:
            raise NotFound()
        vlog.log_event(
            LogEvent.CASE_VIEWED,
            principal_subject=ctx.principal.subject,
            principal_role=_role(ctx.principal),
            case_id=str(case_id),
        )
        anonymized = bool(raw["anonymized"])
        return CaseIdentifiers(
            case_id=case_id, identifiers=None if anonymized else _identifiers(raw), anonymized=anonymized
        )

    async def record_explanation_view(ctx: RequestContext) -> None:
        await _services(ctx).evidence.record_view(ctx.principal, _case_id(ctx), ctx.correlation_id or None)

    async def record_decision(ctx: RequestContext) -> BaseModel:
        body = ctx.body
        assert isinstance(body, DecisionIn)  # noqa: S101
        return await _services(ctx).evidence.record_decision(
            ctx.principal, _case_id(ctx), body, ctx.correlation_id or None
        )

    async def retry_case(ctx: RequestContext) -> BaseModel:
        s = _services(ctx)
        case_id = _case_id(ctx)
        now = s.evidence.clock()
        async with s.db.tx() as conn:
            cur = await conn.execute("SELECT state FROM cases WHERE case_id = %s FOR UPDATE", (case_id,))
            row = await cur.fetchone()
            if row is None:
                raise NotFound()
            if row["state"] != CaseState.NO_DISPONIBLE:
                raise ConflictState()
            try:
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE cases SET state = 'en_evaluacion', attempts = 0, updated_at = %s "
                        "WHERE case_id = %s AND state = 'no_disponible'",
                        (now, case_id),
                    )
                    await conn.execute(
                        "INSERT INTO evaluation_jobs (case_id, attempt, run_at) VALUES (%s, 0, %s)",
                        (case_id, now),
                    )
            except errors.UniqueViolation as exc:  # P-2 (a): choca con una fila viva
                raise ConflictState() from exc
        metrics.CASE_RETRIES.inc()
        vlog.log_event(
            LogEvent.CASE_RETRY_REQUESTED,
            principal_subject=ctx.principal.subject,
            principal_role=_role(ctx.principal),
            case_id=str(case_id),
        )
        return CaseRef(case_id=case_id, state=CaseState.EN_EVALUACION)

    return {
        ("POST", "/v1/intake/applications"): submit_application,
        ("POST", "/v1/cases"): create_case,
        ("GET", "/v1/cases"): list_cases,
        ("GET", "/v1/cases/failures"): list_persistent_failures,
        ("GET", "/v1/cases/{id}"): get_case,
        ("GET", "/v1/cases/{id}/identifiers"): get_case_identifiers,
        ("POST", "/v1/cases/{id}/explanation-views"): record_explanation_view,
        ("POST", "/v1/cases/{id}/decision"): record_decision,
        ("POST", "/v1/cases/{id}/retry"): retry_case,
    }
