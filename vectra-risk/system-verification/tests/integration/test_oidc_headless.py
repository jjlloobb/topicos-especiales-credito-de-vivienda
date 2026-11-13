"""CA-3: login y step-up sin navegador visible contra un Keycloak real con el realm de kind (U12 Paso 5; INF-U12-03; NFR-U12-04; BR-U12-03; P-1).

Keycloak y keycloak-config-cli en Testcontainers (`keycloak_tc`); las credenciales llegan por `Credentials` y el doble de la boveda. El host es dinamico (`127.0.0.1:<puerto>`): el emisor y los
`redirect_uri` de kind se atan en `unit/test_oidc_flow.py`. Una sola espera real (la ventana TOTP de 30 s): el reloj de Keycloak no se puede inyectar. Los rojos estan en la bitacora.
"""

import copy
import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
import pytest
from keycloak_tc import KeycloakStack
from vault_double import TOKEN

from vectra_verification import guard
from vectra_verification.clients.oidc import ASSERTION_TYPE, HeadlessForm, OidcClient, OidcError
from vectra_verification.clock import Clock
from vectra_verification.credentials import Credentials

pytestmark = pytest.mark.integration
STARTED = datetime.now(UTC)
VAULT_ADDR = "http://vault.test"


@pytest.fixture(scope="module")
def credentials(keycloak: KeycloakStack, real_environment: guard.Environment) -> Credentials:
    return Credentials(real_environment, VAULT_ADDR, TOKEN, keycloak.vault())


_WINDOWS: dict[
    str, int
] = {}  # la memoria de ventanas TOTP se comparte entre pruebas: en la herramienta hay un solo cliente; aqui Playwright admite uno por hilo y se crea uno por prueba


@pytest.fixture
def client(
    keycloak: KeycloakStack, real_environment: guard.Environment, credentials: Credentials
) -> Iterator[OidcClient]:
    oidc = OidcClient(real_environment, credentials, Clock(), ca_file=keycloak.pki.ca_file)
    oidc._last_window = _WINDOWS  # noqa: SLF001
    yield oidc
    oidc.close()


def test_login_of_analista_1_gives_a_token_with_its_role(
    client: OidcClient, real_environment: guard.Environment
) -> None:
    session = client.login("analista-1")
    claims = session.claims
    assert "analista" in claims["roles"] and claims["azp"] == "vectra-console"
    assert (
        "console-bff" in claims["aud"] and claims["iss"] == real_environment.issuer and claims["acr"] == "mfa"
    )


def test_step_up_of_cumplimiento_1_has_mfa_and_a_recent_auth_time_and_uses_the_stepup_callback(
    client: OidcClient,
) -> None:
    session = client.step_up("cumplimiento-1")
    assert session.acr == "mfa" and session.step_up
    assert session.auth_time is not None and session.auth_time >= STARTED.replace(microsecond=0)
    assert (datetime.now(UTC) - session.auth_time).total_seconds() <= 900
    assert client.redirect_uri(True).endswith("/stepup-callback")


def test_the_navigation_to_the_redirect_uri_is_aborted_and_no_request_goes_out(client: OidcClient) -> None:
    form = client._form_driver()
    assert isinstance(form, HeadlessForm)
    client.login("analista-2")
    assert form.redirect_requests_finished == 0  # ni `/callback` ni `/stepup-callback` llegaron a la red


def test_an_altered_state_is_an_error_without_exchanging_the_code(client: OidcClient) -> None:
    form = client._form_driver()
    assert isinstance(form, HeadlessForm)
    original = form.submit

    def tampered(authorize_url: str, redirect_uri: str, username: str, password, otp) -> str:  # type: ignore[no-untyped-def]
        url = original(authorize_url, redirect_uri, username, password, otp)
        return re.sub(r"state=[^&]+", "state=alterado", url)

    before = client.token_requests
    form.submit = tampered  # type: ignore[method-assign]
    try:
        with pytest.raises(OidcError, match="state_mismatch"):
            client.login("ingeniero-1")
    finally:
        form.submit = original  # type: ignore[method-assign]
    assert client.token_requests == before


def test_a_nonce_that_does_not_match_is_an_error_and_no_token_stays(client: OidcClient) -> None:
    real_request = client.authorization_request

    def wrong_nonce(step_up: bool):  # type: ignore[no-untyped-def]
        request = real_request(step_up)
        from vectra_verification.clients.oidc import AuthorizationRequest
        from vectra_verification.credentials import Secret

        return AuthorizationRequest(
            request.url, request.redirect_uri, request.state, Secret("otro-nonce"), request.code_verifier
        )

    client.authorization_request = wrong_nonce  # type: ignore[method-assign]
    try:
        with pytest.raises(OidcError, match="nonce_mismatch"):
            client.login("cro-1")
    finally:
        client.authorization_request = real_request  # type: ignore[method-assign]


