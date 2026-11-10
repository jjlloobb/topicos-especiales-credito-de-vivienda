"""Perfiles de Hypothesis de U9 (NFR-U9-52: perfil `ci` con 500 ejemplos y semilla impresa), iguales a los de U0."""

import os
import random

import pytest
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


#: La semilla de las propiedades (NFR-U9-52: «semilla impresa»): `HYPOTHESIS_SEED` o `--hypothesis-seed` para repetir una
#: corrida; si no, una nueva por corrida. Se imprime en la cabecera para poder reproducir un fallo.
_seed: list[int] = []


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    given = config.getoption("hypothesis_seed", default=None)
    seed = (
        int(given)
        if given is not None
        else int(os.environ.get("HYPOTHESIS_SEED", random.SystemRandom().randrange(2**32)))
    )
    config.option.hypothesis_seed = str(seed)
    _seed.append(seed)


def pytest_report_header() -> str:
    return f"hypothesis profile: {_profile}, hypothesis seed: {_seed[0] if _seed else 'n/a'}"


def pytest_runtest_setup(item: pytest.Item) -> None:
    """El tipo de proceso (`service` o `batch`) es global: cada prueba parte limpia (las del servicio crean apps; las del CronJob,
    clientes sin breaker)."""
    from vectra_common import process

    process.reset_for_tests()
