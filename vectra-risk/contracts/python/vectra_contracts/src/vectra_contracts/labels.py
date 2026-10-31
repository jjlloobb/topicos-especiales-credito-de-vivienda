"""Derivacion de etiquetas y features (BR-U0-40..43; business-logic-model §2.3)."""

from datetime import date
from decimal import Decimal
from typing import Final, cast, get_args

from vectra_contracts.catalog import FORBIDDEN_REGISTRY_KEYS
from vectra_contracts.dane import DEPARTMENT_REGION
from vectra_contracts.finance import installment, installment_to_income, loan_to_value, to_decimal4_str
from vectra_contracts.models.application import ApplicationIn
from vectra_contracts.models.features import (
    Band,
    CategoryFeature,
    DecimalFeature,
    FeatureSpec,
    FeatureVector,
    IntFeature,
    MonitoringLabels,
    RangoEdad,
    Region,
)
from vectra_contracts.validation import age_at

_AGE_LIMITS: Final = ((25, "18-25"), (35, "26-35"), (45, "36-45"), (55, "46-55"), (65, "56-65"))
LOW_BAND = Decimal("0.2000")
HIGH_BAND = Decimal("0.3000")
_REGIONS: Final = frozenset(get_args(Region))
_LOOKUP_SEPARATOR: Final = "|"


def age_range(age: int) -> RangoEdad:
    """BR-U0-40: total para 18-120; rangos cerrados."""
    if not 18 <= age <= 120:
        raise ValueError("age_out_of_range")
    for limit, label in _AGE_LIMITS:
        if age <= limit:
            return cast(RangoEdad, label)
    return "66+"


def region_of(department_code: str) -> Region:
    """BR-U0-41."""
    region = DEPARTMENT_REGION[department_code]
    if region not in _REGIONS:
        raise ValueError("region_unknown")
    return cast(Region, region)


def payment_band(ratio: Decimal) -> Band:
    """BR-U0-42."""
    if ratio < LOW_BAND:
        return "lt_20"
    return "gt_30" if ratio > HIGH_BAND else "20_30"


def _ratio(application: ApplicationIn) -> tuple[int, Decimal]:
    cuota = installment(
        application.requested_amount, Decimal(application.proposed_rate_ea), application.term_months
    )
    return cuota, installment_to_income(cuota, application.monthly_income, application.other_income)


def derive_monitoring_labels(application: ApplicationIn, evaluated_on: date) -> MonitoringLabels:
    """BR-U0-43: sexo y estrato se copian; nunca se infieren."""
    _, ratio = _ratio(application)
    return MonitoringLabels(
        sexo=application.sex,
        rango_edad=age_range(age_at(application.birth_date, evaluated_on)),
        region=region_of(application.department_code),
        estrato=application.socioeconomic_stratum,
        banda_capacidad_pago=payment_band(ratio),
    )


def derive(application: ApplicationIn, evaluated_on: date, feature_spec: FeatureSpec) -> FeatureVector:
    """Features estandar mas las del `feature_spec` de la version.

    Una busqueda puede leer un campo de identificacion, pero ese campo nunca es clave del
    vector (BR-U0-34). `free_text` nunca se usa.
    """
    cuota, ratio = _ratio(application)
    features: dict[str, DecimalFeature | IntFeature | CategoryFeature] = {
        "installment_cop": IntFeature(value=cuota),
        "installment_to_income": DecimalFeature(value=to_decimal4_str(ratio)),
        "loan_to_value": DecimalFeature(
            value=to_decimal4_str(loan_to_value(application.requested_amount, application.property_value))
        ),
        "age_years": IntFeature(value=age_at(application.birth_date, evaluated_on)),
    }
    for item in feature_spec.features:
        if item.feature_id in FORBIDDEN_REGISTRY_KEYS or "free_text" in item.source_fields:
            raise ValueError("forbidden_feature_source")
        if item.origin == "derived":
            if item.feature_id not in features:
                raise ValueError("derived_feature_unknown")
        elif item.origin == "field":
            features[item.feature_id] = _field_feature(application, item.source_fields[0])
        else:
            key = _LOOKUP_SEPARATOR.join(str(getattr(application, f) or "") for f in item.source_fields)
            value = (item.table or {}).get(key, item.default)
            if value is None:
                raise ValueError("lookup_without_value")
            features[item.feature_id] = CategoryFeature(value=value)
    return FeatureVector(features=features)


def _field_feature(application: ApplicationIn, field: str) -> DecimalFeature | IntFeature | CategoryFeature:
    if field in FORBIDDEN_REGISTRY_KEYS:
        raise ValueError("forbidden_feature_source")
    value = getattr(application, field)
    return IntFeature(value=value) if isinstance(value, int) else CategoryFeature(value=str(value))
