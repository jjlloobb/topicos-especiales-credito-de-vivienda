"""Prueba de arquitectura (P-U9-04, P-U9-05): busqueda estatica sobre `bias-monitoring/src/vectra_bias/`.

Ningun modulo fuera de `vectra_disparity` construye un `CellResult` con `rate`: la supresion de celdas chicas vive solo en
la libreria, y los tipos de U0 la refuerzan. Los contratos de import-linter se ejecutan en `make imports`.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).parents[2] / "src" / "vectra_bias"
CELL_RESULT = "CellResult"


def _name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def cell_result_with_rate(source: str) -> list[int]:
    """Lineas donde se construye un `CellResult` con `rate` (por palabra clave, por posicion o por `model_construct`),
    o un diccionario literal de celda con `rate` y `status`."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            direct = _name(func) == CELL_RESULT
            construct = isinstance(func, ast.Attribute) and func.attr == "model_construct" and _name(func.value) == CELL_RESULT
            if (direct or construct) and (any(k.arg == "rate" for k in node.keywords) or len(node.args) >= 4):
                lines.append(node.lineno)
        if isinstance(node, ast.Dict):
            keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
            if {"rate", "status", "group", "band"} <= keys:
                lines.append(node.lineno)
    return lines


def test_the_detector_finds_a_cell_result_with_a_rate():
    assert cell_result_with_rate("CellResult(group='a', band='lt_20', n=1, rate='0.5000', status='suficiente')") == [1]
    assert cell_result_with_rate("x.CellResult(*args)") == []
    assert cell_result_with_rate("CellResult.model_construct(rate=1)") == [1]
    assert cell_result_with_rate("{'group': 'a', 'band': 'b', 'rate': 1, 'status': 's'}") == [1]
    assert cell_result_with_rate("CellResult(group='a', band='lt_20', n=1, status='muestra_insuficiente')") == []


def test_no_module_of_vectra_bias_builds_a_cell_result_with_a_rate():
    offenders = {
        f"{path.name}:{line}"
        for path in sorted(SRC.glob("*.py"))
        for line in cell_result_with_rate(path.read_text(encoding="utf-8"))
    }
    assert offenders == set()
