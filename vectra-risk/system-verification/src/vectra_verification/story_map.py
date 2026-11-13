"""Mapa historia -> evidencias (U12 Paso 3; BR-U12-13; domain-entities §4.2). Carga `report/story-map.yaml` y valida el texto.

P-3, recomendacion (a): `parse` es una funcion pura sobre el texto del YAML y `load` es una linea que lee el archivo con `pathlib`. Falla ante una historia de
domain-entities §4 sin fila, ante una historia que no es de §4, ante una fila sin evidencias, ante una evidencia que no es un identificador conocido (`US-609` no lo es:
su evidencia es `LOAD`) y ante una marca `demonstrated` que no coincide con las cuatro historias de demos. `yaml` se permite solo en este modulo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from vectra_verification.report import DEMO_STORY_IDS, ELEMENT_IDS, STORY_IDS, StoryRow


class StoryMapError(ValueError):
    """El mapa no cumple domain-entities §4.2; el mensaje empieza por un codigo estable."""


def parse(text: str) -> dict[str, StoryRow]:
    try:
        document: Any = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise StoryMapError("story_map_not_yaml") from error
    stories = document.get("stories") if isinstance(document, dict) else None
    if not isinstance(stories, dict):
        raise StoryMapError("story_map_shape")
    expected = set(STORY_IDS) | set(DEMO_STORY_IDS)
    for story in stories:
        if story not in expected:
            raise StoryMapError(f"story_unknown:{story}")
    for story in (*STORY_IDS, *DEMO_STORY_IDS):
        if story not in stories:
            raise StoryMapError(f"story_missing:{story}")
    result: dict[str, StoryRow] = {}
    for story, row in stories.items():
        evidence = row.get("evidence") if isinstance(row, dict) else None
        if not isinstance(evidence, list) or not evidence or not all(isinstance(e, str) for e in evidence):
            raise StoryMapError(f"story_evidence_shape:{story}")
        for item in evidence:
            if item not in ELEMENT_IDS:
                raise StoryMapError(f"evidence_unknown:{story}:{item}")
        if row.get("demonstrated", False) is not (story in DEMO_STORY_IDS):
            raise StoryMapError(f"story_demonstrated_mismatch:{story}")
        result[story] = StoryRow(evidence=tuple(evidence), demonstrated=story in DEMO_STORY_IDS)
    return result


def load(path: Path) -> dict[str, StoryRow]:
    return parse(path.read_text(encoding="utf-8"))
