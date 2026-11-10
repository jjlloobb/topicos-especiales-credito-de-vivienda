"""Cache de `serving-config` de scoring (BR-U7-01; P-U7-05; NFR-U7-21): <= 5 s, revalidada con `If-None-Match` y el `etag`.

Si la revalidacion falla con la entrada vencida, el resultado es `None` (`serving_state = no_disponible`): **nunca** se usa una
entrada vencida (AUTONOMIA-04, AUTONOMIA-06). El congelamiento llega entonces en <= 6 s: 5 s de cache mas la llamada.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from vectra_common import deps
from vectra_common.deps import DependencyClient
from vectra_common.errors import DependencyTimeout
from vectra_contracts.models.governance import ServingConfig

from scoring.config import SERVING_CONFIG_CACHE_TTL_MS, SERVING_CONFIG_TIMEOUT_MS
from scoring.metrics import DEADLINE_EXHAUSTED, timed

OK = 200
NOT_MODIFIED = 304


@dataclass
class _Entry:
    config: ServingConfig
    fetched_at: float


class ServingConfigClient:
    """`client` es el de governance (F18, pool 5, su breaker). `clock` es monotonico, para probar el vencimiento."""

    def __init__(
        self,
        client: DependencyClient,
        clock: Callable[[], float] = time.monotonic,
        ttl_ms: int = SERVING_CONFIG_CACHE_TTL_MS,
    ) -> None:
        self._client = client
        self._clock = clock
        self._ttl = ttl_ms / 1000
        self._entry: _Entry | None = None
        self._lock = asyncio.Lock()

    def _fresh(self) -> ServingConfig | None:
        entry = self._entry
        if entry is not None and self._clock() - entry.fetched_at < self._ttl:
            return entry.config
        return None

    async def get(self, deadline: datetime | None = None) -> ServingConfig | None:
        """La configuracion vigente, o `None` si no se pudo confirmar (`no_disponible`)."""
        fresh = self._fresh()
        if fresh is not None:
            return fresh
        async with self._lock:
            fresh = self._fresh()  # otra solicitud pudo revalidar mientras esperabamos
            if fresh is not None:
                return fresh
            return await self._revalidate(deadline)

    async def _revalidate(self, deadline: datetime | None) -> ServingConfig | None:
        stale = self._entry
        headers = {"If-None-Match": f'"{stale.config.etag}"'} if stale is not None else None
        try:
            async with timed("serving_config"):
                response = await deps.call(
                    self._client,
                    "GET",
                    "/v1/serving-config",
                    timeout=SERVING_CONFIG_TIMEOUT_MS / 1000,
                    deadline=deadline,
                    headers=headers,
                )
        except DependencyTimeout:
            DEADLINE_EXHAUSTED.labels(stage="serving_config").inc()
            return None
        except Exception:  # noqa: BLE001 - breaker abierto, conexion caida o similar: no_disponible
            return None
        if response.status_code == NOT_MODIFIED and stale is not None:
            stale.fetched_at = self._clock()
            return stale.config
        if response.status_code != OK:
            return None
        try:
            config = ServingConfig.model_validate_json(response.content)
        except ValueError:
            return None
        self._entry = _Entry(config, self._clock())
        return config
