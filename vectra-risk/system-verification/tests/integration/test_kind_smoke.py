"""El humo de kind (`docs/kind/humo.py`) contra dobles (U12-T06, CA-6).

El login corre contra el Keycloak real de Testcontainers de U12-T02 (con el realm de kind) y el flujo contra los dobles del gateway y del BFF de U12-T02 (`LightGateway`, validado contra el contrato).
Lo que se comprueba: `login` imprime los claims de los cinco usuarios y ningun token; un `iss` distinto del publico se informa como fallo; `flujo` informa el estado de cada llamada y falla si el caso no
llega a `listo` en el plazo (reloj inyectado); un 401 nombra su destino; `consola` cuenta un `securitypolicyviolation` provocado; y `guard` niega un host que no es de kind sin ninguna solicitud.
Nada queda en disco. Lo que **no** demuestra: que funcione en kind (eso es de la plantilla del operador).
"""

from __future__ import annotations

import http.server
import importlib.util
import io
import re
import sys
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
from contract_world import BFF_SPEC, LightGateway
from external_paths import use_u10_doubles
from fake_clock import FakeClock
from keycloak_tc import KeycloakStack
from pydantic import RootModel
from u5_delivery import make_delivery
from vault_double import ADDR, TOKEN, VaultDouble
from vectra_contracts.models.monitoring import FreezeSummary

from vectra_verification import guard
from vectra_verification.clock import Clock
from vectra_verification.credentials import USERS, Credentials
from vectra_verification.evidence import ensure_clean
from vectra_verification.simulator import read_delivery

pytestmark = pytest.mark.integration
HUMO_PATH = Path(__file__).resolve().parents[2] / "docs" / "kind" / "humo.py"
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.")
_WINDOWS: dict[
    str, int
] = {}  # una sola memoria de ventanas TOTP para todos los clientes de la prueba: Keycloak rechaza un codigo reusado en su ventana de 30 s

use_u10_doubles()
import bff_builders  # noqa: E402, I001


