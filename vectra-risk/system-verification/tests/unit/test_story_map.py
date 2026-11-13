"""`story_map` (U12 Paso 3; BR-U12-13; domain-entities §4.2): el mapa real y los mapas rotos de `tests/fixtures/story-map/`."""

import re
from pathlib import Path

import pytest

from vectra_verification import story_map
from vectra_verification.report import DEMO_STORY_IDS, ELEMENT_IDS, STORY_IDS
from vectra_verification.story_map import StoryMapError

UNIT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "story-map"
ENTITIES = (
    UNIT.parent
    / "aidlc-docs"
    / "construction"
    / "system-verification"
    / "functional-design"
    / "domain-entities.md"
)


def _entities_table() -> dict[str, list[str]]:
    """Las 15 filas de domain-entities §4.2: historia -> los identificadores entre comillas inversas de la segunda columna, sin lo que va entre parentesis."""
    section = (
        ENTITIES.read_text(encoding="utf-8").split("### 4.2", 1)[1].split("Origen de las cuatro filas", 1)[0]
    )
    table: dict[str, list[str]] = {}
    for line in section.splitlines():
        match = re.match(r"\| (US-\d+) [^|]*\| ([^|]+) \|", line)
        if match:
            table[match.group(1)] = re.findall(r"`([^`]+)`", re.sub(r"\([^)]*\)", "", match.group(2)))
    return table


def test_the_real_story_map_loads_with_15_rows_and_matches_domain_entities_row_by_row() -> None:
    loaded = story_map.load(UNIT / "report" / "story-map.yaml")
    table = _entities_table()
    assert len(loaded) == 15 == len(table)
    assert {story: list(row.evidence) for story, row in loaded.items()} == table
    assert list(loaded) == list(table)  # tambien el orden


def test_the_four_demo_stories_are_marked_and_the_others_are_not() -> None:
    loaded = story_map.load(UNIT / "report" / "story-map.yaml")
    assert (
        {s for s, row in loaded.items() if row.demonstrated}
        == {"US-304", "US-503", "US-504", "US-505"}
        == set(DEMO_STORY_IDS)
    )
    assert set(STORY_IDS) | set(DEMO_STORY_IDS) == set(loaded)


def test_every_evidence_of_the_real_map_is_one_of_the_26_known_identifiers() -> None:
    loaded = story_map.load(UNIT / "report" / "story-map.yaml")
    assert len(ELEMENT_IDS) == 26 and len(set(ELEMENT_IDS)) == 26
    assert "US-609" not in ELEMENT_IDS
    assert {e for row in loaded.values() for e in row.evidence} <= set(ELEMENT_IDS)


def test_a_map_without_the_us_603_row_fails() -> None:
    with pytest.raises(StoryMapError, match="story_missing:US-603"):
        story_map.load(FIXTURES / "sin-us-603.yaml")


def test_a_map_with_the_evidence_x99_fails() -> None:
    with pytest.raises(StoryMapError, match="evidence_unknown:US-106:X99"):
        story_map.load(FIXTURES / "evidencia-x99.yaml")


def test_a_map_with_us_609_as_evidence_fails() -> None:
    with pytest.raises(StoryMapError, match="evidence_unknown:US-609:US-609"):
        story_map.load(FIXTURES / "us-609-como-evidencia.yaml")


def test_other_broken_maps_fail() -> None:
    with pytest.raises(StoryMapError, match="story_unknown:US-999"):
        story_map.load(FIXTURES / "historia-desconocida.yaml")
    with pytest.raises(StoryMapError, match="story_evidence_shape:US-101"):
        story_map.load(FIXTURES / "fila-vacia.yaml")
    with pytest.raises(StoryMapError, match="story_demonstrated_mismatch:US-503"):
        story_map.load(FIXTURES / "demo-sin-marca.yaml")
    with pytest.raises(StoryMapError, match="story_demonstrated_mismatch:US-101"):
        story_map.load(FIXTURES / "verificada-marcada-demo.yaml")


@pytest.mark.parametrize(
    "text",
    [
        "",
        "- una lista",
        "stories: 3",
        "stories: [a, b]",
        "{unclosed",
        "stories: {US-101: 3}",
        "stories: {US-101: {evidence: SIM-NORMAL}}",
    ],
)
def test_malformed_text_fails(text: str) -> None:
    with pytest.raises(StoryMapError):
        story_map.parse(text)


def test_parse_is_pure_text_validation_and_load_reads_the_file(tmp_path: Path) -> None:
    text = (UNIT / "report" / "story-map.yaml").read_text(encoding="utf-8")
    copy = tmp_path / "story-map.yaml"
    copy.write_text(text, encoding="utf-8")
    assert story_map.load(copy) == story_map.parse(text)
