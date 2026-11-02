"""Perfiles de Hypothesis del workspace (NFR-U0-42, 43), reutilizados de U0."""

import importlib.util
from pathlib import Path

_U0_CONFTEST = Path(__file__).resolve().parents[2] / "contracts" / "tests" / "conftest.py"
_spec = importlib.util.spec_from_file_location("_u0_hypothesis_profiles", _U0_CONFTEST)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
# Al importarlo se registran los perfiles y se carga el de HYPOTHESIS_PROFILE.
_spec.loader.exec_module(_module)

pytest_report_header = _module.pytest_report_header
