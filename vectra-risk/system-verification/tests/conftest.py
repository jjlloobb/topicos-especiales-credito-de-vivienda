"""Perfiles de Hypothesis de U12 (`HYPOTHESIS_PROFILE`: dev, ci, nightly). `ci` = 500 ejemplos; la semilla queda fija e impresa en el
encabezado de pytest tambien en las corridas verdes (NFR-U12-41)."""

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
    """`--hypothesis-seed=N` repite una corrida; sin ella la semilla es nueva y se imprime (NFR-U12-41)."""
    if hypothesis_core.global_force_seed is None:
        hypothesis_core.global_force_seed = secrets.randbelow(2**32)


def pytest_report_header() -> str:
    return f"hypothesis profile: {os.environ.get('HYPOTHESIS_PROFILE', 'dev')}, seed: {hypothesis_core.global_force_seed}"


# --- U12-T02: entorno dinamico (decision del usuario, P-1 (b)) y reloj falso -------------------------------------------------------------------------------
from vectra_verification import guard  # noqa: E402


@pytest.fixture
def dynamic_environment(monkeypatch: pytest.MonkeyPatch) -> guard.Environment:
    """Un `Environment` de prueba (nombre `kind`, host `127.0.0.1:<puerto>`) registrado en `guard.ENVIRONMENTS` solo durante la prueba: la lista real no cambia (F-04: el entorno
    tiene que ser uno de la lista). El emisor y los `redirect_uri` de kind se atan en `test_oidc_flow.py` contra `realm.kind.yaml` y los values del gateway."""
    environment = guard.Environment("kind", "127.0.0.1:34567", "https://127.0.0.1:34567/auth/realms/vectra")
    monkeypatch.setattr(guard, "ENVIRONMENTS", (*guard.ENVIRONMENTS, environment))
    return environment


@pytest.fixture(scope="session")
def u5_delivery() -> "Iterator[Path]":
    """La entrega pequeña de U5 (generador real), una vez por sesion, dentro del worktree."""
    from u5_delivery import SCRATCH, make_delivery, remove

    directory = SCRATCH / f"u5-{os.getpid()}"
    make_delivery(directory)
    yield directory
    remove(directory)
