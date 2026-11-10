"""El caso fijo de la narrativa (US-104, US-105): vector, diccionario y texto esperado, escritos a mano."""

from vectra_contracts.models.features import (
    FeatureContribution,
    FeatureDictionary,
    FeatureDictionaryEntry,
    IntFeature,
)


def contribution(feature_id: str, value: str) -> FeatureContribution:
    return FeatureContribution(feature_id=feature_id, value=IntFeature(value=1), contribution=value)


def entry(feature_id: str, label: str, up: str, down: str) -> FeatureDictionaryEntry:
    return FeatureDictionaryEntry(
        feature_id=feature_id,
        label_es=label,
        increases_risk_phrase_es=up,
        decreases_risk_phrase_es=down,
        applicant_safe=True,
    )


DICTIONARY = FeatureDictionary(
    dictionary_version="d-1",
    model_version_id="mv-fijo",
    entries=[
        entry("dti", "Relación cuota-ingreso", "pesa más cuando sube", "pesa menos cuando baja"),
        entry("mora", "Mora reciente", "aumenta el riesgo", "reduce el riesgo"),
        entry(
            "antig",
            "Antigüedad laboral",
            "poca antigüedad aumenta el riesgo",
            "la antigüedad reduce el riesgo",
        ),
        entry("zeta", "Zeta", "z sube", "z baja"),
        entry("alfa", "Alfa", "a sube", "a baja"),
        entry("cero", "Sin efecto", "no debe salir", "no debe salir"),
    ],
)
# S = 0,40 + 0,30 + 0,15 + 0,10 + 0,05 = 1,00 -> fuerte (0,40 y 0,30), moderada (0,15 y 0,10), leve (0,05).
VECTOR = [
    contribution("cero", "0.00"),
    contribution("antig", "-0.15"),
    contribution("mora", "0.40"),
    contribution("dti", "-0.30"),
    contribution("zeta", "0.05"),
    contribution("alfa", "-0.10"),
]
EXPECTED = (
    "Explicación del riesgo estimado — método SHAP · modelo mv-fijo · plantilla template:v1\n"
    "1. Mora reciente: aumenta el riesgo (influencia fuerte).\n"
    "2. Relación cuota-ingreso: pesa menos cuando baja (influencia fuerte).\n"
    "3. Antigüedad laboral: la antigüedad reduce el riesgo (influencia moderada).\n"
    "4. Alfa: a baja (influencia moderada).\n"
    "5. Zeta: z sube (influencia leve).\n"
    "Aproximación post-hoc: describe qué variables movieron el riesgo estimado; no es una lectura del razonamiento del modelo"
)
