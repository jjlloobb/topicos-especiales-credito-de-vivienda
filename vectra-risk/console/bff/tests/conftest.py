"""Perfiles de Hypothesis de U10 (mismos de `contracts/tests/conftest.py`, NFR-U0-42, 43); `HYPOTHESIS_PROFILE=ci` en `make check`."""

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


# --- fixtures del Bloque C (Pasos 5 a 8): la app real con los dobles de los cinco destinos ---------------------------------
from collections.abc import Callable, Iterator  # noqa: E402
from typing import Any  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from bff_doubles import Doubles  # noqa: E402
from bff_support import Bff, EventLog  # noqa: E402
from bff_world import populate  # noqa: E402
from vectra_common import logging as vlog  # noqa: E402

from console_bff.app import build  # noqa: E402


@pytest.fixture(autouse=True)
def strict_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    """PBT-U0-07 en modo strict: un campo fuera de la allowlist hace fallar la prueba (`VECTRA_LOG_STRICT=1`)."""
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> EventLog:
    log = EventLog()
    original = vlog.log_event

    def recording(event: Any, **fields: Any) -> None:
        log.records.append((event.value, dict(fields)))
        original(event, **fields)

    monkeypatch.setattr(vlog, "log_event", recording)
    return log


@pytest.fixture
def doubles() -> Doubles:
    world = Doubles()
    populate(world)
    return world


@pytest.fixture
def make_bff(doubles: Doubles) -> Iterator[Callable[..., Bff]]:
    """Fabrica de apps con los dobles; las cierra al terminar (cada prueba crea sus propios clientes)."""
    from bff_tokens import authenticator

    made: list[Bff] = []

    def factory(**kwargs: Any) -> Bff:
        app = build(
            doubles.urls(),
            authenticator=kwargs.pop("authenticator", authenticator()),
            transports=doubles.transports(),
            **kwargs,
        )
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://bff.test"
        )
        made.append(Bff(client, app, doubles))
        return made[-1]

    yield factory
    import asyncio

    async def close() -> None:
        for item in made:
            await item.client.aclose()
            await item.app.state.upstreams.aclose()

    asyncio.run(close())


@pytest.fixture
async def bff(make_bff: Callable[..., Bff]) -> Bff:
    return make_bff()
