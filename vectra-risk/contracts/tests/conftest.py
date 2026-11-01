"""Perfiles de Hypothesis (NFR-U0-42, 43)."""

import os

from hypothesis import HealthCheck, settings

settings.register_profile(
    "ci",
    max_examples=500,
    print_blob=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.filter_too_much],
)
settings.register_profile(
    "nightly",
    max_examples=10_000,
    print_blob=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.filter_too_much],
)
settings.register_profile(
    "dev",
    max_examples=25,
    print_blob=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.filter_too_much],
)
_profile = os.environ.get("HYPOTHESIS_PROFILE", "dev")
settings.load_profile(_profile)


def pytest_report_header() -> str:
    return f"hypothesis profile: {_profile}"
