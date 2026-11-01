"""Generadores de dominio compartidos (NFR-U0-44)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from hypothesis import strategies as st

from vectra_contracts.catalog import ExplainerError, Role, Scope, ServingState
from vectra_contracts.dane import MUNICIPALITY_DEPARTMENT
from vectra_contracts.models.application import ApplicationIn
from vectra_contracts.models.explanation import Explanation
from vectra_contracts.models.features import (
    CategoryFeature,
    DecimalFeature,
    FeatureContribution,
    FeatureDictionary,
    FeatureDictionaryEntry,
    FeatureVector,
    IntFeature,
    MonitoringLabels,
)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
EVAL_DAY = date(2026, 10, 31)
SHA = "a" * 64
_NAMES = st.sampled_from(["Ana María Gómez", "Jorge Pérez", "Luz Dary Rincón", "Sofía Ñáñez", "Iván Córdoba"])
municipalities = st.sampled_from(sorted(MUNICIPALITY_DEPARTMENT))
uuids = st.uuids(version=4)
decimal4 = st.integers(min_value=0, max_value=10000).map(lambda n: f"{Decimal(n) / 10000:.4f}")


def _application(**over: Any) -> dict[str, Any]:
    base = {
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
    }
    return {**base, **over}


application_dict = _application


@st.composite
def application_dicts(draw: st.DrawFn) -> dict[str, Any]:
    """Solicitud colombiana realista y valida."""
    municipality = draw(municipalities)
    value = draw(st.integers(50_000_000, 10**10))
    return _application(
        full_name=draw(_NAMES),
        document_number=draw(st.integers(10_000, 9_999_999_999).map(str)),
        birth_date=(EVAL_DAY - timedelta(days=draw(st.integers(19 * 366, 90 * 365)))).isoformat(),
        department_code=MUNICIPALITY_DEPARTMENT[municipality],
        municipality_code=municipality,
        monthly_income=draw(st.integers(1_000_000, 200_000_000)),
        other_income=draw(st.integers(0, 10_000_000)),
        employment_type=draw(st.sampled_from(["asalariado", "independiente", "pensionado"])),
        employment_months=draw(st.integers(0, 720)),
        monthly_obligations=draw(st.integers(0, 10_000_000)),
        max_days_past_due_12m=draw(st.integers(0, 365)),
        property_value=value,
        requested_amount=draw(st.integers(1_000_000, value)),
        term_months=draw(st.integers(12, 360)),
        proposed_rate_ea=f"{draw(st.integers(1, 9999)) / 10000:.4f}",
        sex=draw(st.sampled_from(["F", "M", "no_informado"])),
        socioeconomic_stratum=draw(st.sampled_from(["1", "2", "3", "4", "5", "6", "no_informado"])),
    )


def application_from(data: dict[str, Any]) -> ApplicationIn:
    import json

    return ApplicationIn.model_validate_json(json.dumps(data))


feature_values = st.one_of(
    st.builds(DecimalFeature, value=st.decimals(-1000, 1000, places=4).map(str)),
    st.builds(IntFeature, value=st.integers(-(10**9), 10**9)),
    st.builds(CategoryFeature, value=st.text("abcdefghij_", max_size=20)),
)
feature_vectors = st.builds(
    FeatureVector,
    features=st.dictionaries(st.sampled_from(["installment_to_income", "loan_to_value", "age_years", "zona"]), feature_values),
)
monitoring_labels = st.builds(
    MonitoringLabels,
    sexo=st.sampled_from(["F", "M", "no_informado"]),
    rango_edad=st.sampled_from(["18-25", "26-35", "36-45", "46-55", "56-65", "66+"]),
    region=st.sampled_from(["andina", "caribe", "pacifica", "orinoquia", "amazonia", "insular"]),
    estrato=st.sampled_from(["1", "2", "3", "4", "5", "6", "no_informado"]),
    banda_capacidad_pago=st.sampled_from(["lt_20", "20_30", "gt_30"]),
)
serving_states = st.sampled_from(list(ServingState))
explainer_errors = st.sampled_from(list(ExplainerError))
scope_sets = st.frozensets(st.sampled_from(list(Scope)))
role_sets = st.frozensets(st.sampled_from(list(Role)))


def explanation(version: str = "mv-1", feature_ids: tuple[str, ...] = ("installment_to_income",)) -> Explanation:
    return Explanation(
        model_version_id=version,
        method="shap",
        shap_vector=[
            FeatureContribution(feature_id=f, value=DecimalFeature(value="0.3"), contribution="0.12") for f in feature_ids
        ],
        base_value="0.05",
        narrative="La relación cuota/ingreso aumenta el riesgo.",
        narrative_generator="template:v1",
        feature_dictionary_version="d1",
        posthoc_notice="Aproximación posterior.",
        factuality_check="passed",
    )


def dictionary(version: str = "mv-1", feature_ids: tuple[str, ...] = ("installment_to_income",)) -> FeatureDictionary:
    return FeatureDictionary(
        dictionary_version="d1",
        model_version_id=version,
        entries=[
            FeatureDictionaryEntry(
                feature_id=f,
                label_es=f,
                increases_risk_phrase_es="alto aumenta",
                decreases_risk_phrase_es="bajo reduce",
                applicant_safe=True,
            )
            for f in feature_ids
        ],
    )


CASE = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
