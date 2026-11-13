"""Bordes de los clientes, de la cache y del arranque de U7 (Paso 13: cobertura de ramas, NFR-U7-40). Cada prueba cubre una rama con efecto."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import explainability.app as explainability_app
import pytest
import scoring.app as scoring_app
from scoring.clients import ExplainabilityClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from doubles.samples import ISVC, MODEL, explain_request, scoring_request, vector
from doubles.worlds import ExplainabilityWorld, ScoringWorld, explainability_world, scoring_world
from explainability.explain import result_of
from explainability.narrative import FeatureDictionaryIncomplete, TemplateNarrativeGenerator
from fastapi import FastAPI
from vectra_common.deadline import HEADER, to_header
from vectra_common.errors import ConflictState
from vectra_contracts.catalog import ExplainerError, FailClosedCause
from vectra_contracts.models.explanation import FailClosed
from vectra_contracts.outcome import Recommendation


@pytest.fixture
async def explain_world() -> AsyncIterator[ExplainabilityWorld]:
    built = explainability_world()
    yield built
    await built.aclose()


@pytest.fixture
async def score_world() -> AsyncIterator[ScoringWorld]:
    built = scoring_world()
    yield built
    await built.aclose()


def body(**kwargs: Any) -> str:
    return explain_request(**kwargs).model_dump_json()


# --- explainability -----------------------------------------------------------------------------------------------------------


def test_result_of_maps_every_error_to_its_label() -> None:
    assert result_of(None) == "ok"
    assert result_of(ConflictState()) == "error"  # un 409 sin `reason` no es de las seis etiquetas
    assert result_of(RuntimeError()) == "error"


@pytest.mark.parametrize("payload", [{"explanations": []}, {"explanations": "x"}, {"nada": 1}])
async def test_an_unreadable_explainer_answer_is_a_500(
    explain_world: ExplainabilityWorld, payload: dict[str, Any]
) -> None:
    explain_world.kserve.explain_body = payload
    assert (await explain_world.post("/v1/explanations", body())).status_code == 500


async def test_an_explainer_factor_outside_the_requested_vector_is_a_500(
    explain_world: ExplainabilityWorld,
) -> None:
    explain_world.kserve.contributions = {"installment_cop": 0.1, "no_esta_en_el_vector": 0.2}
    assert (await explain_world.post("/v1/explanations", body())).status_code == 500


class _Incomplete(TemplateNarrativeGenerator):
    def generate(self, shap_vector, dictionary, model_version_id):  # type: ignore[no-untyped-def]
        raise FeatureDictionaryIncomplete("x")


async def test_a_generator_that_finds_a_missing_entry_is_a_422_incomplete(
    explain_world: ExplainabilityWorld,
) -> None:
    explain_world.deps.explainer._generator = _Incomplete()  # noqa: SLF001
    response = await explain_world.post("/v1/explanations", body())
    assert response.status_code == 422 and response.json()["reason"] == "feature_dictionary_incomplete"


async def test_a_deadline_inside_the_50_ms_margin_is_an_immediate_504(
    explain_world: ExplainabilityWorld,
) -> None:
    soon = to_header(datetime.now(UTC) + timedelta(milliseconds=30))  # `deadline - 50 ms` ya paso
    from doubles.auth import service_headers

    response = await explain_world.post(
        "/v1/explanations",
        body(),
        {**service_headers("explainability-service", "scoring:explain"), HEADER: soon},
    )
    assert response.status_code == 504 and explain_world.kserve.recorder.calls == []


async def test_a_dictionary_hit_does_not_call_governance_again(explain_world: ExplainabilityWorld) -> None:
    cache = explain_world.deps.dictionaries
    first = await cache.get(MODEL)
    assert await cache.get(MODEL) is first and explain_world.gov.recorder.count("feature-dictionary") == 1


async def test_the_preload_gives_up_quietly_when_serving_config_is_not_200(
    explain_world: ExplainabilityWorld,
) -> None:
    explain_world.gov.config_faults.status = 503
    assert await explain_world.deps.dictionaries.preload() is None
    explain_world.gov.config_faults.status = None
    assert await explain_world.deps.dictionaries.preload() == MODEL


def _ec_key(tmp_path: Path) -> Path:
    key = ec.generate_private_key(ec.SECP256R1())
    path = tmp_path / "key.pem"
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    return path


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **urls: str) -> None:
    for name, value in {
        **urls,
        "VECTRA_CLIENT_ID": "svc",
        "VECTRA_TOKEN_URL": "http://keycloak/token",
        "VECTRA_ASSERTION_AUDIENCE": "http://keycloak/realm",
        "VECTRA_CLIENT_KEY_PATH": str(_ec_key(tmp_path)),
        "VECTRA_OIDC_ISSUER": "http://keycloak/realm",
        "VECTRA_JWKS_URL": "http://keycloak/jwks",
    }.items():
        monkeypatch.setenv(name, value)


def test_explainability_main_builds_the_app_from_the_environment_and_serves_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _env(
        monkeypatch,
        tmp_path,
        EXPLAINABILITY_GOVERNANCE_URL="http://governance",
        EXPLAINABILITY_REGISTRY_URL="http://registry",
        EXPLAINABILITY_EXPLAINER_URL_TEMPLATE="http://{inference_service}-explainer",
    )
    served: list[FastAPI] = []
    monkeypatch.setattr(explainability_app, "run_service", served.append)
    explainability_app.main()
    assert len(served) == 1 and served[0].title == "explainability-service"


def test_scoring_run_serves_the_app(monkeypatch: pytest.MonkeyPatch) -> None:
    world = scoring_world()
    monkeypatch.setenv("VECTRA_OIDC_ISSUER", "http://keycloak/realm")
    monkeypatch.setenv("VECTRA_JWKS_URL", "http://keycloak/jwks")
    served: list[FastAPI] = []
    monkeypatch.setattr(scoring_app, "run_service", served.append)
    scoring_app.run(world.deps)
    assert len(served) == 1 and served[0].title == "scoring-service"


def test_a_predictor_template_without_the_placeholder_is_rejected() -> None:
    env = {name: "http://x" for name in scoring_app.REQUIRED_ENV}
    with pytest.raises(Exception, match="inference_service"):
        scoring_app.settings_from_env(env)


async def test_the_scoring_lifespan_closes_every_client(score_world: ScoringWorld) -> None:
    async with score_world.app.router.lifespan_context(score_world.app):
        assert all(not client._client.is_closed for client in score_world.deps.clients)  # noqa: SLF001
    assert all(client._client.is_closed for client in score_world.deps.clients)  # noqa: SLF001


async def test_the_explainability_lifespan_closes_every_client(explain_world: ExplainabilityWorld) -> None:
    async with explain_world.app.router.lifespan_context(explain_world.app):
        await asyncio.sleep(0.05)
    assert all(client._client.is_closed for client in explain_world.deps.clients)  # noqa: SLF001


# --- scoring: clientes y cache --------------------------------------------------------------------------------------------------


async def test_concurrent_requests_with_an_expired_cache_revalidate_once(score_world: ScoringWorld) -> None:
    score_world.gov.config_faults.delay = 0.2
    results = await asyncio.gather(*(score_world.recommend(scoring_request()) for _ in range(3)))
    assert all(isinstance(result, Recommendation) for result in results)
    assert score_world.gov.recorder.count("serving-config") == 1  # los otros esperaron al primero


async def test_a_dropped_connection_or_an_unreadable_serving_config_is_no_disponible(
    score_world: ScoringWorld,
) -> None:
    score_world.transports["serving_config"].fault = "connect"
    result = await score_world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.SERVING_CONFIG_UNAVAILABLE
    score_world.transports["serving_config"].fault = None
    score_world.gov.config_faults.status = 200  # 200 sin cuerpo
    result = await score_world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.SERVING_CONFIG_UNAVAILABLE


@pytest.mark.parametrize(
    "answer",
    [
        {"predictions": []},
        {"predictions": [{"score": 0.1, "confidence": "abc", "model_version_id": MODEL}]},
        {"x": 1},
        "texto",
    ],
)
async def test_an_unreadable_predictor_answer_is_no_prediction(
    score_world: ScoringWorld, answer: Any
) -> None:
    score_world.kserve.predict_body = answer
    result = await score_world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.SERVING_CONFIG_UNAVAILABLE


async def test_a_predictor_non_200_is_no_prediction(score_world: ScoringWorld) -> None:
    score_world.kserve.predict_faults.status = 422
    result = await score_world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.SERVING_CONFIG_UNAVAILABLE


@pytest.mark.parametrize(
    ("status", "content", "expected"),
    [
        (409, b'{"reason":"version_mismatch"}', ExplainerError.VERSION_MISMATCH),
        (422, b'{"reason":"feature_dictionary_incomplete"}', ExplainerError.FEATURE_DICTIONARY_INCOMPLETE),
        (422, b'{"reason":"factuality_failed"}', ExplainerError.FACTUALITY_FAILED),
        (422, b"no es json", ExplainerError.ERROR),
        (409, b'["no", "un", "dict"]', ExplainerError.ERROR),
        (409, b'{"reason":3}', ExplainerError.ERROR),
        (504, b"", ExplainerError.TIMEOUT),
        (503, b"", ExplainerError.UNAVAILABLE),
        (500, b"", ExplainerError.ERROR),
        (404, b"", ExplainerError.ERROR),
        (200, b'{"basura":1}', ExplainerError.ERROR),
    ],
)
def test_the_explainer_errors_of_domain_entities_section_5_are_translated(
    status: int, content: bytes, expected: ExplainerError
) -> None:
    assert ExplainabilityClient._translate(status, content) is expected  # noqa: SLF001


async def test_a_client_that_fails_unexpectedly_never_escapes_as_an_exception(
    score_world: ScoringWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("token source roto")

    monkeypatch.setattr("scoring.clients.deps.call", boom)
    orchestrator = score_world.deps.orchestrator
    deadline = datetime.now(UTC) + timedelta(seconds=1)
    assert await orchestrator._predictor.predict(ISVC, vector(), deadline) is None  # noqa: SLF001
    assert await orchestrator._explainer.explain(explain_request(), deadline) is ExplainerError.ERROR  # noqa: SLF001
    assert (await orchestrator._registry.append(None)).kind == "unavailable"  # type: ignore[arg-type]  # noqa: SLF001


async def test_an_unreadable_registry_ack_is_not_retried(score_world: ScoringWorld) -> None:
    score_world.registry.faults.status = 200  # 200 sin ack
    result = await score_world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.REGISTRY_UNAVAILABLE
    assert (
        len([call for call in score_world.registry.calls if call.method == "POST"]) == 2
    )  # 1 intento + el fail_closed


def test_the_default_append_jitter_is_between_0_and_100_ms() -> None:
    from scoring.orchestrator import default_jitter

    assert all(0 <= default_jitter() <= 0.1 for _ in range(200))
