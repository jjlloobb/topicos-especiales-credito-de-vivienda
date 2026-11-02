"""La carga perezosa de `models.api` no cambia la API publica de `vectra_contracts.models`."""

import importlib
import pkgutil
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
