"""Perfiles de Hypothesis del workspace (NFR-U0-42, 43), reutilizados de U0."""

import importlib.util
import os
from pathlib import Path

import pytest

_U0_CONFTEST = Path(__file__).resolve().parents[2] / "contracts" / "tests" / "conftest.py"


def _load_u0_profiles() -> str:
    """Carga el conftest de U0 (registra y activa el perfil) y devuelve su perfil por defecto.

    El por defecto se lee de U0 cargando su modulo sin HYPOTHESIS_PROFILE; luego se
    recarga con el entorno real para dejar activo el perfil que corresponde.
    """
    spec = importlib.util.spec_from_file_location("_u0_hypothesis_profiles", _U0_CONFTEST)
    assert spec is not None and spec.loader is not None
    real = os.environ.pop("HYPOTHESIS_PROFILE", None)
    try:
        default = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(default)
    finally:
        if real is not None:
            os.environ["HYPOTHESIS_PROFILE"] = real
    if real is not None:
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
    return str(default._profile)


_U0_DEFAULT_PROFILE = _load_u0_profiles()


@pytest.fixture(scope="session")
def u0_default_profile() -> str:
    """Perfil por defecto que define U0 cuando HYPOTHESIS_PROFILE no esta fijada."""
    return _U0_DEFAULT_PROFILE
