"""Composiciones y paso a U3 del BFF (BR-U10-03; P-U10-02, 05; NFR-U10-02; US-402, US-403).

- `get_dossier`: registry `get_case_dossier` y case `get_case_identifiers` **en paralelo** (`asyncio.TaskGroup`). El registro
  sin respuesta (timeout, conexion, 5xx o circuito abierto) es 503 y cancela la otra llamada; case sin respuesta da el
  expediente con `identifiers_unavailable = true`; un 403 o un 404 de case es ese error, nunca `identifiers_unavailable`.
- `get_disparity`: governance (`list_models(state=activo,congelado)`) y **despues** bias, en serie y **sin cache** (Q7).
- `run_integrity_check` y `get_integrity_check`: de paso a U3; `already_active` viaja en la respuesta.

Los errores de un destino salen como `UpstreamProblem` (su `Problem` ya traducido); un 2xx que no valida es 500 (BR-U10-04).
"""

import asyncio
from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel, TypeAdapter, ValidationError
from vectra_common.app_factory import RequestContext
from vectra_common.errors import DependencyUnavailable, NotFound, VectraError
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.api import ConsoleDossier, Page
from vectra_contracts.models.application import CaseIdentifiers
from vectra_contracts.models.governance import ModelFilter, ModelVersion
from vectra_contracts.models.monitoring import DisparityFilter, DisparityView
from vectra_contracts.models.registry import (
    IntegrityCheckRef,
    IntegrityCheckRequest,
    IntegrityCheckStatus,
    RegistryDossier,
)
from vectra_contracts.outcome import read_wire

from console_bff.clients import Calls, Reply, UpstreamProblem, path_id, problem_response

_SERVICEABLE = ("activo", "congelado")


def parse_reply[M: BaseModel](model: type[M], reply: Reply) -> M:
    """Un 2xx que no valida contra el modelo del contrato es un 500 (`internal_error`), nunca el cuerpo crudo."""
    try:
        if model.__module__.startswith("vectra_contracts."):
            return read_wire(model, reply.body)  # `CaseDetail` contiene `Recommendation` (U00-T03)
        return model.model_validate_json(reply.body)
    except (ValidationError, ValueError, ContractViolation) as error:
        raise VectraError() from error


def parse_list[T](adapter: TypeAdapter[list[T]], reply: Reply) -> list[T]:
    try:
        return adapter.validate_json(reply.body)
    except (ValidationError, ValueError) as error:
        raise VectraError() from error


def _case_id(ctx: RequestContext) -> str:
    """El `case_id` de la ruta; uno que no es UUID no existe (404), igual que en case-service."""
    path_id(ctx)  # rechaza `.` y `..`
    try:
        return str(UUID(ctx.path_params["id"]))
    except ValueError as error:
        raise NotFound() from error


async def _registry_dossier(calls: Calls, case_id: str) -> RegistryDossier:
    reply = await calls.send("registry", "get_case_dossier", "GET", f"/v1/dossiers/{case_id}")
    if reply.status >= 500:
        raise DependencyUnavailable()  # BR-U10-03: un 5xx del registro es «sin respuesta»
    if not reply.is_success:
        raise UpstreamProblem(problem_response(reply.status, reply.body, calls.ctx.correlation_id))
    return parse_reply(RegistryDossier, reply)


async def _case_identifiers(calls: Calls, case_id: str) -> CaseIdentifiers | None:
    """`None` = case sin respuesta (no es un error del expediente). 403 y 404 se propagan."""
    try:
        reply = await calls.send("case", "get_case_identifiers", "GET", f"/v1/cases/{case_id}/identifiers")
    except DependencyUnavailable:
        return None
    if reply.status >= 500:
        return None
    if not reply.is_success:
        raise UpstreamProblem(problem_response(reply.status, reply.body, calls.ctx.correlation_id))
    return parse_reply(CaseIdentifiers, reply)


def _first_error(group: BaseExceptionGroup[BaseException]) -> BaseException:
    """El registro manda: si fallaron los dos, el error del registro es el que sale."""
    errors = list(group.exceptions)
    unavailable = [e for e in errors if isinstance(e, DependencyUnavailable)]
    return unavailable[0] if unavailable else errors[0]


async def get_dossier(calls: Calls) -> ConsoleDossier:
    case_id = _case_id(calls.ctx)
    try:
        async with asyncio.TaskGroup() as group:
            registry = group.create_task(_registry_dossier(calls, case_id))
            case = group.create_task(_case_identifiers(calls, case_id))
    except BaseExceptionGroup as failed:
        raise _first_error(failed) from None
    dossier, identifiers = registry.result(), case.result()
    if identifiers is None:  # case sin respuesta: no se sabe si esta anonimizado
        return ConsoleDossier(dossier=dossier, identifiers_unavailable=True, anonymized=False)
    return ConsoleDossier(
        dossier=dossier,
        identifiers=None if identifiers.anonymized else identifiers.identifiers,
        identifiers_unavailable=False,
        anonymized=identifiers.anonymized,
    )


def serviceable_version(versions: Sequence[ModelVersion]) -> str | None:
    """La version servible entre las `activo` y `congelado` de governance (P-6 (a)). Ninguna: `None`.

    Con mas de una, la `activo` (la mas reciente si hubiera varias): no deberia ocurrir y queda como candidata de diseno.
    """
    if not versions:
        return None
    ordered = sorted(versions, key=lambda v: (v.state == "activo", v.updated_at), reverse=True)
    return ordered[0].model_version_id


async def get_disparity(calls: Calls) -> DisparityView:
    """Governance y despues bias, sin cache. Con `version` en el filtro governance no se consulta (P-6 (a))."""
    query = calls.ctx.query
    assert isinstance(query, DisparityFilter)  # noqa: S101
    if query.version is None:
        listing = ModelFilter.model_validate({"state": list(_SERVICEABLE), "page_size": 100})
        reply = await calls.fetch("governance", "read", "GET", "/v1/models", query=listing)
        page = parse_reply(Page[ModelVersion], reply)
        query = query.model_copy(update={"version": serviceable_version(page.items)})
    reply = await calls.fetch("bias", "get_dashboard", "GET", "/v1/disparity", query=query)
    return parse_reply(DisparityView, reply)


async def run_integrity_check(calls: Calls) -> tuple[IntegrityCheckRef, int]:
    """202 si no hay otra verificacion activa; 200 con la activa y `already_active = true` (P-U10-05)."""
    body = calls.ctx.body
    assert isinstance(body, IntegrityCheckRequest)  # noqa: S101
    reply = await calls.fetch("registry", "run_integrity_check", "POST", "/v1/integrity-checks", body=body)
    ref = parse_reply(IntegrityCheckRef, reply)
    if reply.status not in (200, 202):
        raise VectraError()
    return ref, reply.status


async def get_integrity_check(calls: Calls) -> IntegrityCheckStatus:
    reply = await calls.fetch(
        "registry", "get_integrity_check", "GET", f"/v1/integrity-checks/{path_id(calls.ctx)}"
    )
    return parse_reply(IntegrityCheckStatus, reply)


__all__ = [
    "get_disparity",
    "get_dossier",
    "get_integrity_check",
    "parse_list",
    "parse_reply",
    "run_integrity_check",
    "serviceable_version",
]
