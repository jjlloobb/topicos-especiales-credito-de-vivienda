"""La carga perezosa de `models.api` no cambia la API publica de `vectra_contracts.models`."""

import importlib
import json
import pkgutil
import subprocess
import sys
import types

import pytest

import vectra_contracts.models as models
from vectra_contracts.models import api


def _public(module: types.ModuleType) -> set[str]:
    return {n for n in vars(module) if not n.startswith("_")}


def _expected() -> set[str]:
    """Lo que el paquete exponia cuando importaba `api` y los demas submodulos de forma eager."""
    names: set[str] = set()
    for info in pkgutil.iter_modules(models.__path__):
        sub = importlib.import_module(f"vectra_contracts.models.{info.name}")
        names.add(info.name)
        names |= _public(sub)
    return names


def test_star_import_exports_the_same_names() -> None:
    ns: dict[str, object] = {}
    exec("from vectra_contracts.models import *", ns)  # noqa: S102
    ns.pop("__builtins__")
    assert set(ns) == _expected()
    assert "TYPE_CHECKING" not in ns and "import_module" not in ns


def test_dir_lists_the_same_names() -> None:
    assert {n for n in dir(models) if not n.startswith("_")} == _expected()


def test_api_is_an_attribute() -> None:
    assert models.api is api
    assert "api" in dir(models)


def test_every_public_name_resolves_to_its_source() -> None:
    for name in _public(api):
        assert getattr(models, name) is getattr(api, name)


def test_unknown_name_raises_attribute_error() -> None:
    with pytest.raises(AttributeError, match="no_existe"):
        models.no_existe  # type: ignore[attr-defined]  # noqa: B018
    assert not hasattr(models, "_privado")


_CLEAN_SCRIPT = """
import json, pkgutil
import vectra_contracts.models as m

# Orden deliberado: nada de lo que sigue puede precargar `api` antes de estas dos lecturas.
listed = dir(m)
api_is_submodule = m.api.__name__ == "vectra_contracts.models.api"
ns = {}
exec("from vectra_contracts.models import *", ns)
ns.pop("__builtins__")
expected = set()
import importlib
import json
for info in pkgutil.iter_modules(m.__path__):
    sub = importlib.import_module("vectra_contracts.models." + info.name)
    expected.add(info.name)
    expected |= {n for n in vars(sub) if not n.startswith("_")}
try:
    m.no_existe
    missing = "sin error"
except AttributeError:
    missing = "AttributeError"
print(json.dumps({
    "star_extra": sorted(set(ns) - expected),
    "star_missing": sorted(expected - set(ns)),
    "dir_missing": sorted(expected - set(listed)),
    "api_is_submodule": api_is_submodule,
    "missing": missing,
}))
"""


def test_models_public_api_in_clean_interpreter() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", _CLEAN_SCRIPT], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report == {
        "star_extra": [],
        "star_missing": [],
        "dir_missing": [],
        "api_is_submodule": True,
        "missing": "AttributeError",
    }
