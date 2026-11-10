"""Paso 9 (CA-2): `POST /v1/applicant-summaries` con un doble del registro que sigue la proyeccion `explanation` de U3 (BR-U7-13, 14; US-110)."""

import io
import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from doubles.auth import user_headers
from doubles.registry import seed_recommendation
from doubles.samples import MODEL, dictionary
from doubles.worlds import ExplainabilityWorld, explainability_world
from vectra_common import logging as vlog
from vectra_contracts.catalog import EntryType, FailClosedCause
from vectra_contracts.models.api import ApplicantSummary
from vectra_contracts.models.explanation import Explanation
from vectra_contracts.models.features import DecimalFeature, FeatureContribution, IntFeature
from vectra_contracts.models.registry import Actor, FailClosedPayload, RegistryEntryIn

from doubles.samples import NOW

FORBIDDEN_WORDS = (
    "0.3100",
    "shap_vector",
    "model_version_id",
    "score",
    "confidence",
    "feature_vector",
    MODEL,
)


def explanation() -> Explanation:
    """Cuatro factores a favor del riesgo, uno en contra y uno que el solicitante no debe ver (`age_years`, no `applicant_safe`)."""
    values = {
        "installment_to_income": "0.3100",
        "loan_to_value": "0.2000",
        "installment_cop": "0.1000",
        "age_years": "0.9000",  # el mayor, pero no `applicant_safe`
    }
    shap = [
        FeatureContribution(
            feature_id=fid,
            value=IntFeature(value=1)
            if fid in ("age_years", "installment_cop")
            else DecimalFeature(value="0.5000"),
            contribution=c,
        )
        for fid, c in values.items()
    ]
    return Explanation(
        model_version_id=MODEL,
        method="shap",
        shap_vector=shap,
        base_value="0.0800",
        narrative="narrativa del analista",
        narrative_generator="template:v1",
        feature_dictionary_version="d-1",
        posthoc_notice="aviso",
        factuality_check="passed",
    )


@pytest.fixture
async def world() -> AsyncIterator[ExplainabilityWorld]:
    built = explainability_world()
    yield built
    await built.aclose()


def request_body(case_id: UUID, entry_id: str) -> str:
    return json.dumps({"case_id": str(case_id), "recommendation_entry_id": entry_id})


async def summarize(world: ExplainabilityWorld, case_id: UUID, entry_id: str, role: str = "analista"):  # type: ignore[no-untyped-def]
    return await world.post(
        "/v1/applicant-summaries",
        request_body(case_id, entry_id),
        user_headers("explainability-service", role),
    )


async def test_a_valid_summary_has_at_most_three_safe_factors_and_the_legend(
    world: ExplainabilityWorld,
) -> None:
    case_id = uuid4()
    stored = seed_recommendation(world.registry, case_id, explanation())
    response = await summarize(world, case_id, stored.ack.registry_entry_id)
    assert response.status_code == 200, response.text
    summary = ApplicantSummary.model_validate_json(response.content)
    labels = [factor.label_es for factor in summary.factors]
    assert labels == ["Etiqueta installment_to_income", "Etiqueta loan_to_value", "Etiqueta installment_cop"]
    assert all(factor.direction == "aumenta" for factor in summary.factors)
    assert "age_years" not in response.text and summary.posthoc_notice
    assert summary.case_id == case_id
    for word in FORBIDDEN_WORDS:  # ni SHAP ni version ni score
        assert word not in response.text
    query = world.registry.calls[-1].query
    assert (
        f"seq={stored.seq}" in query and f"case_id={case_id}" in query and "projection=explanation" in query
    )


async def test_a_case_without_the_recommendation_is_a_409(world: ExplainabilityWorld) -> None:
    response = await summarize(world, uuid4(), "7")
    assert response.status_code == 409 and response.json()["code"] == "conflict_state"
    assert set(response.json()) <= {"type", "title", "status", "code", "correlation_id", "reason"}


