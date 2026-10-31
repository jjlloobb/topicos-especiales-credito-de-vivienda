"""Validacion de tokens (BR-U0-70, NFR-U0-10). Solo RS256 y ES256."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

import jwt
from vectra_contracts.catalog import Role, Scope
from vectra_contracts.models.api import Principal

from vectra_common import deps
from vectra_common.errors import Unauthenticated
from vectra_common.jwks_cache import JwksCache

ALLOWED_ALGORITHMS: Final = ("RS256", "ES256")
LEEWAY_SECONDS: Final = 30
JWKS_TIMEOUT: Final = 2.0
_ROLES: Final = {role.value: role for role in Role}
_SCOPES: Final = {scope.value: scope for scope in Scope}


def _utc(claim: Any) -> datetime:
    return datetime.fromtimestamp(int(claim), UTC)


def principal_from_claims(claims: dict[str, Any]) -> Principal:
    roles = frozenset(_ROLES[name] for name in claims.get("roles", []) if name in _ROLES)
    scopes = frozenset(_SCOPES[name] for name in str(claims.get("scope", "")).split() if name in _SCOPES)
    return Principal(
        subject=str(claims["sub"]),
        kind="user" if "roles" in claims else "service",
        roles=roles,
        scopes=scopes,
        acr=claims.get("acr"),
        auth_time=_utc(claims["auth_time"]) if "auth_time" in claims else None,
        token_expiry=_utc(claims["exp"]),
    )


@dataclass
class Authenticator:
    issuer: str
    audience: str
    jwks: JwksCache
    #: Permite probar `exp` y `nbf` con un reloj fijo.
    now: Callable[[], float] | None = None

    async def authenticate(self, authorization: str | None) -> Principal:
        if not authorization or not authorization.startswith("Bearer "):
            raise Unauthenticated()
        token = authorization.removeprefix("Bearer ").strip()
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise Unauthenticated() from exc
        kid = header.get("kid")
        if header.get("alg") not in ALLOWED_ALGORITHMS or not isinstance(kid, str):
            raise Unauthenticated()
        key = await self.jwks.get_key(kid)
        try:
            claims = jwt.decode(
                token,
                key=key.key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self.audience,
                issuer=self.issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
            return principal_from_claims(claims)
        except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
            raise Unauthenticated() from exc


def authenticator_from_env(service_name: str) -> Authenticator:
    """Lee `VECTRA_OIDC_ISSUER` y `VECTRA_JWKS_URL`; sin ellos el servicio no arranca."""
    issuer = os.environ["VECTRA_OIDC_ISSUER"]
    url = os.environ["VECTRA_JWKS_URL"]

    async def fetch() -> Any:
        return await deps.fetch_json_once(url, JWKS_TIMEOUT)

    deps._verify_context(url)  # noqa: SLF001 - sin CA valida, falla al arrancar
    return Authenticator(issuer=issuer, audience=service_name, jwks=JwksCache(fetch))
