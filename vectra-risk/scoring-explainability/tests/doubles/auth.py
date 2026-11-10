"""Tokens y autenticador de prueba para las apps de U7 (el de U0, con la audiencia del servicio)."""

from typing import Any

from strategies import auth as u0
from vectra_common.authn import Authenticator
from vectra_common.jwks_cache import JwksCache


def authenticator(service: str) -> Authenticator:
    async def fetch() -> Any:
        return u0.jwks_document()

    return Authenticator(issuer=u0.ISSUER, audience=service, jwks=JwksCache(fetch))


def service_headers(service: str, scope: str) -> dict[str, str]:
    """Un token de cliente (sin `roles`): `case-worker` hacia scoring, scoring hacia explainability."""
    return u0.bearer(aud=service, roles=None, acr=None, auth_time=None, scope=scope, sub="svc-client")


def user_headers(service: str, *roles: str) -> dict[str, str]:
    """Un token de usuario del BFF con esos roles."""
    return u0.bearer(aud=service, roles=list(roles))
