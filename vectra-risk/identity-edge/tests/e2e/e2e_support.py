"""Soporte de las pruebas e2e de U2 (U02-T14): configuración por entorno, flujo OIDC, Admin API de Keycloak y Loki.

Los valores esperados salen del diseño o del modelo, nunca de literales propios:
- límites, `max_body`, `Retry-After` y perfiles de cabeceras: `gateway/routes.yaml` y `tests/strategies/gateway_design.py`;
- campos de la fuerza bruta y clientes: `keycloak/realm/realm.kind.yaml` y `tests/strategies/realm_builders.py`;
- host: `gateway/values/kind.yaml`.

Si falta una variable de entorno al ejecutar, la prueba falla con un error explícito (`need`): nunca se salta con `skip`.
Nada de `verify=False`: el TLS se verifica contra `VECTRA_E2E_CA_BUNDLE`. Importar este módulo no lee ninguna variable.
"""

import base64
import hashlib
import html as htmllib
import os
import re
import secrets
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pyotp
import pytest
import yaml

TESTS_DIR = Path(os.environ.get("VECTRA_E2E_TESTS_DIR") or Path(__file__).resolve().parents[1])
EDGE_DIR = TESTS_DIR.parent

ENV_VARS = {
    "VECTRA_E2E_BASE_URL": "URL pública del gateway en kind, por ejemplo https://<hostname de values/kind.yaml>",
    "VECTRA_E2E_CA_BUNDLE": "archivo PEM con la CA que firma el certificado del gateway",
    "SYNTH_<USUARIO>_PASSWORD": "contraseña del usuario sintético (por ejemplo SYNTH_ANALISTA_1_PASSWORD)",
    "SYNTH_<USUARIO>_TOTP_SEED": "semilla TOTP en Base32 del usuario sintético",
    "VECTRA_E2E_ADMIN_URL": "base de la Admin API de Keycloak por port-forward, incluido /auth (BR-U2-12)",
    "VECTRA_E2E_ADMIN_USER": "usuario de la Admin API (realm master)",
    "VECTRA_E2E_ADMIN_PASSWORD": "contraseña del usuario de la Admin API",
    "VECTRA_E2E_ADMIN_CA_BUNDLE": "opcional: CA de la Admin API si no es la del gateway",
    "VECTRA_E2E_LOKI_URL": "URL de Loki por port-forward",
    "VECTRA_E2E_CLIENT_KEYS_DIR": "directorio con <cliente>.pem, la llave privada ES256 de cada cliente de servicio (desde Vault)",
}


def need(name: str) -> str:
    """El valor de una variable obligatoria; si falta, la prueba falla con un error explícito (nunca `skip`)."""
    value = os.environ.get(name)
    if not value:
        pytest.fail(f"falta la variable de entorno {name}: {ENV_VARS.get(name, 'ver e2e_support.ENV_VARS')}", pytrace=False)
    return value


def synth(username: str, kind: str) -> str:
    """`SYNTH_<USUARIO>_<KIND>` del realm: `analista-1` y `PASSWORD` -> `SYNTH_ANALISTA_1_PASSWORD`."""
    return need(f"SYNTH_{username.upper().replace('-', '_')}_{kind}")


