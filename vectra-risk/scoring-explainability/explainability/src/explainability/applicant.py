"""Resumen para el solicitante (BR-U7-14; US-110): funcion pura que devuelve el `ApplicantSummary` de U0 y no lo guarda.

Solo salen hasta 3 factores con `applicant_safe` y SHAP > 0, por |SHAP|; ni valores de SHAP, ni numeros, ni los campos
prohibidos de domain-entities §4 (el `ApplicantSummary` de U0 no tiene sitio para ellos). El log `applicant_summary.generated`
y la ruta son de U07-T03.
"""

from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from vectra_contracts.models.api import ApplicantFactor, ApplicantSummary
from vectra_contracts.models.features import FeatureContribution, FeatureDictionary

from explainability.template_files import read_template

TEMPLATE_ID: Final = "applicant:v1"
TEMPLATE_FILE: Final = "applicant_v1.txt"
MAX_FACTORS: Final = 3


def generate(
    case_id: UUID,
    shap_vector: list[FeatureContribution],
    dictionary: FeatureDictionary,
    generated_at: datetime,
) -> ApplicantSummary:
    """`generated_at` lo inyecta quien llama: la funcion no lee el reloj."""
    safe = {entry.feature_id: entry for entry in dictionary.entries if entry.applicant_safe}
    raising = [item for item in shap_vector if item.feature_id in safe and Decimal(item.contribution) > 0]
    raising.sort(key=lambda item: (-Decimal(item.contribution), item.feature_id))
    factors = [
        ApplicantFactor(label_es=safe[item.feature_id].label_es, direction="aumenta")
        for item in raising[:MAX_FACTORS]
    ]
    notice = read_template(TEMPLATE_FILE, ("posthoc",))["posthoc"]
    return ApplicantSummary(
        case_id=case_id, factors=factors, posthoc_notice=notice, generated_at=generated_at
    )
