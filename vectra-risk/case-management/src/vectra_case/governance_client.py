"""Cliente de governance (F104): `serving-config` (Paso 11, P-1 (a); NFR-U8-15, 30, 31) y `feature_spec` (Paso 14; BR-U8-05).

Un solo `DependencyClient` por proceso (P-U8-02: un pool y un breaker por dependencia), con `deps.call`:
- `serving-config`: 500 ms, cache <= 5 s con `If-None-Match`. Una respuesta con la forma vieja falla la validacion estricta de
  `ServingConfig` y se informa como `ServingConfigInvalid`: el llamador (barrido, worker) falla cerrado.
- `feature_spec`: 1 s, por `model_version_id`, sin expiracion (una version publicada es inmutable) y con LRU de 4 versiones.
- El pool lo fija quien crea el cliente: 2 en `case-service` (`GOVERNANCE_SERVICE_POOL`), 4 en `case-worker` (`GOVERNANCE_WORKER_POOL`).
- Solo timeout, conexion y 5xx cuentan como fallo del breaker (los aplica `deps.call`); un 4xx no. Una sola llamada por consulta
  (NFR-U8-33): ningun reintento aqui; el reintento es el siguiente intento del caso (backoff, BR-U8-07).
- Cada llamada lleva ademas un tope duro con `asyncio.timeout` (el `httpx.Timeout` de `deps` limita cada fase, no la llamada entera).
"""

import asyncio
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from vectra_common import deps
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_contracts.models.features import FeatureSpec
from vectra_contracts.models.governance import ServingConfig

from vectra_case.config import (
    BREAKER_FAILURE_RATIO,
    BREAKER_HALF_OPEN_AFTER,
    BREAKER_WINDOW_CALLS,
    BREAKER_WINDOW_SECONDS,
    FEATURE_SPEC_TIMEOUT,
    GOVERNANCE_SERVICE_POOL,
    SERVING_CONFIG_CACHE_TTL,
    SERVING_CONFIG_TIMEOUT,
)

NOT_MODIFIED = 304
OK = 200
FEATURE_SPEC_CACHE_SIZE = 4  # LRU de versiones (BR-U8-05): la activa, la anterior y dos mas por un rollback


class ServingConfigInvalid(Exception):  # noqa: N818
    """La respuesta no cumple `ServingConfig` (p. ej. la forma vieja, sin `cutoff`) ni `FeatureSpec`."""


class ServingConfigClient:
    def __init__(
        self,
        base_url: str,
        token_source: deps.TokenSource | None,
        *,
        pool: int = GOVERNANCE_SERVICE_POOL,
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
            pool,
            transport=transport,
            token_source=token_source,
        )
        self._clock = clock
        self._cached: ServingConfig | None = None
        self._fetched_at = 0.0
        self._specs: OrderedDict[str, FeatureSpec] = OrderedDict()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self) -> ServingConfig:
        if self._cached is not None and self._clock() - self._fetched_at <= SERVING_CONFIG_CACHE_TTL:
            return self._cached
        headers = {"If-None-Match": f'"{self._cached.etag}"'} if self._cached is not None else None
        response = await self._get("/v1/serving-config", SERVING_CONFIG_TIMEOUT, headers)
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

    async def _get(self, path: str, timeout: float, headers: dict[str, str] | None = None) -> Any:
        try:
            async with asyncio.timeout(timeout):  # tope duro, ademas del timeout de `deps.call`
                return await deps.call(self._client, "GET", path, timeout=timeout, headers=headers)
        except TimeoutError as exc:
            raise DependencyTimeout() from exc

    async def feature_spec(self, model_version_id: str) -> FeatureSpec:
        """`GET /v1/models/{id}/feature-spec`: cache por version sin expiracion y LRU de 4 (se descarta la menos usada)."""
        cached = self._specs.get(model_version_id)
        if cached is not None:
            self._specs.move_to_end(model_version_id)
            return cached
        response = await self._get(f"/v1/models/{model_version_id}/feature-spec", FEATURE_SPEC_TIMEOUT)
        if response.status_code != OK:
            raise DependencyUnavailable()
        try:
            spec = FeatureSpec.model_validate_json(response.content)
        except ValidationError as exc:
            raise ServingConfigInvalid() from exc
        self._specs[model_version_id] = spec
        if len(self._specs) > FEATURE_SPEC_CACHE_SIZE:
            self._specs.popitem(last=False)
        return spec
