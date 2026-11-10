"""La unica llamada de bias a governance: `POST /v1/models/{id}/freeze` (BR-U9-12, F27; P-U9-02; NFR-U9-22).

Solo el CronJob usa este modulo (import-linter: el servicio no puede importarlo). Token de `bias-monitoring-job`
(`vectra_common.service_token`, ya en el `DependencyClient`). Reintentos solo ante timeout, error de conexion o 5xx:
3 reintentos a 1, 2 y 4 s, 4 llamadas como maximo por version y corrida. Un 409 es exito para la corrida (la version ya esta
congelada o no es la activa) y nunca se reintenta; otro 4xx tampoco, y deja el `freeze` como fallido.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from vectra_common import deps
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_contracts.models.monitoring import FreezeContext

from vectra_bias import config

FROZEN: Final = "congelado"
CONFLICT: Final = "409"
FAILED: Final = "fallido"
HTTP_OK_MAX: Final = 299
HTTP_CONFLICT: Final = 409
HTTP_SERVER_ERROR: Final = 500
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class FreezeOutcome:
    outcome: str  # `congelado`, `409` o `fallido`
    attempts: int
    reason: str | None = None  # codigo estable del ultimo fallo, sin texto de la respuesta

    @property
    def ok(self) -> bool:
        return self.outcome in (FROZEN, CONFLICT)


async def freeze(
    client: deps.DependencyClient, model_version_id: str, context: FreezeContext, sleep: Sleep = asyncio.sleep
) -> FreezeOutcome:
    content = context.model_dump_json().encode()
    path = f"/v1/models/{model_version_id}/freeze"
    delays = (*config.FREEZE_RETRY_DELAYS_S, None)
    reason = "unknown"
    for attempt, delay in enumerate(delays, start=1):
        try:
            response = await deps.call(
                client,
                "POST",
                path,
                timeout=config.FREEZE_TIMEOUT_S,
                headers={"content-type": "application/json"},
                content=content,
            )
        except DependencyTimeout:
            reason = "timeout"
        except DependencyUnavailable:
            reason = "unavailable"
        else:
            status = response.status_code
            if status == HTTP_CONFLICT:
                return FreezeOutcome(CONFLICT, attempt)
            if status <= HTTP_OK_MAX:
                return FreezeOutcome(FROZEN, attempt)
            if status < HTTP_SERVER_ERROR:
                return FreezeOutcome(FAILED, attempt, f"status_{status}")
            reason = f"status_{status}"
        if delay is not None:
            await sleep(delay)
    return FreezeOutcome(FAILED, len(delays), reason)
