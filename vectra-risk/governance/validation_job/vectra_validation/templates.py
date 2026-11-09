"""Textos del informe. Una prueba les aplica la lista unica de frases prohibidas de U0 (FR-BIA-08, BR-U0-94)."""

from typing import Final

DISCLAIMER: Final = (
    "La disparidad inicial mide diferencias de tasa favorable entre grupos sobre el dataset de validacion; "
    "no certifica ausencia de discriminacion ni sustituye la revision de cumplimiento."
)
TEMPLATES: Final = (DISCLAIMER,)
