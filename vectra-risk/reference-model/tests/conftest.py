"""Perfiles de Hypothesis de U5 (NFR-U5-33: perfil `ci` con 500 ejemplos y semilla impresa), iguales a los de U0."""

import importlib.util
import os
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from hypothesis import HealthCheck, settings
from vectra_reference.generate import load_config, with_overrides
from vectra_reference.release import ProxyRelease, Release, run_adversarial, run_proxy_release, run_release

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


@pytest.fixture(scope="session")
def reference_release(tmp_path_factory: pytest.TempPathFactory) -> Release:
    """La entrega completa con la semilla de referencia (Pasos 2 a 5), una sola vez por sesion de pruebas."""
    return run_release(tmp_path_factory.mktemp("release"))


@pytest.fixture(scope="session")
def reference_proxy(reference_release: Release) -> ProxyRelease:
    """Los 5 paquetes de la variante proxy (Paso 6), escritos junto a la entrega de referencia."""
    return run_proxy_release(reference_release)


@pytest.fixture(scope="session")
def reference_adversarial(reference_release: Release) -> dict[str, object]:
    """El conjunto adversarial (Paso 7) escrito en `adversarial/` de la entrega de referencia: su manifiesto."""
    return run_adversarial(reference_release)


@pytest.fixture(scope="session")
def small_release(tmp_path_factory: pytest.TempPathFactory) -> Release:
    """Entrega chica (6 000 filas, sin exigir el AUC minimo) para las pruebas del paquete: tarda segundos."""
    config = with_overrides(load_config(), n_rows=6000)
    return run_release(tmp_path_factory.mktemp("small-release"), config, enforce_min_auc=False)


def _load(name: str) -> ModuleType:
    path = Path(__file__).parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def u4_registration() -> ModuleType:
    """Copia de la validacion de registro de U4 (BR-U4-06), porque U4 todavia no existe (plan de U5, Paso 5)."""
    return _load("u4_registration_copy")


@pytest.fixture(scope="session")
def u4_validate(u4_registration: ModuleType) -> Callable[..., None]:
    return u4_registration.validate_registration  # type: ignore[no-any-return]
