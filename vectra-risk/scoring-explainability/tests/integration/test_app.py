"""Paso 12 (CA-5): `create_app` de los dos servicios, arranque, readiness, scopes, roles y etiquetas de metricas (P-U7-07; NFR-U7-21)."""

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import explainability.metrics as explainability_metrics
import httpx
import pytest
import scoring.metrics as scoring_metrics
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from doubles.explainability import ExplainabilityDouble
from doubles.governance import GovernanceDouble
from doubles.kserve import KServeDouble
from doubles.registry import RegistryDouble
from doubles.servers import Server
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from strategies import auth as u0
from vectra_contracts.catalog import Outcome, ReasonCode
from vectra_contracts.outcome import RecommendResult, Recommendation
from doubles.auth import authenticator, service_headers, user_headers
from doubles.registry import seed_recommendation
from doubles.samples import explain_request, scoring_request, serving_config
from doubles.worlds import explainability_world, scoring_world
from explainability.app import REQUIRED_ENV as EXPLAINABILITY_ENV
from explainability.app import build_handlers as explainability_handlers
from explainability.app import settings_from_env as explainability_settings
from prometheus_client import generate_latest
from scoring.app import REQUIRED_ENV as SCORING_ENV
from scoring.app import build_handlers as scoring_handlers
from scoring.app import settings_from_env as scoring_settings
from vectra_common.metrics import REGISTRY as METRICS
from vectra_common.ops_server import GRACEFUL_SHUTDOWN
from vectra_contracts.errors import ContractViolation
from vectra_contracts.routes import REGISTRY

from integration.test_applicant_summaries import explanation  # noqa: E402


