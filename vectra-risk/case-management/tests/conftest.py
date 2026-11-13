"""Perfiles de Hypothesis de U8 (mismos de `contracts/tests/conftest.py`, NFR-U0-42, 43); `HYPOTHESIS_PROFILE=ci` en `make check`.

La semilla queda fija y visible en el encabezado de pytest en toda corrida, tambien en verde (NFR-U8-52; patron de
`scoring-explainability/tests/conftest.py`): `--hypothesis-seed=N` la repite."""

import os
import secrets

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import core as hypothesis_core

_SUPPRESS = [HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.filter_too_much]
settings.register_profile(
    "ci", max_examples=500, print_blob=True, deadline=None, suppress_health_check=_SUPPRESS
)
settings.register_profile(
    "nightly", max_examples=10_000, print_blob=True, deadline=None, suppress_health_check=_SUPPRESS
)
settings.register_profile(
    "dev", max_examples=25, print_blob=True, deadline=None, suppress_health_check=_SUPPRESS
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    if hypothesis_core.global_force_seed is None:
        hypothesis_core.global_force_seed = secrets.randbelow(2**32)


def pytest_report_header() -> str:
    return f"hypothesis profile: {os.environ.get('HYPOTHESIS_PROFILE', 'dev')}, seed: {hypothesis_core.global_force_seed}"
