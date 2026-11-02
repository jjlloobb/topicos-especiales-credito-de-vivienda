"""Cada modulo (publico o privado) se importa como primer import de un proceso limpio (US-111)."""

import importlib.util
import pkgutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOTS = ("vectra_contracts", "vectra_common")


def _walk(package: str, locations: list[str]) -> list[str]:
    names: list[str] = []
    for info in pkgutil.iter_modules(locations):
        if info.name.startswith("__"):
            continue
        full = f"{package}.{info.name}"
        names.append(full)
        if info.ispkg:
            names.extend(_walk(full, [str(Path(info.module_finder.path) / info.name)]))  # type: ignore[union-attr]
    return names


def _public_modules() -> list[str]:
    modules: list[str] = []
    for root in _ROOTS:
        spec = importlib.util.find_spec(root)
        assert spec is not None and spec.submodule_search_locations is not None
        modules.append(root)
        modules.extend(_walk(root, list(spec.submodule_search_locations)))
    return sorted(modules)


@pytest.mark.parametrize("module", _public_modules())
def test_each_module_imports_in_isolation(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import {module}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
