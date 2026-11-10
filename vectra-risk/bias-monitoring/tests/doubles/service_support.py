"""Soporte de las pruebas del servicio (Paso 9): la app de `vectra_bias.app.build` con ASGI en proceso, tokens de usuario y de
servicio firmados con la llave de prueba de U0 y el doble del registro de U3 de `world.py`."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from scenario import NOW, POLICY
from strategies import auth as u0_auth
from vectra_bias import app as bias_app
from vectra_bias import config
from vectra_bias.cache import SingleFlightCache
from vectra_common.authn import Authenticator
from vectra_common.jwks_cache import JwksCache
from vectra_common.logging import configure
from world import REGISTRY_URL, World

SERVICE = "bias-monitoring-service"
BASE = "http://bias"
TODAY = NOW.date()


def authenticator() -> Authenticator:
    async def fetch() -> Any:
        return u0_auth.jwks_document()

    return Authenticator(issuer=u0_auth.ISSUER, audience=SERVICE, jwks=JwksCache(fetch))


def user(role: str, subject: str = "user-1") -> dict[str, str]:
    """Cabeceras de un usuario con ese rol (token firmado con la llave de U0, audiencia del servicio)."""
    return u0_auth.bearer(aud=SERVICE, sub=subject, roles=[role])


def service(scope: str, client: str = "governance-service") -> dict[str, str]:
    return u0_auth.bearer(
        aud=SERVICE, sub=f"svc-{client}", roles=None, acr=None, auth_time=None, scope=scope, azp=client
    )


def write_policy(path: Path, policy: config.MonitoringPolicy = POLICY) -> Path:
    """Un `values-monitoring-policy.yaml` valido con esos cinco parametros (el `ConfigMap` de prueba)."""
    stale = (
        f"{policy.stale_after_s // 3600}h"
        if policy.stale_after_s % 3600 == 0
        else f"{policy.stale_after_s // 60}m"
    )
    path.write_text(
        f"threshold_pp: {policy.threshold_pp}\nn_min: {policy.n_min}\nwindow_days: {policy.window_days}\n"
        f'schedule: "{policy.schedule}"\nstale_after: {stale}\n',
        encoding="utf-8",
    )
    return path


class Service:
    """La app en proceso contra los dobles; `client` habla ASGI (sin red) y `logs` captura el log estructurado."""

    def __init__(
        self,
        world: World,
        *,
        policy: config.MonitoringPolicy = POLICY,
        now: Callable[[], datetime] = lambda: NOW,
        cache: SingleFlightCache | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.world = world
        token = world.keycloak.provider("decision-registry-service", ("registry:read:monitoring",))
        self.app = bias_app.build(
            bias_app.ServiceConfig(REGISTRY_URL, policy),
            token,
            authenticator=authenticator(),
            transport=transport or world.registry.transport(),
            clock=now,
            cache=cache,
        )
        self.stream = io.StringIO()
        configure(SERVICE, self.stream)  # `create_app` configuro stdout: se redirige para leer los eventos
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False), base_url=BASE
        )

    @property
    def logs(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.stream.getvalue().splitlines() if line.strip()]

    def events(self, name: str) -> list[dict[str, Any]]:
        return [line for line in self.logs if line.get("event") == name]

    async def get(self, path: str, role: str = "cumplimiento", **kwargs: Any) -> httpx.Response:
        return await self.client.get(path, headers=user(role, kwargs.pop("subject", "user-1")), **kwargs)


def registry_reads(world: World) -> int:
    """Lecturas que llegaron al doble del registro (`freezes` y `daily:query`)."""
    return len(world.registry.calls)


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def dec(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)
