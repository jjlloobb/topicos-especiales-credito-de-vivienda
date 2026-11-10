"""Ejemplos de `factuality` (US-105): un factor invertido da `False`; diccionario incompleto; independencia del generador."""

import ast
from pathlib import Path

import explainability
from explainability.factuality import FactualityValidator
from u7_cases import DICTIONARY, EXPECTED, VECTOR, contribution

V = FactualityValidator()


def test_the_fixed_narrative_validates() -> None:
    assert V.validate(EXPECTED, VECTOR, DICTIONARY, "mv-fijo") is True


def test_us105_a_narrative_with_an_inverted_factor_is_false() -> None:
    inverted = EXPECTED.replace("Mora reciente: aumenta el riesgo", "Mora reciente: reduce el riesgo")
    assert inverted != EXPECTED
    assert V.validate(inverted, VECTOR, DICTIONARY, "mv-fijo") is False


def test_a_vector_that_the_dictionary_does_not_cover_is_false() -> None:
    assert (
        V.validate(EXPECTED, [*VECTOR, contribution("desconocido", "9.00")], DICTIONARY, "mv-fijo") is False
    )


def test_the_validator_does_not_read_the_generator_or_the_template() -> None:
    source = (Path(explainability.__file__).parent / "factuality.py").read_text(encoding="utf-8")
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in (node.names if isinstance(node, ast.Import) else [None])
    }
    assert not any(name and ("narrative" in name or "template_files" in name) for name in imported)
