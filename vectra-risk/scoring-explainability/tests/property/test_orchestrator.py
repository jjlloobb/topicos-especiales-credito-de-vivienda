"""PBT-U7-07 y 08 y la propiedad de P-U7-01 sobre el `orchestrator` con dobles (CA-4; US-103, 109, 111, 113; RT-1).

La semilla de Hypothesis sale en el encabezado de pytest (`conftest.py`).
"""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from doubles.governance import GovernanceDouble
from doubles.kserve import KServeDouble
from doubles.samples import MODEL, OTHER_MODEL, dictionary, scoring_request, serving_config
from doubles.worlds import ScoringWorld, scoring_world
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from vectra_contracts.catalog import EntryType, FailClosedCause
from vectra_contracts.labels import derive
from vectra_contracts.models.application import ApplicationIn
from vectra_contracts.models.explanation import FailClosed
from vectra_contracts.models.features import FeatureSpec
from vectra_contracts.outcome import Recommendation
from vectra_reference.adversarial import rt1_cases
from vectra_reference.release import Release

SERVING = ("activo", "congelado", "caido")
PREDICT = ("ok", "timeout", "connect", "http503", "invalid_score", "other_version")
EXPLAIN = (
    "ok",
    "timeout",
    "connect",
    "http503",
    "http500",
    "version_mismatch",
    "dictionary",
    "factuality",
    "other_version",
)
REGISTRY = ("ok", "fail_once", "always_503", "timeout", "reject_422")


@dataclass(frozen=True)
class Scenario:
    serving: str
    same_version: bool
    predict: str
    explain: str
    registry: str


scenarios = st.builds(
    Scenario,
    serving=st.sampled_from(SERVING),
    same_version=st.booleans(),
    predict=st.sampled_from(PREDICT),
    explain=st.sampled_from(EXPLAIN),
    registry=st.sampled_from(REGISTRY),
)


def configure(world: ScoringWorld, scenario: Scenario) -> None:
    if scenario.serving == "congelado":
        world.gov.config = serving_config(state="congelado")
    elif scenario.serving == "caido":
        world.transports["serving_config"].fault = "timeout"
    kserve, explain, registry = world.kserve, world.explain, world.registry
    transports = world.transports
    match scenario.predict:
        case "timeout" | "connect":
            transports["predict"].fault = scenario.predict
        case "http503":
            kserve.predict_faults.status = 503
        case "invalid_score":
            kserve.score = 1.5
        case "other_version":
            kserve.predict_version = OTHER_MODEL
    match scenario.explain:
        case "timeout" | "connect":
            transports["explainability"].fault = scenario.explain
        case "http503":
            explain.error = (503, "dependency_unavailable", None)
        case "http500":
            explain.error = (500, "internal_error", None)
        case "version_mismatch":
            explain.error = (409, "conflict_state", "version_mismatch")
        case "dictionary":
            explain.error = (422, "unprocessable_explanation", "feature_dictionary_incomplete")
        case "factuality":
            explain.error = (422, "unprocessable_explanation", "factuality_failed")
        case "other_version":
            explain.version = OTHER_MODEL
    match scenario.registry:
        case "fail_once":
            registry.faults.fail_next = 1
        case "always_503":
            registry.faults.status = 503
        case "timeout":
            transports["registry"].fault = "timeout"
        case "reject_422":
            registry.reject_status = 422


