"""Ejemplos de borde de `object_rules` (plan de pruebas de U10-T01): un caso limite por regla."""

from vectra_contracts.catalog import CaseState, FinalOutcome

from console_bff import object_rules as o
from console_bff.object_rules import ObjectVerdict

ACCEPT, CONFLICT = ObjectVerdict.ACCEPT, ObjectVerdict.CONFLICT


def test_record_decision_only_when_listo() -> None:
    assert o.record_decision(CaseState.LISTO) is ACCEPT
    assert (
        o.record_decision(CaseState.DECIDIDO) is CONFLICT
    )  # `decision_already_recorded` lo explica el destino


def test_explanation_view_listo_or_decidido() -> None:
    assert o.record_explanation_view(CaseState.DECIDIDO) is ACCEPT
    assert o.record_explanation_view(CaseState.EN_EVALUACION) is CONFLICT


def test_applicant_summary_needs_decidido_and_desfavorable() -> None:
    assert o.create_applicant_summary(CaseState.DECIDIDO, FinalOutcome.DESFAVORABLE) is ACCEPT
    assert o.create_applicant_summary(CaseState.DECIDIDO, FinalOutcome.FAVORABLE) is CONFLICT
    assert o.create_applicant_summary(CaseState.DECIDIDO, None) is CONFLICT
    assert o.create_applicant_summary(CaseState.LISTO, FinalOutcome.DESFAVORABLE) is CONFLICT


def test_retry_case_rejects_anonymized() -> None:
    assert o.retry_case(CaseState.NO_DISPONIBLE, False) is ACCEPT
    assert o.retry_case(CaseState.NO_DISPONIBLE, True) is CONFLICT


def test_start_validation_retry_after_failure() -> None:
    assert o.start_validation("registrado") is ACCEPT
    assert o.start_validation("validacion_fallida") is ACCEPT
    assert o.start_validation("en_validacion") is CONFLICT


def test_retire_model_includes_validacion_fallida() -> None:
    assert o.retire_model("validacion_fallida") is ACCEPT
    assert o.retire_model("inactivo") is ACCEPT
    assert o.retire_model("rechazado") is ACCEPT
    assert o.retire_model("activo") is CONFLICT


def test_approve_policy_rejection_needs_justification() -> None:
    assert o.approve_policy("propuesta", "aprobada", None) is ACCEPT
    assert o.approve_policy("propuesta", "rechazada", "umbral laxo") is ACCEPT
    assert o.approve_policy("propuesta", "rechazada", None) is CONFLICT
    assert o.approve_policy("propuesta", "rechazada", "  ") is CONFLICT
    assert o.approve_policy("activa", "aprobada", None) is CONFLICT


def test_data_source_decision_needs_report() -> None:
    assert o.decide_data_source("en_evaluacion", True) is ACCEPT
    assert o.decide_data_source("en_evaluacion", False) is CONFLICT
    assert o.decide_data_source("propuesta", True) is CONFLICT


def test_source_comparison_needs_matching_candidate_and_active_version() -> None:
    assert o.start_source_comparison("en_evaluacion", "ds-1", "ds-1", True) is ACCEPT
    assert o.start_source_comparison("en_evaluacion", "ds-1", "ds-2", True) is CONFLICT
    assert o.start_source_comparison("en_evaluacion", "ds-1", None, True) is CONFLICT
    assert o.start_source_comparison("en_evaluacion", "ds-1", "ds-1", False) is CONFLICT
    assert o.start_source_comparison("propuesta", "ds-1", "ds-1", True) is CONFLICT
