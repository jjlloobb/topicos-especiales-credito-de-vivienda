"""Validador de factualidad (BR-U7-11; US-105), independiente del generador.

No importa `narrative` (contrato de import-linter) ni lee la plantilla: el encabezado y la leyenda esperados son constantes
propias, y la seleccion, el desempate y la intensidad se reimplementan con otra aritmetica (`Fraction`). Asi un error del
generador no se replica aqui. Cualquier diferencia con lo esperado da `False`.
"""

from fractions import Fraction
from typing import Final

from vectra_contracts.models.features import FeatureContribution, FeatureDictionary

HEADER: Final = "Explicación del riesgo estimado — método SHAP · modelo {model} · plantilla template:v1"
LEGEND: Final = "Aproximación post-hoc: describe qué variables movieron el riesgo estimado; no es una lectura del razonamiento del modelo"
LIMIT: Final = 5
INTENSITIES: Final = ("fuerte", "moderada", "leve")

#: (etiqueta, direccion, intensidad) de un factor, tal como lo dice una linea o como lo exige el vector.
Reading = tuple[str, str, str]


def _expected_ids(shap_vector: list[FeatureContribution]) -> list[tuple[str, Fraction]]:
    """(feature_id, SHAP) de los factores que deben mostrarse: mayor |SHAP| primero, empates por `feature_id`, sin ceros."""
    ranked = [
        (item.feature_id, Fraction(item.contribution))
        for item in shap_vector
        if Fraction(item.contribution) != 0
    ]
    ranked.sort(key=lambda pair: (-abs(pair[1]), pair[0]))
    return ranked[:LIMIT]


def _intensity(magnitude: Fraction, total: Fraction) -> str:
    share = magnitude / total
    if share >= Fraction(3, 10):
        return "fuerte"
    return "moderada" if share >= Fraction(1, 10) else "leve"


def _expected_readings(
    shap_vector: list[FeatureContribution], dictionary: FeatureDictionary
) -> list[Reading] | None:
    """Las lecturas que debe tener la narrativa, o `None` si el diccionario no cubre un factor mostrado."""
    shown = _expected_ids(shap_vector)
    total = sum((abs(value) for _, value in shown), Fraction(0))
    labels = {entry.feature_id: entry.label_es for entry in dictionary.entries}
    readings: list[Reading] = []
    for feature_id, value in shown:
        if feature_id not in labels:
            return None
        readings.append(
            (labels[feature_id], "aumenta" if value > 0 else "reduce", _intensity(abs(value), total))
        )
    return readings


def _recognise(line: str, number: int, dictionary: FeatureDictionary) -> set[Reading]:
    """Las lecturas posibles de una linea contra el diccionario: etiqueta, frase de direccion e intensidad."""
    found: set[Reading] = set()
    for entry in dictionary.entries:
        prefix = f"{number}. {entry.label_es}: "
        if not line.startswith(prefix):
            continue
        for direction, phrase in (
            ("aumenta", entry.increases_risk_phrase_es),
            ("reduce", entry.decreases_risk_phrase_es),
        ):
            for intensity in INTENSITIES:
                if line == f"{prefix}{phrase} (influencia {intensity}).":
                    found.add((entry.label_es, direction, intensity))
    return found


def validate(
    narrative: str,
    shap_vector: list[FeatureContribution],
    dictionary: FeatureDictionary,
    model_version_id: str,
) -> bool:
    """`True` solo si la narrativa dice exactamente lo que el vector y el diccionario exigen."""
    expected = _expected_readings(shap_vector, dictionary)
    if expected is None:
        return False
    parts = narrative.split("\n")
    if len(parts) != len(expected) + 2:
        return False
    header, lines, legend = parts[0], parts[1:-1], parts[-1]
    if header != HEADER.format(model=model_version_id) or legend != LEGEND:
        return False
    return all(
        want in _recognise(line, number, dictionary)
        for number, (line, want) in enumerate(zip(lines, expected, strict=True), start=1)
    )


class FactualityValidator:
    """Fachada del validador: `validate(narrative, shap_vector, dictionary, model_version_id) -> bool`."""

    def validate(
        self,
        narrative: str,
        shap_vector: list[FeatureContribution],
        dictionary: FeatureDictionary,
        model_version_id: str,
    ) -> bool:
        return validate(narrative, shap_vector, dictionary, model_version_id)