def load_humo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("humo_kind", HUMO_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # los dataclass de `humo.py` buscan su modulo aqui
    spec.loader.exec_module(module)
    return module


humo = load_humo()


class PollClock(Clock):
    """El reloj real, salvo en los sondeos: un `sleep` corto solo avanza `monotonic()` (se anota y no duerme); uno largo (la espera de la ventana TOTP, que Keycloak mide con su propio reloj) duerme de verdad."""

    def __init__(self) -> None:
        self.offset = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return time.monotonic() + self.offset

    def sleep(self, seconds: float) -> None:
        if seconds >= 10:
            time.sleep(seconds)
        elif seconds > 0:
            self.sleeps.append(seconds)
            self.offset += seconds


class Gateway(LightGateway):
    """`LightGateway` mas `GET /api/console/freezes` (la lectura de `cumplimiento-1`), validado contra el contrato."""

    def _routes(self) -> list[Any]:
        return [*super()._routes(), ("/api/console/freezes", ("GET", self._freezes))]

    def _freezes(self, request: httpx.Request, template: str) -> httpx.Response:
        return self._reply(BFF_SPEC, "GET", template, 200, [], RootModel[list[FreezeSummary]])


@pytest.fixture(scope="module")
def delivery(tmp_path_factory: pytest.TempPathFactory) -> Any:
    directory = tmp_path_factory.mktemp("u12t06-delivery")
    make_delivery(directory, n_rows=2000)
    return read_delivery(directory, datetime.now(UTC))


def real_world(
    keycloak: KeycloakStack, *, transport: httpx.BaseTransport | None = None, clock: Any = None
) -> Any:
    args = humo.parser({}).parse_args(
        [
            "login",
            "--issuer",
            keycloak.issuer,
            "--gateway-host",
            keycloak.host,
            "--ca-file",
            str(keycloak.pki.ca_file),
        ]
    )
    world = humo.build_world(
        args,
        {"VAULT_ADDR": ADDR, "VAULT_TOKEN": TOKEN},
        vault_transport=keycloak.vault(),
        transport=transport,
        clock=clock,
    )
    world.oidc._last_window = _WINDOWS  # noqa: SLF001
    return world


def run(argv: list[str], keycloak: KeycloakStack, **kw: Any) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    world = real_world(keycloak, transport=kw.pop("transport", None), clock=kw.pop("clock", None))
    code = humo.main(
        [
            *argv,
            "--issuer",
            keycloak.issuer,
            "--gateway-host",
            keycloak.host,
            "--ca-file",
            str(keycloak.pki.ca_file),
        ],
        {},
        out=out,
        err=err,
        world=world,
        **kw,
    )
    return code, out.getvalue(), err.getvalue()


# --- login ------------------------------------------------------------------------------------------------------------------------------------------


def test_login_prints_the_claims_of_the_five_users_and_no_token(
    keycloak: KeycloakStack, real_environment: guard.Environment
) -> None:
    code, out, err = run(["login"], keycloak)
    assert code == 0, out + err
    for user in USERS:
        line = next(line for line in out.splitlines() if f" {user}:" in line)
        assert (
            line.startswith("OK")
            and f"iss={real_environment.issuer}" in line
            and "acr=mfa" in line
            and "'console-bff'" in line
        )
    assert "roles=['cro']" in out and "roles=['ingeniero_riesgo']" in out and "roles=['cumplimiento']" in out
    assert not JWT.search(out + err)
    credentials = Credentials(real_environment, ADDR, TOKEN, keycloak.vault())
    for user in USERS:
        credentials.user_password(user)
        credentials.user_totp_seed(user)
    ensure_clean(out + err, credentials.secret_values())


class FakeSession:
    def __init__(self, claims: dict[str, Any], acr: str | None = "mfa") -> None:
        self.claims, self.acr, self.auth_time = claims, acr, datetime(2026, 11, 13, tzinfo=UTC)


class FakeOidc:
    def __init__(self, claims: dict[str, Any], acr: str | None = "mfa") -> None:
        self._claims, self._acr = claims, acr

    def login(self, user: str) -> FakeSession:
        return FakeSession(self._claims, self._acr)

    def close(self) -> None:
        return None


def fake_world(claims: dict[str, Any], acr: str | None = "mfa") -> Any:
    credentials = Credentials(guard.KIND, ADDR, TOKEN, VaultDouble("secret", {}))
    return humo.World(guard.KIND, FakeOidc(claims, acr), credentials, FakeClock(), None, False, lambda: None)


@pytest.mark.parametrize(
    ("claims", "acr", "needle"),
    [
        (
            {"iss": "https://otro.example/auth/realms/vectra", "aud": ["console-bff"], "roles": ["analista"]},
            "mfa",
            "iss distinto del publico",
        ),
        ({"iss": guard.KIND.issuer, "aud": ["otro"], "roles": ["analista"]}, "mfa", "aud sin console-bff"),
        ({"iss": guard.KIND.issuer, "aud": ["console-bff"], "roles": []}, "mfa", "sin el rol"),
        (
            {"iss": guard.KIND.issuer, "aud": ["console-bff"], "roles": ["analista"]},
            "pwd",
            "acr distinto de mfa",
        ),
    ],
)
def test_login_reports_a_token_that_is_not_the_public_one_as_a_failure(
    claims: dict[str, Any], acr: str, needle: str
) -> None:
    out = io.StringIO()
    code = humo.login(fake_world(claims, acr), out)
    assert code == 1 and needle in out.getvalue() and out.getvalue().count("FALLA") == len(USERS)


def test_login_explains_an_oidc_error_with_what_to_look_at() -> None:
    class Failing(FakeOidc):
        def login(self, user: str) -> FakeSession:
            raise humo.OidcError("token_issuer_not_allowed")

    world = fake_world({})
    world.oidc = Failing({})
    out = io.StringIO()
    assert humo.login(world, out) == 1
    assert "token_issuer_not_allowed: el iss del token no es el publico" in out.getvalue()


# --- flujo -------------------------------------------------------------------------------------------------------------------------------------------


def test_flujo_reports_the_status_of_each_call_and_ends_with_a_decision_and_an_ack(
    keycloak: KeycloakStack, delivery: Any
) -> None:
    light = Gateway()
    code, out, err = run(["flujo"], keycloak, transport=light, population=delivery)
    assert code == 0, out + err
    assert "caso listo con registry_entry_id" in out and "decision registrada con ack" in out
    assert (
        "  200 POST /api/intake/v1/intake/applications" in out
        and "  200 GET /api/console/models" in out
        and "  200 GET /api/console/freezes" in out
    )
    assert "  200 POST /api/console/cases/{id}/decision" in out
    assert len(light.intake_keys) == 1 and light.decision_posts
    assert not JWT.search(out + err)


def test_flujo_fails_when_the_case_never_reaches_listo_within_the_plazo_with_an_injected_clock(
    keycloak: KeycloakStack, delivery: Any
) -> None:
    light = Gateway()
    light.auto_ready = False
    clock = PollClock()
    code, out, _ = run(
        ["flujo", "--timeout", "20"], keycloak, transport=light, population=delivery, clock=clock
    )
    assert code == 1 and "FALLA el caso no llego a listo en 20 s: quedo en en_evaluacion" in out
    assert not light.decision_posts and sum(clock.sleeps) >= 20


def test_flujo_a_401_names_the_destination_that_rejects_the_token(
    keycloak: KeycloakStack, delivery: Any
) -> None:
    light = Gateway()
    light.status_override["GET /api/console/models"] = 401
    code, out, _ = run(["flujo"], keycloak, transport=light, population=delivery)
    assert code == 1
    assert "FALLA 401 en GET /api/console/models: el destino governance-service rechaza el token" in out


def test_flujo_a_429_from_the_gateway_is_a_failure(keycloak: KeycloakStack, delivery: Any) -> None:
    light = Gateway()
    light.intake_script.append((429, {}))
    code, out, _ = run(["flujo"], keycloak, transport=light, population=delivery)
    assert code == 1 and "FALLA 429 en POST /api/intake/v1/intake/applications" in out


def test_modelos_prints_only_the_ids_and_states(keycloak: KeycloakStack) -> None:
    light = Gateway()
    light.models = {
        "mv-ref": bff_builders.model_version("mv-ref", "activo"),
        "mv-p": bff_builders.model_version("mv-p", "congelado"),
    }
    code, out, _ = run(["modelos"], keycloak, transport=light)
    assert code == 0
    assert (
        out.strip()
        == '[{"model_version_id": "mv-ref", "state": "activo"}, {"model_version_id": "mv-p", "state": "congelado"}]'
    )


# --- guard -------------------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("issuer", "host"),
    [
        ("https://vectra.banco.example/auth/realms/vectra", "vectra.banco.example"),
        ("https://vectra.staging.banco.internal/auth/realms/vectra", "vectra.staging.banco.internal"),
        ("https://vectra.localtest.me/auth/realms/vectra", "otro.localtest.me"),
    ],
)
def test_guard_denies_a_host_that_is_not_kind_without_any_request(issuer: str, host: str) -> None:
    vault = VaultDouble("secret", {})
    out, err = io.StringIO(), io.StringIO()
    code = humo.main(
        ["login", "--issuer", issuer, "--gateway-host", host],
        {"VAULT_ADDR": ADDR, "VAULT_TOKEN": TOKEN},
        out=out,
        err=err,
        vault_transport=vault,
    )
    assert code == 3 and "LA HERRAMIENTA SE NIEGA" in err.getvalue()
    assert vault.count == 0 and out.getvalue() == ""


