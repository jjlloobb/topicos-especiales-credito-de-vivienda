"""Cache de JWKS con single-flight (P-U0-06, NFR-U0-11, 12). Sin extender una cache vencida."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Final

import jwt

from vectra_common.errors import DependencyUnavailable, Unauthenticated
from vectra_common.metrics import JWKS_REFRESH

CACHE_TTL: Final = 600.0
MIN_REFRESH_INTERVAL: Final = 30.0


class JwksCache:
    def __init__(
        self, fetch: Callable[[], Awaitable[Any]], clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._fetch = fetch
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._loaded_at: float | None = None
        self._last_refresh: float | None = None
        self._lock = asyncio.Lock()

    def _valid(self) -> bool:
        return self._loaded_at is not None and self._clock() - self._loaded_at < CACHE_TTL

    def _throttled(self) -> bool:
        return self._last_refresh is not None and self._clock() - self._last_refresh < MIN_REFRESH_INTERVAL

    def _from_cache(self, kid: str) -> jwt.PyJWK:
        """Cache vigente, o 503 si no la hay; un `kid` que no esta en la vigente es 401."""
        if not self._valid():
            raise DependencyUnavailable()
        key = self._keys.get(kid)
        if key is None:
            raise Unauthenticated()
        return key

    async def get_key(self, kid: str) -> jwt.PyJWK:
        if self._valid() and kid in self._keys:
            return self._keys[kid]
        # Con un refresco en curso se espera su resultado (single-flight), no se responde 503.
        if self._throttled() and not self._lock.locked():
            JWKS_REFRESH.labels(result="throttled").inc()
            return self._from_cache(kid)
        async with self._lock:
            if self._valid() and kid in self._keys:
                return self._keys[kid]
            if self._throttled():
                JWKS_REFRESH.labels(result="throttled").inc()
                return self._from_cache(kid)
            self._last_refresh = self._clock()
            try:
                document = await self._fetch()
                keys = {
                    key_id: jwt.PyJWK.from_dict(item)
                    for item in document["keys"]
                    if (key_id := item.get("kid"))
                }
            except (DependencyUnavailable, KeyError, TypeError, jwt.PyJWTError) as exc:
                JWKS_REFRESH.labels(result="error").inc()
                if isinstance(exc, DependencyUnavailable) or not self._valid():
                    return self._from_cache(kid)
                raise DependencyUnavailable() from exc
            self._keys = keys
            self._loaded_at = self._clock()
            JWKS_REFRESH.labels(result="ok").inc()
            return self._from_cache(kid)
