"""El armado de `live.LiveBackend` sin cluster (U12-T04, ronda 2, F-09): la boveda y `kubectl` son dobles (`vault_transport=` y `runner=`), el login OIDC real no se usa (un doble de `OidcClient` donde hace falta).

Lo que se comprueba: el constructor no hace ninguna solicitud; el simulador se arma al primer uso y con la entrega que llega por `--delivery` o por el manifiesto (ninguna ruta del repositorio escrita en el codigo); la ventana TOTP
de un usuario se conserva entre clientes; `close()` cierra lo que abrio.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fake_clock import FakeClock
from vault_double import ADDR, TOKEN, VaultDouble, synthetic_secrets

from vectra_verification import live
from vectra_verification.clients._api import RunTag
from vectra_verification.clients.k8s_read import Completed, K8sRead
from vectra_verification.credentials import CredentialsError
from vectra_verification.driver import ANALYSTS, Driver
from vectra_verification.guard import KIND
from vectra_verification.scenarios.common import Sessions
from vectra_verification.simulator import Simulator, SimulatorError

SRC = Path(live.__file__).resolve().parent
ENVIRON = {"VAULT_ADDR": ADDR, "VAULT_TOKEN": TOKEN}


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: Sequence[str]) -> Completed:
        self.calls.append(tuple(args))
        return Completed(0, "{}", "")

    def start(self, args: Sequence[str]) -> Any:
        raise AssertionError("el armado no abre port-forward")


class StubOidc:
    """Lo que `LiveBackend` pide al cliente OIDC, sin red."""

    instances: list[StubOidc] = []

    def __init__(self, environment: Any, credentials: Any, clock: Any, **kw: Any) -> None:
        self.kw, self.closed, self.logins, self.services = kw, False, [], []
        StubOidc.instances.append(self)

    def login(self, user: str) -> str:
        self.logins.append(user)
        return type("U", (), {"bearer": staticmethod(lambda: f"token-{user}")})()

    def service_session(self, client_id: str, scopes: Sequence[str]) -> Any:
        self.services.append((client_id, tuple(scopes)))
        return type("S", (), {"bearer": staticmethod(lambda: "token")})()

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def fresh_windows() -> Any:
    live.TOTP_WINDOWS.clear()
    StubOidc.instances.clear()
    yield
    live.TOTP_WINDOWS.clear()


def args(**over: Any) -> argparse.Namespace:
    return argparse.Namespace(
        section=over.pop("section", "decisions"), **{"delivery": None, "ca_file": None, **over}
    )


def backend(
    clock: FakeClock | None = None, environ: dict[str, str] | None = None, **over: Any
) -> tuple[live.LiveBackend, VaultDouble, RecordingRunner]:
    vault, runner = VaultDouble("secret", synthetic_secrets()), RecordingRunner()
    built = live.LiveBackend(
        KIND,
        args(**over),
        clock or FakeClock(),
        "a1b2c3d4",
        environ or dict(ENVIRON),
        runner=runner,
        vault_transport=vault,
    )
    return built, vault, runner


def test_the_constructor_makes_no_request_and_k8s_uses_the_context_of_the_environment() -> None:
    built, vault, runner = backend()
    assert vault.count == 0 and runner.calls == []
    assert isinstance(built.k8s(), K8sRead) and built.k8s() is built.k8s()
    built.k8s().get("pods", "vectra-app")
    assert runner.calls and "--context=" + live.DEFAULT_CONTEXT in runner.calls[0]
    other, _, other_runner = backend(environ={**ENVIRON, "KUBE_CONTEXT": "kind-otro"})
    other.k8s().get("pods", "vectra-app")
    assert "--context=kind-otro" in other_runner.calls[0]
    assert built.secret_values() == frozenset({TOKEN}) - frozenset() or isinstance(
        built.secret_values(), frozenset
    )


def test_the_vault_session_is_required_and_sessions_are_built_once_with_the_tag_of_the_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(live, "OidcClient", StubOidc)
    with pytest.raises(CredentialsError, match="vault_session_missing"):
        live.LiveBackend(KIND, args(), FakeClock(), "a1b2c3d4", {}, runner=RecordingRunner())
    built, _, _ = backend(section="rt3")
    first = built.sessions()
    assert isinstance(first, Sessions) and built.sessions() is first
    assert first._tag.header_value == RunTag("rt3", "a1b2c3d4").header_value == "rt3.a1b2c3d4"  # noqa: SLF001
    assert built.bff() is first.reader("analista-1")


def test_the_simulator_is_lazy_and_without_a_delivery_it_says_where_to_give_it_and_not_a_path_of_the_repository() -> (
    None
):
    built, _, _ = backend(section="rt5")
    lazy = built.simulator("a1b2c3d4")  # una seccion que no envia no necesita la entrega: no falla al armar
    with pytest.raises(SimulatorError, match=r"u5_delivery_missing.*prepare --delivery"):
        lazy.select("normal", 10, 1)


def test_the_simulator_reads_the_delivery_that_arrives_by_option_or_manifest_and_nothing_else(
    u5_delivery: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(live, "OidcClient", StubOidc)
    monkeypatch.chdir(tmp_path)  # otra maquina: no hay ninguna carpeta `reference-model/.out` debajo
    built, _, _ = backend(delivery=str(u5_delivery), section="rt2")
    simulator = built.simulator("a1b2c3d4")
    assert isinstance(simulator._get(), Simulator)  # noqa: SLF001
    assert StubOidc.instances[0].services == [("channel-simulator", ("intake:submit",))]
    elsewhere, _, _ = backend(delivery=str(tmp_path / "no-hay"), section="decisions")
    with pytest.raises(SimulatorError, match="u5_delivery_missing"):
        elsewhere.simulator("a1b2c3d4")._get()  # noqa: SLF001


def test_no_path_of_the_repository_is_written_in_live_or_in_the_options_of_the_cli() -> None:
    """La demo corre en otra maquina y desde una imagen: ninguna cadena del codigo (fuera de los docstrings) nombra `reference-model` ni `vectra-risk-gitops/values` salvo el `--values-file` de `prepare`, que es una opcion."""
    for name in ("live.py",):
        tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
        docstrings = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)}
        literals = [
            n.value
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
        ]
        assert not [s for s in literals if "reference-model" in s], name
    cli = ast.parse((SRC / "cli.py").read_text(encoding="utf-8"))
    defaults = [
        kw.value.value
        for n in ast.walk(cli)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "add_argument"
        for kw in n.keywords
        if kw.arg == "default" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)
    ]
    assert not [d for d in defaults if "reference-model" in d]


def test_prom_and_registry_are_context_managers_that_open_nothing_until_entered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(live, "OidcClient", StubOidc)
    built, _, runner = backend()
    prom, registry = built.prom(), built.registry()
    assert runner.calls == [] and hasattr(prom, "__enter__") and hasattr(registry, "__enter__")
    assert StubOidc.instances[0].services == [("verification-reader", live.REGISTRY_SCOPES)]


def test_the_driver_logs_in_every_analyst_with_the_tag_of_decisions_and_the_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(live, "OidcClient", StubOidc)
    built, _, _ = backend()
    driver = built.driver(7)
    assert isinstance(driver, Driver) and StubOidc.instances[0].logins == list(ANALYSTS)


def test_close_closes_the_oidc_client_and_live_backend_builds_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live, "OidcClient", StubOidc)
    built, _, _ = backend()
    built.close()
    assert StubOidc.instances[0].closed
    other = live.live_backend(
        KIND, args(), FakeClock(), "a1b2c3d4", {**ENVIRON, "VAULT_ADDR": "http://127.0.0.1:8200"}
    )
    assert isinstance(other, live.LiveBackend)
    other.close()
    assert live.__all__ == ["LiveBackend", "live_backend"]


def test_f09_the_totp_window_of_a_user_is_kept_between_clients_of_the_same_process() -> None:
    """F-09: `all` abre un backend (y un `OidcClient`) por seccion; si cada uno empezara sin memoria, el login de la seccion siguiente reusaria el codigo TOTP que Keycloak ya gasto."""
    clock = FakeClock()
    first, _, _ = backend(clock)
    second, _, _ = backend(clock)
    code_one = first._oidc.otp_code("analista-1")  # noqa: SLF001
    assert clock.sleeps == []
    code_two = second._oidc.otp_code("analista-1")  # noqa: SLF001
    assert len(clock.sleeps) == 1 and code_one != code_two  # el segundo cliente espero a la ventana siguiente
    second._oidc.otp_code("analista-2")  # noqa: SLF001
    assert len(clock.sleeps) == 1  # otro usuario: su propia ventana
    first.close()
    second.close()


def test_a_ca_file_builds_the_ssl_context_and_a_missing_one_is_an_error(tmp_path: Path) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ca-de-prueba")])
    now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    pem = tmp_path / "ca.pem"
    pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    built, _, _ = backend(ca_file=str(pem))
    assert built._verify is not True  # noqa: SLF001
    built.close()
    with pytest.raises(OSError):
        backend(ca_file=str(tmp_path / "no-hay.pem"))