def test_without_the_vault_session_it_says_so_and_exits_2() -> None:
    out, err = io.StringIO(), io.StringIO()
    assert humo.main(["login"], {}, out=out, err=err) == 2 and "VAULT_ADDR" in err.getvalue()


def test_nothing_is_written_to_disk(
    keycloak: KeycloakStack, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    run(["login"], keycloak)
    assert list(tmp_path.iterdir()) == []


# --- consola -----------------------------------------------------------------------------------------------------------------------------------------

LOGIN_PAGE = "<form method=post action=/auth/login><input name=username><input name=password type=password><button type=submit>x</button></form>"
OTP_PAGE = "<form method=post action=/auth/otp><input name=otp><button type=submit>x</button></form>"
APP_PAGE = "<html><body>consola{extra}</body></html>"


class Spa(http.server.BaseHTTPRequestHandler):
    """Una SPA de mentira detras de un login de dos pasos. `mode`: `limpia`, `csp` (una pagina que viola su propia politica), `sin-cookie` o `recarga-al-login`."""

    mode = "limpia"
    loads = 0

    def log_message(self, *args: Any) -> None:
        return None

    def reply(self, status: int, body: str = "", headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/":
            return self.reply(302, headers={"Location": "/auth/login"})
        if path == "/auth/login":
            return self.reply(200, LOGIN_PAGE)
        if path == "/callback":
            return self.reply(302, headers={"Location": "/casos"})
        Spa.loads += 1
        if (
            self.mode == "recarga-al-login" and Spa.loads > 1
        ):  # la segunda carga es la recarga: la sesion se perdio
            return self.reply(302, headers={"Location": "/auth/login"})
        headers = {"Content-Security-Policy": "default-src 'self'; script-src 'self'"}
        if self.mode != "sin-cookie":
            headers["Set-Cookie"] = "vectra-spa-route=abc; Path=/"
        extra = "<script>window.inline = 1</script>" if self.mode == "csp" else ""
        self.reply(200, APP_PAGE.format(extra=extra), headers)

    def do_POST(self) -> None:  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path == "/auth/login":
            return self.reply(200, OTP_PAGE)
        return self.reply(302, headers={"Location": "/callback?code=1&state=2"})


@pytest.fixture
def spa() -> Iterator[Any]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Spa)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


class OtpOidc:
    def otp_code(self, user: str) -> str:
        return "123456"

    def close(self) -> None:
        return None


def test_consola_always_launches_chromium_with_its_sandbox() -> None:
    options = humo.launch_options(["--ignore-certificate-errors-spki-list=abc"])
    assert options["chromium_sandbox"] is True and options["headless"] is True
    assert not any("no-sandbox" in a for a in options["args"])
    assert "no-sandbox" not in HUMO_PATH.read_text(encoding="utf-8")


@pytest.fixture
def host_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """Esta prueba corre en un host que puede no permitir los espacios de nombres de usuario sin privilegios (AppArmor): solo aqui se pide Chromium sin su sandbox. La orden real nunca lo hace
    (`test_consola_always_launches_chromium_with_its_sandbox`); el sandbox de verdad se ejerce en la imagen (U12-T05, CA-4) y en el paso F3 de la guia."""
    monkeypatch.setattr(
        humo,
        "launch_options",
        lambda extra: {"headless": True, "chromium_sandbox": False, "args": list(extra)},
    )


def run_consola(spa_server: Any, mode: str) -> tuple[int, str]:
    Spa.mode, Spa.loads = mode, 0
    vault = VaultDouble(
        "secret",
        {
            "identity/synthetic-users": {
                "SYNTH_ANALISTA_1_PASSWORD": "clave-de-prueba",
                "SYNTH_ANALISTA_1_TOTP_SEED": "JBSWY3DPEHPK3PXP",
            }
        },
    )
    world = humo.World(
        guard.KIND,
        OtpOidc(),
        Credentials(guard.KIND, ADDR, TOKEN, vault),
        FakeClock(),
        None,
        False,
        lambda: None,
    )
    out = io.StringIO()
    url = f"http://127.0.0.1:{spa_server.server_address[1]}/"
    code = humo.main(["consola", "--spa-url", url], {}, out=out, world=world)
    return code, out.getvalue()


def test_consola_logs_in_by_full_redirect_reloads_and_finds_no_violation(
    spa: Any, host_sandbox: None
) -> None:
    code, out = run_consola(spa, "limpia")
    assert code == 0, out
    assert (
        "securitypolicyviolation: 0" in out
        and "cookie vectra-spa-route: presente" in out
        and "clave-de-prueba" not in out
    )


def test_consola_counts_a_provoked_securitypolicyviolation(spa: Any, host_sandbox: None) -> None:
    code, out = run_consola(spa, "csp")
    assert code == 1
    assert "securitypolicyviolation: 2" in out  # una al cargar la pagina y otra al recargarla
    assert "FALLA CSP enforce: script-src" in out


def test_consola_a_missing_affinity_cookie_and_a_reload_that_loses_the_session_are_failures(
    spa: Any, host_sandbox: None
) -> None:
    code, out = run_consola(spa, "sin-cookie")
    assert code == 1 and "cookie vectra-spa-route: AUSENTE" in out
    code, out = run_consola(spa, "recarga-al-login")
    assert code == 1 and "prompt=none" in out
