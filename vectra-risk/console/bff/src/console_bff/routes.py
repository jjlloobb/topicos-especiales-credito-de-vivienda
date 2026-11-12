"""Las 30 rutas del BFF y su handler (BR-U10-01, 03; P-U10-01; US-402, US-403, US-602).

Los 30 `RouteContract` ya existen en U0 (`REGISTRY["console-bff"]`): este modulo **no** los copia. Rol y MFA los aplica el
middleware de U0 (`require`); la regla de objeto corre aqui, dentro del handler y **antes** de reenviar la accion (BR-U10-01):
el BFF lee el objeto con el token del usuario, aplica la funcion pura de `OBJECT_RULES` y, si rechaza, responde sin llamar a la
escritura (`CONFLICT` -> 409 `conflict_state`; `FORBIDDEN` -> 403 `forbidden`). El destino vuelve a validar (defensa en profundidad).

Deny by default (P-U10-01): antes de `create_app`, las claves de `OBJECT_RULES` tienen que ser **exactamente** los
`operation_id` de las 30 rutas; si falta o sobra una, `ContractViolation` y el proceso no arranca. `None` declarado vale.
"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Final

from pydantic import BaseModel, TypeAdapter
from starlette.responses import Response
from vectra_common.app_factory import Handler, HandlerKey, RequestContext, respond
from vectra_common.errors import ConflictState, Forbidden, NotFound, VectraError
from vectra_contracts.catalog import Role
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.api import (
    ApplicantSummaryRequest,
    CaseDetail,
    Page,
    SessionInfo,
)
from vectra_contracts.models.governance import (
    DataSource,
    ModelFilter,
    ModelState,
    ModelVersion,
    ModelVersionDetail,
    PolicyDecisionIn,
    PolicyVersion,
    SourceComparisonIn,
)
from vectra_contracts.routes import REGISTRY, RouteContract

from console_bff import compose, object_rules
from console_bff.client_errors import principal_role, report_client_error
from console_bff.clients import (
    Calls,
    Reply,
    UpstreamProblem,
    Upstreams,
    path_id,
    problem_response,
    quote_segment,
)
from console_bff.object_rules import ObjectVerdict

SERVICE: Final = "console-bff"
PREFIX: Final = "/api/console"
LOCALE: Final = "es-CO"

# `operation_id` -> (destino, clave de `OPERATION_TIMEOUT_SECONDS`). Un endpoint del BFF, una llamada al destino (BR-U10-03).
PASSTHROUGH: Final[Mapping[str, tuple[str, str]]] = {
    "get_api_console_cases": ("case", "list_cases"),
    "get_api_console_cases_failures": ("case", "list_persistent_failures"),
    "get_api_console_cases_id": ("case", "get_case"),
    "post_api_console_cases": ("case", "create_manual_application"),
    "post_api_console_cases_id_explanation-views": ("case", "record_explanation_view"),
    "post_api_console_cases_id_decision": ("case", "record_decision"),
    "post_api_console_cases_id_retry": ("case", "retry_case"),
    "get_api_console_models": ("governance", "read"),
    "get_api_console_models_id": ("governance", "read"),
    "get_api_console_policies": ("governance", "read"),
    "get_api_console_data-sources": ("governance", "read"),
    "post_api_console_models": ("governance", "transition"),
    "post_api_console_models_id_validations": ("governance", "transition"),
    "post_api_console_data-sources_id_comparisons": ("governance", "transition"),
    "post_api_console_models_id_approval": ("governance", "transition"),
    "post_api_console_models_id_frozen-resolution": ("governance", "transition"),
    "post_api_console_models_id_retirement": ("governance", "transition"),
    "post_api_console_policies": ("governance", "transition"),
    "post_api_console_policies_id_approval": ("governance", "transition"),
    "post_api_console_data-sources": ("governance", "transition"),
    "post_api_console_data-sources_id_decision": ("governance", "transition"),
    "get_api_console_freezes": ("bias", "list_freezes"),
    "get_api_console_freezes_id": ("bias", "get_context_package"),
}

_POLICIES = TypeAdapter(list[PolicyVersion])
_SOURCES = TypeAdapter(list[DataSource])


def verify_object_rules(contracts: list[RouteContract] | None = None) -> None:
    """P-U10-01: las claves de `OBJECT_RULES` son **exactamente** los `operation_id` de las rutas; si no, no arranca."""
    ids = {route.operation_id for route in (contracts if contracts is not None else REGISTRY[SERVICE])}
    declared = set(object_rules.OBJECT_RULES)
    if declared != ids:
        raise ContractViolation(
            f"OBJECT_RULES no coincide con las rutas: sin regla declarada {sorted(ids - declared)}, "
            f"sobran {sorted(declared - ids)}"
        )


def _enforce(verdict: ObjectVerdict) -> None:
    if verdict is ObjectVerdict.CONFLICT:
        raise ConflictState()
    if verdict is ObjectVerdict.FORBIDDEN:
        raise Forbidden()


def _rule(contract: RouteContract) -> Callable[..., ObjectVerdict]:
    rule = object_rules.OBJECT_RULES[contract.operation_id]
    if rule is None:  # pragma: no cover - solo se pide para las rutas con regla
        raise ContractViolation(f"{contract.operation_id}: sin regla de objeto")
    return rule


# --- lecturas previas que alimentan cada regla (tabla «Que lectura alimenta cada regla» de la tarea) ---


async def _case_detail(calls: Calls) -> CaseDetail:
    reply = await calls.fetch("case", "get_case", "GET", f"/v1/cases/{path_id(calls.ctx)}")
    return compose.parse_reply(CaseDetail, reply)


async def _model_state(calls: Calls) -> ModelState:
    reply = await calls.fetch("governance", "read", "GET", f"/v1/models/{path_id(calls.ctx)}")
    return compose.parse_reply(ModelVersionDetail, reply).state


async def _policy(calls: Calls) -> PolicyVersion:
    reply = await calls.fetch("governance", "read", "GET", "/v1/policies")
    wanted = calls.ctx.path_params["id"]
    for item in compose.parse_list(_POLICIES, reply):
        if item.policy_version_id == wanted:
            return item
    raise NotFound()  # no hay lectura por id: un objeto que no aparece en la lista no existe


async def _data_source(calls: Calls) -> DataSource:
    reply = await calls.fetch("governance", "read", "GET", "/v1/data-sources")
    wanted = calls.ctx.path_params["id"]
    for item in compose.parse_list(_SOURCES, reply):
        if item.ds_id == wanted:
            return item
    raise NotFound()


Gate = Callable[[Calls], Awaitable[None]]


def _gate(contract: RouteContract) -> Gate | None:
    """La lectura previa y la regla de la ruta, o `None` si su regla esta declarada como ausente."""
    if object_rules.OBJECT_RULES[contract.operation_id] is None:
        return None
    rule = _rule(contract)
    name = contract.operation_id

    async def case_state(calls: Calls) -> None:
        _enforce(rule((await _case_detail(calls)).state))

    async def retry(calls: Calls) -> None:
        detail = await _case_detail(calls)
        _enforce(rule(detail.state, detail.anonymized))

    async def model_state(calls: Calls) -> None:
        _enforce(rule(await _model_state(calls)))

    async def policy(calls: Calls) -> None:
        body = calls.ctx.body
        assert isinstance(body, PolicyDecisionIn)  # noqa: S101
        found = await _policy(calls)
        _enforce(rule(found.state, body.decision, body.justification))

    async def data_source_decision(calls: Calls) -> None:
        found = await _data_source(calls)
        _enforce(rule(found.state, found.pre_post_report is not None))

    async def comparison(calls: Calls) -> None:
        body = calls.ctx.body
        assert isinstance(body, SourceComparisonIn)  # noqa: S101
        ds_id = calls.ctx.path_params["id"]
        source = await _data_source(calls)
        candidate_reply = await calls.fetch(
            "governance", "read", "GET", f"/v1/models/{quote_segment(body.candidate_version_id)}"
        )
        candidate = compose.parse_reply(ModelVersionDetail, candidate_reply)
        active_reply = await calls.fetch(
            "governance",
            "read",
            "GET",
            "/v1/models",
            query=ModelFilter.model_validate({"state": ["activo"], "page_size": 1}),
        )
        active = compose.parse_reply(Page[ModelVersion], active_reply)
        _enforce(rule(source.state, ds_id, candidate.source_candidate_for, bool(active.items)))

    gates: dict[str, Gate] = {
        "post_api_console_cases_id_explanation-views": case_state,
        "post_api_console_cases_id_decision": case_state,
        "post_api_console_cases_id_retry": retry,
        "post_api_console_models_id_validations": model_state,
        "post_api_console_models_id_approval": model_state,
        "post_api_console_models_id_frozen-resolution": model_state,
        "post_api_console_models_id_retirement": model_state,
        "post_api_console_policies_id_approval": policy,
        "post_api_console_data-sources_id_decision": data_source_decision,
        "post_api_console_data-sources_id_comparisons": comparison,
    }
    return gates.get(name)


def finish(contract: RouteContract, reply: Reply, correlation_id: str) -> BaseModel | Response:
    """2xx -> el mismo estado que el destino, validado contra el modelo de la ruta; error -> su `Problem` (BR-U10-04)."""
    if not reply.is_success:
        return problem_response(reply.status, reply.body, correlation_id)
    model = contract.response_model
    if model is None:
        if reply.status not in (200, 204):
            raise VectraError()
        return Response(status_code=reply.status)
    if reply.status != 200 and reply.status not in contract.alternate_statuses:
        raise VectraError()
    parsed = compose.parse_reply(model, reply)
    return parsed if reply.status == 200 else respond(parsed, reply.status)


def _relay(handler: Callable[[RequestContext], Awaitable[Any]]) -> Handler:
    """Un error de un destino (`UpstreamProblem`) sale como su respuesta de error ya traducida."""

    async def wrapped(ctx: RequestContext) -> Any:
        try:
            return await handler(ctx)
        except UpstreamProblem as relayed:
            return relayed.response

    return wrapped


def _destination_path(contract: RouteContract, ctx: RequestContext) -> str:
    tail = contract.path.removeprefix(PREFIX)
    if "{id}" in tail:
        tail = tail.replace("{id}", path_id(ctx))
    return f"/v1{tail}"


def _passthrough(upstreams: Upstreams, contract: RouteContract, destination: str, operation: str) -> Handler:
    gate = _gate(contract)

    async def handler(ctx: RequestContext) -> Any:
        calls = Calls(upstreams, ctx)
        if gate is not None:
            await gate(calls)
        reply = await calls.send(
            destination,
            operation,
            contract.method,
            _destination_path(contract, ctx),
            query=ctx.query,
            body=ctx.body,
        )
        return finish(contract, reply, ctx.correlation_id)

    return _relay(handler)


def _applicant_summary(upstreams: Upstreams, contract: RouteContract) -> Handler:
    rule = _rule(contract)

    async def handler(ctx: RequestContext) -> Any:
        calls = Calls(upstreams, ctx)
        detail = await _case_detail(calls)
        final = detail.decision.final_outcome if detail.decision is not None else None
        _enforce(rule(detail.state, final))
        if (
            detail.recommendation_entry_id is None
        ):  # «explicacion sincronizada» de C03: sin ella no se llama a U7
            raise ConflictState()
        request = ApplicantSummaryRequest(
            case_id=detail.case_id, recommendation_entry_id=detail.recommendation_entry_id
        )
        reply = await calls.send(
            "explainability", "applicant_summary", "POST", "/v1/applicant-summaries", body=request
        )
        return finish(contract, reply, ctx.correlation_id)

    return _relay(handler)


async def get_me(ctx: RequestContext) -> BaseModel:
    """`SessionInfo` solo de los claims del token (P-8 (a)): sin `auth_time` es 403; con varios roles, el primero alfabetico."""
    principal = ctx.principal
    if principal.auth_time is None:
        raise Forbidden()
    return SessionInfo(
        role=Role(principal_role(principal)),
        mfa=principal.acr == "mfa",
        auth_time=principal.auth_time,
        locale=LOCALE,
    )


def build_handlers(upstreams: Upstreams) -> dict[HandlerKey, Handler]:
    """El mapa `(metodo, ruta) -> handler` de las 30 rutas. Falla antes de `create_app` si una no declara su regla."""
    verify_object_rules()
    special: dict[str, Handler] = {
        "get_api_console_me": get_me,
        "post_api_console_client-errors": report_client_error,
        "get_api_console_cases_id_dossier": _relay(lambda ctx: compose.get_dossier(Calls(upstreams, ctx))),
        "get_api_console_disparity": _relay(lambda ctx: compose.get_disparity(Calls(upstreams, ctx))),
        "post_api_console_integrity-checks": _relay(lambda ctx: _run_integrity(upstreams, ctx)),
        "get_api_console_integrity-checks_id": _relay(
            lambda ctx: compose.get_integrity_check(Calls(upstreams, ctx))
        ),
    }
    handlers: dict[HandlerKey, Handler] = {}
    for contract in REGISTRY[SERVICE]:
        operation_id = contract.operation_id
        if operation_id == "post_api_console_cases_id_applicant-summary":
            handler = _applicant_summary(upstreams, contract)
        elif operation_id in special:
            handler = special[operation_id]
        else:
            destination, operation = PASSTHROUGH[operation_id]
            handler = _passthrough(upstreams, contract, destination, operation)
        handlers[(contract.method, contract.path)] = handler
    return handlers


async def _run_integrity(upstreams: Upstreams, ctx: RequestContext) -> BaseModel | Response:
    ref, status = await compose.run_integrity_check(Calls(upstreams, ctx))
    return ref if status == 200 else respond(ref, status)


__all__ = ["PASSTHROUGH", "build_handlers", "finish", "get_me", "verify_object_rules"]
