"""PBT-U7-06 de `applicant` (BR-U7-14; US-110): sin campos prohibidos ni numeros; solo `applicant_safe` con SHAP > 0, a lo sumo 3."""

import re
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from explainability.applicant import generate
from hypothesis import given
from u7_cases import DICTIONARY, contribution
from u7_strategies import cases
from vectra_contracts.models.api import ApplicantSummary
from vectra_contracts.models.features import FeatureContribution, FeatureDictionary

CASE_ID = UUID("12345678-1234-5678-1234-567812345678")
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
FORBIDDEN_FIELDS = {
    "shap_vector",
    "contribution",
    "model_version_id",
    "score",
    "confidence",
    "policy_version_id",
    "feature_vector",
}
UNIT = Path(__file__).resolve().parents[2]


@given(cases())
def test_pbt_u7_06_summary_has_only_safe_positive_factors_and_no_numbers(
    case: tuple[FeatureDictionary, list[FeatureContribution], str],
) -> None:
    dictionary, vector, model = case
    summary = generate(CASE_ID, vector, dictionary, NOW)
    assert isinstance(summary, ApplicantSummary)
    assert summary.case_id == CASE_ID and summary.generated_at == NOW

    safe_labels = {e.feature_id: e.label_es for e in dictionary.entries if e.applicant_safe}
    candidates = sorted(
        (item for item in vector if item.feature_id in safe_labels and Decimal(item.contribution) > 0),
        key=lambda item: (-Decimal(item.contribution), item.feature_id),
    )
    assert len(summary.factors) <= 3
    assert len(summary.factors) == min(3, len(candidates))
    assert [f.label_es for f in summary.factors] == [safe_labels[item.feature_id] for item in candidates[:3]]
    assert all(f.direction == "aumenta" for f in summary.factors)
    unsafe_or_not_positive = {
        e.label_es
        for e in dictionary.entries
        if e.label_es not in [safe_labels[i.feature_id] for i in candidates]
    }
    assert not unsafe_or_not_positive & {f.label_es for f in summary.factors}

    # Ni campos prohibidos ni numeros en nada de lo que sale.
    dumped = summary.model_dump(mode="json")
    assert set(dumped) == {"case_id", "factors", "posthoc_notice", "generated_at"}
    assert not FORBIDDEN_FIELDS & set(dumped)
    assert all(set(f) == {"label_es", "direction"} for f in dumped["factors"])
    assert not re.search(r"\d", summary.posthoc_notice)
    assert not any(re.search(r"\d", f.label_es + f.direction) for f in summary.factors)
    flat = summary.posthoc_notice + "".join(f.label_es for f in summary.factors)
    for item in vector:
        assert item.contribution not in flat
    assert model not in flat


def test_example_a_rejection_shows_up_to_three_safe_factors_without_forbidden_fields() -> None:
    from u7_cases import entry

    dictionary = FeatureDictionary(
        dictionary_version="d-1",
        model_version_id="mv-fijo",
        entries=[
            entry("a", "Mora reciente", "sube", "baja"),
            entry("b", "Relación cuota-ingreso", "sube", "baja"),
            entry("c", "Historial de ahorro", "sube", "baja"),
            entry("d", "Antigüedad laboral", "sube", "baja"),
            entry("e", "Zona del inmueble", "sube", "baja").model_copy(update={"applicant_safe": False}),
            entry("f", "Ocupación", "sube", "baja"),
        ],
    )
    vector = [
        contribution("e", "0.90"),  # el mayor, pero no es seguro para el solicitante
        contribution("a", "0.40"),
        contribution("b", "0.30"),
        contribution("c", "0.20"),
        contribution("d", "0.10"),  # cuarto seguro: queda fuera
        contribution("f", "-0.50"),  # reduce el riesgo: no entra
    ]
    summary = generate(CASE_ID, vector, dictionary, NOW)
    assert [f.label_es for f in summary.factors] == [
        "Mora reciente",
        "Relación cuota-ingreso",
        "Historial de ahorro",
    ]
    text = summary.model_dump_json()
    for forbidden in (
        "0.40",
        "mv-fijo",
        "d-1",
        "Zona del inmueble",
        "Ocupación",
        "shap",
        "score",
        "confidence",
    ):
        assert forbidden not in text
    assert generate(CASE_ID, vector, dictionary, NOW) == summary


def test_example_without_safe_positive_factors_still_returns_the_notice() -> None:
    summary = generate(CASE_ID, [contribution("dti", "-0.3")], DICTIONARY, NOW)
    assert summary.factors == []
    assert summary.posthoc_notice.startswith("Esta es una aproximación")


def test_the_applicant_template_has_no_forbidden_phrases() -> None:
    template = UNIT / "explainability" / "templates" / "applicant_v1.txt"
    script = UNIT.parent / "contracts" / "tools" / "forbidden_phrases.py"
    done = subprocess.run(
        [sys.executable, str(script), str(template)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stdout
