"""Perfiles de Hypothesis de U8 (mismos de `contracts/tests/conftest.py`, NFR-U0-42, 43); `HYPOTHESIS_PROFILE=ci` en `make check`."""

import os

from hypothesis import HealthCheck, settings

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
