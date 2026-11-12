"""Paso 8 (CA-6): armado de la app, configuracion por entorno, sondas y apagado ordenado (INF-U10-01; NFR-U10-60).

Las sondas son solo del proceso (`readiness=None`): `/readyz` es 200 con los cinco destinos caidos y sus circuitos abiertos.
El arranque como proceso real esta en `test_service_shutdown.py`.
"""

import signal
from collections.abc import Iterator

import bff_tokens
import httpx
import pytest
from bff_support import Bff

from console_bff import app as bff_app
from console_bff.clients import DESTINATIONS

ENV = {
    "VECTRA_OIDC_ISSUER": "http://kc.test/auth/realms/vectra",
    "VECTRA_JWKS_URL": "http://kc.test/certs",
    "VECTRA_CASE_URL": "http://case.test",
    "VECTRA_GOVERNANCE_URL": "http://gov.test",
    "VECTRA_REGISTRY_URL": "http://reg.test",
    "VECTRA_EXPLAINABILITY_URL": "http://exp.test",
    "VECTRA_BIAS_URL": "http://bias.test",
}


@pytest.fixture(autouse=True)
def restore_sigterm() -> Iterator[None]:
    """`main()` instala su manejador de SIGTERM en el proceso de pytest: se restaura al terminar cada prueba."""
    previous = signal.getsignal(signal.SIGTERM)
    yield
    signal.signal(signal.SIGTERM, previous)


async def test_readyz_and_healthz_are_200_with_the_five_destinations_down_and_their_circuits_open(
    bff: Bff,
) -> None:
    """INF-U10-01: la readiness no mira a los destinos (cada uno tiene su circuito): 200 aunque todos esten abiertos."""
    from vectra_common import deps
    from vectra_common.errors import DependencyUnavailable

    for double in bff.doubles.transports().values():
        double.down()
    upstreams = bff.app.state.upstreams
    for name in DESTINATIONS:
        for _ in range(20):  # las 20 llamadas fallidas de NFR-U10-30 abren el circuito de ese destino
            with pytest.raises(DependencyUnavailable):
                await deps.call(upstreams.clients[name], "GET", "/v1/x", timeout=1.0)
    assert {name: upstreams.clients[name].breaker.state.name for name in DESTINATIONS} == dict.fromkeys(
        DESTINATIONS, "OPEN"
    )
    token = bff_tokens.bearer(bff_tokens.ROLES)
    assert (
        await bff.client.get("/api/console/cases", headers=token)
    ).status_code == 503  # y por eso las vistas dan 503
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=bff.app.state.ops_app), base_url="http://ops.test"
    ) as ops:
        assert (await ops.get("/readyz")).status_code == 200
        assert (await ops.get("/healthz")).status_code == 200


def test_the_required_variables_are_the_two_of_u0_and_the_five_destination_urls() -> None:
    assert set(bff_app.REQUIRED) == set(ENV)
    assert set(bff_app.URL_VARIABLES) == set(DESTINATIONS)
    assert bff_app.OPTIONAL == ("VECTRA_CA_BUNDLE",)


@pytest.mark.parametrize("missing", sorted(ENV))
def test_a_missing_variable_stops_the_start_and_the_message_names_it(missing: str) -> None:
    env = {k: v for k, v in ENV.items() if k != missing}
    with pytest.raises(bff_app.ConfigError, match=missing):
        bff_app.urls_from_env(env)


def test_an_empty_variable_counts_as_missing() -> None:
    with pytest.raises(bff_app.ConfigError, match="VECTRA_BIAS_URL"):
        bff_app.urls_from_env({**ENV, "VECTRA_BIAS_URL": ""})


def test_https_without_a_ca_bundle_does_not_start() -> None:
    with pytest.raises(bff_app.ConfigError, match="VECTRA_CA_BUNDLE"):
        bff_app.urls_from_env({**ENV, "VECTRA_CASE_URL": "https://case.test"})
    assert (
        bff_app.urls_from_env({**ENV, "VECTRA_CASE_URL": "https://case.test", "VECTRA_CA_BUNDLE": "/ca.pem"})[
            "case"
        ]
        == "https://case.test"
    )


def test_the_urls_map_to_the_five_destinations() -> None:
    assert bff_app.urls_from_env(ENV) == {
        "case": "http://case.test",
        "governance": "http://gov.test",
        "registry": "http://reg.test",
        "explainability": "http://exp.test",
        "bias": "http://bias.test",
    }


def test_build_app_reads_the_environment_and_builds_the_30_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    app = bff_app.build_app()
    assert len([r for r in app.router.routes if getattr(r, "methods", None)]) == 30
    assert app.state.ops_app is not None


def test_main_without_a_mandatory_variable_exits_with_2_and_names_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("VECTRA_CASE_URL")
    served: list[object] = []
    monkeypatch.setattr(bff_app, "run_service", served.append)
    with pytest.raises(SystemExit) as stop:
        bff_app.main()
    assert stop.value.code == bff_app.EXIT_CONFIG == 2
    assert "VECTRA_CASE_URL" in capsys.readouterr().err and served == []


def test_main_serves_the_app_with_run_service(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    served: list[object] = []
    monkeypatch.setattr(bff_app, "run_service", served.append)
    bff_app.main()
    assert len(served) == 1 and served[0].state.upstreams is not None  # type: ignore[attr-defined]


def test_main_with_a_contract_violation_exits_with_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from console_bff import object_rules

    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(object_rules, "OBJECT_RULES", {})
    with pytest.raises(SystemExit) as stop:
        bff_app.main()
    assert stop.value.code == 2 and "sin regla declarada" in capsys.readouterr().err


async def test_shutdown_closes_the_five_clients(bff: Bff) -> None:
    """Al apagar (lifespan de la app) se cierran los cinco `DependencyClient` (`aclose`)."""
    upstreams = bff.app.state.upstreams
    assert not any(client._client.is_closed for client in upstreams.clients.values())  # noqa: SLF001
    async with bff.app.router.lifespan_context(bff.app):
        pass
    assert all(client._client.is_closed for client in upstreams.clients.values())  # noqa: SLF001


def test_main_installs_a_sigterm_handler_that_exits_with_code_0(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tras un apagado ordenado uvicorn re-emite la senal con el manejador previo: el de `main` la vuelve un `SystemExit(0)`."""
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(bff_app, "run_service", lambda app: None)
    bff_app.main()
    handler = signal.getsignal(signal.SIGTERM)
    assert handler is bff_app._exit_clean  # noqa: SLF001
    with pytest.raises(SystemExit) as stop:
        handler(signal.SIGTERM, None)  # type: ignore[operator]
    assert stop.value.code == 0