# --- el diseño ------------------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def routes() -> dict[str, Any]:
    return yaml.safe_load((EDGE_DIR / "gateway" / "routes.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def realm() -> dict[str, Any]:
    return yaml.safe_load((EDGE_DIR / "keycloak" / "realm" / "realm.kind.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def kind_values() -> dict[str, Any]:
    return yaml.safe_load((EDGE_DIR / "gateway" / "values" / "kind.yaml").read_text(encoding="utf-8"))


def route(name: str) -> dict[str, Any]:
    return next(r for r in routes()["routes"] if r["name"] == name)


def rate_limit(name: str) -> dict[str, Any]:
    return next(r for r in routes()["rate_limits"] if r["name"] == name)


# La unidad de un contador de `routes.yaml` es una `unit` de Envoy Ratelimit (Second, Minute, Hour, Day): su ventana en segundos.
WINDOW_SECONDS = {"Second": 1, "Minute": 60, "Hour": 3600, "Day": 86400}


def window_seconds(limit_name: str) -> int:
    """La ventana del contador `limit_name` de `rate_limits` en `routes.yaml`. El contador es de ventana fija, alineada a la unidad."""
    return WINDOW_SECONDS[rate_limit(limit_name)["unit"]]


def wait_for_next_window(limit_name: str, margin: float = 1.0) -> None:
    """Espera al comienzo de la siguiente ventana fija del contador, para que una ráfaga entera caiga en una sola ventana."""
    window = window_seconds(limit_name)
    time.sleep(window - (time.time() % window) + margin)


def max_body_bytes(route_name: str) -> int:
    """`max_body` de la ruta (por ejemplo `64Ki`) en bytes."""
    found = re.fullmatch(r"(\d+)Ki", route(route_name)["max_body"])
    assert found, route(route_name)["max_body"]
    return int(found.group(1)) * 1024


def approver_role() -> str:
    """Un rol al que BR-U2-03 exige MFA (los de `realm_builders.MFA_ROLES`)."""
    import realm_builders as rb

    return str(rb.MFA_ROLES[0])


def intake_scope() -> str:
    return str(route("intake")["auth"]["scopes"][0])


def public_host() -> str:
    return str(kind_values()["hostname"])


def brute_force() -> dict[str, Any]:
    keys = ("failureFactor", "waitIncrementSeconds", "maxFailureWaitSeconds", "maxDeltaTimeSeconds", "maxTemporaryLockouts", "permanentLockout", "bruteForceStrategy")
    return {k: realm()[k] for k in keys}


# --- gateway --------------------------------------------------------------------------------------------------


def tls_context(bundle_var: str = "VECTRA_E2E_CA_BUNDLE") -> ssl.SSLContext:
    return ssl.create_default_context(cafile=need(bundle_var))


def gateway_client() -> httpx.Client:
    return httpx.Client(base_url=need("VECTRA_E2E_BASE_URL"), verify=tls_context(), follow_redirects=False, timeout=15.0)


REALM_PATH = "/auth/realms/vectra"
OIDC = f"{REALM_PATH}/protocol/openid-connect"
TOKEN_PATH = f"{OIDC}/token"


def decode(token: str) -> dict[str, Any]:
    """Los claims del JWT sin verificar la firma: el token vino del endpoint de token por TLS verificado."""
    return dict(jwt.decode(token, options={"verify_signature": False}))


# --- flujo OIDC con PKCE (sin SPA) ------------------------------------------------------------------------------


@dataclass
class Step:
    """Una respuesta del flujo: la página (`html`) o la redirección final al `redirect_uri` (`location`)."""

    status: int
    html: str
    location: str | None = None

    @property
    def code(self) -> str | None:
        if self.location is None:
            return None
        return parse_qs(urlparse(self.location).query).get("code", [None])[0]


def form_action(html: str) -> str:
    found = re.search(r'<form[^>]*\saction="([^"]*login-actions[^"]*)"', html)
    assert found, "la página no tiene un formulario de login-actions"
    return htmllib.unescape(found.group(1))


def hidden_fields(html: str) -> dict[str, str]:
    fields = {}
    for tag in re.findall(r"<input[^>]*>", html):
        if re.search(r'type="hidden"', tag) and (name := re.search(r'name="([^"]+)"', tag)):
            value = re.search(r'value="([^"]*)"', tag)
            fields[name.group(1)] = htmllib.unescape(value.group(1)) if value else ""
    return fields


_LAST_OTP: dict[str, str] = {}


def totp_code(seed: str) -> str:
    """Un código TOTP que Keycloak no haya visto: reusar el de la misma ventana lo rechaza (BR-U2-03)."""
    totp = pyotp.TOTP(seed)
    for offset in (0, totp.interval):
        code = totp.at(time.time() + offset)
        if _LAST_OTP.get(seed) != code:
            _LAST_OTP[seed] = code
            return code
    time.sleep(totp.interval + 1)
    code = totp.now()
    _LAST_OTP[seed] = code
    return code


class Flow:
    """Authorization Code con PKCE contra `vectra-console`, con el login hecho a mano (`httpx`)."""

    def __init__(self, http: httpx.Client | None = None, client_id: str = "vectra-console") -> None:
        self.http = http or gateway_client()
        self.client_id = client_id
        self.verifier = ""
        self.redirect_uri = ""

    def close(self) -> None:
        self.http.close()

    def authorize_url(self, redirect_path: str = "/callback", **params: str | int) -> str:
        """La URL de la solicitud de autorización (PKCE S256), con un `code_verifier` nuevo."""
        self.redirect_uri = f"https://{public_host()}{redirect_path}"
        self.verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b"=").decode()
        query = {
            "client_id": self.client_id, "redirect_uri": self.redirect_uri, "response_type": "code", "scope": "openid",
            "state": secrets.token_urlsafe(12), "nonce": secrets.token_urlsafe(12),
            "code_challenge": challenge, "code_challenge_method": "S256", **params,
        }  # fmt: skip
        return str(httpx.URL(f"{self.http.base_url}{OIDC}/auth", params=query))

    def start(self, redirect_path: str = "/callback", **params: str | int) -> Step:
        return self._follow(self.http.get(self.authorize_url(redirect_path, **params)))

    def _follow(self, response: httpx.Response) -> Step:
        """Sigue las redirecciones internas; se detiene en la del `redirect_uri` y la devuelve como `location`."""
        for _ in range(8):
            if response.status_code not in (301, 302, 303, 307):
                return Step(response.status_code, response.text)
            target = response.headers["location"]
            if target.startswith(self.redirect_uri):
                return Step(response.status_code, response.text, location=target)
            response = self.http.get(target)
        raise AssertionError("demasiadas redirecciones en el flujo de login")

    def post(self, step: Step, fields: dict[str, str]) -> Step:
        return self._follow(self.http.post(form_action(step.html), data={**hidden_fields(step.html), **fields}))

    def password(self, step: Step, username: str, password: str) -> Step:
        return self.post(step, {"username": username, "password": password})

    def otp(self, step: Step, seed: str) -> Step:
        return self.post(step, {"otp": totp_code(seed)})

    def login(self, username: str, password: str, with_otp: bool = True, **params: str | int) -> Step:
        """Usuario y contraseña, y el TOTP si Keycloak lo pide (con la semilla de `SYNTH_<USUARIO>_TOTP_SEED`)."""
        step = self.password(self.start(**params), username, password)
        if step.location is None and 'name="otp"' in step.html and with_otp:
            step = self.otp(step, synth(username, "TOTP_SEED"))
        return step

    def exchange(self, code: str) -> dict[str, Any]:
        response = self.http.post(
            TOKEN_PATH,
            data={"grant_type": "authorization_code", "client_id": self.client_id, "code": code, "redirect_uri": self.redirect_uri, "code_verifier": self.verifier},
        )
        assert response.status_code == 200, response.text
        return dict(response.json())


def user_tokens(username: str, **params: str | int) -> dict[str, Any]:
    """Los tokens de un usuario sintético: contraseña y TOTP de `SYNTH_<USUARIO>_*`."""
    flow = Flow()
    try:
        step = flow.login(username, synth(username, "PASSWORD"), **params)
        assert step.code, f"el login de {username} no terminó en un código: HTTP {step.status}"
        return flow.exchange(step.code)
    finally:
        flow.close()


def user_access_token(_gateway: httpx.Client, username: str) -> str:
    return str(user_tokens(username)["access_token"])


def service_token(gateway: httpx.Client, client_id: str, scope: str | None = None) -> str:
    """Client credentials con `private_key_jwt` ES256 (BR-U2-09); la llave la deja el operador en `VECTRA_E2E_CLIENT_KEYS_DIR`."""
    key = (Path(need("VECTRA_E2E_CLIENT_KEYS_DIR")) / f"{client_id}.pem").read_text(encoding="utf-8")
    now = int(time.time())
    url = f"{gateway.base_url}{TOKEN_PATH}"
    assertion = jwt.encode({"iss": client_id, "sub": client_id, "aud": url, "jti": secrets.token_hex(16), "iat": now, "exp": now + 60}, key, algorithm="ES256")
    form = {
        "grant_type": "client_credentials", "client_id": client_id,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer", "client_assertion": assertion,
    }  # fmt: skip
    if scope:
        form["scope"] = scope
    response = gateway.post(TOKEN_PATH, data=form)
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def bearer(token: str, **headers: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", **headers}


# --- Admin API de Keycloak (BR-U2-12) ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Account:
    username: str
    password: str
    user_id: str


class Admin:
    """Admin API de Keycloak por port-forward. Crea y borra usuarios efímeros; lee el estado de la fuerza bruta."""

    def __init__(self, http: httpx.Client, base: str) -> None:
        self.http = http
        self.base = base.rstrip("/")
        self._token: tuple[str, float] = ("", 0.0)

    @classmethod
    def connect(cls) -> "Admin":
        bundle = "VECTRA_E2E_ADMIN_CA_BUNDLE" if os.environ.get("VECTRA_E2E_ADMIN_CA_BUNDLE") else "VECTRA_E2E_CA_BUNDLE"
        return cls(httpx.Client(verify=tls_context(bundle), timeout=15.0), need("VECTRA_E2E_ADMIN_URL"))

    def __enter__(self) -> "Admin":
        return self

    def __exit__(self, *_: object) -> None:
        self.http.close()

    def _headers(self) -> dict[str, str]:
        token, expires = self._token
        if time.time() >= expires:
            response = self.http.post(
                f"{self.base}/realms/master/protocol/openid-connect/token",
                data={"grant_type": "password", "client_id": "admin-cli", "username": need("VECTRA_E2E_ADMIN_USER"), "password": need("VECTRA_E2E_ADMIN_PASSWORD")},
            )
            assert response.status_code == 200, response.text
            token, expires = response.json()["access_token"], time.time() + 30
            self._token = (token, expires)
        return {"Authorization": f"Bearer {token}"}

    def call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return self.http.request(method, f"{self.base}/admin/realms/vectra{path}", headers=self._headers(), **kwargs)

    def create_user(self, username: str, password: str, role: str, required_actions: list[str]) -> Account:
        body = {
            "username": username, "enabled": True, "emailVerified": False, "requiredActions": required_actions,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        }  # fmt: skip
        created = self.call("POST", "/users", json=body)
        assert created.status_code == 201, created.text
        user_id = created.headers["location"].rsplit("/", 1)[1]
        representation = self.call("GET", f"/roles/{role}")
        assert representation.status_code == 200, representation.text
        mapped = self.call("POST", f"/users/{user_id}/role-mappings/realm", json=[representation.json()])
        assert mapped.status_code == 204, mapped.text
        return Account(username, password, user_id)

    def delete_user(self, user_id: str) -> None:
        self.call("DELETE", f"/users/{user_id}")

    def brute_force_status(self, user_id: str) -> dict[str, Any]:
        response = self.call("GET", f"/attack-detection/brute-force/users/{user_id}")
        assert response.status_code == 200, response.text
        return dict(response.json())

    def settled_status(self, user_id: str, predicate: Callable[[dict[str, Any]], bool], timeout: float = 10.0) -> dict[str, Any]:
        """Keycloak procesa los fallos en un hilo aparte: espera a que el estado cumpla `predicate`."""
        deadline = time.time() + timeout
        status = self.brute_force_status(user_id)
        while not predicate(status) and time.time() < deadline:
            time.sleep(0.25)
            status = self.brute_force_status(user_id)
        return status


# --- Loki (H6) --------------------------------------------------------------------------------------------------

KEYCLOAK_STREAM = os.environ.get("VECTRA_E2E_LOKI_KEYCLOAK_SELECTOR") or '{namespace="vectra-identity"}'
GATEWAY_STREAM = os.environ.get("VECTRA_E2E_LOKI_GATEWAY_SELECTOR") or '{namespace="vectra-edge"}'


class Loki:
    def __init__(self, http: httpx.Client, base: str) -> None:
        self.http = http
        self.base = base.rstrip("/")

    @classmethod
    def connect(cls) -> "Loki":
        return cls(httpx.Client(timeout=30.0), need("VECTRA_E2E_LOKI_URL"))

    def __enter__(self) -> "Loki":
        return self

    def __exit__(self, *_: object) -> None:
        self.http.close()

    def lines(self, logql: str, start_ns: int) -> list[str]:
        response = self.http.get(
            f"{self.base}/loki/api/v1/query_range",
            params={"query": logql, "start": str(start_ns), "end": str(time.time_ns() + 5_000_000_000), "limit": "1000", "direction": "forward"},
        )
        assert response.status_code == 200, response.text
        return [value[1] for stream in response.json()["data"]["result"] for value in stream["values"]]

    def wait_for(self, logql: str, start_ns: int, timeout: float = 90.0) -> list[str]:
        """Las líneas que casan con `logql` desde `start_ns`; Loki las recibe con retraso, así que se reintenta."""
        deadline = time.time() + timeout
        found = self.lines(logql, start_ns)
        while not found and time.time() < deadline:
            time.sleep(3)
            found = self.lines(logql, start_ns)
        return found
