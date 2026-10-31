"""Features, etiquetas y diccionario (domain-entities §2 y §4)."""

from typing import Annotated, Any, Literal

from pydantic import Field, field_validator

from vectra_contracts.catalog import IDENTIFICATION_FIELDS
from vectra_contracts.models.application import Sex, Stratum
from vectra_contracts.models.base import DecimalStr, StrictModel

RangoEdad = Literal["18-25", "26-35", "36-45", "46-55", "56-65", "66+"]
Region = Literal["andina", "caribe", "pacifica", "orinoquia", "amazonia", "insular"]
Band = Literal["lt_20", "20_30", "gt_30"]
Attribute = Literal["sexo", "rango_edad", "region", "estrato"]


class DecimalFeature(StrictModel):
    type: Literal["decimal"] = "decimal"
    value: DecimalStr


class IntFeature(StrictModel):
    type: Literal["int"] = "int"
    value: int


class CategoryFeature(StrictModel):
    type: Literal["category"] = "category"
    value: Annotated[str, Field(max_length=60)]


FeatureValue = Annotated[DecimalFeature | IntFeature | CategoryFeature, Field(discriminator="type")]


class FeatureVector(StrictModel):
    features: dict[str, FeatureValue]

    @field_validator("features")
    @classmethod
    def _no_identifiers(cls, value: dict[str, Any]) -> dict[str, Any]:
        if IDENTIFICATION_FIELDS & set(value) or "free_text" in value:
            raise ValueError("forbidden_feature_key")
        return value


class MonitoringLabels(StrictModel):
    sexo: Sex
    rango_edad: RangoEdad
    region: Region
    estrato: Stratum
    banda_capacidad_pago: Band


class FeatureContribution(StrictModel):
    feature_id: str
    value: FeatureValue
    contribution: DecimalStr


class FeatureDictionaryEntry(StrictModel):
    feature_id: str
    label_es: Annotated[str, Field(max_length=80)]
    unit: Annotated[str, Field(max_length=20)] | None = None
    increases_risk_phrase_es: Annotated[str, Field(max_length=160)]
    decreases_risk_phrase_es: Annotated[str, Field(max_length=160)]
    applicant_safe: bool


class FeatureDictionary(StrictModel):
    dictionary_version: str
    model_version_id: str
    entries: list[FeatureDictionaryEntry]


class FeatureSpecItem(StrictModel):
    """`feature_spec.json` de U5: feature derivada, campo permitido o busqueda en tabla."""

    feature_id: str
    origin: Literal["derived", "field", "lookup"]
    source_fields: list[str] = []
    table: dict[str, str] | None = None
    default: Annotated[str, Field(max_length=60)] | None = None


class FeatureSpec(StrictModel):
    model_version_id: str
    features: list[FeatureSpecItem]
