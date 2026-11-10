"""`scoring-service`: app, arranque y apagado (Paso 12; INF-U7-01, 03, 04; NFR-U7-30, 31; P-U7-07).

Una ruta de `REGISTRY`, `POST /v1/recommendations` (F15, scope `case:recommend`), sobre `create_app` de U0. Readiness y liveness solo
del proceso (8081). El apagado lo hace `ops_server` (uvicorn con `timeout_graceful_shutdown = 10`): una solicitud en curso, con su
append al registro, termina antes de salir (INF-U7-03). El chart solo inyecta URLs (INF-U7-04); los presupuestos son `config.py`.
"""

import os
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from fastapi import FastAPI
from fastapi.responses import Response
from vectra_common import process
from vectra_common.app_factory import Handler, HandlerKey, RequestContext, create_app
from vectra_common.authn import Authenticator
from vectra_common.deps import DependencyClient, TokenSource
from vectra_common.ops_server import run_service
from vectra_contracts.catalog import Scope
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.api import ScoringRequest
from vectra_contracts.routes import REGISTRY

from scoring import config
from scoring.clients import ExplainabilityClient, PolicySource, PredictClient, RegistryClient
from scoring.orchestrator import Orchestrator
from scoring.serving_config_client import ServingConfigClient

SERVICE: Final = "scoring-service"
GOVERNANCE_AUDIENCE: Final = "governance-service"
EXPLAINABILITY_AUDIENCE: Final = "explainability-service"
REGISTRY_AUDIENCE: Final = "decision-registry-service"
#: Lo unico que inyecta el chart (INF-U7-04). La plantilla de KServe lleva `{inference_service}`.
REQUIRED_ENV: Final = (
    "SCORING_GOVERNANCE_URL",
    "SCORING_EXPLAINABILITY_URL",
    "SCORING_REGISTRY_URL",
    "SCORING_PREDICTOR_URL_TEMPLATE",
)

TokenFactory = Callable[[str, tuple[Scope, ...]], TokenSource | None]


@dataclass(frozen=True)
class Settings:
    governance_url: str
    explainability_url: str
    registry_url: str
    predictor_url_template: str


def settings_from_env(env: Mapping[str, str]) -> Settings:
    missing = [name for name in REQUIRED_ENV if not env.get(name)]
    if missing:
        raise ContractViolation(f"faltan variables de entorno: {', '.join(missing)}")
    template = env["SCORING_PREDICTOR_URL_TEMPLATE"]
    if "{inference_service}" not in template or "://" not in template:
        raise ContractViolation("SCORING_PREDICTOR_URL_TEMPLATE debe ser una URL con {inference_service}")
    return Settings(
        env["SCORING_GOVERNANCE_URL"],
        env["SCORING_EXPLAINABILITY_URL"],
        env["SCORING_REGISTRY_URL"],
        template,
    )


@dataclass
class ScoringDeps:
    orchestrator: Orchestrator
    clients: list[DependencyClient]


def _no_token(_audience: str, _scopes: tuple[Scope, ...]) -> TokenSource | None:
    return None


def build_deps(
    settings: Settings,
    policy_source: PolicySource,
    tokens: TokenFactory = _no_token,
    transports: Mapping[str, Any] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    **orchestrator_kwargs: Any,
) -> ScoringDeps:
    """Un cliente por dependencia (P-U7-04): `:predict` 20, explainability 20, registro 10, `serving-config` 5. `transports` solo en pruebas."""
    process.ensure_service()
    wired = transports or {}

    def client(name: str, url: str, pool: int, audience: str, scopes: tuple[Scope, ...]) -> DependencyClient:
        return DependencyClient(
            name,
            url,
            config.BREAKER,
            pool,
            transport=wired.get(name),
            token_source=tokens(audience, scopes) if audience else None,
        )

    # KServe no autentica con JWT (mTLS de Linkerd, U1): sin audiencia; el host lo arma `PredictClient` con la plantilla.
    scheme = settings.predictor_url_template.partition("://")[0]
    predict = client("predict", f"{scheme}://kserve.invalid", config.PREDICT_POOL, "", ())
    explain = client(
        "explainability",
        settings.explainability_url,
        config.EXPLAINABILITY_POOL,
        EXPLAINABILITY_AUDIENCE,
        (Scope.SCORING_EXPLAIN,),
    )
    registry = client(
        "registry",
        settings.registry_url,
        config.REGISTRY_POOL,
        REGISTRY_AUDIENCE,
        (Scope.REGISTRY_APPEND_SCORING,),
    )
    serving = client(
        "serving_config",
        settings.governance_url,
        config.SERVING_CONFIG_POOL,
        GOVERNANCE_AUDIENCE,
        (Scope.GOVERNANCE_READ_SERVING,),
    )
    orchestrator = Orchestrator(
        ServingConfigClient(serving),
        PredictClient(predict, settings.predictor_url_template),
        ExplainabilityClient(explain),
        RegistryClient(registry),
        policy_source,
        clock=clock,
        **orchestrator_kwargs,
    )
    return ScoringDeps(orchestrator, [predict, explain, registry, serving])


def build_handlers(deps: ScoringDeps) -> dict[HandlerKey, Handler]:
    async def recommendations(ctx: RequestContext) -> Response:
        assert isinstance(ctx.body, ScoringRequest)
        # Las dos variantes de `RecommendResult` ya estan construidas (y `Recommendation` solo se construye con las fabricas de U0):
        # se serializan tal cual, sin pasarlas otra vez por `RecommendResult(...)`.
        result = await deps.orchestrator.recommend(ctx.body)
        return Response(result.model_dump_json(exclude_none=True), media_type="application/json")

    return {("POST", "/v1/recommendations"): recommendations}


def create_scoring_app(
    deps: ScoringDeps,
    *,
    authenticator: Authenticator | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    app = create_app(
        SERVICE, REGISTRY[SERVICE], build_handlers(deps), authenticator=authenticator, clock=clock
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            for client in deps.clients:
                await client.aclose()

    app.router.lifespan_context = lifespan
    return app


def run(deps: ScoringDeps) -> None:
    """Sirve 8080 y 8081; el apagado espera <= 10 s a las solicitudes en curso (`ops_server.GRACEFUL_SHUTDOWN`)."""
    run_service(create_scoring_app(deps))


def main() -> None:
    """Arranque en el cluster. Falta la fuente de `cutoff`, `low_confidence_threshold` y `channel_rules` (ver `PolicySource`):
    hasta que el diseno la defina, el proceso no arranca en lugar de fallar cerrado en silencio en cada solicitud."""
    settings_from_env(os.environ)
    raise ContractViolation(
        "policy_source_undefined: ServingConfig no trae los parametros de la politica y ninguna ruta del contrato los sirve a scoring"
    )
