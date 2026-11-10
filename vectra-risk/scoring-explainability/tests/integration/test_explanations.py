"""Paso 8 (CA-1): `POST /v1/explanations` con dobles de KServe y de governance (BR-U7-08 a 11; P-U7-01, 04, 05; US-104, 105, 111)."""

import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from doubles.governance import GovernanceDouble
from doubles.kserve import KServeDouble
from doubles.samples import ISVC, MODEL, OTHER_MODEL, dictionary, explain_request, vector
from doubles.worlds import ExplainabilityWorld, explainability_world
from vectra_common.deadline import HEADER, to_header
from vectra_contracts.models.explanation import Explanation
from vectra_contracts.models.features import FeatureDictionary
from vectra_common.metrics import REGISTRY as METRICS

from explainability.dictionary_cache import DictionaryCache
from explainability.explain import Explainer
from explainability.narrative import TemplateNarrativeGenerator


@pytest.fixture
async def world() -> AsyncIterator[ExplainabilityWorld]:
    built = explainability_world()
    yield built
    await built.aclose()


def body(**kwargs: object) -> str:
    return explain_request(**kwargs).model_dump_json()  # type: ignore[arg-type]


def result_count(result: str) -> float:
    return METRICS.get_sample_value("vectra_explanations_total", {"result": result}) or 0.0


async def test_a_cold_cache_runs_the_dictionary_and_explain_in_parallel(world: ExplainabilityWorld) -> None:
    world.gov.dictionary_faults.delay = 0.4
    world.kserve.explain_faults.delay = 0.4
    started = time.perf_counter()
    response = await world.post("/v1/explanations", body())
    elapsed = time.perf_counter() - started
    assert response.status_code == 200, response.text
    assert 0.38 < elapsed < 0.6, elapsed  # ~400 ms, no ~800 ms
    explanation = Explanation.model_validate_json(response.content)
    assert explanation.model_version_id == MODEL
    assert explanation.factuality_check == "passed"
    assert explanation.feature_dictionary_version == "d-1"
    assert explanation.narrative.startswith("Explicación del riesgo estimado")


async def test_the_second_request_uses_the_cache(world: ExplainabilityWorld) -> None:
    assert (await world.post("/v1/explanations", body())).status_code == 200
    assert (await world.post("/v1/explanations", body())).status_code == 200
    assert world.gov.recorder.count("feature-dictionary") == 1


async def test_a_past_deadline_is_an_immediate_504(world: ExplainabilityWorld) -> None:
    past = to_header(datetime.now(UTC) - timedelta(seconds=1))
    started = time.perf_counter()
    response = await world.post("/v1/explanations", body(), _with(HEADER, past))
    assert response.status_code == 504
    assert response.json()["code"] == "deadline_exceeded"
    assert time.perf_counter() - started < 0.1
    assert world.kserve.recorder.calls == [] and world.gov.calls == []  # nada se llamo


def _with(name: str, value: str) -> dict[str, str]:
    from doubles.auth import service_headers

    return {**service_headers("explainability-service", "scoring:explain"), name: value}


