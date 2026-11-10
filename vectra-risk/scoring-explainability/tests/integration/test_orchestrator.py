"""Paso 11 (CA-4): ejemplos del `orchestrator` con dobles de U3, U4 y U6 y explainability (BR-U7-01, 02, 03, 12, 15, 16; US-103, 111, 113)."""

import time
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from doubles.governance import GovernanceDouble
from doubles.samples import ISVC, MODEL, OTHER_MODEL, POLICY, scoring_request, serving_config
from doubles.worlds import ScoringWorld, scoring_world
from vectra_common.metrics import REGISTRY as METRICS
from vectra_contracts.catalog import EntryType, FailClosedCause
from vectra_contracts.models.explanation import FailClosed
from vectra_contracts.outcome import RecommendResult, Recommendation


@pytest.fixture
async def world() -> AsyncIterator[ScoringWorld]:
    built = scoring_world()
    yield built
    await built.aclose()


def metric(name: str, **labels: str) -> float:
    return METRICS.get_sample_value(name, labels) or 0.0


async def test_us103_a_full_recommendation_carries_m_and_p(world: ScoringWorld) -> None:
    world.kserve.score = 0.2
    result = await world.recommend(scoring_request())
    assert isinstance(result, Recommendation), result
    assert result.model_version_id == MODEL and result.policy_version_id == POLICY
    assert result.explanation.model_version_id == MODEL
    assert (
        result.registry_entry_id == world.registry.entries(EntryType.RECOMMENDATION)[0].ack.registry_entry_id
    )
    assert result.outcome.value == "favorable"  # 0.2 < cutoff 0.5
    assert world.kserve.recorder.calls[0].path == f"/v1/models/{ISVC}:predict"


async def test_the_endpoint_returns_200_with_the_recommend_result(world: ScoringWorld) -> None:
    response = await world.post(scoring_request())
    assert response.status_code == 200 and response.json()["kind"] == "recommendation"
    assert response.json()["registry_entry_id"] == "1"
    assert isinstance(
        RecommendResult.from_wire(response.content), Recommendation
    )  # pasa la capa estructural de U0


async def test_us111_rt3_an_explainer_of_another_version_is_version_mismatch_and_the_metric_rises(
    world: ScoringWorld,
) -> None:
    world.explain.error = (409, "conflict_state", "version_mismatch")
    before = metric("vectra_scoring_failclosed_total", cause="version_mismatch")
    result = await world.recommend(scoring_request())
    assert (
        isinstance(result, FailClosed)
        and result.cause is FailClosedCause.VERSION_MISMATCH
        and result.retryable
    )
    assert metric("vectra_scoring_failclosed_total", cause="version_mismatch") == before + 1
    assert world.registry.entries(EntryType.RECOMMENDATION) == []


async def test_a_prediction_of_another_version_than_the_explanation_is_version_mismatch(
    world: ScoringWorld,
) -> None:
    world.kserve.predict_version = OTHER_MODEL
    result = await world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.VERSION_MISMATCH


async def test_a_requested_version_different_from_serving_config_is_version_mismatch_without_calls(
    world: ScoringWorld,
) -> None:
    result = await world.recommend(scoring_request(model_version_id=OTHER_MODEL))
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.VERSION_MISMATCH
    assert world.kserve.recorder.calls == [] and world.explain.calls == []


async def test_a_frozen_model_and_a_different_requested_version_is_model_frozen_without_calls() -> None:
    gov = GovernanceDouble(serving_config(state="congelado"))
    world = scoring_world(gov=gov)
    result = await world.recommend(scoring_request(model_version_id=OTHER_MODEL))
    assert (
        isinstance(result, FailClosed)
        and result.cause is FailClosedCause.MODEL_FROZEN
        and not result.retryable
    )
    assert result.status == "modelo_congelado"
    assert world.kserve.recorder.calls == [] and world.explain.calls == []
    await world.aclose()


async def test_two_requests_with_the_same_attempt_use_different_keys_not_derived_from_the_case(
    world: ScoringWorld,
) -> None:
    case_id = uuid4()
    for _ in range(2):
        assert isinstance(await world.recommend(scoring_request(case_id=case_id, attempt=1)), Recommendation)
    keys = world.registry.keys(EntryType.RECOMMENDATION)
    assert len(keys) == 2 and len(set(keys)) == 2
    for key in keys:
        assert UUID(key).version == 4  # un UUID v4, no un uuid5 de `case_id` ni de `attempt`


