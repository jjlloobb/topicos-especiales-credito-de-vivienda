"""`derive` con `feature_spec` (business-logic-model §2.3; U5 FD)."""

from datetime import date

import pytest
from strategies.domain import application_dict, application_from

from vectra_contracts.labels import derive
from vectra_contracts.models.features import FeatureSpec, FeatureSpecItem

DAY = date(2026, 10, 31)


def spec(*items):
    return FeatureSpec(model_version_id="mv-1", features=list(items))


def test_lookup_applied_and_identifier_source_never_a_key():
    item = FeatureSpecItem(feature_id="zona_vivienda", origin="lookup", source_fields=["municipality_code"], table={"11001": "zona_a"}, default="otra")
    vector = derive(application_from(application_dict()), DAY, spec(item))
    assert vector.features["zona_vivienda"].value == "zona_a"
    assert "municipality_code" not in vector.features and "free_text" not in vector.features
    assert {"installment_cop", "installment_to_income", "loan_to_value", "age_years"} <= set(vector.features)


def test_lookup_default_and_composite_key():
    item = FeatureSpecItem(feature_id="canal_detalle", origin="lookup", source_fields=["channel", "broker_id"], table={"web|": "directo"}, default="otro")
    assert derive(application_from(application_dict()), DAY, spec(item)).features["canal_detalle"].value == "directo"
    assert derive(application_from(application_dict(channel="x")), DAY, spec(item)).features["canal_detalle"].value == "otro"
    miss = FeatureSpecItem(feature_id="c", origin="lookup", source_fields=["channel"], table={})
    with pytest.raises(ValueError, match="lookup_without_value"):
        derive(application_from(application_dict()), DAY, spec(miss))


def test_field_and_derived_origins():
    items = [FeatureSpecItem(feature_id="employment_months", origin="field", source_fields=["employment_months"]), FeatureSpecItem(feature_id="employment_type", origin="field", source_fields=["employment_type"]), FeatureSpecItem(feature_id="loan_to_value", origin="derived")]
    vector = derive(application_from(application_dict()), DAY, spec(*items))
    assert vector.features["employment_months"].value == 48 and vector.features["employment_type"].value == "asalariado"
    with pytest.raises(ValueError, match="derived_feature_unknown"):
        derive(application_from(application_dict()), DAY, spec(FeatureSpecItem(feature_id="x", origin="derived")))


@pytest.mark.parametrize(
    "item",
    [
        FeatureSpecItem(feature_id="full_name", origin="field", source_fields=["full_name"]),
        FeatureSpecItem(feature_id="x", origin="field", source_fields=["email"]),
        FeatureSpecItem(feature_id="x", origin="lookup", source_fields=["free_text"], table={}),
    ],
)
def test_forbidden_sources(item):
    with pytest.raises(ValueError, match="forbidden_feature_source"):
        derive(application_from(application_dict()), DAY, spec(item))