@pytest.mark.parametrize(
    "header", [to_header(datetime.now(UTC) + timedelta(hours=1)), "no-es-una-fecha", "2026-11-10T12:00:00"]
)
async def test_a_far_or_malformed_deadline_still_cuts_at_700_ms(
    world: ExplainabilityWorld, header: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # El timeout por llamada (500 ms, NFR-U7-10) es menor que el tope: se sube para ver que corta el tope propio de 700 ms.
    monkeypatch.setattr("explainability.explain.EXPLAIN_TIMEOUT_MS", 5_000)
    world.kserve.explain_faults.delay = 3.0
    started = time.perf_counter()
    response = await world.post("/v1/explanations", body(), _with(HEADER, header))
    elapsed = time.perf_counter() - started
    assert response.status_code == 504, response.text
    assert 0.65 < elapsed < 0.85, elapsed  # una cabecera manipulada no extiende el presupuesto


async def test_the_cut_is_the_header_minus_50_ms_when_it_is_the_smaller(world: ExplainabilityWorld) -> None:
    world.kserve.explain_faults.delay = 3.0
    soon = to_header(datetime.now(UTC) + timedelta(milliseconds=350))
    started = time.perf_counter()
    response = await world.post("/v1/explanations", body(), _with(HEADER, soon))
    elapsed = time.perf_counter() - started
    assert response.status_code == 504
    assert 0.2 < elapsed < 0.45, elapsed  # deadline - 50 ms ~ 300 ms


async def test_rt3_an_explainer_of_another_version_is_a_409_version_mismatch(
    world: ExplainabilityWorld,
) -> None:
    world.kserve.explain_version = OTHER_MODEL
    before = result_count("version_mismatch")
    response = await world.post("/v1/explanations", body())
    assert response.status_code == 409
    assert response.json()["code"] == "conflict_state" and response.json()["reason"] == "version_mismatch"
    assert result_count("version_mismatch") == before + 1


async def test_a_dictionary_of_another_version_is_a_409(world: ExplainabilityWorld) -> None:
    world.gov.dictionaries[MODEL] = dictionary(model_version_id=OTHER_MODEL)
    response = await world.post("/v1/explanations", body())
    assert response.status_code == 409 and response.json()["reason"] == "version_mismatch"


async def test_an_incomplete_dictionary_is_a_422(world: ExplainabilityWorld) -> None:
    world.gov.dictionaries[MODEL] = dictionary(ids=("installment_cop", "age_years"))
    response = await world.post("/v1/explanations", body())
    assert response.status_code == 422
    assert response.json()["code"] == "unprocessable_explanation"
    assert response.json()["reason"] == "feature_dictionary_incomplete"


class _Altered(TemplateNarrativeGenerator):
    """Un generador alterado: invierte el signo de la primera linea."""

    def generate(self, shap_vector, dictionary, model_version_id):  # type: ignore[no-untyped-def]
        text = super().generate(shap_vector, dictionary, model_version_id)
        return (
            text.replace("sube el riesgo", "baja el riesgo", 1)
            if "sube el riesgo" in text
            else text.replace("baja el riesgo", "sube el riesgo", 1)
        )


async def test_an_altered_generator_is_a_422_factuality_failed(world: ExplainabilityWorld) -> None:
    world.deps.explainer._generator = _Altered()  # noqa: SLF001
    response = await world.post("/v1/explanations", body())
    assert response.status_code == 422
    assert (
        response.json()["code"] == "unprocessable_explanation"
        and response.json()["reason"] == "factuality_failed"
    )


async def test_five_versions_drop_the_least_recently_used(world: ExplainabilityWorld) -> None:
    cache = world.deps.dictionaries
    versions = [f"mv-0000000{n}" for n in range(5)]
    for version in versions:
        world.gov.dictionaries[version] = dictionary(model_version_id=version)
    for version in versions[:4]:
        await cache.get(version)
    cache.cached(versions[0])  # la 0 se usa: la menos usada pasa a ser la 1
    await cache.get(versions[4])
    assert cache.versions == [versions[2], versions[3], versions[0], versions[4]]
    assert cache.cached(versions[1]) is None


@pytest.mark.parametrize("fault", ["connect", "timeout"])
async def test_r3_a_dropped_connection_to_explain_is_a_503_or_504_never_a_500(
    world: ExplainabilityWorld, fault: str
) -> None:
    """F22 apagado en D1: la conexion se descarta; scoring debe recibir 503 o 504, nunca 500."""
    world.faults["explain"].fault = fault
    response = await world.post("/v1/explanations", body())
    assert response.status_code in (503, 504), response.text
    assert response.json()["code"] in ("dependency_unavailable", "deadline_exceeded")


async def test_governance_down_is_a_503(world: ExplainabilityWorld) -> None:
    world.gov.dictionary_faults.status = 503
    response = await world.post("/v1/explanations", body())
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
    world.gov.dictionary_faults.status = 404
    assert (await world.post("/v1/explanations", body())).status_code == 503


async def test_a_kserve_503_is_a_503_and_a_4xx_is_a_500(world: ExplainabilityWorld) -> None:
    world.kserve.explain_faults.status = 503
    assert (await world.post("/v1/explanations", body())).status_code == 503
    world.kserve.explain_faults.status = 422
    assert (await world.post("/v1/explanations", body())).status_code == 500


async def test_the_dictionary_call_is_cancelled_when_explain_fails(world: ExplainabilityWorld) -> None:
    world.gov.dictionary_faults.delay = 2.0
    world.kserve.explain_faults.status = 503
    started = time.perf_counter()
    response = await world.post("/v1/explanations", body())
    assert response.status_code == 503
    assert time.perf_counter() - started < 0.5  # no espera al diccionario


async def test_the_explain_url_uses_the_requested_inference_service(world: ExplainabilityWorld) -> None:
    await world.post("/v1/explanations", body(isvc="isvc-12345678"))
    call = world.kserve.recorder.calls[0]
    assert call.path == "/v1/models/isvc-12345678:explain"
    assert call.headers["host"] == "isvc-12345678-explainer.vectra-serving"
    assert call.headers["x-vectra-deadline"]  # la cabecera de presupuesto se propaga


async def test_the_response_has_no_free_text_and_the_request_forbids_it(world: ExplainabilityWorld) -> None:
    raw = body().replace('"features":{', '"features":{"free_text":{"type":"category","value":"x"},', 1)
    response = await world.post("/v1/explanations", raw)
    assert response.status_code == 422
    assert world.kserve.recorder.calls == []


async def test_the_preload_fetches_the_active_version_and_never_blocks_startup() -> None:
    gov = GovernanceDouble()
    world = explainability_world(gov=gov)
    async with world.app.router.lifespan_context(world.app):
        for _ in range(50):
            if world.deps.dictionaries.cached(MODEL) is not None:
                break
            import asyncio

            await asyncio.sleep(0.02)
    assert world.deps.dictionaries.versions == [MODEL]
    assert gov.recorder.count("serving-config") == 1
    await world.aclose()


def test_the_vector_helper_is_the_one_the_double_understands() -> None:
    assert set(vector().features) == {
        "installment_cop",
        "installment_to_income",
        "loan_to_value",
        "age_years",
    }
    assert ISVC.startswith("isvc-")
    assert isinstance(dictionary(), FeatureDictionary) and DictionaryCache and Explainer and KServeDouble
