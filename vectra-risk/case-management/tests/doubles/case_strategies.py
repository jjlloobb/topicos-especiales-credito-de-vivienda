"""Generadores de U8 (BLM §4). Patron copiado de `contracts/tests/strategies/domain.py` (U0, NFR-U0-44): ninguna unidad importa las
pruebas de U0 por ruta. Cambios: `recommendation_from_wire` construye una `Recommendation` por la unica via publica (`from_wire`),
y las solicitudes se separan en identificacion y `cases.application` (sin el grupo de identificacion, con `sex` y estrato)."""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from hypothesis import strategies as st

from vectra_contracts.catalog import CaseState, Outcome
from vectra_contracts.dane import MUNICIPALITY_DEPARTMENT
from vectra_contracts.models.application import ApplicationIn, CaseIdentifierGroup
from vectra_contracts.outcome import Recommendation, RecommendResult

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
EVAL_DAY = date(2026, 10, 31)
SHA = "a" * 64
SHAP_IDS = ("installment_to_income", "loan_to_value", "age_years")
CASE = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
IDENTIFICATION = tuple(CaseIdentifierGroup.model_fields)
_NAMES = st.sampled_from(["Ana María Gómez", "Jorge Pérez", "Luz Dary Rincón", "Sofía Ñáñez", "Iván Córdoba"])
# Texto libre adversarial: marcado, saltos de linea, comillas y Unicode (BR-U8-01); es imprimible, como exige BR-U0-29.
free_texts = st.one_of(
    st.none(),
    st.sampled_from(
        ["<script>alert(1)</script>", "'; DROP TABLE cases; --", "línea 1\nlínea 2\t¿ñ?", "😀 " * 5]
    ),
    st.text(
        st.characters(codec="utf-8", categories=("L", "N", "P", "S"), include_characters=" "), max_size=200
    ),
)
municipalities = st.sampled_from(sorted(MUNICIPALITY_DEPARTMENT))


@st.composite
def application_dicts(draw: st.DrawFn) -> dict[str, Any]:
    """Solicitud colombiana valida (`ApplicationIn` en JSON), con PII y texto libre."""
    municipality = draw(municipalities)
    value = draw(st.integers(50_000_000, 10**10))
    doc = draw(st.integers(10_000, 9_999_999_999).map(str))
    data: dict[str, Any] = {
        "full_name": draw(_NAMES),
        "document_type": "CC",
        "document_number": doc,
        "birth_date": (EVAL_DAY - timedelta(days=draw(st.integers(19 * 366, 90 * 365)))).isoformat(),
        "phone": "3001234567",
        "email": "ana.gomez@example.com",
        "address": "Cra 7 # 45-10",
        "department_code": MUNICIPALITY_DEPARTMENT[municipality],
        "municipality_code": municipality,
        "monthly_income": draw(st.integers(1_000_000, 200_000_000)),
        "other_income": draw(st.integers(0, 10_000_000)),
        "employment_type": draw(st.sampled_from(["asalariado", "independiente", "pensionado"])),
        "employment_months": draw(st.integers(0, 720)),
        "monthly_obligations": draw(st.integers(0, 10_000_000)),
        "max_days_past_due_12m": draw(st.integers(0, 365)),
        "property_value": value,
        "requested_amount": draw(st.integers(1_000_000, value)),
        "term_months": draw(st.integers(12, 360)),
        "proposed_rate_ea": f"{draw(st.integers(1, 9999)) / 10000:.4f}",
        "property_condition": draw(st.sampled_from(["nueva", "usada"])),
        "channel": "web",
        "sex": draw(st.sampled_from(["F", "M", "no_informado"])),
        "socioeconomic_stratum": draw(st.sampled_from(["1", "2", "3", "4", "5", "6", "no_informado"])),
    }
    text = draw(free_texts)
    if text is not None:
        data["free_text"] = text
    return data


def application_from(data: dict[str, Any]) -> ApplicationIn:
    return ApplicationIn.model_validate_json(json.dumps(data))


def split_application(data: dict[str, Any]) -> tuple[CaseIdentifierGroup, dict[str, Any]]:
    """(identificadores, `cases.application`): esta ultima es `ApplicationIn` sin el grupo de identificacion y CON `sex` y estrato."""
    app = application_from(data)
    identifiers = CaseIdentifierGroup.model_validate_json(app.model_dump_json(include=set(IDENTIFICATION)))
    rest = json.loads(app.model_dump_json(exclude=set(IDENTIFICATION)))
    assert isinstance(rest, dict)
    return identifiers, rest


def recommendation_from_wire(
    outcome: Outcome = Outcome.FAVORABLE, feature_ids: tuple[str, ...] = SHAP_IDS, case_id: UUID = CASE
) -> Recommendation:
    shap = [
        {"feature_id": f, "value": {"type": "decimal", "value": "0.3"}, "contribution": "0.12"}
        for f in feature_ids
    ]
    body = {
        "kind": "recommendation",
        "case_id": str(case_id),
        "score": "0.4200",
        "confidence": "0.9000",
        "outcome": outcome.value,
        "reasons": [],
        "model_version_id": "mv-1",
        "policy_version_id": "p1",
        "explanation": {
            "model_version_id": "mv-1",
            "method": "shap",
            "shap_vector": shap,
            "base_value": "0.05",
            "narrative": "La relación cuota/ingreso aumenta el riesgo.",
            "narrative_generator": "template:v1",
            "feature_dictionary_version": "d1",
            "posthoc_notice": "Aproximación posterior.",
            "factuality_check": "passed",
        },
        "registry_entry_id": "7",
        "evaluated_at": NOW.isoformat(),
        "feature_vector_hash": SHA,
    }
    rec = RecommendResult.from_wire(json.dumps(body))
    assert isinstance(rec, Recommendation)
    return rec


outcomes = st.sampled_from(list(Outcome))
states = st.sampled_from(list(CaseState))
