"""Los servicios de U7 conectados a sus dobles, en proceso (`AsgiTransport`) o, con `real=True`, por sockets."""

from dataclasses import dataclass, field
from typing import Any

import httpx
from explainability.app import ExplainabilityDeps, Settings, build_deps, create_explainability_app
from fastapi import FastAPI
from scoring.app import ScoringDeps
from scoring.app import Settings as ScoringSettings
from scoring.app import build_deps as build_scoring_deps
from scoring.app import create_scoring_app
from scoring.clients import PolicyParameters
from vectra_contracts.models.api import ScoringRequest
from vectra_contracts.models.explanation import FailClosed
from vectra_contracts.outcome import Recommendation

from doubles.explainability import ExplainabilityDouble

from doubles.auth import authenticator, service_headers
from doubles.governance import GovernanceDouble
from doubles.kserve import KServeDouble
from doubles.registry import RegistryDouble
from doubles.servers import Server
from doubles.transports import AsgiTransport

TEMPLATE = "http://{inference_service}-explainer.vectra-serving"


@dataclass
class ExplainabilityWorld:
    gov: GovernanceDouble
    kserve: KServeDouble
    registry: RegistryDouble
    deps: ExplainabilityDeps
    app: FastAPI
    faults: dict[str, AsgiTransport] = field(default_factory=dict)
    servers: list[Server] = field(default_factory=list)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False),
            base_url="http://explainability",
        )

    async def post(self, path: str, body: str, headers: dict[str, str] | None = None) -> httpx.Response:
        async with self.client() as client:
            return await client.post(
                path,
                content=body,
                headers={
                    "content-type": "application/json",
                    **(
                        headers
                        if headers is not None
                        else service_headers("explainability-service", "scoring:explain")
                    ),
                },
            )

    async def aclose(self) -> None:
        for client in self.deps.clients:
            await client.aclose()
        for server in self.servers:
            server.stop()


def explainability_world(
    gov: GovernanceDouble | None = None,
    kserve: KServeDouble | None = None,
    registry: RegistryDouble | None = None,
    clock: Any = None,
    **deps_kwargs: Any,
) -> ExplainabilityWorld:
    gov, kserve, registry = gov or GovernanceDouble(), kserve or KServeDouble(), registry or RegistryDouble()
    transports = {
        "dictionary": AsgiTransport(gov.app),
        "registry": AsgiTransport(registry.app),
        "explain": AsgiTransport(kserve.app),
    }
    extra = {"clock": clock} if clock is not None else {}
    deps = build_deps(
        Settings("http://governance", "http://registry", TEMPLATE),
        transports=transports,
        **extra,
        **deps_kwargs,
    )
    app = create_explainability_app(deps, authenticator=authenticator("explainability-service"), **extra)
    return ExplainabilityWorld(gov, kserve, registry, deps, app, faults=transports)


# --- scoring ----------------------------------------------------------------------------------------------------------------

SCORING_TEMPLATE = "http://{inference_service}-predictor.vectra-serving"


class StaticPolicy:
    """La fuente de la politica activa en las pruebas (la real esta sin definir, ver la bitacora)."""

    def __init__(self, cutoff: str = "0.5000", low_confidence_threshold: str = "0.6000") -> None:
        self.parameters: PolicyParameters | None = PolicyParameters(
            cutoff=cutoff, low_confidence_threshold=low_confidence_threshold, channel_rules=[]
        )
        self.calls = 0

    async def get(self, policy_version_id: str) -> PolicyParameters | None:
        self.calls += 1
        return self.parameters


class FakeToken:
    """Un `TokenSource` firmado con la llave de prueba de U0, para que la app real de explainability autentique a scoring."""

    def __init__(self, audience: str, scopes: tuple[Any, ...]) -> None:
        self._audience = audience
        self._scope = " ".join(str(getattr(scope, "value", scope)) for scope in scopes)

    async def token(self) -> str:
        return service_headers(self._audience, self._scope)["authorization"].removeprefix("Bearer ")

    def invalidate(self) -> None:
        return None


def _tokens(audience: str, scopes: tuple[Any, ...]) -> FakeToken:
    return FakeToken(audience, scopes)


@dataclass
class ScoringWorld:
    gov: GovernanceDouble
    kserve: KServeDouble
    explain: ExplainabilityDouble
    registry: RegistryDouble
    policy: StaticPolicy
    deps: ScoringDeps
    app: FastAPI
    transports: dict[str, AsgiTransport]
    real_explainability: ExplainabilityWorld | None = None
    servers: list[Server] = field(default_factory=list)

    async def recommend(self, request: ScoringRequest) -> Recommendation | FailClosed:
        return await self.deps.orchestrator.recommend(request)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False), base_url="http://scoring"
        )

    async def post(self, request: ScoringRequest, headers: dict[str, str] | None = None) -> httpx.Response:
        async with self.client() as client:
            return await client.post(
                "/v1/recommendations",
                content=request.model_dump_json(),
                headers={
                    "content-type": "application/json",
                    **(
                        headers
                        if headers is not None
                        else service_headers("scoring-service", "case:recommend")
                    ),
                },
            )

    async def aclose(self) -> None:
        for client in self.deps.clients:
            await client.aclose()
        if self.real_explainability is not None:
            await self.real_explainability.aclose()
        for server in self.servers:
            server.stop()


def scoring_world(
    gov: GovernanceDouble | None = None,
    kserve: KServeDouble | None = None,
    explain: ExplainabilityDouble | None = None,
    registry: RegistryDouble | None = None,
    policy: StaticPolicy | None = None,
    real_explainability: bool = False,
    **kwargs: Any,
) -> ScoringWorld:
    gov, kserve, explain = (
        gov or GovernanceDouble(),
        kserve or KServeDouble(),
        explain or ExplainabilityDouble(),
    )
    registry, policy = registry or RegistryDouble(), policy or StaticPolicy()
    chain = explainability_world(gov=gov, kserve=kserve, registry=registry) if real_explainability else None
    transports = {
        "serving_config": AsgiTransport(gov.app),
        "predict": AsgiTransport(kserve.app),
        "registry": AsgiTransport(registry.app),
        "explainability": AsgiTransport(chain.app if chain is not None else explain.app),
    }
    deps = build_scoring_deps(
        ScoringSettings("http://governance", "http://explainability", "http://registry", SCORING_TEMPLATE),
        policy,
        tokens=_tokens,
        transports=transports,
        sleep=_no_sleep,
        jitter=lambda: 0.0,
        **kwargs,
    )
    app = create_scoring_app(deps, authenticator=authenticator("scoring-service"))
    return ScoringWorld(gov, kserve, explain, registry, policy, deps, app, transports, chain)


async def _no_sleep(_seconds: float) -> None:
    return None
