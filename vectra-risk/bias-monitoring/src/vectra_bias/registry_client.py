"""Lecturas del registro de U3 (F26): `GET /v1/monitoring/freezes` y `POST /v1/monitoring/daily:query` (BR-U9-07, 09; P-U9-02).

Solo lectura. En el CronJob el `DependencyClient` va con `breaker="disabled"` tras `process.init("batch")`; en el servicio
(Bloque D), con breaker: este modulo recibe el cliente ya construido y no decide eso. Ningun modulo de `vectra_bias` importa
`httpx`: `vectra_common.deps.call` devuelve la respuesta.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from pydantic import TypeAdapter, ValidationError
from vectra_common import deps
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_contracts.models.monitoring import (
    DayRange,
    FreezeRecord,
    MonitoringQuery,
    MonitoringRangeRequest,
    MonitoringWindow,
)
from vectra_contracts.routes import REGISTRY

from vectra_bias import config

REGISTRY_SERVICE: Final = "decision-registry-service"


def route_path(service: str, method: str, tail: str) -> str:
    """La ruta del contrato de `service` (`REGISTRY` de U0) con ese metodo y que termina en `tail`. Falla si no hay exactamente una:
    ningun modulo de U9 escribe una ruta del contrato como literal."""
    found = [r.path for r in REGISTRY[service] if r.method == method and r.path.endswith(tail)]
    if len(found) != 1:
        raise LookupError(f"{service} {method} ...{tail}: {len(found)} rutas en el contrato")
    return found[0]


FREEZES_PATH: Final = route_path(REGISTRY_SERVICE, "GET", "/freezes")
QUERY_PATH: Final = route_path(REGISTRY_SERVICE, "POST", ":query")
MAX_RANGES_PER_QUERY: Final = 12  # `MonitoringQuery.ranges` (U0 §9.4): con 4 por version caben 3 versiones
_FREEZES = TypeAdapter(list[FreezeRecord])
_JSON: Final = {"content-type": "application/json", "accept": "application/json"}


class RegistryError(Exception):
    """Lectura fallida o incompleta: la corrida falla con `reason=lectura` y nunca congela (BR-U9-10)."""


async def _send(
    client: deps.DependencyClient, method: str, path: str, timeout: float, content: bytes | None
) -> bytes:
    try:
        response = await deps.call(client, method, path, timeout=timeout, headers=_JSON, content=content)
    except (DependencyTimeout, DependencyUnavailable) as error:
        raise RegistryError(type(error).__name__) from error
    if response.status_code != 200:
        raise RegistryError(f"status_{response.status_code}")
    return response.content


async def read_freezes(client: deps.DependencyClient) -> list[FreezeRecord]:
    """Los congelamientos con sus resoluciones (las `reactivar` fijan el inicio de la ventana, BR-U9-08)."""
    body = await _send(client, "GET", FREEZES_PATH, config.FREEZES_TIMEOUT_S, None)
    try:
        return _FREEZES.validate_json(body)
    except ValidationError as error:
        raise RegistryError("freezes_invalid") from error


async def query_daily(client: deps.DependencyClient, query: MonitoringQuery) -> MonitoringWindow:
    """Una solicitud de `monitoring/daily:query` (timeout de `config.QUERY_TIMEOUT_S` por solicitud)."""
    body = await _send(
        client, "POST", QUERY_PATH, config.QUERY_TIMEOUT_S, query.model_dump_json(exclude_none=True).encode()
    )
    try:
        return MonitoringWindow.model_validate_json(body)
    except ValidationError as error:
        raise RegistryError("window_invalid") from error


def plan_queries(
    ranges: Iterable[MonitoringRangeRequest], unattributable: DayRange | None = None
) -> list[MonitoringQuery]:
    """Solicitudes de <= 12 rangos, sin omitir ninguno. `unattributable_range` va **solo** en la primera (BR-U9-09): U3 devuelve
    `unattributable_invalid` como un unico valor por solicitud y las demas lo devuelven en 0."""
    items = list(ranges)
    queries = [
        MonitoringQuery(
            ranges=items[i : i + MAX_RANGES_PER_QUERY],
            include_versions=False,
            unattributable_range=unattributable if i == 0 else None,
        )
        for i in range(0, len(items), MAX_RANGES_PER_QUERY)
    ]
    return queries
