"""Paso 1: el arbol de dependencias de runtime de `vectra_disparity` esta vacio (P-U9-05). CA-2."""

import ast
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # vectra-risk/
PACKAGE = ROOT / "bias-monitoring" / "disparity"


def test_pyproject_declares_no_dependencies():
    project = tomllib.loads((PACKAGE / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["name"] == "vectra-disparity"
    assert project["dependencies"] == []
    assert "optional-dependencies" not in project


def test_lock_has_no_dependencies_for_vectra_disparity():
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    entry = next(p for p in lock["package"] if p["name"] == "vectra-disparity")
    assert "dependencies" not in entry
    assert "optional-dependencies" not in entry


def test_every_import_is_standard_library_or_the_package_itself():
    allowed = set(sys.stdlib_module_names) | {"vectra_disparity"}
    offenders = []
    for path in sorted((PACKAGE / "src" / "vectra_disparity").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""] if node.level == 0 else []
            offenders += [f"{path.name}:{n}" for n in names if n.split(".")[0] not in allowed]
    assert offenders == []