def oracle(scenario: Scenario) -> FailClosedCause | None:
    """La tabla de BR-U0-02 escrita aparte de `check_preconditions`: la causa de menor numero que aplica, o ninguna."""
    if scenario.serving == "congelado":
        return FailClosedCause.MODEL_FROZEN
    if scenario.serving == "caido":
        return FailClosedCause.SERVING_CONFIG_UNAVAILABLE
    if not scenario.same_version:
        return FailClosedCause.VERSION_MISMATCH  # sin llamadas
    if scenario.predict in ("timeout", "connect", "http503"):
        return FailClosedCause.SERVING_CONFIG_UNAVAILABLE
    if scenario.predict == "invalid_score":
        return FailClosedCause.MODEL_OUTPUT_INVALID
    if scenario.predict == "other_version":
        return (
            FailClosedCause.VERSION_MISMATCH
        )  # el predictor de `serving-config` responde otra version: sin explicador
    by_explain = {
        "timeout": FailClosedCause.TIMEOUT,
        "connect": FailClosedCause.EXPLAINER_UNAVAILABLE,
        "http503": FailClosedCause.EXPLAINER_UNAVAILABLE,
        "http500": FailClosedCause.EXPLAINER_ERROR,
        "version_mismatch": FailClosedCause.VERSION_MISMATCH,
        "dictionary": FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE,
        "factuality": FailClosedCause.FACTUALITY_FAILED,
    }
    applicable: list[FailClosedCause] = []
    if scenario.explain in by_explain:
        applicable.append(by_explain[scenario.explain])
    if scenario.explain == "other_version":  # una `Explanation` de otra version que la prediccion
        applicable.append(FailClosedCause.VERSION_MISMATCH)
    if applicable:
        return min(applicable, key=lambda cause: cause.number)
    if scenario.registry in ("always_503", "timeout", "reject_422"):
        return FailClosedCause.REGISTRY_UNAVAILABLE
    return None


async def run(scenario: Scenario) -> None:
    world = scoring_world()
    try:
        configure(world, scenario)
        requested = MODEL if scenario.same_version else OTHER_MODEL
        result = await world.recommend(scoring_request(model_version_id=requested))
        # PBT-U7-07: siempre un `RecommendResult` (la ruta responde 200); nunca una excepcion.
        assert isinstance(result, Recommendation | FailClosed)
        expected = oracle(scenario)
        if expected is None:
            assert isinstance(result, Recommendation), (scenario, result)
            # Una `Recommendation` solo sale con `registry_entry_id` y con la misma version en prediccion y explicacion.
            assert result.registry_entry_id
            assert result.model_version_id == result.explanation.model_version_id == MODEL
            stored = {item.ack.registry_entry_id for item in world.registry.entries(EntryType.RECOMMENDATION)}
            assert result.registry_entry_id in stored
        else:
            assert isinstance(result, FailClosed) and result.cause is expected, (scenario, result)
            if expected is not FailClosedCause.REGISTRY_UNAVAILABLE:
                assert not world.registry.entries(EntryType.RECOMMENDATION)
            if expected in (FailClosedCause.MODEL_FROZEN, FailClosedCause.VERSION_MISMATCH) and (
                scenario.serving == "congelado" or not scenario.same_version
            ):
                assert world.kserve.recorder.calls == [] and world.explain.calls == []  # sin llamadas
        for entry in world.registry.entries(
            EntryType.FAIL_CLOSED
        ):  # BR-U7-16: `cause` y nada de `local_cause`
            payload = entry.entry.payload.model_dump(exclude_none=True)  # type: ignore[union-attr]
            assert set(payload) == {"cause", "retryable", "attempt"}
    finally:
        await world.aclose()


@settings(deadline=None, suppress_health_check=list(HealthCheck))
@given(scenarios)
def test_pbt_u7_07_every_combination_of_failures_ends_in_a_recommend_result(scenario: Scenario) -> None:
    asyncio.run(run(scenario))


# --- P-U7-01: sin invocar el registro para una `recommendation`, se responde antes de 1 s -----------------------------------------

latencies = st.sampled_from((0.0, 0.2, 0.4, 0.9, 2.0))


@settings(max_examples=12, deadline=None, suppress_health_check=list(HealthCheck))
@given(serving=latencies, predict=latencies, explain=latencies, registry=st.sampled_from((0.0, 0.1)))
def test_p_u7_01_without_a_recommendation_append_the_answer_comes_before_1_s(
    serving: float, predict: float, explain: float, registry: float
) -> None:
    async def scenario() -> tuple[float, bool, object]:
        world = scoring_world()
        try:
            world.gov.config_faults.delay = serving
            world.kserve.predict_faults.delay = predict
            world.explain.faults.delay = explain
            world.registry.faults.delay = registry
            started = time.perf_counter()
            result = await world.recommend(scoring_request())
            elapsed = time.perf_counter() - started
            invoked = any(
                call.method == "POST" and b'"entry_type":"recommendation"' in call.body
                for call in world.registry.calls
            )
            return elapsed, invoked, result
        finally:
            await world.aclose()

    elapsed, invoked, result = asyncio.run(scenario())
    assert isinstance(result, Recommendation | FailClosed)
    if not invoked:
        assert elapsed < 1.0, (elapsed, serving, predict, explain, registry)


