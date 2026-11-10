"""Ejemplos de `narrative` (US-104): caso fijo, plantilla, desempate, ceros y una sola implementacion (NFR-U7-32)."""

import ast
import subprocess
import sys
from pathlib import Path

import explainability
import pytest
from explainability import narrative as narrative_module
from explainability.narrative import (
    FeatureDictionaryIncomplete,
    NarrativeGenerator,
    TemplateNarrativeGenerator,
    intensity_of,
    select_top,
)
from explainability.template_files import TemplateError, read_template
from u7_cases import DICTIONARY, EXPECTED, VECTOR, contribution, entry
from vectra_contracts.models.features import FeatureDictionary

UNIT = Path(__file__).resolve().parents[2]
TEMPLATE = UNIT / "explainability" / "templates" / "template_v1.txt"


def test_us104_fixed_case_is_identical_to_the_expected_text() -> None:
    assert TemplateNarrativeGenerator().generate(VECTOR, DICTIONARY, "mv-fijo") == EXPECTED


def test_ties_break_by_feature_id_not_by_label() -> None:
    # Misma |SHAP|; "alfa" < "zeta" por id, y la etiqueta «Zeta» no gana por ninguna razon alfabetica distinta.
    swapped = FeatureDictionary(
        dictionary_version="d-1",
        model_version_id="mv-fijo",
        entries=[entry("alfa", "Zorro", "u", "d"), entry("zeta", "Abeja", "u", "d")],
    )
    vector = [contribution("zeta", "0.20"), contribution("alfa", "-0.20")]
    lines = TemplateNarrativeGenerator().generate(vector, swapped, "mv-1").split("\n")[1:-1]
    assert [line.split(":")[0] for line in lines] == ["1. Zorro", "2. Abeja"]
    assert [item.feature_id for item in select_top(vector)] == ["alfa", "zeta"]


def test_zero_shap_never_enters_and_an_all_zero_vector_has_only_header_and_notice() -> None:
    text = TemplateNarrativeGenerator().generate(
        [contribution("cero", "0.00"), contribution("dti", "0.0000")], DICTIONARY, "mv-1"
    )
    assert len(text.split("\n")) == 2
    assert "Sin efecto" not in text


def test_only_five_lines_even_with_more_factors() -> None:
    vector = [contribution(f"f{i}", f"0.{i}0") for i in range(1, 9)]
    dictionary = FeatureDictionary(
        dictionary_version="d",
        model_version_id="m",
        entries=[entry(f"f{i}", f"Factor {chr(96 + i)}", "sube", "baja") for i in range(1, 9)],
    )
    text = TemplateNarrativeGenerator().generate(vector, dictionary, "m")
    assert len(text.split("\n")) == 7
    assert "Factor h" in text and "Factor d" in text and "Factor c" not in text


def test_a_factor_missing_from_the_dictionary_is_reported() -> None:
    with pytest.raises(FeatureDictionaryIncomplete, match="desconocido"):
        TemplateNarrativeGenerator().generate([contribution("desconocido", "0.5")], DICTIONARY, "mv-1")


def test_intensity_thresholds_are_030_and_010_inclusive() -> None:
    from decimal import Decimal

    total = Decimal(100)
    assert intensity_of(Decimal(30), total) == "fuerte"
    assert intensity_of(Decimal("29.99"), total) == "moderada"
    assert intensity_of(Decimal(10), total) == "moderada"
    assert intensity_of(Decimal("9.99"), total) == "leve"


def test_nfr_u7_32_there_is_a_single_implementation_of_the_generator() -> None:
    assert NarrativeGenerator.__subclasses__() == [TemplateNarrativeGenerator]
    assert TemplateNarrativeGenerator.template_id == "template:v1"
    # Tambien en el codigo: ninguna otra clase del paquete hereda de la interfaz.
    subclasses = []
    for path in sorted(Path(explainability.__file__).parent.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and any(
                ast.unparse(base).endswith("NarrativeGenerator") for base in node.bases
            ):
                subclasses.append(node.name)
    assert subclasses == ["TemplateNarrativeGenerator"]
    assert narrative_module.TEMPLATE_ID == "template:v1"


def test_the_template_has_no_forbidden_phrases() -> None:
    root = UNIT.parent
    done = subprocess.run(
        [sys.executable, str(root / "contracts/tools/forbidden_phrases.py"), str(TEMPLATE)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout


def test_template_loading_falls_back_and_reports_what_is_missing(tmp_path: Path) -> None:
    empty, full = tmp_path / "a", tmp_path / "b"
    empty.mkdir()
    full.mkdir()
    (full / "x.txt").write_text("# comentario\n@uno hola mundo\n@dos \n", encoding="utf-8")
    assert read_template("x.txt", ("uno", "dos"), (empty, full)) == {"uno": "hola mundo", "dos": ""}
    with pytest.raises(TemplateError, match="plantilla_no_encontrada"):
        read_template("y.txt", ("uno",), (empty, full))
    with pytest.raises(TemplateError, match="plantilla_incompleta: x.txt: tres"):
        read_template("x.txt", ("uno", "tres"), (full,))