async def test_the_append_retry_reuses_the_key_and_the_fail_closed_uses_another(world: ScoringWorld) -> None:
    world.explain.error = (503, "dependency_unavailable", None)
    result = await world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.EXPLAINER_UNAVAILABLE
    assert world.registry.keys(EntryType.RECOMMENDATION) == []
    other = scoring_world()
    other.registry.faults.fail_next = 1
    assert isinstance(await other.recommend(scoring_request()), Recommendation)
    posts = [call for call in other.registry.calls if call.method == "POST"]
    assert len(posts) == 2
    import json

    assert json.loads(posts[0].body)["idempotency_key"] == json.loads(posts[1].body)["idempotency_key"]
    await other.aclose()


async def test_the_fail_closed_entry_has_cause_and_no_local_cause_or_escalated_at(
    world: ScoringWorld,
) -> None:
    world.explain.error = (504, "deadline_exceeded", None)
    result = await world.recommend(scoring_request(attempt=3))
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.TIMEOUT
    [stored] = world.registry.entries(EntryType.FAIL_CLOSED)
    payload = stored.entry.payload.model_dump(mode="json", exclude_none=True)  # type: ignore[union-attr]
    assert payload == {"cause": "timeout", "retryable": True, "attempt": 3}
    assert str(stored.entry.idempotency_key) not in world.registry.keys(EntryType.RECOMMENDATION)
    assert (
        "local_cause" not in world.registry.calls[0].body.decode()
        and "escalated_at" not in world.registry.calls[0].body.decode()
    )


async def test_the_real_registry_rejects_a_local_cause_payload_with_422_not_403(world: ScoringWorld) -> None:
    """Candidata de U03-T03: `local_cause` junto a `cause` no valida (BR-U0-38), como en el registro real."""
    bad = (
        '{"entry_type":"fail_closed","actor":{"kind":"service","id":"scoring-service"},"occurred_at":"2026-11-10T12:00:00Z",'
        '"correlation_id":"'
        + "0" * 32
        + '","idempotency_key":"'
        + str(uuid4())
        + '","payload":{"cause":"timeout",'
        '"local_cause":"scoring_unreachable","retryable":true,"attempt":1}}'
    )
    import httpx

    from doubles.transports import AsgiTransport

    async with httpx.AsyncClient(
        transport=AsgiTransport(world.registry.app), base_url="http://registry"
    ) as client:
        assert (await client.post("/v1/entries", content=bad)).status_code == 422


async def test_the_recommendation_payload_copies_received_at_channel_attempt_and_first_evaluation(
    world: ScoringWorld,
) -> None:
    request = scoring_request(attempt=2, first_evaluation=False, channel="app")
    assert isinstance(await world.recommend(request), Recommendation)
    [stored] = world.registry.entries(EntryType.RECOMMENDATION)
    payload = stored.entry.payload.model_dump(mode="json")  # type: ignore[union-attr]
    assert payload["received_at"] == "2026-11-10T11:59:59Z"
    assert payload["channel"] == "app" and payload["attempt"] == 2 and payload["first_evaluation"] is False
    assert payload["monitoring_labels"] == request.monitoring_labels.model_dump(mode="json")


async def test_the_fail_closed_entry_does_not_carry_received_at_channel_or_first_evaluation(
    world: ScoringWorld,
) -> None:
    world.explain.error = (503, "dependency_unavailable", None)
    await world.recommend(scoring_request(attempt=2, first_evaluation=False))
    body = world.registry.calls[-1].body.decode()
    for name in ("received_at", "channel", "first_evaluation"):
        assert name not in body


async def test_us113_a_registry_without_replica_is_registry_unavailable_and_nothing_is_delivered(
    world: ScoringWorld,
) -> None:
    world.registry.faults.status = 503
    result = await world.recommend(scoring_request())
    assert (
        isinstance(result, FailClosed)
        and result.cause is FailClosedCause.REGISTRY_UNAVAILABLE
        and result.retryable
    )
    posts = [call for call in world.registry.calls if call.method == "POST"]
    assert len(posts) == 3  # dos intentos de la recommendation y el fail_closed best effort


async def test_a_registry_failing_once_is_two_calls_with_the_same_key_and_one_entry(
    world: ScoringWorld,
) -> None:
    world.registry.faults.fail_next = 1
    result = await world.recommend(scoring_request())
    assert isinstance(result, Recommendation)
    assert len(world.registry.entries(EntryType.RECOMMENDATION)) == 1
    assert metric("vectra_registry_append_attempts_total", attempt="2", result="ok") >= 1


