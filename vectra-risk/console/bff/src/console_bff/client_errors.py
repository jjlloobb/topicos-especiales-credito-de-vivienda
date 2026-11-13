"""`POST /api/console/client-errors` (BR-U10-22; P-U10-09; NFR-U10-34): el BFF valida, cuenta y emite; no guarda nada.

La validacion del cuerpo (`ClientErrorReport`, `extra = "forbid"`, `error_code` de un catalogo cerrado) la hace U0 antes
del handler: un campo extra, un mensaje libre o un codigo fuera del catalogo es 422 y no llega aqui (sin evento ni metrica).
El `correlation_id` del cuerpo se valida y **no** se emite (P-7 (a)): el del registro es el de la solicitud al BFF.
"""

from vectra_common import logging as vlog
from vectra_common.app_factory import RequestContext
from vectra_contracts.catalog import LogEvent
from vectra_contracts.models.api import ClientErrorReport, Principal

from console_bff.metrics import CLIENT_ERRORS


def principal_role(principal: Principal) -> str:
    """La misma convencion que `_role` de `vectra_case.api`: el primer rol en orden alfabetico, o vacio."""
    return sorted(role.value for role in principal.roles)[0] if principal.roles else ""


async def report_client_error(ctx: RequestContext) -> None:
    report = ctx.body
    assert isinstance(report, ClientErrorReport)  # noqa: S101 - `create_app` ya lo valido con el modelo de la ruta
    CLIENT_ERRORS.labels(error_code=report.error_code).inc()
    vlog.log_event(
        LogEvent.CONSOLE_CLIENT_ERROR,
        error_code=report.error_code,
        route_template=report.route_template,
        app_version=report.app_version,
        principal_subject=ctx.principal.subject,
        principal_role=principal_role(ctx.principal),
    )
