"""Perfiles de Hypothesis de U11 (`HYPOTHESIS_PROFILE`: dev, ci, nightly). `ci` = 500 ejemplos; la semilla queda fija e impresa en el
encabezado de pytest tambien en las corridas verdes (NFR-U11-31)."""

import logging
import os
import secrets
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import core as hypothesis_core

# Los modulos de apoyo de las pruebas viven junto a este archivo; con `--import-mode=importlib` no estan en `sys.path`.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "doubles"))

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
    """`--hypothesis-seed=N` repite una corrida; sin ella la semilla es nueva y se imprime (NFR-U11-31)."""
    if hypothesis_core.global_force_seed is None:
        hypothesis_core.global_force_seed = secrets.randbelow(2**32)


def pytest_report_header() -> str:
    return f"hypothesis profile: {os.environ.get('HYPOTHESIS_PROFILE', 'dev')}, seed: {hypothesis_core.global_force_seed}"


def pytest_runtest_setup(item: pytest.Item) -> None:
    """El tipo de proceso (`service` o `batch`) es global: cada prueba parte limpia."""
    from vectra_common import process

    process.reset_for_tests()


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    """`vectra_common.logging.configure` reemplaza los manejadores del logger raiz: cada prueba deja el logging como lo encontro."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
