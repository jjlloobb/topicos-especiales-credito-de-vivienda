"""Perfiles de Hypothesis del workspace (NFR-U0-42, 43), reutilizados de U0 (mismo metodo que identity-edge)."""

import importlib.util
import os
from pathlib import Path

_U0_CONFTEST = Path(__file__).resolve().parents[2] / "contracts" / "tests" / "conftest.py"


def _load_u0_profiles() -> None:
    """Carga el conftest de U0: registra los perfiles `ci`, `nightly` y `dev` y activa el de HYPOTHESIS_PROFILE."""
    spec = importlib.util.spec_from_file_location("_u0_hypothesis_profiles", _U0_CONFTEST)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    os.environ.setdefault("HYPOTHESIS_PROFILE", "dev")


_load_u0_profiles()
