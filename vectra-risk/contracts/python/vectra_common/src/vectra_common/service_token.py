"""Token de servicio: client credentials con `private_key_jwt` (U2 BR-U2-09). Unico cliente de `/token`."""

import asyncio
import os
import secrets
import time
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any, Final

import jwt

from vectra_common import deps
from vectra_common.errors import DependencyUnavailable

ASSERTION_TYPE: Final = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
ASSERTION_LIFETIME: Final = 60
RENEW_BEFORE: Final = 30
TOKEN_TIMEOUT: Final = 2.0
Poster = Callable[[str, Mapping[str, str], float], Awaitable[Any]]


class ServiceTokenProvider:
    """Guarda el token hasta `RENEW_BEFORE` s antes de vencer; pide uno solo a la vez."""

    def __init__(
        self,
        client_id: str,
        token_url: str,
        private_key: str,
        audience: str,
        scopes: tuple[str, ...],
        *,
        algorithm: str = "ES256",
        key_id: str | None = None,
        poster: Poster | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._client_id = client_id
        self._token_url = token_url
        self._private_key = private_key
        self._audience = audience
        self._scopes = scopes
        self._algorithm = algorithm
        self._key_id = key_id
        self._poster = poster or deps.post_form_once
        self._clock = clock
        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._expires_at = 0.0

    def invalidate(self) -> None:
        self._token = None

    def _assertion(self) -> str:
        now = int(self._clock())
        claims = {
            "iss": self._client_id,
            "sub": self._client_id,
            "aud": self._token_url,
            "jti": secrets.token_hex(16),
            "iat": now,
            "exp": now + ASSERTION_LIFETIME,
        }
        headers = {"kid": self._key_id} if self._key_id else None
        return jwt.encode(claims, self._private_key, algorithm=self._algorithm, headers=headers)

    async def token(self) -> str:
        async with self._lock:
            if self._token is not None and self._clock() < self._expires_at - RENEW_BEFORE:
                return self._token
            answer = await self._poster(
                self._token_url,
                {
                    "grant_type": "client_credentials",
                    "client_assertion_type": ASSERTION_TYPE,
                    "client_assertion": self._assertion(),
                    "scope": " ".join(self._scopes),
                    "audience": self._audience,
                },
                TOKEN_TIMEOUT,
            )
            try:
                self._token = str(answer["access_token"])
                self._expires_at = self._clock() + float(answer["expires_in"])
            except (KeyError, TypeError, ValueError) as exc:
                raise DependencyUnavailable() from exc
            return self._token


def provider_from_env(audience: str, scopes: tuple[str, ...]) -> ServiceTokenProvider:
    """Lee `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH` y `VECTRA_CLIENT_KEY_ID`."""
    return ServiceTokenProvider(
        os.environ["VECTRA_CLIENT_ID"],
        os.environ["VECTRA_TOKEN_URL"],
        Path(os.environ["VECTRA_CLIENT_KEY_PATH"]).read_text(encoding="utf-8"),
        audience,
        scopes,
        key_id=os.environ.get("VECTRA_CLIENT_KEY_ID"),
    )