async def get(app: object, path: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ops") as client:  # type: ignore[arg-type]
        return await client.get(path)


def test_both_services_start_with_the_handlers_of_every_route_of_the_registry() -> None:
    scoring, explainability = scoring_world(), explainability_world()
    assert set(scoring_handlers(scoring.deps)) == {(r.method, r.path) for r in REGISTRY["scoring-service"]}
    assert (
        set(explainability_handlers(explainability.deps))
        == {(r.method, r.path) for r in REGISTRY["explainability-service"]}
        == {("POST", "/v1/explanations"), ("POST", "/v1/applicant-summaries")}
    )
    assert {r.path for r in REGISTRY["scoring-service"]} == {"/v1/recommendations"}
    assert GRACEFUL_SHUTDOWN == 10  # INF-U7-03: el apagado espera a lo en curso <= 10 s


async def test_with_governance_down_explainability_is_ready_and_the_first_explanation_asks_the_dictionary() -> (
    None
):
    world = explainability_world()
    world.faults["dictionary"].fault = "connect"
    async with world.app.router.lifespan_context(world.app):
        await asyncio.sleep(0.1)  # la precarga fallo sin bloquear el arranque
        assert (await get(world.app.state.ops_app, "/readyz")).status_code == 200
        assert (await get(world.app.state.ops_app, "/healthz")).status_code == 200
        assert world.deps.dictionaries.versions == []
        world.faults["dictionary"].fault = None  # governance vuelve
        response = await world.post("/v1/explanations", explain_request().model_dump_json())
        assert response.status_code == 200, response.text
        assert world.gov.recorder.count("feature-dictionary") == 1  # la primera explicacion lo pidio
    await world.aclose()


async def test_readiness_and_liveness_depend_only_on_the_process_in_scoring() -> None:
    world = scoring_world()
    for name in ("serving_config", "predict", "explainability", "registry"):
        world.transports[name].fault = "connect"
    assert (await get(world.app.state.ops_app, "/readyz")).status_code == 200
    assert (await get(world.app.state.ops_app, "/healthz")).status_code == 200
    await world.aclose()


async def test_a_route_without_the_scope_is_403_and_without_a_token_is_401() -> None:
    scoring, explainability = scoring_world(), explainability_world()
    wrong = service_headers("scoring-service", "scoring:explain")  # el scope de F20 en la ruta de F15
    assert (await scoring.post(scoring_request(), wrong)).status_code == 403
    assert (await scoring.post(scoring_request(), {})).status_code == 401
    assert (
        await scoring.post(scoring_request(), service_headers("scoring-service", "case:recommend"))
    ).status_code == 200
    other = service_headers("explainability-service", "case:recommend")
    assert (
        await explainability.post("/v1/explanations", explain_request().model_dump_json(), other)
    ).status_code == 403
    assert (
        await explainability.post("/v1/explanations", explain_request().model_dump_json(), {})
    ).status_code == 401
    await scoring.aclose()
    await explainability.aclose()


@pytest.mark.parametrize(
    ("roles", "status"),
    [(("analista",), 200), (("cro",), 200), (("ingeniero_riesgo",), 403), (("cumplimiento",), 403)],
)
async def test_applicant_summaries_only_for_analista_or_cro(roles: tuple[str, ...], status: int) -> None:
    world = explainability_world()
    case_id = uuid4()
    stored = seed_recommendation(world.registry, case_id, explanation())
    body = json.dumps({"case_id": str(case_id), "recommendation_entry_id": stored.ack.registry_entry_id})
    response = await world.post(
        "/v1/applicant-summaries", body, user_headers("explainability-service", *roles)
    )
    assert response.status_code == status, response.text
    await world.aclose()


async def test_a_service_token_cannot_ask_for_an_applicant_summary() -> None:
    world = explainability_world()
    body = json.dumps({"case_id": str(uuid4()), "recommendation_entry_id": "1"})
    response = await world.post(
        "/v1/applicant-summaries", body, service_headers("explainability-service", "scoring:explain")
    )
    assert response.status_code == 403  # los roles son del BFF (F12), no de un cliente de servicio
    await world.aclose()


async def test_metric_labels_are_inside_the_p_u7_07_allowlist_and_never_carry_ids() -> None:
    scoring, explainability = scoring_world(), explainability_world()
    case_id = uuid4()
    assert (await scoring.post(scoring_request(case_id=case_id))).status_code == 200
    scoring.explain.error = (409, "conflict_state", "version_mismatch")
    await scoring.post(scoring_request(case_id=case_id))
    await explainability.post("/v1/explanations", explain_request(case_id=case_id).model_dump_json())
    declared = {*scoring_metrics.ALL, *explainability_metrics.ALL}
    names = {metric._name for metric in declared}  # noqa: SLF001
    assert (
        len(names) == 7
    )  # las 8 de P-U7-08 menos `vectra_circuit_state` (U0); dos nombres los comparten los servicios
    seen = 0
    for family in METRICS.collect():
        if not any(family.name.startswith(name) for name in names):
            continue
        for sample in family.samples:
            assert set(sample.labels) - {"le"} <= scoring_metrics.LABEL_ALLOWLIST, (
                sample.name,
                sample.labels,
            )  # `le` es del bucket del histograma
            seen += 1
    assert seen > 0
    exposition = generate_latest(METRICS).decode()
    assert (
        str(case_id) not in exposition and "mv-0000" not in exposition and "isvc-" not in exposition
    )  # sin ids ni versiones
    assert scoring_metrics.LABEL_ALLOWLIST == explainability_metrics.LABEL_ALLOWLIST
    await scoring.aclose()
    await explainability.aclose()


def test_the_chart_only_injects_urls_and_the_settings_name_what_is_missing() -> None:
    assert set(SCORING_ENV) | set(EXPLAINABILITY_ENV) == {
        "SCORING_GOVERNANCE_URL",
        "SCORING_EXPLAINABILITY_URL",
        "SCORING_REGISTRY_URL",
        "SCORING_PREDICTOR_URL_TEMPLATE",
        "EXPLAINABILITY_GOVERNANCE_URL",
        "EXPLAINABILITY_REGISTRY_URL",
        "EXPLAINABILITY_EXPLAINER_URL_TEMPLATE",
    }
    with pytest.raises(ContractViolation, match="SCORING_REGISTRY_URL"):
        scoring_settings(
            {
                "SCORING_GOVERNANCE_URL": "http://g",
                "SCORING_EXPLAINABILITY_URL": "http://e",
                "SCORING_PREDICTOR_URL_TEMPLATE": "http://{inference_service}",
            }
        )
    with pytest.raises(ContractViolation, match="EXPLAINABILITY_EXPLAINER_URL_TEMPLATE"):
        explainability_settings(
            {"EXPLAINABILITY_GOVERNANCE_URL": "http://g", "EXPLAINABILITY_REGISTRY_URL": "http://r"}
        )
    with pytest.raises(ContractViolation, match="inference_service"):
        explainability_settings(
            {
                "EXPLAINABILITY_GOVERNANCE_URL": "http://g",
                "EXPLAINABILITY_REGISTRY_URL": "http://r",
                "EXPLAINABILITY_EXPLAINER_URL_TEMPLATE": "http://fijo",
            }
        )
    good = {name: "http://x/{inference_service}" for name in SCORING_ENV}
    assert scoring_settings(good).predictor_url_template == "http://x/{inference_service}"


class _RealProcess:
    """`python -m scoring.app` como proceso, con `REQUIRED_ENV` y los `VECTRA_*` de U0 apuntando a dobles HTTP (U04-T09, CA-6).

    El unico ajuste es de puertos: `ops_server.serve` usa 8080/8081 por omision, y aqui se cambian por puertos libres para que
    dos corridas no choquen; el `main()` que se ejecuta es el real (`runpy`, `run_name="__main__"`)."""

    def __init__(self, tmp_path: Path, gov: GovernanceDouble, kserve: KServeDouble) -> None:
        self.gov, self.kserve = gov, kserve
        self.explain, self.registry = ExplainabilityDouble(), RegistryDouble()
        self.servers = [
            Server(app).start()
            for app in (
                gov.app,
                self.explain.app,
                self.registry.app,
                kserve.app,
                Starlette(routes=[Route("/jwks", self._jwks)]),
                Starlette(routes=[Route("/token", self._token, methods=["POST"])]),
            )
        ]
        key = tmp_path / "client.pem"
        key.write_bytes(
            ec.generate_private_key(ec.SECP256R1()).private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        self.port, self.ops_port = _free_port(), _free_port()
        code = (
            "import runpy, vectra_common.ops_server as o\n"
            f"o.serve.__kwdefaults__.update(port={self.port}, ops_port={self.ops_port})\n"
            "runpy.run_module('scoring.app', run_name='__main__')\n"
        )
        self.env = {
            **os.environ,
            "SCORING_GOVERNANCE_URL": self.servers[0].url,
            "SCORING_EXPLAINABILITY_URL": self.servers[1].url,
            "SCORING_REGISTRY_URL": self.servers[2].url,
            "SCORING_PREDICTOR_URL_TEMPLATE": self.servers[3].url + "/{inference_service}",
            "VECTRA_OIDC_ISSUER": u0.ISSUER,
            "VECTRA_JWKS_URL": self.servers[4].url + "/jwks",
            "VECTRA_CLIENT_ID": "scoring-service",
            "VECTRA_TOKEN_URL": self.servers[5].url + "/token",
            "VECTRA_CLIENT_KEY_PATH": str(key),
        }
        self.process = subprocess.Popen([sys.executable, "-c", code], env=self.env)  # noqa: S603

    @staticmethod
    async def _jwks(_request: Request) -> JSONResponse:
        return JSONResponse(u0.jwks_document())

    @staticmethod
    async def _token(_request: Request) -> JSONResponse:
        return JSONResponse({"access_token": "t", "expires_in": 300})

    async def ready(self) -> None:
        async with httpx.AsyncClient() as client:
            for _ in range(400):
                assert self.process.poll() is None, (
                    f"scoring.app termino al arrancar: {self.process.returncode}"
                )
                try:
                    if (await client.get(f"http://127.0.0.1:{self.ops_port}/readyz")).status_code == 200:
                        return
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.05)
        raise AssertionError("scoring.app no quedo listo")

    async def recommend(self) -> Recommendation:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"http://127.0.0.1:{self.port}/v1/recommendations",
                content=scoring_request().model_dump_json(),
                headers={
                    "content-type": "application/json",
                    **service_headers("scoring-service", "case:recommend"),
                },
            )
        assert response.status_code == 200, response.text
        result = RecommendResult.from_wire(response.content)
        assert isinstance(result, Recommendation), result
        return result

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        for server in self.servers:
            server.stop()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def test_main_starts_the_real_process_and_the_outcome_follows_the_cutoff_served_by_serving_config(
    tmp_path: Path,
) -> None:
    kserve = KServeDouble()
    kserve.score = 0.4  # el mismo score queda de un lado u otro del corte segun lo que sirva `serving-config`
    gov = GovernanceDouble(serving_config(cutoff="0.5000", low_confidence_threshold="0.1000"))
    process = _RealProcess(tmp_path, gov, kserve)
    try:
        await process.ready()
        first = await process.recommend()
        assert first.policy_version_id == gov.config.policy_version_id
        assert first.outcome is Outcome.FAVORABLE and ReasonCode.SCORE_BAJO_CORTE in first.reasons
        gov.config = serving_config(cutoff="0.3000", low_confidence_threshold="0.1000", etag="etag-2")
        await asyncio.sleep(5.3)  # P-U7-05: la cache de `serving-config` de scoring dura <= 5 s
        second = await process.recommend()
        assert (
            second.outcome is Outcome.DESFAVORABLE
            and ReasonCode.SCORE_SOBRE_CORTE in second.reasons
            and ReasonCode.SCORE_BAJO_CORTE not in second.reasons
        )
    finally:
        process.stop()


