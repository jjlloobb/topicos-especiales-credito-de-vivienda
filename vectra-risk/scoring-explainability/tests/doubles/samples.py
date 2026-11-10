"""Datos de ejemplo de las pruebas de servicios: versiones, vector, diccionario y `ScoringRequest`."""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from vectra_contracts.models.api import ExplainRequest, ScoringRequest
from vectra_contracts.models.features import (
    DecimalFeature,
    FeatureDictionary,
    FeatureDictionaryEntry,
    FeatureVector,
    IntFeature,
    MonitoringLabels,
)
from vectra_contracts.models.governance import NormativeParams, ServingConfig

MODEL = "mv-0000abcd"
OTHER_MODEL = "mv-0000ffff"
ISVC = "isvc-0000abcd"
OTHER_ISVC = "isvc-0000ffff"
POLICY = "pol-000000000001"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
FEATURE_IDS = ("installment_cop", "installment_to_income", "loan_to_value", "age_years")


def vector(extra: dict[str, int] | None = None) -> FeatureVector:
    features: dict[str, DecimalFeature | IntFeature] = {
        "installment_cop": IntFeature(value=1_200_000),
        "installment_to_income": DecimalFeature(value="0.2400"),
        "loan_to_value": DecimalFeature(value="0.7000"),
        "age_years": IntFeature(value=38),
    }
    for name, value in (extra or {}).items():
        features[name] = IntFeature(value=value)
    return FeatureVector(features=features)


def dictionary(
    model_version_id: str = MODEL, version: str = "d-1", ids: tuple[str, ...] = FEATURE_IDS
) -> FeatureDictionary:
    return FeatureDictionary(
        dictionary_version=version,
        model_version_id=model_version_id,
        entries=[
            FeatureDictionaryEntry(
                feature_id=feature_id,
                label_es=f"Etiqueta {feature_id}",
                increases_risk_phrase_es=f"{feature_id} sube el riesgo",
                decreases_risk_phrase_es=f"{feature_id} baja el riesgo",
                applicant_safe=feature_id != "age_years",
            )
            for feature_id in ids
        ],
    )


def normative() -> NormativeParams:
    return NormativeParams(
        vis_max_property_value=150_000_000,
        usury_cap_ea="0.2500",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC).date(),
        source_ref="SFC-2026",
    )


def serving_config(
    model_version_id: str = MODEL,
    state: str = "activo",
    isvc: str = ISVC,
    etag: str = "etag-1",
    with_normative: bool = True,
) -> ServingConfig:
    return ServingConfig(
        model_version_id=model_version_id,
        state=state,  # type: ignore[arg-type]
        policy_version_id=POLICY,
        feature_dictionary_version="d-1",
        effective_from=NOW,
        inference_service=isvc,
        etag=etag,
        normative_current=normative() if with_normative else None,
    )


def scoring_request(
    case_id: UUID | None = None,
    attempt: int = 1,
    model_version_id: str = MODEL,
    features: FeatureVector | None = None,
    first_evaluation: bool = True,
    channel: str = "web",
    property_value: int = 300_000_000,
    proposed_rate_ea: str = "0.1200",
) -> ScoringRequest:
    return ScoringRequest.model_validate_json(
        json.dumps(
            {
                "case_id": str(case_id or uuid4()),
                "features": (features or vector()).model_dump(mode="json"),
                "monitoring_labels": MonitoringLabels(
                    sexo="no_informado",
                    rango_edad="36-45",
                    region="andina",
                    estrato="no_informado",
                    banda_capacidad_pago="20_30",
                ).model_dump(mode="json"),
                "policy_inputs": {
                    "property_value": property_value,
                    "proposed_rate_ea": proposed_rate_ea,
                    "channel": channel,
                },
                "attempt": attempt,
                "model_version_id": model_version_id,
                "received_at": "2026-11-10T11:59:59.000Z",
                "first_evaluation": first_evaluation,
            }
        )
    )


def explain_request(
    case_id: UUID | None = None,
    model_version_id: str = MODEL,
    isvc: str = ISVC,
    features: FeatureVector | None = None,
) -> ExplainRequest:
    return ExplainRequest(
        case_id=case_id or uuid4(),
        model_version_id=model_version_id,
        inference_service=isvc,
        features=features or vector(),
        prediction_score="0.1000",
    )
