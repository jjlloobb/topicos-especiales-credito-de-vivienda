"""Login y step-up sin navegador visible, refresco y tokens de servicio (U12 Paso 5; INF-U12-03; NFR-U12-04; BR-U12-03).

La herramienta actua como el cliente publico `vectra-console` (U2): Authorization Code con PKCE S256, sin *password grant* (el realm no lo ofrece). Genera `state`,
`nonce` y `code_verifier`; abre la URL de autorizacion en **Chromium sin interfaz con Playwright**, que llena el formulario de Keycloak con la contraseña y el codigo
TOTP; **intercepta** la navegacion al `redirect_uri` registrado antes de salir a la red (la SPA nunca se carga: la respuesta de Keycloak se pide sin seguir la redireccion, se toma `code` y `state` de su `Location` y la navegacion se cierra con un 204); compara
`state` (si no coincide, error **sin** llamar al endpoint de token), canjea `code` con el `code_verifier` y valida el ID token: firma contra el JWKS del realm, `iss` exacto
(`guard.check_token_issuer`), `aud = vectra-console`, `exp`, `nonce` y `acr = mfa`; en el step-up, ademas, `auth_time` de hace `MFA_MAX_AGE` segundos o menos.

Reglas que este modulo cumple y las pruebas fijan:
- Los tokens solo viven en memoria (`TokenSet`, con `Secret`: no salen en `repr()`); ningun mensaje de error lleva un token, una contraseña, un codigo TOTP, el `code`, el
  `code_verifier` ni la URL de retorno. Nada se escribe a disco; el contexto de Playwright se descarta tras cada login, tambien si falla (`finally`).
- Un login fallido **no** se reintenta: el realm bloquea para siempre al quinto fallo (`failureFactor: 5`, `permanentLockout: true`). Una pasada por el formulario y, si
  Keycloak lo rechaza, un error claro.
- Reuso de TOTP: Keycloak rechaza un codigo ya usado en la misma ventana de 30 s. Se guarda, por usuario, la ventana del ultimo codigo usado y, antes de otro login o step-up
  del mismo usuario en esa ventana, se espera a la siguiente **con el reloj inyectado**.
- Vigencia (P-7): `accessTokenLifespan` es 300 s. La sesion renueva con `grant_type=refresh_token` antes de vencer y guarda **el refresh token nuevo** (el realm los rota y
  rechaza uno ya usado); si el refresco falla, hace **un** login nuevo.
- Tokens de servicio: `client_credentials` con `private_key_jwt` ES256. La `aud` de la aserción es el **emisor del entorno** (medido en U02-T21: Keycloak publica un solo emisor
  y rechaza una aserción con la URL interna de token).
- Confianza TLS, lo que de verdad protege cada camino (P-2). Hay **dos** caminos y no son el mismo: (1) los subrecursos de la pagina (CSS, JS, imagenes) los pide Chromium, que solo acepta el
  certificado del servidor del entorno por su huella SPKI (`--ignore-certificate-errors-spki-list`, tomada por una conexion TLS **verificada** con la CA del entorno); (2) las **navegaciones**, incluido el POST con la
  contraseña y el codigo TOTP, las pide `route.fetch` desde el proceso de Playwright (Node), que no usa esa huella: confia en las CA publicas de Node mas la del entorno que se le da por `NODE_EXTRA_CA_CERTS`
  (`ca_file`). Ningun camino acepta un certificado cualquiera ni usa `ignore_https_errors`, y sin la CA el fallo de TLS termina en un `OidcError` (probado con Node sin la CA). Dar la misma CA a los dos caminos en
  la imagen es del Paso 15 (U12-T04). Nunca el modo sin aislamiento de Chromium.
- Un fallo de Playwright (TLS, red, arranque o cierre del contexto) sale como `OidcError` con codigo estable (`browser_error`, `browser_launch_error`, `browser_close_error`): sus mensajes traen la URL de
  autorizacion (`state`, `nonce`, `code_challenge`) y no salen del modulo.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import socket
import ssl
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from playwright.sync_api import Browser, Playwright, Route, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from vectra_verification import guard
from vectra_verification.clock import Clock
from vectra_verification.credentials import Credentials, CredentialsError, Secret
from vectra_verification.guard import Environment, GuardError

CONSOLE_CLIENT: Final = "vectra-console"
CONSOLE_AUDIENCE: Final = "console-bff"
SCOPE: Final = "openid"  # el de la SPA (`console/spa/src/auth/manager.ts`)
CALLBACK: Final = "/callback"
STEP_UP_CALLBACK: Final = "/stepup-callback"
MFA_MAX_AGE: Final = (
    900  # `vectra_contracts.routes.MFA_MAX_AGE`: lo que el BFF exige de `auth_time` en el step-up
)
TOTP_PERIOD: Final = 30
TOTP_MARGIN_SECONDS: Final = 1.0
REFRESH_LEEWAY_SECONDS: Final = 60.0
ASSERTION_LIFETIME_SECONDS: Final = 60
ASSERTION_TYPE: Final = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
SERVICE_CLIENTS: Final = ("channel-simulator", "verification-reader")
ALGORITHMS: Final = ("RS256", "ES256", "PS256")
FORM_TIMEOUT_MS: Final = 30_000
HTTP_TIMEOUT: Final = 20.0


class OidcError(Exception):
    """Fallo del login, del canje o de un token. El mensaje es un codigo estable: nunca lleva un token, una contraseña, un TOTP, el `code`, el `code_verifier` ni la URL de retorno."""


@dataclass(frozen=True)
class TokenSet:
    """Los tokens de una sesion, solo en memoria: `repr()` y `str()` no los muestran."""

    access_token: Secret
    refresh_token: Secret | None
    id_token: Secret | None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def code_challenge(verifier: str) -> str:
    """`BASE64URL(SHA-256(code_verifier))` (RFC 7636, §4.2)."""
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


@dataclass(frozen=True)
class AuthorizationRequest:
    """Lo que se genera en cada login: nada se reusa entre logins. El `code_verifier` y el `nonce` no salen en `repr()`."""

    url: str
    redirect_uri: str
    state: str
    nonce: Secret
    code_verifier: Secret


def _query_of(url: str) -> dict[str, str]:
    return {key: values[-1] for key, values in parse_qs(urlsplit(url).query, keep_blank_values=True).items()}


def server_spki_pin(
    host: str, port: int, ca_file: Path | None
) -> str:  # pragma: no cover - conexion TLS real; la ejercita test_oidc_headless
    """La huella SPKI (base64 de SHA-256) del certificado que presenta `host:port`, tomada por una conexion TLS **verificada** con la CA del entorno."""
    context = ssl.create_default_context(cafile=str(ca_file) if ca_file else None)
    with (
        socket.create_connection((host, port), timeout=HTTP_TIMEOUT) as sock,
        context.wrap_socket(sock, server_hostname=host) as tls,
    ):
        der = tls.getpeercert(binary_form=True)
    if der is None:
        raise OidcError("tls_certificate_missing")
    spki = (
        x509.load_der_x509_certificate(der)
        .public_key()
        .public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    return base64.b64encode(hashlib.sha256(spki).digest()).decode()


class FormDriver:
    """Quien llena el formulario de Keycloak. La implementacion real es `HeadlessForm`; las pruebas sin navegador inyectan otra."""

    def submit(
        self, authorize_url: str, redirect_uri: str, username: str, password: Secret, otp: Callable[[], str]
    ) -> str:
        """Devuelve la URL del `redirect_uri` (con `code` y `state`) a la que Keycloak redirigio. Una sola pasada; sin reintentos."""
        raise NotImplementedError

    def close(self) -> None:
        return None


class HeadlessForm(FormDriver):
    """Chromium sin interfaz con Playwright (API sincrona). Un contexto nuevo por login, cerrado en un `finally`; el navegador se lanza una vez y se cierra en `close()`."""

    def __init__(
        self, spki_pin: str | None, *, ca_file: Path | None = None, timeout_ms: int = FORM_TIMEOUT_MS
    ) -> None:
        self._spki_pin = spki_pin
        self._ca_file = ca_file
        self._timeout_ms = timeout_ms
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.contexts_opened = 0
        self.contexts_closed = 0
        self.rejection_text = ""
        self.redirect_requests_finished = (
            0  # solicitudes al `redirect_uri` que llegaron a completarse: tiene que ser 0 (se abortan)
        )

    def _launch(self) -> Browser:
        if self._browser is None:
            # `route.fetch` (las navegaciones se piden sin seguir redirecciones) la hace el proceso de Playwright, no Chromium: confia en la CA del entorno por `NODE_EXTRA_CA_CERTS`.
            previous = os.environ.get("NODE_EXTRA_CA_CERTS")
            if self._ca_file is not None:
                os.environ["NODE_EXTRA_CA_CERTS"] = str(self._ca_file)
            try:
                self._playwright = sync_playwright().start()
            finally:
                if previous is None:
                    os.environ.pop("NODE_EXTRA_CA_CERTS", None)
                else:
                    os.environ["NODE_EXTRA_CA_CERTS"] = previous
            args = [f"--ignore-certificate-errors-spki-list={self._spki_pin}"] if self._spki_pin else []
            self._browser = self._playwright.chromium.launch(headless=True, args=args)
        return self._browser

    def close(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            self._browser = None
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None

    @staticmethod
    def _visible_error(page: Any) -> str:
        """El texto de un mensaje de error **visible** de Keycloak (un marcador oculto no cuenta); vacio si no hay."""
        for element in page.locator(
            "#input-error, .kc-feedback-text, .pf-m-danger, [id^=input-error], #kc-error-message"
        ).all():
            if element.is_visible() and (text := element.inner_text().strip()):
                return str(text)[:200]
        return ""

    def submit(
        self, authorize_url: str, redirect_uri: str, username: str, password: Secret, otp: Callable[[], str]
    ) -> str:
        """Todo fallo de Playwright (TLS, red, arranque, cierre del contexto) sale como `OidcError` con codigo estable: el mensaje y la traza de Playwright traen la URL de autorizacion
        (`state`, `nonce`, `code_challenge`) y no salen del modulo (`from None`)."""
        try:
            browser = self._launch()
            context = browser.new_context(
                ignore_https_errors=False, service_workers="block", accept_downloads=False
            )
        except PlaywrightError:
            raise OidcError("browser_launch_error") from None
        self.contexts_opened += 1
        try:
            returned_url = self._drive(context, authorize_url, redirect_uri, username, password, otp)
        except BaseException:
            self._discard(context)  # un fallo al cerrar no tapa el error original
            raise
        if self._discard(context):
            raise OidcError("browser_close_error") from None
        return returned_url

    def _discard(self, context: Any) -> bool:
        """Cierra el contexto (siempre, y se cuenta); devuelve si el cierre fallo."""
        try:
            context.close()
        except PlaywrightError:
            return True
        finally:
            self.contexts_closed += 1
        return False

    def _drive(
        self,
        context: Any,
        authorize_url: str,
        redirect_uri: str,
        username: str,
        password: Secret,
        otp: Callable[[], str],
    ) -> str:
        returned: list[str] = []
        failed = False  # un fallo dentro del manejador de rutas
        crashed = False  # un fallo de Playwright en el flujo principal

        def intercept(route: Route) -> None:
            """Playwright no llama al manejador en cada salto de una redireccion del servidor: la de Keycloak al `redirect_uri` no se veria. Por eso las **navegaciones** se piden sin seguir
            redirecciones (`max_redirects=0`): si la respuesta redirige al `redirect_uri`, se toma `Location` y la navegacion se cierra con un 204 (el navegador no sale a la red ni carga la SPA);
            si redirige a otro sitio, se le entrega al navegador tal cual. Una solicitud directa al `redirect_uri` se aborta.

            F-N1 (U12-T04): un fallo de `route.fetch` (TLS, red, tiempo) **no sale** del manejador: Playwright lo imprimiria en stderr como «Error occurred in event listener» con el `Call log`, que
            trae la URL de autorizacion (`state`, `nonce`, `code_challenge`) y, con Keycloak colgado, la cookie de sesion. Se captura aqui, se aborta la ruta y se anota solo que fallo."""
            nonlocal failed
            try:
                request = route.request
                if request.url.startswith(redirect_uri):
                    returned.append(request.url)  # solo en memoria
                    route.abort()
                    return
                if not request.is_navigation_request():
                    route.continue_()
                    return
                response = route.fetch(max_redirects=0)
                location = response.headers.get("location", "")
                if 300 <= response.status < 400 and location.startswith(redirect_uri):
                    returned.append(location)
                    route.fulfill(status=204, body="")
                else:
                    route.fulfill(response=response)
            except PlaywrightError:
                failed = True  # el texto de Playwright no se guarda ni se imprime
                try:
                    route.abort()
                except PlaywrightError:
                    pass  # la ruta ya estaba resuelta o el contexto se cerro: el fallo ya quedo anotado

        def finished(request: Any) -> None:
            if request.url.startswith(redirect_uri):
                self.redirect_requests_finished += 1

        # F-N3 (U12-T04): `route`, `on` y `new_page` tambien dentro del `try`. F-N2: el `OidcError` se lanza **fuera** del `except`, para que el `PlaywrightError` (con la URL) no quede en `__context__`.
        try:
            context.route("**/*", intercept)
            context.on("requestfinished", finished)
            page = context.new_page()
            page.goto(authorize_url, wait_until="domcontentloaded", timeout=self._timeout_ms)
            if not page.locator("input[name=username]").count():
                raise OidcError("login_form_missing")
            page.locator("input[name=username]").fill(username)
            page.locator("input[name=password]").fill(password.reveal())
            page.locator("[type=submit]").first.click(no_wait_after=True)
            filled_otp = False
            waited = 0
            while not returned and not failed:
                if page.locator("input[name=otp]").count() and not filled_otp:
                    page.locator("input[name=otp]").fill(otp())
                    page.locator("[type=submit]").first.click(no_wait_after=True)
                    filled_otp = True
                elif message := self._visible_error(page):
                    self.rejection_text = (
                        message
                        + " | "
                        + page.title()
                        + " | "
                        + ",".join(
                            page.locator("input").evaluate_all("els => els.map(e => e.name + ':' + e.type)")
                        )
                    )  # solo nombres de campo, sin valores
                    raise OidcError("login_rejected")  # un solo intento: el realm bloquea al quinto fallo
                page.wait_for_timeout(100)
                waited += 100
                if waited > self._timeout_ms:
                    raise OidcError("login_timeout")
        except PlaywrightError:
            crashed = True  # el mensaje de Playwright puede traer la URL de retorno con su `code`
        if crashed or (failed and not returned):
            raise OidcError("browser_error")
        return returned[0]


class UserSession:
    """La sesion de un usuario: sus tokens en memoria y lo que el BFF necesita de ellos. `bearer()` renueva el token antes de que venza."""

    def __init__(
        self,
        client: OidcClient,
        user: str,
        step_up: bool,
        tokens: TokenSet,
        claims: dict[str, Any],
        auth_time: datetime | None,
    ) -> None:
        self._client = client
        self.user = user
        self.step_up = step_up
        self._tokens = tokens
        self.claims = claims
        self.auth_time = auth_time
        self.refreshes = 0
        self.relogins = 0

    def __repr__(self) -> str:
        return f"UserSession(user={self.user!r}, step_up={self.step_up})"

    @property
    def tokens(self) -> TokenSet:
        return self._tokens

    @property
    def expires_at(self) -> datetime:
        return datetime.fromtimestamp(float(self.claims["exp"]), UTC)

    @property
    def acr(self) -> str | None:
        value = self.claims.get("acr")
        return str(value) if value is not None else None

    def bearer(self) -> str:
        """El access token vigente: si vence en menos de `REFRESH_LEEWAY_SECONDS`, se renueva primero."""
        if (self.expires_at - self._client.clock.now()).total_seconds() <= REFRESH_LEEWAY_SECONDS:
            self.refresh()
        return self._tokens.access_token.reveal()

    def refresh(self) -> None:
        """`refresh_token` rotativo; guarda el nuevo. Si Keycloak lo rechaza, **un** login nuevo del mismo tipo (P-7 (a))."""
        refresh = self._tokens.refresh_token
        if refresh is not None:
            try:
                self._tokens, self.claims = self._client.exchange_refresh(refresh)
                self.refreshes += 1
                return
            except OidcError:
                pass  # rechazado o vencido: un login nuevo (y solo uno)
        replaced = self._client.step_up(self.user) if self.step_up else self._client.login(self.user)
        self._tokens, self.claims, self.auth_time = replaced._tokens, replaced.claims, replaced.auth_time
        self.relogins += 1


class ServiceSession:
    """El token de servicio de `channel-simulator` o `verification-reader` (client_credentials), renovado antes de vencer."""

    def __init__(self, client: OidcClient, client_id: str, scope: str) -> None:
        self._client = client
        self.client_id = client_id
        self.scope = scope
        self._token: Secret | None = None
        self.claims: dict[str, Any] = {}
        self.requests = 0

    def __repr__(self) -> str:
        return f"ServiceSession(client={self.client_id!r})"

    def bearer(self) -> str:
        now = self._client.clock.now().timestamp()
        if self._token is None or float(self.claims["exp"]) - now <= REFRESH_LEEWAY_SECONDS:
            self._token, self.claims = self._client.exchange_service(self.client_id, self.scope)
            self.requests += 1
        return self._token.reveal()


class OidcClient:
    def __init__(
        self,
        environment: Environment,
        credentials: Credentials,
        clock: Clock,
        *,
        ca_file: Path | None = None,
        transport: httpx.BaseTransport | None = None,
        form: FormDriver | None = None,
        totp_windows: dict[str, int] | None = None,
    ) -> None:
        guard.check_known(environment)
        self._environment = environment
        self._credentials = credentials
        self.clock = clock
        self._ca_file = ca_file
        self._http = httpx.Client(
            transport=transport,
            verify=ssl.create_default_context(cafile=str(ca_file)) if ca_file else True,
            timeout=HTTP_TIMEOUT,
        )
        self._form = form
        self._last_window: dict[str, int] = (
            totp_windows if totp_windows is not None else {}
        )  # compartida entre clientes si se pasa (F-09)
        self._jwks: dict[str, Any] = {}
        self.token_requests = 0

    # ---- direcciones del entorno -----------------------------------------------------------------------------------------------------------------
    @property
    def environment(self) -> Environment:
        return self._environment

    @property
    def token_url(self) -> str:
        return f"{self._environment.issuer}/protocol/openid-connect/token"

    @property
    def authorization_url(self) -> str:
        return f"{self._environment.issuer}/protocol/openid-connect/auth"

    @property
    def jwks_url(self) -> str:
        return f"{self._environment.issuer}/protocol/openid-connect/certs"

    def redirect_uri(self, step_up: bool) -> str:
        return f"https://{self._environment.host}{STEP_UP_CALLBACK if step_up else CALLBACK}"

    def close(self) -> None:
        try:
            if self._form is not None:
                self._form.close()
        finally:
            self._http.close()

    def _form_driver(self) -> FormDriver:
        if self._form is None:  # pragma: no cover - Chromium real; lo ejercita test_oidc_headless
            parts = urlsplit(self._environment.issuer)
            pin = server_spki_pin(parts.hostname or "", parts.port or 443, self._ca_file)
            self._form = HeadlessForm(pin, ca_file=self._ca_file)
        return self._form

    # ---- solicitud de autorizacion ---------------------------------------------------------------------------------------------------------------
    def authorization_request(self, step_up: bool) -> AuthorizationRequest:
        """`state`, `nonce` y `code_verifier` nuevos en cada llamada. El step-up agrega `prompt=login`, `max_age=0` y `acr_values=mfa` (como la SPA)."""
        verifier = secrets.token_urlsafe(48)
        state, nonce = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
        redirect = self.redirect_uri(step_up)
        query: dict[str, str] = {
            "response_type": "code",
            "client_id": CONSOLE_CLIENT,
            "scope": SCOPE,
            "redirect_uri": redirect,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge(verifier),
            "code_challenge_method": "S256",
        }
        if step_up:
            query.update({"prompt": "login", "max_age": "0", "acr_values": "mfa"})
        return AuthorizationRequest(
            f"{self.authorization_url}?{urlencode(query)}", redirect, state, Secret(nonce), Secret(verifier)
        )

    # ---- TOTP ------------------------------------------------------------------------------------------------------------------------------------
    def otp_code(self, user: str) -> str:
        """El codigo TOTP de `user` en una ventana distinta de la del ultimo que se uso: si es la misma, espera a la siguiente con el reloj inyectado."""
        now = self.clock.now()
        window = int(now.timestamp() // TOTP_PERIOD)
        last = self._last_window.get(user)
        if last is not None and window <= last:
            self.clock.sleep((last + 1) * TOTP_PERIOD - now.timestamp() + TOTP_MARGIN_SECONDS)
            now = self.clock.now()
            window = int(now.timestamp() // TOTP_PERIOD)
        self._last_window[user] = window
        return self._credentials.totp(user, now)

    # ---- login y step-up -------------------------------------------------------------------------------------------------------------------------
    def login(self, user: str) -> UserSession:
        return self._interactive(user, step_up=False)

    def step_up(self, user: str) -> UserSession:
        return self._interactive(user, step_up=True)

    def _interactive(self, user: str, *, step_up: bool) -> UserSession:
        try:
            password = self._credentials.user_password(user)
        except CredentialsError as error:
            raise OidcError(str(error).split(":", 1)[0]) from None
        request = self.authorization_request(step_up)
        returned = self._form_driver().submit(
            request.url, request.redirect_uri, user, password, lambda: self.otp_code(user)
        )
        query = _query_of(returned)
        if "error" in query:
            raise OidcError("authorization_error")
        if not secrets.compare_digest(query.get("state", ""), request.state):
            raise OidcError("state_mismatch")  # antes de canjear: el endpoint de token no recibe nada
        code = query.get("code")
        if not code:
            raise OidcError("code_missing")
        form = {
            "grant_type": "authorization_code",
            "client_id": CONSOLE_CLIENT,
            "code": code,
            "redirect_uri": request.redirect_uri,
            "code_verifier": request.code_verifier.reveal(),
        }
        body = self._token_request(form)
        tokens, claims, id_claims = self._accept(body, nonce=request.nonce.reveal())
        if id_claims.get("acr") != "mfa":
            raise OidcError("acr_not_mfa")
        auth_time = self._auth_time(id_claims)
        if step_up:
            if auth_time is None or (self.clock.now() - auth_time).total_seconds() > MFA_MAX_AGE:
                raise OidcError("auth_time_too_old")
        return UserSession(self, user, step_up, tokens, claims, auth_time)

    def _auth_time(self, claims: dict[str, Any]) -> datetime | None:
        value = claims.get("auth_time")
        return datetime.fromtimestamp(float(value), UTC) if isinstance(value, int | float) else None

    # ---- token endpoint --------------------------------------------------------------------------------------------------------------------------
    def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        self.token_requests += 1
        try:
            response = self._http.post(self.token_url, data=form)
        except httpx.HTTPError as error:
            raise OidcError(f"token_endpoint_unreachable:{type(error).__name__}") from None
        if response.status_code != 200:
            raise OidcError(f"token_endpoint_status_{response.status_code}")
        try:
            body = response.json()
        except ValueError:
            raise OidcError("token_endpoint_response_shape") from None
        if not isinstance(body, dict) or not isinstance(body.get("access_token"), str):
            raise OidcError("token_endpoint_response_shape")
        return body

    def _accept(
        self, body: dict[str, Any], *, nonce: str | None
    ) -> tuple[TokenSet, dict[str, Any], dict[str, Any]]:
        """Valida el access token (y el ID token si viene) y devuelve los tokens, los claims del access token y los del ID token."""
        access = self._verify(str(body["access_token"]), audience=CONSOLE_AUDIENCE)
        id_claims: dict[str, Any] = {}
        id_token = body.get("id_token")
        if isinstance(id_token, str):
            id_claims = self._verify(id_token, audience=CONSOLE_CLIENT)
            if nonce is not None and not secrets.compare_digest(str(id_claims.get("nonce", "")), nonce):
                raise OidcError("nonce_mismatch")
        elif nonce is not None:
            raise OidcError("id_token_missing")
        refresh = body.get("refresh_token")
        tokens = TokenSet(
            Secret(str(body["access_token"])),
            Secret(refresh) if isinstance(refresh, str) else None,
            Secret(id_token) if isinstance(id_token, str) else None,
        )
        return tokens, access, id_claims

    def exchange_refresh(self, refresh: Secret) -> tuple[TokenSet, dict[str, Any]]:
        body = self._token_request(
            {"grant_type": "refresh_token", "client_id": CONSOLE_CLIENT, "refresh_token": refresh.reveal()}
        )
        tokens, claims, _ = self._accept(body, nonce=None)
        return tokens, claims

    # ---- verificacion de tokens ------------------------------------------------------------------------------------------------------------------
    def _key_for(self, kid: str | None) -> Any:
        for attempt in (0, 1):
            keys = self._jwks.get("keys", [])
            for jwk in keys:
                if jwk.get("kid") == kid:
                    return jwt.PyJWK(jwk).key
            if attempt == 0:
                try:
                    response = self._http.get(self.jwks_url)
                    self._jwks = response.json() if response.status_code == 200 else {}
                except (httpx.HTTPError, ValueError):
                    raise OidcError("jwks_unreachable") from None
        raise OidcError("token_key_unknown")

    def _verify(self, token: str, *, audience: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            unverified = jwt.decode(token, options={"verify_signature": False})
        except jwt.PyJWTError:
            raise OidcError("token_malformed") from None
        try:
            guard.check_token_issuer(self._environment, str(unverified.get("iss")))  # antes de usar el token
        except GuardError as error:
            raise OidcError(str(error)) from None
        key = self._key_for(header.get("kid"))
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=list(ALGORITHMS),
                options={"verify_aud": False, "verify_exp": False, "verify_iat": False, "verify_nbf": False},
            )
        except jwt.PyJWTError:
            raise OidcError("token_signature_invalid") from None
        claimed = claims.get("aud")
        audiences = [claimed] if isinstance(claimed, str) else list(claimed or [])
        if audience not in audiences:
            raise OidcError("token_audience_invalid")
        if (
            not isinstance(claims.get("exp"), int | float)
            or float(claims["exp"]) <= self.clock.now().timestamp()
        ):
            raise OidcError("token_expired")
        return dict(claims)

    # ---- tokens de servicio ----------------------------------------------------------------------------------------------------------------------
    def service_session(self, client_id: str, scopes: Sequence[str]) -> ServiceSession:
        if client_id not in SERVICE_CLIENTS:
            raise OidcError("service_client_unknown")
        return ServiceSession(self, client_id, " ".join(scopes))

    def client_assertion(self, client_id: str) -> Secret:
        """`private_key_jwt` ES256: `iss = sub = client_id`, `aud` = el emisor del entorno (la URL interna de token la rechaza Keycloak), `jti`, `iat` y `exp` a 60 s."""
        try:
            key = self._credentials.client_key(client_id).reveal()
        except CredentialsError as error:
            raise OidcError(str(error).split(":", 1)[0]) from None
        issued = int(self.clock.now().timestamp())
        claims = {
            "iss": client_id,
            "sub": client_id,
            "aud": self._environment.issuer,
            "jti": str(uuid.uuid4()),
            "iat": issued,
            "exp": issued + ASSERTION_LIFETIME_SECONDS,
        }
        try:
            return Secret(jwt.encode(claims, key, algorithm="ES256"))
        except (jwt.PyJWTError, ValueError, TypeError):
            raise OidcError("client_key_invalid") from None

    def exchange_service(self, client_id: str, scope: str) -> tuple[Secret, dict[str, Any]]:
        form = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_assertion_type": ASSERTION_TYPE,
            "client_assertion": self.client_assertion(client_id).reveal(),
        }
        if scope:
            form["scope"] = scope
        body = self._token_request(form)
        token = str(body["access_token"])
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
        except jwt.PyJWTError:
            raise OidcError("token_malformed") from None
        try:
            guard.check_token_issuer(self._environment, str(unverified.get("iss")))
        except GuardError as error:
            raise OidcError(str(error)) from None
        header = jwt.get_unverified_header(token)
        key = self._key_for(header.get("kid"))
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=list(ALGORITHMS),
                options={"verify_aud": False, "verify_exp": False, "verify_iat": False, "verify_nbf": False},
            )
        except jwt.PyJWTError:
            raise OidcError("token_signature_invalid") from None
        return Secret(token), dict(claims)
