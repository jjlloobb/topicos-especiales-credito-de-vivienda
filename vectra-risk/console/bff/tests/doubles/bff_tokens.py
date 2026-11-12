"""Tokens de prueba del BFF: el emisor de U0 (`contracts/tests/strategies/auth.py`) con los claims de U2.

Claims de U2: `roles`, `acr`, `auth_time`, `aud = console-bff` y `azp = vectra-console`. La audiencia del BFF es su nombre de servicio.
"""

import time
from typing import Any

from strategies import auth as u0
from vectra_common.authn import Authenticator
from vectra_common.jwks_cache import JwksCache

AUDIENCE = "console-bff"
CLIENT = "vectra-console"
ROLES = ("analista", "ingeniero_riesgo", "cro", "cumplimiento")
STALE_SECONDS = 1000  # > 900 s de MFA_MAX_AGE


def authenticator() -> Authenticator:
    async def jwks() -> Any:
        return u0.jwks_document()

    return Authenticator(issuer=u0.ISSUER, audience=AUDIENCE, jwks=JwksCache(jwks))


def bearer(roles: tuple[str, ...] | list[str] = ("analista",), **over: Any) -> dict[str, str]:
    base: dict[str, Any] = {"aud": AUDIENCE, "azp": CLIENT, "roles": list(roles), "sub": "user-1"}
    return u0.bearer(**{**base, **over})


def stale_auth_time() -> int:
    return int(time.time()) - STALE_SECONDS


def for_state(state: str, roles: tuple[str, ...] | list[str]) -> dict[str, str]:
    """Las columnas de estado del token de la matriz (BR-U10-19) para los `roles` dados."""
    if state == "valid":
        return bearer(roles)
    if state == "expired":
        return bearer(roles, exp=int(time.time()) - 3600)
    if state == "other_audience":
        return bearer(roles, aud="otro-servicio")
    if state == "acr_pwd":
        return bearer(roles, acr="pwd")
    if state == "stale_auth_time":
        return bearer(roles, auth_time=stale_auth_time())
    if state == "bad_signature":
        return u0.bearer(key=u0.OTHER_KEY, aud=AUDIENCE, azp=CLIENT, roles=list(roles), sub="user-1")
    raise ValueError(state)


TOKEN_STATES = ("valid", "expired", "other_audience", "acr_pwd", "stale_auth_time", "bad_signature")
