"""`explainability-service`: app, arranque y apagado (Paso 12; INF-U7-01, 03, 04; NFR-U7-21, 30, 31; P-U7-07).

Dos rutas de `REGISTRY` (`POST /v1/explanations`, F20, y `POST /v1/applicant-summaries`, F12) sobre `create_app` de U0. Readiness y
liveness solo del proceso (8081). La precarga del diccionario no bloquea el arranque: corre en segundo plano y, si governance no
responde, la primera explicacion pide el diccionario. El chart solo inyecta URLs (INF-U7-04); los presupuestos son `config.py`.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from fastapi import FastAPI
from pydantic import BaseModel
from vectra_common import process, service_token
from vectra_common.app_factory import Handler, HandlerKey, RequestContext, create_app
from vectra_common.authn import Authenticator
from vectra_common.deps import DependencyClient, TokenSource
from vectra_common.ops_server import run_service
from vectra_contracts.catalog import Scope
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.api import ApplicantSummaryRequest, ExplainRequest
from vectra_contracts.routes import REGISTRY

from explainability import config
from explainability.dictionary_cache import DictionaryCache
from explainability.explain import Explainer
from explainability.factuality import FactualityValidator
from explainability.narrative import TemplateNarrativeGenerator
from explainability.summaries import ApplicantSummaries, RegistryExplanations

SERVICE: Final = "explainability-service"
GOVERNANCE_AUDIENCE: Final = "governance-service"
REGISTRY_AUDIENCE: Final = "decision-registry-service"
# U2 solo concede `governance:read-dictionary` a este cliente (realm): la precarga de la version activa (F18) recibe 403 y se omite.
GOVERNANCE_SCOPES: Final = (Scope.GOVERNANCE_READ_DICTIONARY,)
REGISTRY_SCOPES: Final = (Scope.REGISTRY_READ_EXPLANATION,)
#: Lo unico que inyecta el chart (INF-U7-04). La plantilla lleva `{inference_service}`: el host del `Service` de KServe.
REQUIRED_ENV: Final = (
    "EXPLAINABILITY_GOVERNANCE_URL",
    "EXPLAINABILITY_REGISTRY_URL",
    "EXPLAINABILITY_EXPLAINER_URL_TEMPLATE",
)

TokenFactory = Callable[[str, tuple[Scope, ...]], TokenSource | None]


@dataclass(frozen=True)
class Settings:
    governance_url: str
    registry_url: str
    explainer_url_template: str


def settings_from_env(env: Mapping[str, str]) -> Settings:
    missing = [name for name in REQUIRED_ENV if not env.get(name)]
    if missing:
        raise ContractViolation(f"faltan variables de entorno: {', '.join(missing)}")
    template = env["EXPLAINABILITY_EXPLAINER_URL_TEMPLATE"]
    if "{inference_service}" not in template or "://" not in template:
        raise ContractViolation(
            "EXPLAINABILITY_EXPLAINER_URL_TEMPLATE debe ser una URL con {inference_service}"
        )
    return Settings(env["EXPLAINABILITY_GOVERNANCE_URL"], env["EXPLAINABILITY_REGISTRY_URL"], template)


@dataclass
class ExplainabilityDeps:
    explainer: Explainer
    summaries: ApplicantSummaries
    dictionaries: DictionaryCache
    clients: list[DependencyClient]


def _no_token(_audience: str, _scopes: tuple[Scope, ...]) -> TokenSource | None:
    return None


def build_deps(
    settings: Settings,
    tokens: TokenFactory = _no_token,
    transports: Mapping[str, Any] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ExplainabilityDeps:
    """Un cliente por dependencia (P-U7-04). `transports` (por nombre de dependencia) solo lo usan las pruebas."""
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

    # KServe no autentica con JWT (mTLS de Linkerd, U1): sin audiencia. El host lo arma `Explainer` con la plantilla.
    scheme = settings.explainer_url_template.partition("://")[0]
    explain_client = client("explain", f"{scheme}://kserve.invalid", config.EXPLAIN_POOL, "", ())
    governance = client(
        "dictionary", settings.governance_url, config.DICTIONARY_POOL, GOVERNANCE_AUDIENCE, GOVERNANCE_SCOPES
    )
    registry = client(
        "registry", settings.registry_url, config.REGISTRY_POOL, REGISTRY_AUDIENCE, REGISTRY_SCOPES
    )
    dictionaries = DictionaryCache(governance)
    return ExplainabilityDeps(
        explainer=Explainer(
            explain_client,
            dictionaries,
            TemplateNarrativeGenerator(),
            FactualityValidator(),
            settings.explainer_url_template,
            clock,
        ),
        summaries=ApplicantSummaries(RegistryExplanations(registry), dictionaries, clock),
        dictionaries=dictionaries,
        clients=[explain_client, governance, registry],
    )


def build_handlers(deps: ExplainabilityDeps) -> dict[HandlerKey, Handler]:
    async def explanations(ctx: RequestContext) -> BaseModel:
        assert isinstance(ctx.body, ExplainRequest)
        return await deps.explainer.explain(ctx.body, ctx.deadline)

    async def applicant_summaries(ctx: RequestContext) -> BaseModel:
        assert isinstance(ctx.body, ApplicantSummaryRequest)
        return await deps.summaries.summarize(ctx.body)

    return {
        ("POST", "/v1/explanations"): explanations,
        ("POST", "/v1/applicant-summaries"): applicant_summaries,
    }


def create_explainability_app(
    deps: ExplainabilityDeps,
    *,
    authenticator: Authenticator | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    app = create_app(
        SERVICE, REGISTRY[SERVICE], build_handlers(deps), authenticator=authenticator, clock=clock
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        preload = asyncio.create_task(deps.dictionaries.preload())  # NFR-U7-21: no bloquea el arranque
        try:
            yield
        finally:
            preload.cancel()
            await asyncio.gather(preload, return_exceptions=True)
            for client in deps.clients:
                await client.aclose()

    app.router.lifespan_context = lifespan
    return app


def main() -> None:
    settings = settings_from_env(os.environ)
    deps = build_deps(settings, tokens=service_token.provider_from_env)
    run_service(create_explainability_app(deps))
