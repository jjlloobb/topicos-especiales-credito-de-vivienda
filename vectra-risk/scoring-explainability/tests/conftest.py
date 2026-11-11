"""Perfiles de Hypothesis de U7 (`HYPOTHESIS_PROFILE`: dev, ci, nightly). `ci` = 500 ejemplos, semilla impresa (NFR-U7-42)."""

import os
import secrets
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import core as hypothesis_core
from vectra_reference.release import Release, run_release

# Los modulos de apoyo (`u7_strategies`) viven junto a este archivo; con `--import-mode=importlib` no estan en `sys.path`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

_COMMON = {
    "print_blob": True,
    "deadline": None,
    "suppress_health_check": [HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.filter_too_much],
}
settings.register_profile("ci", max_examples=500, **_COMMON)
settings.register_profile("nightly", max_examples=10_000, **_COMMON)
settings.register_profile("dev", max_examples=25, **_COMMON)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    """La semilla de Hypothesis queda fija y visible en toda corrida (NFR-U7-42): `--hypothesis-seed=N` la repite."""
    if hypothesis_core.global_force_seed is None:
        hypothesis_core.global_force_seed = secrets.randbelow(2**32)


def pytest_report_header() -> str:
    return f"hypothesis profile: {os.environ.get('HYPOTHESIS_PROFILE', 'dev')}, seed: {hypothesis_core.global_force_seed}"


@pytest.fixture(scope="session")
def reference_release(tmp_path_factory: pytest.TempPathFactory) -> Release:
    """La entrega real de U5 (casos RT-4, umbral de confianza calibrado), una sola vez por sesion; como en `model-serving`."""
    return run_release(tmp_path_factory.mktemp("release"))
