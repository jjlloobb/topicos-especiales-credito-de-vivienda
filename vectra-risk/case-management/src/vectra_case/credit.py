"""Lectura del estado de credito del core (Paso 12; BR-U8-21; INF-U8-02; NFR-U8-25, 31, 43). Solo `GET`.

Con `core.enabled = false` no se crea el cliente, no se llama y no se registra nada en el breaker: `no_integrado`.
Sin cache; timeout de 500 ms. 404 -> `sin_credito`; error o timeout -> `no_disponible`. Nunca lanza.
"""

import asyncio
from typing import Any
from uuid import UUID

from vectra_common import deps
from vectra_common.errors import VectraError
from vectra_contracts.catalog import CreditStatus
from vectra_contracts.models.api import CreditStatusView

from vectra_case.config import (
    BREAKER_FAILURE_RATIO,
    BREAKER_HALF_OPEN_AFTER,
    BREAKER_WINDOW_CALLS,
    BREAKER_WINDOW_SECONDS,
    CORE_POOL,
    CORE_TIMEOUT,
)

NOT_FOUND = 404
OK = 200


class CreditReader:
    def __init__(
        self,
        enabled: bool,
        base_url: str | None = None,
        token_source: deps.TokenSource | None = None,
        *,
        transport: Any = None,
    ) -> None:
        self.enabled = enabled
        self._client: deps.DependencyClient | None = None
        if enabled:
            if not base_url:
                raise ValueError("core.enabled exige la URL del core")
            self._client = deps.DependencyClient(
                "core",
                base_url,
                deps.BreakerConfig(
                    open_for=BREAKER_HALF_OPEN_AFTER,
                    window_size=BREAKER_WINDOW_CALLS,
                    failure_ratio=BREAKER_FAILURE_RATIO,
                    window_seconds=BREAKER_WINDOW_SECONDS,
                ),
                CORE_POOL,
                transport=transport,
                token_source=token_source,
            )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def status(self, case_id: UUID) -> CreditStatus:
        if self._client is None:
            return CreditStatus.NO_INTEGRADO
        try:
            async with asyncio.timeout(CORE_TIMEOUT):  # tope duro, ademas del timeout de `deps.call`
                response = await deps.call(
                    self._client, "GET", f"/v1/credits/{case_id}", timeout=CORE_TIMEOUT
                )
            if response.status_code == NOT_FOUND:
                return CreditStatus.SIN_CREDITO
            if response.status_code != OK:
                return CreditStatus.NO_DISPONIBLE
            return CreditStatusView.model_validate_json(response.content).status
        except (VectraError, ValueError, TimeoutError):
            return CreditStatus.NO_DISPONIBLE
