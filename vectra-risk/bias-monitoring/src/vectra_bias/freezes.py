"""Congelamientos (BR-U9-19; US-304): la lista de `FreezeSummary` y el paquete de un congelamiento (`FreezeRecord` de U0).

Se leen de `GET /v1/monitoring/freezes` de U3, que no tiene ruta por id: `get_freeze` busca por `freeze_id` en la lista. El
`FreezeRecord` sale tal como lo guardo el registro (el contrato de U0 manda sobre la BLM §2.3, que lo llama `FreezeContext`).
"""

from __future__ import annotations

from vectra_common import deps
from vectra_common.errors import DependencyUnavailable, NotFound
from vectra_contracts.models.monitoring import FreezeRecord, FreezeSummary, Resolution

from vectra_bias.registry_client import RegistryError, read_freezes


def latest_resolution(record: FreezeRecord) -> Resolution | None:
    """La resolucion mas reciente: con `investigar` y luego `reactivar`, la `reactivar` (BR-U9-19)."""
    return max(record.resolutions, key=lambda r: r.recorded_at, default=None)


def summarize(record: FreezeRecord) -> FreezeSummary:
    package = record.context_package
    return FreezeSummary(
        freeze_id=record.freeze_id,
        model_version_id=record.model_version_id,
        frozen_at=record.frozen_at,
        trigger_attribute=package.trigger_attribute,
        model_aggregate=package.after.model_aggregate,
        resolution=latest_resolution(record),
    )


async def _records(client: deps.DependencyClient) -> list[FreezeRecord]:
    try:
        return await read_freezes(client)
    except RegistryError as error:
        raise DependencyUnavailable() from error


async def list_freezes(client: deps.DependencyClient) -> list[FreezeSummary]:
    return [summarize(record) for record in await _records(client)]


async def get_freeze(client: deps.DependencyClient, freeze_id: str) -> FreezeRecord:
    """El `FreezeRecord` de `freeze_id`; 404 `not_found` si no existe."""
    for record in await _records(client):
        if record.freeze_id == freeze_id:
            return record
    raise NotFound()