# --- PBT-U7-08 (RT-1): solo `free_text` difiere -> misma recomendacion y misma narrativa --------------------------------------------


@pytest.fixture(scope="module")
def spec_and_cases(reference_release: Release) -> tuple[FeatureSpec, list[dict[str, Any]]]:
    spec = FeatureSpec.model_validate_json(
        Path(reference_release.package_dir, "feature_spec.json").read_text(encoding="utf-8")
    )
    return spec, rt1_cases()


def vector_of(application: dict[str, Any], spec: FeatureSpec):  # type: ignore[no-untyped-def]
    parsed = ApplicationIn.model_validate_json(json.dumps(application))
    from datetime import date

    return derive(parsed, date(2026, 11, 10), spec)


async def evaluate(features, spec: FeatureSpec) -> tuple[Recommendation, ScoringWorld]:  # type: ignore[no-untyped-def]
    version = spec.model_version_id
    gov = GovernanceDouble(
        serving_config(model_version_id=version), {version: dictionary(version, ids=tuple(features.features))}
    )
    world = scoring_world(gov=gov, kserve=KServeDouble(version), real_explainability=True)
    result = await world.recommend(
        scoring_request(case_id=_CASE, model_version_id=version, features=features)
    )
    assert isinstance(result, Recommendation), result
    return result, world


from uuid import UUID  # noqa: E402

_CASE = UUID(int=11)


def comparable(result: Recommendation) -> dict[str, Any]:
    body = json.loads(result.model_dump_json())
    for volatile in ("registry_entry_id", "evaluated_at"):
        body.pop(volatile)
    return body


async def check_pair(case: dict[str, Any], free_text: str | None, spec: FeatureSpec) -> None:
    first = dict(case["input"])
    second = dict(case["paired_with"])
    if free_text is not None:
        first["free_text"] = free_text
    assert first.get("free_text") != second.get("free_text") or free_text is None
    left, world_a = await evaluate(vector_of(first, spec), spec)
    right, world_b = await evaluate(vector_of(second, spec), spec)
    try:
        assert comparable(left) == comparable(right)  # misma recomendacion y misma narrativa
        assert left.explanation.narrative == right.explanation.narrative
        for world in (world_a, world_b):  # `free_text` no viaja a ninguna dependencia (BR-U7-12)
            seen = [*world.kserve.recorder.calls, *world.registry.calls, *world.gov.calls]
            assert all(b"free_text" not in call.body and "free_text" not in call.query for call in seen)
    finally:
        await world_a.aclose()
        await world_b.aclose()


def test_pbt_u7_08_the_20_rt1_pairs_give_identical_outputs(
    spec_and_cases: tuple[FeatureSpec, list[dict[str, Any]]],
) -> None:
    spec, cases = spec_and_cases
    assert len(cases) == 20
    for case in cases:
        asyncio.run(check_pair(case, None, spec))


@settings(max_examples=40, deadline=None, suppress_health_check=list(HealthCheck))
@given(data=st.data(), text=st.text(alphabet="abcdefghij klmnopqrstuvwxyz.,", min_size=1, max_size=120))
def test_pbt_u7_08_generated_free_text_does_not_change_the_output(
    spec_and_cases: tuple[FeatureSpec, list[dict[str, Any]]], data: st.DataObject, text: str
) -> None:
    spec, cases = spec_and_cases
    case = data.draw(st.sampled_from(cases))
    try:
        ApplicationIn.model_validate_json(json.dumps({**case["input"], "free_text": text}))
    except ValidationError:
        assume(False)
    asyncio.run(check_pair(case, text, spec))
