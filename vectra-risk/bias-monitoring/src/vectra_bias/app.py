"""Punto de entrada de `bias-monitoring-service` (puertos 8080 y 8081): `python -m vectra_bias.app` (P-U9-05).

La configuracion llega **solo** por variables de entorno (las pone el chart del Paso 12, U09-T04; sin valores por omision salvo
la ultima fila). Si falta una obligatoria el proceso termina con codigo 2 y el mensaje la nombra; una politica fuera de rango tambien
lo detiene (`config.load_policy`).

| Variable                                | Uso                                                                          |
|-----------------------------------------|------------------------------------------------------------------------------|
| `VECTRA_REGISTRY_URL`                   | `decision-registry-service` (U3, F26): `monitoring/freezes` y `daily:query`    |
| `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_ID`  | token de servicio del cliente `bias-monitoring-service` (`private_key_jwt`)   |
| `VECTRA_CLIENT_KEY_PATH`                | llave privada del cliente, montada de solo lectura                           |
| `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL` | validacion de tokens de entrada (U0)                                         |
| `VECTRA_CA_BUNDLE`                      | CA para cualquiera de las URL anteriores con `https`                         |
| `VECTRA_CLIENT_KEY_ID` (opcional)       | `kid` de la llave del cliente                                                |
| `VECTRA_POLICY_PATH` (opcional)         | parametros de cumplimiento; por omision `config.POLICY_PATH` (el `ConfigMap`) |

La imagen es una sola con los dos puntos de entrada (`run` del CronJob y `app` del servicio): este modulo no importa `freeze_client`
ni `run` (import-linter, `servicio-no-congela`, y `-X importtime` en `tests/integration/test_entrypoint.py`).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from fastapi import FastAPI
from pydantic import BaseModel, TypeAdapter
from starlette.responses import Response
from vectra_common import logging as vlog
from vectra_common import process
from vectra_common.app_factory import Handler, RequestContext, create_app
from vectra_common.authn import Authenticator
from vectra_common.deps import BreakerConfig, DependencyClient, TokenSource
from vectra_common.ops_server import run_service
from vectra_common.service_token import provider_from_env
from vectra_contracts.catalog import LogEvent, Scope
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.monitoring import CompareSourceRequest, DisparityFilter, FreezeSummary

from vectra_bias import compare, config, dashboard, freezes
from vectra_bias.cache import SingleFlightCache
from vectra_bias.registry_client import REGISTRY_SERVICE, route_path

SERVICE: Final = "bias-monitoring-service"
#: Las obligatorias son exactamente las que pondra el `Deployment` del chart (U09-T04 compara los nombres).
REQUIRED: Final = (
    "VECTRA_REGISTRY_URL",
    "VECTRA_TOKEN_URL",
    "VECTRA_CLIENT_ID",
    "VECTRA_CLIENT_KEY_PATH",
    "VECTRA_OIDC_ISSUER",
    "VECTRA_JWKS_URL",
)
OPTIONAL: Final = ("VECTRA_CLIENT_KEY_ID", "VECTRA_POLICY_PATH", "VECTRA_CA_BUNDLE")
EXIT_CONFIG: Final = 2
#: P-U9-02: los umbrales de U7 (las ultimas 20 llamadas en 30 s, abre con la mitad fallida, 10 s abierto).
BREAKER: Final = BreakerConfig(open_for=10, window_size=20, failure_ratio=0.5, window_seconds=30)
REGISTRY_CONNECTIONS: Final = 16


class ConfigError(Exception):
    """Falta una variable obligatoria o algo de la configuracion no se puede usar. El mensaje la nombra, nunca su valor."""


@dataclass(frozen=True)
class ServiceConfig:
    registry_url: str
    policy: config.MonitoringPolicy


def config_from_env(environ: Mapping[str, str] | None = None) -> ServiceConfig:
    """Lee solo el entorno. Falla si falta una obligatoria, si una URL `https` no tiene `VECTRA_CA_BUNDLE` o si la politica no vale."""
    env = os.environ if environ is None else environ
    missing = [name for name in REQUIRED if not env.get(name)]
    if missing:
        raise ConfigError(f"faltan variables de entorno obligatorias: {', '.join(missing)}")
    secure = [
        n
        for n in ("VECTRA_REGISTRY_URL", "VECTRA_TOKEN_URL", "VECTRA_JWKS_URL")
        if env[n].startswith("https://")
    ]
    if secure and not env.get("VECTRA_CA_BUNDLE"):
        raise ConfigError("falta VECTRA_CA_BUNDLE: hay URL https y la verificacion nunca se desactiva")
    path = Path(env.get("VECTRA_POLICY_PATH") or config.POLICY_PATH)
    try:
        policy = config.load_policy(path)
    except config.PolicyError as error:
        raise ConfigError(f"politica de cumplimiento invalida (VECTRA_POLICY_PATH): {error}") from error
    return ServiceConfig(env["VECTRA_REGISTRY_URL"], policy)


def _route(method: str, tail: str) -> tuple[str, str]:
    return (method, route_path(SERVICE, method, tail))


def _role(ctx: RequestContext) -> str:
    """El rol con el que consulta (`cro` o `cumplimiento`: el contrato solo deja pasar esos); un servicio no tiene."""
    return ",".join(sorted(role.value for role in ctx.principal.roles))


def build_handlers(
    client: DependencyClient,
    policy: config.MonitoringPolicy,
    cache: SingleFlightCache,
    clock: Callable[[], datetime],
) -> dict[tuple[str, str], Handler]:
    """Los cuatro handlers, con las llaves `(metodo, ruta)` de `REGISTRY[SERVICE]` (nunca literales)."""

    async def disparity(ctx: RequestContext) -> BaseModel:
        assert isinstance(ctx.query, DisparityFilter)
        view = await dashboard.get_disparity(client, policy, cache, ctx.query, clock)
        # NFR-U9-32: cada consulta, tambien la servida desde la cache, con el que consulta (no con el que lleno la cache).
        vlog.log_event(
            LogEvent.DISPARITY_VIEWED,
            principal_subject=ctx.principal.subject,
            principal_role=_role(ctx),
            model_version_id=view.model_version_id,
            window_from=view.window.from_day.isoformat(),
            window_to=view.window.to_day.isoformat(),
        )
        return view

    async def list_freezes(_: RequestContext) -> Response:
        summaries = await freezes.list_freezes(client)
        body = TypeAdapter(list[FreezeSummary]).dump_json(summaries, exclude_none=True)
        return Response(body, media_type="application/json")

    async def get_freeze(ctx: RequestContext) -> BaseModel:
        record = await freezes.get_freeze(client, ctx.path_params["id"])
        vlog.log_event(
            LogEvent.FREEZE_CONTEXT_VIEWED,
            principal_subject=ctx.principal.subject,
            principal_role=_role(ctx),
            model_version_id=record.model_version_id,
        )
        return record

    async def source_comparison(ctx: RequestContext) -> BaseModel:
        assert isinstance(ctx.body, CompareSourceRequest)
        return compare.compare_source(ctx.body, policy)

    return {
        _route("GET", "/disparity"): disparity,
        _route("GET", "/freezes"): list_freezes,
        _route("GET", "/{id}"): get_freeze,
        _route("POST", "/source-comparisons"): source_comparison,
    }


def build(
    cfg: ServiceConfig,
    token_source: TokenSource | None,
    *,
    authenticator: Authenticator | None = None,
    transport: Any = None,  # un `httpx.AsyncBaseTransport` (las pruebas): este modulo no importa httpx
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    cache: SingleFlightCache | None = None,
) -> FastAPI:
    """`create_app` con el `DependencyClient` del registro **con breaker** (P-U9-02) y la readiness solo del proceso."""
    process.ensure_service()
    client = DependencyClient(
        "registry",
        cfg.registry_url,
        BREAKER,
        REGISTRY_CONNECTIONS,
        transport=transport,
        token_source=token_source,
    )
    handlers = build_handlers(client, cfg.policy, cache or SingleFlightCache(), clock)
    return create_app(SERVICE, handlers=handlers, authenticator=authenticator, readiness=None, clock=clock)


def build_app() -> FastAPI:
    cfg = config_from_env()
    try:
        token = provider_from_env(REGISTRY_SERVICE, (Scope.REGISTRY_READ_MONITORING.value,))
    except OSError as error:
        raise ConfigError(f"VECTRA_CLIENT_KEY_PATH no se puede leer ({type(error).__name__})") from error
    return build(cfg, token)


def main() -> None:
    try:
        app = build_app()
    except (ConfigError, ContractViolation) as error:
        sys.stderr.write(f"bias-monitoring-service no arranca: {error}\n")
        raise SystemExit(EXIT_CONFIG) from None
    run_service(app)


__all__ = ["REQUIRED", "SERVICE", "ConfigError", "build", "build_app", "config_from_env", "main"]

if __name__ == "__main__":
    main()
