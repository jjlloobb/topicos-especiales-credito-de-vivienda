"""Paso 7: PBT-U8-04 y ejemplos (BR-U8-13, 13b, 21; US-107)."""

import json
from datetime import timedelta
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from case_strategies import (
    CASE,
    NOW,
    application_dicts,
    recommendation_from_wire,
    split_application,
    states,
)
from vectra_case.views import CaseRow, application_view, case_detail, case_summary, persistent_failure
from vectra_contracts.catalog import CaseState, CreditStatus, Decision, FinalOutcome, Outcome
from vectra_contracts.models.api import CaseDetail, DecisionView
from vectra_contracts.models.application import ApplicationView

RESULT_STATES = {CaseState.LISTO, CaseState.DECIDIDO}
FORBIDDEN_FIELDS = ("score", "outcome", "recommendation", "explanation")
REC = recommendation_from_wire(Outcome.DESFAVORABLE)
DECISION = DecisionView(
    decision=Decision.SIGUE,
    final_outcome=FinalOutcome.DESFAVORABLE,
    used_factors=["ninguno"],
    justification="",
    decided_at=NOW,
    decided_by="ana",
)


def make_row(
    data: dict[str, Any], state: CaseState, *, anonymized: bool, with_rec: bool, **over: Any
) -> CaseRow:
    identifiers, application = split_application(data)
    fields: dict[str, Any] = {
        "case_id": CASE,
        "state": state,
        "channel": "web",
        "created_at": NOW,
        "application": application,
        "attempts": 3,
        "last_cause": "scoring_unreachable",
        "model_frozen_after_recommendation": False,
        "anonymized": anonymized,
        "identifiers": None if anonymized else identifiers,
        "recommendation": REC if with_rec else None,
        "recommendation_entry_id": "7" if with_rec else None,
        "decision": DECISION,
        "credit_status": CreditStatus.APROBADO,
        "no_disponible_since": NOW,
    }
    return CaseRow(**{**fields, **over})


def dump(model: Any) -> str:
    return model.model_dump_json()


@given(data=application_dicts(), state=states, anonymized=st.booleans(), with_rec=st.booleans())
def test_views_never_leak_outside_listo_and_decidido(data, state, anonymized, with_rec):
    row = make_row(data, state, anonymized=anonymized, with_rec=with_rec)
    summary, detail = case_summary(row), case_detail(row)
    identifiers, _ = split_application(data)
    for view in (summary, detail):
        # Ninguna vista del analista contiene sex ni estrato, en ningun nivel.
        raw = json.loads(dump(view))
        assert not {"sex", "socioeconomic_stratum"} & _keys(raw)
        if state not in RESULT_STATES:
            assert view.score is None
            assert view.outcome is None
    if state not in RESULT_STATES:
        assert detail.recommendation is None
        assert detail.recommendation_entry_id is None
        raw = json.loads(dump(detail))
        assert raw["recommendation"] is None  # el campo existe en el modelo, sin valor
        assert not {"explanation", "shap_vector"} & _keys(raw)
        assert raw["score"] is None
        assert raw["outcome"] is None
        assert detail.decision is None
        assert detail.credit_status is None
    if state in RESULT_STATES and with_rec:
        assert summary.outcome is REC.outcome
        assert summary.score == REC.score
        assert detail.recommendation == REC
    # La bandeja: su unica identificacion es `applicant_display`; nunca el documento completo ni otros identificadores.
    summary_json = dump(summary)
    assert set(json.loads(summary_json)) == {
        "case_id",
        "state",
        "channel",
        "created_at",
        "outcome",
        "score",
        "applicant_display",
    }
    if not anonymized and len(identifiers.document_number) > 4:
        assert identifiers.document_number not in summary_json
    for secret in (identifiers.email, identifiers.phone, identifiers.address):
        assert secret not in summary_json
    # `identifiers` solo si el caso no esta anonimizado; y la marca es coherente.
    assert (detail.identifiers is not None) == (not anonymized)
    assert detail.anonymized is anonymized
    assert (summary.applicant_display == "") == anonymized


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


@given(data=application_dicts(), state=states)
def test_attempts_and_last_cause_follow_the_state(data, state):
    detail = case_detail(make_row(data, state, anonymized=False, with_rec=True))
    assert detail.attempts == 3
    shows = state in {CaseState.EN_SINCRONIZACION, CaseState.NO_DISPONIBLE}
    assert detail.last_cause == ("scoring_unreachable" if shows else None)


@given(data=application_dicts())
def test_application_view_drops_monitoring_fields_and_keeps_the_rest(data):
    _, application = split_application(data)
    assert {"sex", "socioeconomic_stratum"} <= set(application)  # `cases.application` si los guarda
    view = application_view(application)
    assert not {"sex", "socioeconomic_stratum"} & set(view.model_dump())
    assert set(view.model_dump()) == set(ApplicationView.model_fields)


