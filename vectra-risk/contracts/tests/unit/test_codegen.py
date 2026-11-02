"""P-U0-12, NFR-U0-30: las specs salen del registro."""

import yaml

from tools.codegen import role_matrix, spec_for, ts_enums
from vectra_contracts.routes import REGISTRY


def test_registry_spec_has_monitoring_routes():
    spec = spec_for("decision-registry-service", REGISTRY["decision-registry-service"])
    assert spec["paths"]["/v1/monitoring/daily:query"]["post"]["x-vectra-scopes"] == ["registry:read:monitoring"]
    assert spec["paths"]["/v1/monitoring/freezes"]["get"]["x-vectra-scopes"] == ["registry:read:monitoring"]
    assert yaml.safe_dump(spec)


def test_decimal4_is_string_in_spec():
    spec = spec_for("scoring-service", REGISTRY["scoring-service"])
    rate = spec["components"]["schemas"]["PolicyInputs"]["properties"]["proposed_rate_ea"]
    assert rate["type"] == "string" and rate["pattern"].endswith(r"\.\d{4}$")


def test_recommend_result_discriminated():
    spec = spec_for("scoring-service", REGISTRY["scoring-service"])
    schema = spec["components"]["schemas"]["RecommendResult"]
    assert schema["discriminator"]["propertyName"] == "kind"


def test_matrix_and_enums():
    assert "`/api/console/models/{id}/retirement`" in role_matrix()
    assert 'export const PROBLEM_REASONS = ["decision_already_recorded"' in ts_enums()


def test_recommendation_spec_has_enums():
    """Domain-entities 3.3: la spec lleva los enumerados cerrados de `Recommendation`."""
    spec = spec_for("scoring-service", REGISTRY["scoring-service"])
    props = spec["components"]["schemas"]["Recommendation"]["properties"]
    outcome = props["outcome"]
    if "$ref" in outcome:
        outcome = spec["components"]["schemas"][outcome["$ref"].rsplit("/", 1)[1]]
    assert sorted(outcome["enum"]) == ["desfavorable", "favorable", "revision_requerida"]
    assert props["reasons"]["items"] == {"$ref": "#/components/schemas/ReasonCode"}
    assert spec["components"]["schemas"]["ReasonCode"]["enum"]
