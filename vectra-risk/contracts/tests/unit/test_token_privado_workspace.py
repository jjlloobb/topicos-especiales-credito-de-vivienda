"""P-U0-03 capa 3, en todo el workspace (U00-T03; F-01 y R2-01 de la ronda 1 y 2 de U08-T02).

`contracts/.importlinter` solo ve modulos de U0 y no ve nombres. Esta prueba recorre con `ast` todo el Python de `vectra-risk/` y falla
si algun archivo fuera de `outcome/` toca el token privado: importa `vectra_contracts.outcome._internal`, nombra `CONSTRUCTION_TOKEN`
o pasa la ruta del modulo a `importlib.import_module` / `__import__` / `sys.modules`. Limite conocido: una ruta armada con cadenas
dinamicas (`"vectra_contracts." + x`) no se ve estaticamente; `test_construction_token_is_not_a_public_attribute_of_outcome` cubre el
atributo en tiempo de ejecucion.
"""

import ast
import os
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]  # vectra-risk/
OUTCOME = ROOT / "contracts" / "python" / "vectra_contracts" / "src" / "vectra_contracts" / "outcome"
SKIP_DIRS = frozenset({".venv", "node_modules", "__pycache__", ".git", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".hypothesis"})
# Nombre de modulo y de simbolo partidos para que esta prueba no se nombre a si misma al recorrer el arbol.
MODULE = "vectra_contracts.outcome." + "_internal"
TOKEN = "CONSTRUCTION" + "_TOKEN"
DYNAMIC_IMPORTERS = frozenset({"import_module", "__import__"})

# Lista de permitidos: archivos fuera de `outcome/` que pueden nombrar el token, cada uno con su porque. Hoy solo esta prueba, que
# lo nombra para detectarlo (partido en dos cadenas, asi que ni siquiera se ve a si misma). Las pruebas de U0 en `contracts/tests/`
# no usan el token: construyen con `build_outcome` o `read_wire`.
ALLOWED: dict[Path, str] = {
    Path(__file__).resolve(): "define el detector; nombra el token para buscarlo",
}


def member_roots() -> list[Path]:
    members = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["workspace"]["members"]
    return [ROOT / m for m in members]


def python_files() -> list[Path]:
    found: list[Path] = []
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        found += [Path(base) / n for n in names if n.endswith(".py")]
    return sorted(found)


def _docstrings(tree: ast.AST) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                found.add(id(body[0].value))
    return found


def _callee(func: ast.expr) -> str:
    return func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""


def violations_in(source: str) -> list[str]:
    tree = ast.parse(source)
    docs = _docstrings(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import):
            found += [f"{line}: import {a.name}" for a in node.names if a.name.startswith(MODULE)]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(MODULE):
                found.append(f"{line}: from {module} import ...")
            elif module.endswith("vectra_contracts.outcome") or (node.level and module in {"", "outcome"}):
                found += [
                    f"{line}: from {module or '.'} import {a.name}"
                    for a in node.names
                    if a.name in {"_internal", TOKEN}
                ]
        elif isinstance(node, ast.Name) and node.id == TOKEN:
            found.append(f"{line}: nombra {TOKEN}")
        elif isinstance(node, ast.Attribute) and node.attr == TOKEN:
            found.append(f"{line}: nombra .{TOKEN}")
        elif isinstance(node, ast.Call) and _callee(node.func) in DYNAMIC_IMPORTERS:
            args = [a for a in node.args[:1] if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            found += [f"{line}: {_callee(node.func)}({a.value!r})" for a in args if a.value.startswith(MODULE)]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs and MODULE in node.value:
            found.append(f"{line}: cadena {node.value!r}")
    return sorted(set(found))


def test_token_is_closed_in_the_whole_workspace(capsys: pytest.CaptureFixture[str]):
    roots = member_roots()
    files = python_files()
    assert files and all(r.is_dir() for r in roots), roots
    assert all(any(r in p.parents for p in files) for r in roots), "un miembro del workspace sin ningun .py recorrido"
    bad: dict[str, list[str]] = {}
    scanned = 0
    for path in files:
        if OUTCOME in path.parents or path.resolve() in ALLOWED:
            continue
        scanned += 1
        found = violations_in(path.read_text(encoding="utf-8"))
        if found:
            bad[str(path.relative_to(ROOT))] = found
    with capsys.disabled():
        print(f"\nraices (miembros de pyproject.toml): {[str(r.relative_to(ROOT)) for r in roots]}")
        print(f"archivos recorridos: {scanned} de {len(files)} .py")
    assert not bad, f"el token privado de outcome se toca fuera de outcome: {bad}"


@pytest.mark.parametrize(
    "source",
    [
        f"from {MODULE} import {TOKEN}",
        f"import {MODULE}",
        "def f():\n    from vectra_contracts.outcome._internal import X\n",
        f"from vectra_contracts.outcome import {TOKEN}",
        "from vectra_contracts.outcome import _internal",
        "from vectra_contracts.outcome import _internal as t",
        f"x = obj.{TOKEN}",
        f"x = {TOKEN}",
        f"import importlib\ndef f():\n    return importlib.import_module('{MODULE}')",
        f"m = __import__('{MODULE}')",
        f"import sys\nsys.modules['{MODULE}']",
    ],
)
def test_detector_catches_each_route(source: str):
    assert violations_in(source)


@pytest.mark.parametrize(
    "source",
    [
        "from vectra_contracts.outcome import Recommendation, build_outcome, read_wire",
        "import importlib\nimportlib.import_module('vectra_contracts.outcome')",
        '"""Menciona vectra_contracts.outcome._internal solo en una docstring."""',
    ],
)
def test_detector_lets_public_api_pass(source: str):
    assert not violations_in(source)


def test_the_probe_of_the_reviewer_is_caught():
    """La sonda de F-01 (ronda 1 de U08-T02): importa `_CONTEXT` de `views`, o el token directamente, y fabrica una `Recommendation`."""
    probe = (
        "from vectra_contracts.outcome import Recommendation\n"
        f"from vectra_contracts.outcome import {TOKEN}\n"
        f"fake = Recommendation.model_validate_json(raw, context={{'token': {TOKEN}}})\n"
    )
    assert len(violations_in(probe)) >= 2

