"""Perfiles de Hypothesis de U7 (`HYPOTHESIS_PROFILE`: dev, ci, nightly)."""

import os

from hypothesis import HealthCheck, settings

_COMMON = {
    "print_blob": True,
    "deadline": None,
    "suppress_health_check": [HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.filter_too_much],
}
settings.register_profile("ci", max_examples=500, **_COMMON)
settings.register_profile("nightly", max_examples=10_000, **_COMMON)
settings.register_profile("dev", max_examples=25, **_COMMON)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
