"""Narrativa determinista del analista (BR-U7-10, NFR-U7-32; US-104): `template:v1`, sin LLM ni numeros de SHAP.

Una sola implementacion de `NarrativeGenerator`. El validador de factualidad (`factuality`) NO importa este modulo (BR-U7-11).
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Final, Literal

from vectra_contracts.models.features import FeatureContribution, FeatureDictionary, FeatureDictionaryEntry

from explainability.template_files import read_template

TEMPLATE_ID: Final = "template:v1"
TEMPLATE_FILE: Final = "template_v1.txt"
MAX_LINES: Final = 5

Direction = Literal["aumenta", "reduce"]
Intensity = Literal["fuerte", "moderada", "leve"]


class FeatureDictionaryIncomplete(LookupError):
    """El diccionario no cubre un factor mostrado (`feature_dictionary_incomplete`, domain-entities §5)."""


class NarrativeGenerator(ABC):
    """Interfaz del generador de narrativa (NFR-U7-32: la unica implementacion registrada es la de plantilla)."""

    template_id: str

    @abstractmethod
    def generate(
        self, shap_vector: list[FeatureContribution], dictionary: FeatureDictionary, model_version_id: str
    ) -> str: ...


def select_top(shap_vector: list[FeatureContribution]) -> list[FeatureContribution]:
    """Hasta 5 factores de mayor |SHAP|, sin ceros; el desempate es el orden lexicografico de `feature_id` (BR-U7-10)."""
    nonzero = [item for item in shap_vector if Decimal(item.contribution) != 0]
    return sorted(nonzero, key=lambda item: (-abs(Decimal(item.contribution)), item.feature_id))[:MAX_LINES]


def intensity_of(magnitude: Decimal, total: Decimal) -> Intensity:
    """`fuerte` si |SHAP|/S >= 0,30; `moderada` si esta en [0,10; 0,30); `leve` si < 0,10 (domain-entities §3), con S > 0."""
    if magnitude * 10 >= total * 3:
        return "fuerte"
    if magnitude * 10 >= total:
        return "moderada"
    return "leve"


class TemplateNarrativeGenerator(NarrativeGenerator):
    """`template:v1`: encabezado, una linea por factor y la leyenda post-hoc, leidos de `templates/template_v1.txt`."""

    template_id = TEMPLATE_ID

    def __init__(self) -> None:
        text = read_template(TEMPLATE_FILE, ("header", "line", "posthoc"))
        self._header, self._line, self._posthoc = text["header"], text["line"], text["posthoc"]

    @property
    def posthoc_notice(self) -> str:
        return self._posthoc

    def generate(
        self, shap_vector: list[FeatureContribution], dictionary: FeatureDictionary, model_version_id: str
    ) -> str:
        entries: dict[str, FeatureDictionaryEntry] = {entry.feature_id: entry for entry in dictionary.entries}
        shown = select_top(shap_vector)
        total = sum((abs(Decimal(item.contribution)) for item in shown), Decimal(0))
        lines = [self._header.format(model_version_id=model_version_id)]
        for number, item in enumerate(shown, start=1):
            entry = entries.get(item.feature_id)
            if entry is None:
                raise FeatureDictionaryIncomplete(item.feature_id)
            raises = Decimal(item.contribution) > 0
            lines.append(
                self._line.format(
                    n=number,
                    label_es=entry.label_es,
                    phrase=entry.increases_risk_phrase_es if raises else entry.decreases_risk_phrase_es,
                    intensity=intensity_of(abs(Decimal(item.contribution)), total),
                )
            )
        lines.append(self._posthoc)
        return "\n".join(lines)
