"""Perfiles de Hypothesis de U5 (NFR-U5-33: perfil `ci` con 500 ejemplos y semilla impresa), iguales a los de U0."""

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
_profile = os.environ.get("HYPOTHESIS_PROFILE", "dev")
settings.load_profile(_profile)


def pytest_report_header() -> str:
    return f"hypothesis profile: {_profile}"