def test_every_playwright_context_is_closed_also_after_a_failed_login(
    keycloak: KeycloakStack, real_environment: guard.Environment
) -> None:
    vault = keycloak.vault()
    vault.secrets = copy.deepcopy(vault.secrets)
    vault.secrets["identity/synthetic-users"]["SYNTH_CRO_1_PASSWORD"] = "contrasena-equivocada-2"
    creds = Credentials(real_environment, VAULT_ADDR, TOKEN, vault)
    clone = OidcClient(real_environment, creds, Clock(), ca_file=keycloak.pki.ca_file)
    clone._last_window = _WINDOWS  # noqa: SLF001
    try:
        with pytest.raises(OidcError, match="login_rejected"):
            clone.login("cro-1")  # un solo intento: el realm bloquea para siempre al quinto fallo
        form = clone._form
        assert isinstance(form, HeadlessForm) and form.contexts_opened == form.contexts_closed == 1
    finally:
        clone.close()


def test_no_password_seed_or_token_is_on_disk_after_a_login_and_before_closing_the_browser(
    keycloak: KeycloakStack,
    real_environment: guard.Environment,
    credentials: Credentials,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work = keycloak.workdir.parent / f"disk-{os.getpid()}"
    for name in ("home", "tmp", "cwd"):
        (work / name).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv(
        "PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ".cache" / "ms-playwright")
    )  # antes de cambiar HOME
    monkeypatch.setenv("HOME", str(work / "home"))
    monkeypatch.setenv("TMPDIR", str(work / "tmp"))
    monkeypatch.chdir(work / "cwd")
    isolated = OidcClient(real_environment, credentials, Clock(), ca_file=keycloak.pki.ca_file)
    isolated._last_window = _WINDOWS  # noqa: SLF001
    try:
        session = isolated.login("ingeniero-1")
        needles = [
            credentials.user_password("ingeniero-1").reveal(),
            credentials.user_totp_seed("ingeniero-1").reveal(),
            session.tokens.access_token.reveal(),
        ]
        needles += [
            t.reveal() for t in (session.tokens.refresh_token, session.tokens.id_token) if t is not None
        ]
        found: list[str] = []
        scanned = 0
        for path in work.rglob("*"):
            if path.is_file():
                scanned += 1
                data = path.read_bytes()
                if any(n.encode() in data for n in needles) or re.search(
                    rb"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.", data
                ):
                    found.append(path.name)
        assert scanned > 0 and found == []
    finally:
        isolated.close()
        import shutil

        shutil.rmtree(work, ignore_errors=True)


def test_totp_reuse_the_second_login_of_the_same_user_waits_for_the_next_window_and_passes(
    client: OidcClient,
) -> None:
    first = client.login("analista-1")
    second = client.login("analista-1")  # la unica espera real: la ventana de 30 s de Keycloak
    assert first.acr == second.acr == "mfa"


def test_login_then_step_up_of_cumplimiento_1_back_to_back_as_in_rt2(client: OidcClient) -> None:
    client.login("cumplimiento-1")
    assert client.step_up("cumplimiento-1").step_up


def test_refresh_gives_a_valid_token_and_keeps_the_new_refresh_token(client: OidcClient) -> None:
    session = client.login("analista-2")
    old = session.tokens.refresh_token
    assert old is not None
    session.refresh()
    assert (
        session.refreshes == 1
        and session.tokens.refresh_token is not None
        and session.tokens.refresh_token.reveal() != old.reveal()
    )
    assert "analista" in session.claims["roles"]
    with pytest.raises(OidcError):  # el realm rota: el anterior ya no sirve
        client.exchange_refresh(old)


def test_service_tokens_of_verification_reader_and_channel_simulator(client: OidcClient) -> None:
    reader = client.service_session(
        "verification-reader", ["registry:read:metrics", "registry:read:monitoring"]
    )
    reader.bearer()
    scopes = set(reader.claims["scope"].split())
    assert {"registry:read:metrics", "registry:read:monitoring"} <= scopes
    audiences = reader.claims["aud"] if isinstance(reader.claims["aud"], list) else [reader.claims["aud"]]
    assert "decision-registry-service" in audiences
    simulator = client.service_session("channel-simulator", ["intake:submit"])
    simulator.bearer()
    assert (
        simulator.claims["azp"] == "channel-simulator"
        and "intake:submit" in simulator.claims["scope"].split()
    )


def test_red_without_the_scopes_the_reader_token_has_no_audience(client: OidcClient) -> None:
    bare = client.service_session("verification-reader", [])
    bare.bearer()
    audiences = bare.claims.get("aud", [])
    audiences = audiences if isinstance(audiences, list) else [audiences]
    assert "decision-registry-service" not in audiences


def test_red_keycloak_rejects_an_assertion_whose_audience_is_another_url(
    client: OidcClient, credentials: Credentials, real_environment: guard.Environment, keycloak: KeycloakStack
) -> None:
    now = int(datetime.now(UTC).timestamp())

    def exchange(aud: str) -> httpx.Response:
        claims = {
            "iss": "channel-simulator",
            "sub": "channel-simulator",
            "aud": aud,
            "jti": os.urandom(8).hex(),
            "iat": now,
            "exp": now + 60,
        }
        assertion = jwt.encode(
            claims, credentials.client_key("channel-simulator").reveal(), algorithm="ES256"
        )
        form = {
            "grant_type": "client_credentials",
            "client_id": "channel-simulator",
            "client_assertion_type": ASSERTION_TYPE,
            "client_assertion": assertion,
            "scope": "intake:submit",
        }
        with httpx.Client(verify=keycloak.ssl_context()) as http:
            return http.post(client.token_url, data=form)

    assert exchange(real_environment.issuer).status_code == 200
    rejected = exchange(
        "https://keycloak.vectra-identity.svc:8443/auth/realms/vectra/protocol/openid-connect/token"
    )
    assert rejected.status_code == 400 and "Invalid token audience" in rejected.text


def test_red_a_wrong_client_or_an_unregistered_redirect_uri_gets_no_login_form(
    client: OidcClient, keycloak: KeycloakStack
) -> None:
    good = client.authorization_request(False).url
    query = {k: v[-1] for k, v in parse_qs(urlsplit(good).query).items()}
    for change in ({"client_id": "otro-cliente"}, {"redirect_uri": f"https://{keycloak.host}/no-registrado"}):
        with httpx.Client(verify=keycloak.ssl_context(), follow_redirects=True) as http:
            response = http.get(f"{client.authorization_url}?{urlencode({**query, **change})}")
        assert 'name="username"' not in response.text and response.status_code in (400, 404)


def test_credentials_come_from_the_vault_double_not_from_test_variables(
    keycloak: KeycloakStack, real_environment: guard.Environment
) -> None:
    """Las credenciales del login salen de la cadena boveda -> `Credentials`: el doble recibe las lecturas, los valores son los generados para el realm y ninguno esta en el entorno del proceso."""
    vault = keycloak.vault()
    creds = Credentials(real_environment, VAULT_ADDR, TOKEN, vault)
    assert vault.count == 0
    password, seed = creds.user_password("analista-1").reveal(), creds.user_totp_seed("analista-1").reveal()
    assert vault.count >= 1 and all(r.url.path.endswith("identity/synthetic-users") for r in vault.requests)
    assert (
        password == keycloak.generated.variables["SYNTH_ANALISTA_1_PASSWORD"]
        and seed == keycloak.generated.variables["SYNTH_ANALISTA_1_TOTP_SEED"]
    )
    assert password not in os.environ.values() and seed not in os.environ.values()
    assert (
        creds.user_password("analista-1").reveal() == password and vault.count == 1
    )  # una lectura del secreto compartido


def test_red_f03_a_tls_failure_in_the_form_is_a_stable_oidc_error_without_the_authorization_url(
    keycloak: KeycloakStack,
    real_environment: guard.Environment,
    credentials: Credentials,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Node (que hace `route.fetch`) sin la CA del entorno: el fallo de TLS no escapa como `playwright.Error` ni deja `state`, `nonce` o `code_challenge` en el mensaje o la traza."""
    import traceback

    from vectra_verification.clients.oidc import server_spki_pin

    monkeypatch.delenv("NODE_EXTRA_CA_CERTS", raising=False)
    pin = server_spki_pin("127.0.0.1", keycloak.port, keycloak.pki.ca_file)
    client = OidcClient(
        real_environment,
        credentials,
        Clock(),
        ca_file=keycloak.pki.ca_file,
        form=HeadlessForm(pin, ca_file=None),
    )
    client._last_window = _WINDOWS  # noqa: SLF001
    requests = []
    real_request = client.authorization_request

    def recording(step_up: bool):  # type: ignore[no-untyped-def]
        requests.append(real_request(step_up))
        return requests[-1]

    client.authorization_request = recording  # type: ignore[method-assign]
    try:
        with pytest.raises(OidcError) as error:
            client.login("cro-1")
        text = "".join(traceback.format_exception(error.value)) + str(error.value)
        (request,) = requests
        assert str(error.value) in ("browser_error", "browser_close_error", "login_timeout")
        for secret in (
            request.state,
            request.nonce.reveal(),
            request.code_verifier.reveal(),
            request.url,
            "code_challenge=",
            "self-signed",
            "Call log",
        ):
            assert secret not in text, secret
    finally:
        client.close()


def test_red_without_the_window_wait_keycloak_itself_rejects_the_reused_totp_code(
    client: OidcClient, credentials: Credentials
) -> None:
    """Rojo de CA-3: sin la espera de la ventana el segundo login lo rechaza **Keycloak**, no un doble. Se espera (real, <= 22 s) a empezar al principio de una ventana para que los dos logins caigan en la misma."""
    import time

    elapsed = time.time() % 30
    if elapsed > 20:
        time.sleep(30 - elapsed + 1)  # la unica otra espera real: alinear el inicio con la ventana
    client.login("analista-2")  # con la memoria de ventanas: espera si el codigo de la ventana ya se uso
    client.otp_code = lambda user: credentials.totp(user, datetime.now(UTC))  # type: ignore[method-assign]  # sin memoria ni espera
    with pytest.raises(OidcError, match="login_rejected"):
        client.login("analista-2")