# --- ejemplos (CA-4) ---

BASE = {
    "full_name": "Ana María Gómez",
    "document_type": "CC",
    "document_number": "1020304050",
    "birth_date": "1985-03-14",
    "phone": "3001234567",
    "email": "ana.gomez@example.com",
    "address": "Cra 7 # 45-10",
    "department_code": "11",
    "municipality_code": "11001",
    "monthly_income": 6_000_000,
    "other_income": 0,
    "employment_type": "asalariado",
    "employment_months": 48,
    "monthly_obligations": 500_000,
    "max_days_past_due_12m": 0,
    "property_value": 300_000_000,
    "requested_amount": 200_000_000,
    "term_months": 240,
    "proposed_rate_ea": "0.1250",
    "property_condition": "nueva",
    "channel": "web",
    "sex": "F",
    "socioeconomic_stratum": "3",
}


def test_applicant_display_is_name_and_last_four_digits():
    summary = case_summary(make_row(BASE, CaseState.EN_EVALUACION, anonymized=False, with_rec=False))
    assert summary.applicant_display == "Ana María Gómez 4050"


def test_applicant_display_is_empty_when_anonymized():
    summary = case_summary(make_row(BASE, CaseState.DECIDIDO, anonymized=True, with_rec=True))
    assert summary.applicant_display == ""


def test_applicant_display_is_empty_without_identifiers_even_if_not_anonymized():
    row = make_row(BASE, CaseState.LISTO, anonymized=False, with_rec=True, identifiers=None)
    assert case_summary(row).applicant_display == ""


def test_application_without_sex_nor_stratum_while_passing_it_raw_fails():
    """Rojo de la tarea: pasar `cases.application` tal cual a `CaseDetail` rompe; `views` los quita antes."""
    _, application = split_application(BASE)
    with pytest.raises(ValidationError):
        ApplicationView.model_validate_json(json.dumps(application))
    detail = case_detail(make_row(BASE, CaseState.LISTO, anonymized=False, with_rec=True))
    assert "sex" not in detail.application.model_dump()
    assert "socioeconomic_stratum" not in detail.application.model_dump()


def test_decidido_carries_credit_status_and_decision():
    detail = case_detail(make_row(BASE, CaseState.DECIDIDO, anonymized=False, with_rec=True))
    assert detail.credit_status is CreditStatus.APROBADO
    assert detail.decision == DECISION
    assert detail.recommendation_entry_id == "7"


def test_listo_has_no_credit_status_even_if_the_row_carries_one():
    detail = case_detail(make_row(BASE, CaseState.LISTO, anonymized=False, with_rec=True))
    assert detail.credit_status is None
    assert detail.decision is None


@pytest.mark.parametrize("state", [CaseState.EN_SINCRONIZACION, CaseState.NO_DISPONIBLE])
def test_last_cause_and_attempts_in_failure_states(state):
    detail = case_detail(make_row(BASE, state, anonymized=False, with_rec=False, attempts=6))
    assert (detail.attempts, detail.last_cause) == (6, "scoring_unreachable")


def test_persistent_failure_has_its_since():
    since = NOW + timedelta(hours=1)
    failure = persistent_failure(
        make_row(
            BASE,
            CaseState.NO_DISPONIBLE,
            anonymized=False,
            with_rec=False,
            attempts=6,
            no_disponible_since=since,
        )
    )
    assert (failure.case_id, failure.channel, failure.created_at) == (CASE, "web", NOW)
    assert (failure.attempts, failure.last_cause, failure.since) == (6, "scoring_unreachable", since)


def test_persistent_failure_without_last_cause_is_empty_text():
    row = make_row(BASE, CaseState.NO_DISPONIBLE, anonymized=False, with_rec=False, last_cause=None)
    assert persistent_failure(row).last_cause == ""


@pytest.mark.parametrize(
    ("state", "since"),
    [(CaseState.LISTO, NOW), (CaseState.NO_DISPONIBLE, None)],
)
def test_persistent_failure_requires_no_disponible_and_since(state, since):
    with pytest.raises(ValueError, match="persistent_failure"):
        persistent_failure(make_row(BASE, state, anonymized=False, with_rec=False, no_disponible_since=since))


def test_anonymized_detail_drops_identifiers_even_if_the_row_carries_them():
    identifiers, _ = split_application(BASE)
    row = make_row(BASE, CaseState.DECIDIDO, anonymized=True, with_rec=True, identifiers=identifiers)
    detail = case_detail(row)
    assert isinstance(detail, CaseDetail)
    assert detail.identifiers is None
    assert case_summary(row).applicant_display == ""
