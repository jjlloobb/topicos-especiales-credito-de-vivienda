"""Cliente de `serving-config` de governance (Paso 11, P-1 (a); NFR-U8-15, 30, 31).

Solo la lectura de `serving-config` (F104): `deps.call` con timeout de 500 ms, el breaker de NFR-U8-31 y cache <= 5 s con
`If-None-Match`. U08-T04 le anade `feature_spec` y no lo duplica. Una respuesta con la forma vieja falla la validacion estricta de
`ServingConfig` y se informa como `ServingConfigInvalid`: el llamador (barrido) falla cerrado.
"""

import time
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from vectra_common import deps
from vectra_common.errors import DependencyUnavailable
from vectra_contracts.models.governance import ServingConfig

from vectra_case.config import (
    BREAKER_FAILURE_RATIO,
    BREAKER_HALF_OPEN_AFTER,
    BREAKER_WINDOW_CALLS,
    BREAKER_WINDOW_SECONDS,
    GOVERNANCE_SERVICE_POOL,
    SERVING_CONFIG_TIMEOUT,
)

CACHE_TTL = 5.0
NOT_MODIFIED = 304
OK = 200


class ServingConfigInvalid(Exception):  # noqa: N818
    """La respuesta no cumple `ServingConfig` (p. ej. la forma vieja, sin `cutoff`)."""


class ServingConfigClient:
    def __init__(
        self,
        base_url: str,
        token_source: deps.TokenSource | None,
        *,
        transport: Any = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = deps.DependencyClient(
            "governance",
            base_url,
            deps.BreakerConfig(
                open_for=BREAKER_HALF_OPEN_AFTER,
                window_size=BREAKER_WINDOW_CALLS,
                failure_ratio=BREAKER_FAILURE_RATIO,
                window_seconds=BREAKER_WINDOW_SECONDS,
            ),
            GOVERNANCE_SERVICE_POOL,
            transport=transport,
            token_source=token_source,
        )
        self._clock = clock
        self._cached: ServingConfig | None = None
        self._fetched_at = 0.0

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self) -> ServingConfig:
        if self._cached is not None and self._clock() - self._fetched_at <= CACHE_TTL:
            return self._cached
        headers = {"If-None-Match": f'"{self._cached.etag}"'} if self._cached is not None else None
        response = await deps.call(
            self._client, "GET", "/v1/serving-config", timeout=SERVING_CONFIG_TIMEOUT, headers=headers
        )
        if response.status_code == NOT_MODIFIED and self._cached is not None:
            self._fetched_at = self._clock()
            return self._cached
        if response.status_code != OK:
            raise DependencyUnavailable()
        try:
            config = ServingConfig.model_validate_json(response.content)
        except ValidationError as exc:
            raise ServingConfigInvalid() from exc
        self._cached, self._fetched_at = config, self._clock()
        return config