async def test_a_fail_closed_entry_has_no_explanation_and_is_a_409(world: ExplainabilityWorld) -> None:
    case_id = uuid4()
    entry = RegistryEntryIn(
        entry_type=EntryType.FAIL_CLOSED,
        case_id=case_id,
        actor=Actor(kind="service", id="scoring-service"),
        occurred_at=NOW,
        correlation_id="0" * 32,
        idempotency_key=uuid4(),
        payload=FailClosedPayload(cause=FailClosedCause.TIMEOUT, retryable=True, attempt=1),
    )
    stored = world.registry._commit(entry)  # noqa: SLF001
    assert (await summarize(world, case_id, stored.ack.registry_entry_id)).status_code == 409


@pytest.mark.parametrize("defective_registry", [False, True])
async def test_abuse_an_entry_id_of_another_case_is_a_409_without_partial_data(
    world: ExplainabilityWorld, defective_registry: bool
) -> None:
    other_case, mine = uuid4(), uuid4()
    stored = seed_recommendation(world.registry, other_case, explanation())
    world.registry.ignore_case_filter = (
        defective_registry  # el registro de U3 devuelve la pagina vacia; si no, explainability lo comprueba
    )
    response = await summarize(world, mine, stored.ack.registry_entry_id)
    assert response.status_code == 409 and response.json()["code"] == "conflict_state"
    assert "factors" not in response.text and "Etiqueta" not in response.text


@pytest.mark.parametrize("entry_id", ["abc", "-1", "1.5", "", "²"])
async def test_a_malformed_entry_id_is_a_409_without_calling_the_registry(
    world: ExplainabilityWorld, entry_id: str
) -> None:
    assert (await summarize(world, uuid4(), entry_id)).status_code == 409
    assert world.registry.calls == []


async def test_the_log_carries_the_case_id_and_never_the_summary(
    world: ExplainabilityWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    stream = io.StringIO()
    vlog.configure("explainability-service", stream)
    case_id = uuid4()
    stored = seed_recommendation(world.registry, case_id, explanation())
    response = await summarize(world, case_id, stored.ack.registry_entry_id, role="cro")
    assert response.status_code == 200
    lines = [json.loads(line) for line in stream.getvalue().splitlines() if line.startswith("{")]
    generated = [line for line in lines if line.get("event") == "applicant_summary.generated"]
    assert len(generated) == 1
    assert generated[0]["case_id"] == str(case_id)
    assert set(generated[0]) <= {
        "event",
        "case_id",
        "level",
        "timestamp",
        "service",
        "correlation_id",
        "span_id",
    }
    text = json.dumps(generated[0])
    assert "Etiqueta" not in text and "aviso" not in text and "factors" not in text


async def test_the_summary_is_not_stored(world: ExplainabilityWorld) -> None:
    case_id = uuid4()
    stored = seed_recommendation(world.registry, case_id, explanation())
    before = len(world.registry.stored)
    assert (await summarize(world, case_id, stored.ack.registry_entry_id)).status_code == 200
    assert len(world.registry.stored) == before and all(call.method == "GET" for call in world.registry.calls)


async def test_a_registry_down_is_a_503_toward_the_bff(world: ExplainabilityWorld) -> None:
    world.registry.faults.status = 503
    response = await summarize(world, uuid4(), "1")
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
    world.registry.faults.status = 403  # un 4xx del registro es un defecto de configuracion, no un caso ajeno
    assert (await summarize(world, uuid4(), "1")).status_code == 500


async def test_a_dictionary_that_cannot_be_read_is_a_503(world: ExplainabilityWorld) -> None:
    case_id = uuid4()
    stored = seed_recommendation(world.registry, case_id, explanation())
    world.gov.dictionary_faults.status = 503
    assert (await summarize(world, case_id, stored.ack.registry_entry_id)).status_code == 503


async def test_the_registry_client_has_its_own_pool_and_breaker(world: ExplainabilityWorld) -> None:
    names = {client.breaker is not None for client in world.deps.clients}
    assert names == {True} and len({id(client.breaker) for client in world.deps.clients}) == 3


def test_the_fixture_dictionary_covers_the_explanation() -> None:
    assert {e.feature_id for e in dictionary().entries} >= {c.feature_id for c in explanation().shap_vector}