async def test_a_registry_that_commits_and_then_fails_is_recovered_by_the_retry_with_the_original_ack(
    world: ScoringWorld,
) -> None:
    world.registry.commit_then_fail = 1
    result = await world.recommend(scoring_request())
    assert isinstance(result, Recommendation) and len(world.registry.entries(EntryType.RECOMMENDATION)) == 1
    assert result.registry_entry_id == "1"


async def test_a_registry_that_confirms_at_2_6_s_in_both_attempts_is_fail_closed_the_entry_exists_and_abandoned_is_1(
    world: ScoringWorld,
) -> None:
    world.registry.faults.delay = 2.6
    abandoned = metric("vectra_registry_append_abandoned_total")
    started = time.perf_counter()
    result = await world.recommend(scoring_request())
    elapsed = time.perf_counter() - started
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.REGISTRY_UNAVAILABLE
    assert len(world.registry.entries(EntryType.RECOMMENDATION)) == 1  # el reintento reutilizo la llave
    assert metric("vectra_registry_append_abandoned_total") == abandoned + 1
    assert 5.0 < elapsed < 6.2, elapsed  # 2 x 2,5 s + el fail_closed de 250 ms


@pytest.mark.parametrize("status", [400, 403, 422, 500])
async def test_a_4xx_registry_answer_is_one_attempt_only(world: ScoringWorld, status: int) -> None:
    world.registry.reject_status = status
    result = await world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.REGISTRY_UNAVAILABLE
    posts = [call for call in world.registry.calls if call.method == "POST"]
    assert len(posts) == 2  # un solo intento de la recommendation + el fail_closed


async def test_an_idempotency_conflict_is_registry_unavailable_and_is_logged(world: ScoringWorld) -> None:
    import io
    import json

    from vectra_common import logging as vlog

    stream = io.StringIO()
    vlog.configure("scoring-service", stream)
    keys = iter([UUID(int=7)] * 2 + [uuid4(), uuid4()])
    world.deps.orchestrator._uuid = lambda: next(keys)  # noqa: SLF001
    assert isinstance(await world.recommend(scoring_request(case_id=uuid4())), Recommendation)
    result = await world.recommend(scoring_request(case_id=uuid4()))  # misma llave, otro contenido
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.REGISTRY_UNAVAILABLE
    events = [
        json.loads(line).get("event") for line in stream.getvalue().splitlines() if line.startswith("{")
    ]
    assert "registry.idempotency_conflict" in events
    posts = [call for call in world.registry.calls if call.method == "POST"]
    assert len(posts) == 3  # 1 + 1 (409, sin reintento) + el fail_closed


async def test_a_deadline_exhausted_stage_is_counted(world: ScoringWorld) -> None:
    world.kserve.predict_faults.delay = 2.0
    before = metric("vectra_deadline_exhausted_total", stage="predict")
    started = time.perf_counter()
    result = await world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.SERVING_CONFIG_UNAVAILABLE
    assert time.perf_counter() - started < 0.7  # el predictor corta a 300 ms
    assert metric("vectra_deadline_exhausted_total", stage="predict") == before + 1


@pytest.mark.parametrize(
    ("error", "cause"),
    [
        ((504, "deadline_exceeded", None), FailClosedCause.TIMEOUT),
        ((503, "dependency_unavailable", None), FailClosedCause.EXPLAINER_UNAVAILABLE),
        ((500, "internal_error", None), FailClosedCause.EXPLAINER_ERROR),
        ((409, "conflict_state", "version_mismatch"), FailClosedCause.VERSION_MISMATCH),
        (
            (422, "unprocessable_explanation", "feature_dictionary_incomplete"),
            FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE,
        ),
        ((422, "unprocessable_explanation", "factuality_failed"), FailClosedCause.FACTUALITY_FAILED),
    ],
)
async def test_every_explainer_error_is_its_own_fail_closed_cause_and_is_retryable(
    world: ScoringWorld, error: tuple[int, str, str | None], cause: FailClosedCause
) -> None:
    """La tabla de domain-entities §5 de punta a punta (US-105: factor invertido -> `factuality_failed` -> `FailClosed`)."""
    world.explain.error = error
    result = await world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is cause and result.retryable
    assert result.status == "en_sincronizacion"
    assert world.registry.entries(EntryType.RECOMMENDATION) == []
    [stored] = world.registry.entries(EntryType.FAIL_CLOSED)
    assert stored.entry.payload.cause is cause  # type: ignore[union-attr]
