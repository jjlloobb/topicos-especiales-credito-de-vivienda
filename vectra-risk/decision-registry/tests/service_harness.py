"""La app del servicio con tokens de prueba, sin Keycloak (el JWKS y las llaves de prueba son los de U0)."""

from datetime import datetime, timedelta
from typing import Any

import httpx
from entries import NOW
from strategies import auth as u0_auth
from vectra_registry.api import ServiceConfig, create_service_app
from vectra_registry.pools import Pools

APPEND_SCORING = "registry:append:scoring"
APPEND_CASE = "registry:append:case"
APPEND_GOVERNANCE = "registry:append:governance"
READ_EXPLANATION = "registry:read:explanation"
READ_METRICS = "registry:read:metrics"
READ_MONITORING = "registry:read:monitoring"


class Clock:
    """Reloj del servicio, fijo y movible (BR-U3-05)."""

    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


def service_token(scope: str, **over: Any) -> dict[str, str]:
    """Cabecera `Authorization` de un servicio (sin `roles`) con ese scope."""
    return u0_auth.bearer(sub="svc-test", roles=None, acr=None, auth_time=None, scope=scope, **over)


def user_token(role: str, *, mfa: bool = True, at: datetime = NOW, **over: Any) -> dict[str, str]:
    """Cabecera `Authorization` de una persona; `auth_time` se mide contra el reloj del servicio (`at`), no el real."""
    stamp = int(at.timestamp())
    return u0_auth.bearer(
        sub=f"user-{role}", roles=[role], acr="mfa" if mfa else "pwd", auth_time=stamp - 60 if mfa else stamp - 4000, **over
    )


def client_for(pools: Pools, config: ServiceConfig) -> httpx.AsyncClient:
    app = create_service_app(pools, config, authenticator=u0_auth.authenticator())
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://registry"
    )
