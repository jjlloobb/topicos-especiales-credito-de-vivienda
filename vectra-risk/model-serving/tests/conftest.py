"""Fixtures de U6: la entrega real de U5 (modelo base y paquetes RT-3), una vez por sesion, y los perfiles de Hypothesis."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings
from vectra_reference.adversarial import rt3_cases
from vectra_reference.release import Release, run_release

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
    """La entrega de referencia de U5 (modelo base, AUC minimo exigido), una sola vez por sesion de pruebas."""
    return run_release(tmp_path_factory.mktemp("release"))


@pytest.fixture(scope="session")
def package_dir(reference_release: Release) -> Path:
    return reference_release.package_dir


@pytest.fixture(scope="session")
def rt3_dirs(reference_release: Release, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Los 4 paquetes RT-3 (`RT3-a`..`RT3-d`) que construye U5 a partir del paquete base."""
    out = tmp_path_factory.mktemp("adversarial")
    rt3_cases(reference_release.package_dir, out)
    return {case: out / "rt3" / case for case in ("RT3-a", "RT3-b", "RT3-c", "RT3-d")}


@pytest.fixture
def copy_package(package_dir: Path, tmp_path: Path) -> Callable[[], Path]:
    """Copia del paquete base que una prueba puede alterar sin afectar a las demas."""
    import shutil

    def make() -> Path:
        target = tmp_path / "package"
        shutil.copytree(package_dir, target)
        return target

    return make