async def test_main_policy_parameters_and_policy_version_id_come_from_the_same_snapshot() -> None:
    world = scoring_world()
    world.kserve.score = 0.4
    world.deps.orchestrator._serving._ttl = 0  # noqa: SLF001 - sin cache: cada solicitud lee la foto vigente del doble
    try:
        world.gov.config = serving_config(
            policy_version_id="pol-a", cutoff="0.5000", low_confidence_threshold="0.1000", etag="a"
        )
        first = await world.recommend(scoring_request())
        world.gov.config = serving_config(
            policy_version_id="pol-b", cutoff="0.3000", low_confidence_threshold="0.1000", etag="b"
        )
        second = await world.recommend(scoring_request())
        assert isinstance(first, Recommendation) and isinstance(second, Recommendation)
        assert (first.policy_version_id, first.outcome) == ("pol-a", Outcome.FAVORABLE)
        assert (second.policy_version_id, second.outcome) == ("pol-b", Outcome.DESFAVORABLE)
        assert [call.method for call in world.gov.calls].count(
            "GET"
        ) == 2  # sin una segunda llamada por solicitud
    finally:
        await world.aclose()


def test_the_authenticator_helper_checks_the_service_audience() -> None:
    assert authenticator("scoring-service").audience == "scoring-service"
