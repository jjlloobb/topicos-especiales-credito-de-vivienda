"""Keycloak y keycloak-config-cli reales en Docker, con el realm de kind sin editar (U02-T22).

Modelo: `system-verification/tests/doubles/keycloak_tc.py` de la rama `tarea/U12-T02` (otra unidad; no se importa). Escrito de nuevo y **sin** reparar nada tras importar:
ni enlazar configuraciones que config-cli deje sueltas ni completar el perfil de los usuarios.

Igual que kind: la imagen de Keycloak es la de la linea `FROM` de `keycloak/Dockerfile` (por digest), con `KC_HTTP_RELATIVE_PATH=/auth` y `KC_HOSTNAME` como URL completa;
config-cli es `adorsys/keycloak-config-cli@<digest de values/kind.yaml>` con las variables `IMPORT_*` leidas de `values/common.yaml`, `KEYCLOAK_SSLVERIFY=true` y el mismo
YAML. Las `$(env:...)` las genera este modulo (contrasenas, semillas Base32 y un JWKS ES256 por cliente como cadena JSON entre comillas).

Diferencias con kind (cada una se anota en `docs/realm-importacion.md`):
- la imagen es la base con `start` y la base embebida (H2), no la construida con `--db=postgres` y `start --optimized`; sin Postgres, sin Infinispan externo, sin el gateway;
- el host es `127.0.0.1:<puerto aleatorio>` y el certificado, de una CA desechable, no el del host publico de kind con su CA;
- el administrador de arranque es `bootstrap` con contrasena al azar (en kind, el secreto `keycloak-bootstrap-admin`);
- config-cli corre con `network_mode=host` y 768 MiB; el Job de kind, en su pod con el truststore armado por un initContainer (aqui, un PKCS12 generado);
- el tema `vectra` se monta pero el realm no lo activa (como en kind).

Nunca se abre una conexion a otro host que `127.0.0.1:<puerto>`: el cliente lleva una guarda que lo impide. Todo temporal vive en `platform/.tools/tmp/u02t22/` (ignorado por git).
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import ipaddress
import json
import re
import secrets
import shutil
import socket
import ssl
import string
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import httpx
import pyotp
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from testcontainers.core.container import DockerContainer

EDGE = Path(__file__).resolve().parents[2]
ROOT = EDGE.parent
sys.path.insert(0, str(EDGE / "tests" / "e2e"))
from e2e_support import Step, decode, form_action, hidden_fields  # noqa: E402  (el flujo de login de U02-T14: solo sus utilidades, no su `Flow`)

KEYCLOAK_DIR = EDGE / "keycloak"
REALM_FILE = KEYCLOAK_DIR / "realm" / "realm.kind.yaml"
OLD_REALM_FILE = EDGE / "tests" / "fixtures" / "realm-pre-u02t22" / "realm.kind.yaml"
SCRATCH = ROOT / "platform" / ".tools" / "tmp" / "u02t22"
MEASUREMENTS = SCRATCH / "measurements.log"
REALM = "vectra"
STARTUP_SECONDS = 300
ENV_REF = re.compile(r"\$\(env:([A-Z0-9_]+)\)")
ALPHANUMERIC = string.ascii_letters + string.digits
LABEL = {"vectra.u02t22": "1"}
FORBIDDEN_PORTS = (443, 8080, 8081, 8200, 8443)


def measure(line: str) -> None:
    """Una medida: a la salida y al archivo que lee la bitacora (sin secretos)."""
    sys.stdout.write(f"[u02t22] {line}\n")
    sys.stdout.flush()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with MEASUREMENTS.open("a", encoding="utf-8") as out:
        out.write(f"{time.strftime('%H:%M:%S')} {line}\n")


# --- lo que sale de los archivos de kind -----------------------------------------------------------------------


def keycloak_image() -> str:
    found = re.search(r"^FROM\s+(\S+)", (KEYCLOAK_DIR / "Dockerfile").read_text(encoding="utf-8"), re.MULTILINE)
    assert found, "sin FROM en keycloak/Dockerfile"
    return found.group(1)


def config_cli_image() -> str:
    values = yaml.safe_load((KEYCLOAK_DIR / "values" / "kind.yaml").read_text(encoding="utf-8"))
    return f"adorsys/keycloak-config-cli@{values['vectra']['configCli']['image']['digest']}"


def config_cli_env_from_chart() -> dict[str, str]:
    """Las variables `IMPORT_*` del Job (plantilla de `values/common.yaml`), leidas y no copiadas."""
    template = (KEYCLOAK_DIR / "values" / "common.yaml").read_text(encoding="utf-8")
    found = dict(re.findall(r"\{ name: (IMPORT_\w+), value: \"?([^\",}]+?)\"? \}", template))
    assert set(found) == {"IMPORT_VARSUBSTITUTION_ENABLED", "IMPORT_VARSUBSTITUTION_UNDEFINEDISERROR"} | {"IMPORT_FILES_LOCATIONS"}, found
    return {k: v for k, v in found.items() if k != "IMPORT_FILES_LOCATIONS"}


def realm_references(*files: Path) -> set[str]:
    return {name for f in files for name in ENV_REF.findall(f.read_text(encoding="utf-8"))}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    assert port not in FORBIDDEN_PORTS
    return port


# --- variables generadas ---------------------------------------------------------------------------------------


def _b64url(number: int) -> str:
    return base64.urlsafe_b64encode(number.to_bytes(32, "big")).rstrip(b"=").decode()


def _jwks() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    n = key.public_key().public_numbers()
    jwk = {"kty": "EC", "crv": "P-256", "x": _b64url(n.x), "y": _b64url(n.y), "use": "sig", "alg": "ES256", "kid": hashlib.sha256(f"{n.x}:{n.y}".encode()).hexdigest()[:16]}
    return json.dumps({"keys": [jwk]}, separators=(",", ":"), sort_keys=True)


def generate(references: set[str], hostname: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in sorted(references):
        if name == "PUBLIC_HOSTNAME":
            out[name] = hostname
        elif name == "NOMBRE":
            out[name] = "NOMBRE"  # la linea 3 del realm cita `$(env:NOMBRE)` en un comentario (candidata ya registrada)
        elif name.endswith("_PASSWORD"):
            out[name] = secrets.choice(string.ascii_letters) + "".join(secrets.choice(ALPHANUMERIC) for _ in range(19))
        elif name.endswith("_TOTP_SEED"):
            out[name] = base64.b32encode(secrets.token_bytes(20)).decode()
        elif name.startswith("CLIENT_") and name.endswith("_JWKS"):
            out[name] = json.dumps(_jwks())  # cadena JSON entre comillas, como la entrega el ExternalSecret de kind
        else:
            raise AssertionError(f"variable del realm sin generador: {name}")
    return out


# --- PKI desechable --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pki:
    ca_file: Path
    cert_file: Path
    key_file: Path
    truststore: Path
    truststore_password: str


def make_pki(directory: Path) -> Pki:
    now = datetime.datetime.now(datetime.UTC)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "u02t22-test-ca")])
    ca = (
        x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=4))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )  # fmt: skip
    key = ec.generate_private_key(ec.SECP256R1())
    leaf = (
        x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])).issuer_name(ca_name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1)).not_valid_after(now + datetime.timedelta(hours=4))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )  # fmt: skip
    directory.mkdir(parents=True, exist_ok=True)
    ca_file, cert_file, key_file, truststore = (directory / n for n in ("ca.crt", "tls.crt", "tls.key", "truststore.p12"))
    ca_file.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_file.write_bytes(leaf.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    password = secrets.token_hex(8)
    truststore.write_bytes(pkcs12.serialize_java_truststore([pkcs12.PKCS12Certificate(ca, b"u02t22-ca")], serialization.BestAvailableEncryption(password.encode())))
    for path in (ca_file, cert_file, key_file, truststore):
        path.chmod(0o644)  # el usuario del contenedor no es el del anfitrion; el contenido es desechable
    directory.chmod(0o755)
    return Pki(ca_file, cert_file, key_file, truststore, password)


# --- la guarda: nunca otro host ---------------------------------------------------------------------------------


class ForeignHost(AssertionError):
    pass


class HostGuard(httpx.BaseTransport):
    """Rechaza toda solicitud cuyo destino no sea `https://127.0.0.1:<puerto>`: el cluster de kind no es alcanzable desde aqui."""

    def __init__(self, port: int, context: ssl.SSLContext) -> None:
        self.port = port
        self.inner = httpx.HTTPTransport(verify=context)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        if (url.scheme, url.host, url.port) != ("https", "127.0.0.1", self.port):
            raise ForeignHost(f"destino rechazado por la guarda: {url.scheme}://{url.host}:{url.port} (solo https://127.0.0.1:{self.port})")
        return self.inner.handle_request(request)

    def close(self) -> None:
        self.inner.close()


# --- la pila -----------------------------------------------------------------------------------------------------


@dataclass
class Account:
    username: str
    password: str
    user_id: str


class Stack:
    """Un Keycloak real y config-cli. `import_realm` aplica un YAML de realm como el Job de kind."""

    def __init__(self, workdir: Path, port: int, pki: Pki, variables: dict[str, str], admin_password: str, container: DockerContainer) -> None:
        self.workdir, self.port, self.pki, self.variables = workdir, port, pki, variables
        self.admin_password, self.container = admin_password, container
        self.host = f"127.0.0.1:{port}"
        self.base_url = f"https://{self.host}"
        self.context = ssl.create_default_context(cafile=str(pki.ca_file))
        self.import_logs: list[str] = []
        self._admin_token = ("", 0.0)
        self._admin = self.client()

    def client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, transport=HostGuard(self.port, self.context), follow_redirects=False, timeout=30.0)

    def synth(self, username: str, kind: str) -> str:
        return self.variables[f"SYNTH_{username.upper().replace('-', '_')}_{kind}"]

    # logs
    def keycloak_log(self) -> str:
        return str(self.container.get_logs()[0].decode(errors="replace") + self.container.get_logs()[1].decode(errors="replace"))

    def keycloak_log_lines(self, needle: str) -> list[str]:
        return [ln for ln in self.keycloak_log().splitlines() if needle in ln]

    # config-cli
    def import_realm(self, realm_file: Path) -> str:
        env = {
            "KEYCLOAK_URL": f"{self.base_url}/auth",
            "KEYCLOAK_SSLVERIFY": "true",
            "KEYCLOAK_USER": "bootstrap",
            "KEYCLOAK_PASSWORD": self.admin_password,
            "KEYCLOAK_AVAILABILITYCHECK_ENABLED": "true",
            "KEYCLOAK_AVAILABILITYCHECK_TIMEOUT": "120s",
            "IMPORT_FILES_LOCATIONS": "file:/config/realm.kind.yaml",
            **config_cli_env_from_chart(),
            "JAVA_OPTS": f"-XX:MaxRAMPercentage=70 -Djavax.net.ssl.trustStore=/trust/truststore.p12 -Djavax.net.ssl.trustStoreType=PKCS12 -Djavax.net.ssl.trustStorePassword={self.pki.truststore_password}",
            **self.variables,
        }
        cli = (
            DockerContainer(config_cli_image())
            .with_kwargs(network_mode="host", mem_limit="768m", labels=LABEL)
            .with_volume_mapping(str(realm_file), "/config/realm.kind.yaml", "ro")
            .with_volume_mapping(str(self.pki.truststore.parent), "/trust", "ro")
        )
        for key, value in env.items():
            cli.with_env(key, value)
        try:
            cli.start()
            status = cli.get_wrapped_container().wait(timeout=240).get("StatusCode")
            log = cli.get_logs()[0].decode(errors="replace") + cli.get_logs()[1].decode(errors="replace")
        finally:
            cli.stop(force=True, delete_volume=True)
        (self.workdir / f"config-cli-{len(self.import_logs)}.log").write_text(log, encoding="utf-8")
        self.import_logs.append(log)
        if status != 0:
            raise RuntimeError(f"keycloak-config-cli termino con {status}:\n{log[-3000:]}")
        return log

    # administracion
    def _headers(self) -> dict[str, str]:
        token, expires = self._admin_token
        if time.time() >= expires:
            response = self._admin.post(
                "/auth/realms/master/protocol/openid-connect/token",
                data={"grant_type": "password", "client_id": "admin-cli", "username": "bootstrap", "password": self.admin_password},
            )
            assert response.status_code == 200, response.text
            token, expires = response.json()["access_token"], time.time() + 30
            self._admin_token = (token, expires)
        return {"Authorization": f"Bearer {token}"}

    def admin(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return self._admin.request(method, f"/auth/admin/realms/{REALM}{path}", headers=self._headers(), **kwargs)

    def delete_realm(self) -> None:
        response = self._admin.request("DELETE", f"/auth/admin/realms/{REALM}", headers=self._headers())
        assert response.status_code in (204, 404), response.text

    def partial_export(self) -> dict[str, Any]:
        response = self.admin("POST", "/partial-export", params={"exportClients": "false", "exportGroupsAndRoles": "false"})
        assert response.status_code == 200, response.text
        return dict(response.json())

    def create_user(self, username: str, password: str, role: str) -> Account:
        body = {"username": username, "enabled": True, "requiredActions": [], "credentials": [{"type": "password", "value": password, "temporary": False}]}
        created = self.admin("POST", "/users", json=body)
        assert created.status_code == 201, created.text
        user_id = created.headers["location"].rsplit("/", 1)[1]
        representation = self.admin("GET", f"/roles/{role}")
        assert representation.status_code == 200, representation.text
        assert self.admin("POST", f"/users/{user_id}/role-mappings/realm", json=[representation.json()]).status_code == 204
        return Account(username, password, user_id)

    def delete_user(self, user_id: str) -> None:
        self.admin("DELETE", f"/users/{user_id}")

    def brute_force_status(self, user_id: str) -> dict[str, Any]:
        response = self.admin("GET", f"/attack-detection/brute-force/users/{user_id}")
        assert response.status_code == 200, response.text
        return dict(response.json())

    def realm_representation(self) -> dict[str, Any]:
        response = self.admin("GET", "")
        assert response.status_code == 200, response.text
        return dict(response.json())

    def close(self) -> None:
        self._admin.close()


# --- login: Authorization Code + PKCE con vectra-console ----------------------------------------------------------

_LAST_OTP: dict[str, str] = {}


def totp_code(seed: str) -> str:
    """Un codigo TOTP que Keycloak no haya visto (reusar el de la ventana lo rechaza); si ya se usaron la ventana actual y la siguiente, espera."""
    totp = pyotp.TOTP(seed)
    for offset in (0, totp.interval):
        code = totp.at(time.time() + offset)
        if _LAST_OTP.get(seed) != code:
            _LAST_OTP[seed] = code
            return code
    time.sleep(totp.interval + 1)
    _LAST_OTP[seed] = totp.now()
    return _LAST_OTP[seed]


def page_text(html: str) -> str:
    """El mensaje de una pagina de Keycloak, sin etiquetas: el de error si lo hay."""
    for pattern in (r'id="kc-error-message"[^>]*>(.*?)</div>', r'class="[^"]*kc-feedback-text[^"]*"[^>]*>(.*?)</span>', r'class="[^"]*instruction[^"]*"[^>]*>(.*?)</'):
        found = re.search(pattern, html, re.DOTALL)
        if found:
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", found.group(1))).strip()
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()[:300]


class Login:
    """El flujo de `tests/e2e/e2e_support.py` (`Flow`) con el `redirect_uri` de este contenedor, no el de kind."""

    def __init__(self, stack: Stack, client_id: str = "vectra-console") -> None:
        self.stack, self.client_id = stack, client_id
        self.http = stack.client()
        self.verifier = ""
        self.redirect_uri = ""

    def close(self) -> None:
        self.http.close()

    def start(self, redirect_path: str = "/callback", **params: str | int) -> Step:
        self.redirect_uri = f"https://{self.stack.host}{redirect_path}"
        self.verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b"=").decode()
        query = {
            "client_id": self.client_id, "redirect_uri": self.redirect_uri, "response_type": "code", "scope": "openid",
            "state": secrets.token_urlsafe(12), "nonce": secrets.token_urlsafe(12),
            "code_challenge": challenge, "code_challenge_method": "S256", **params,
        }  # fmt: skip
        return self._follow(self.http.get(f"/auth/realms/{REALM}/protocol/openid-connect/auth", params=query))

    def _follow(self, response: httpx.Response) -> Step:
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

    def login(self, username: str, password: str, seed: str | None, **params: str | int) -> Step:
        """Usuario y contrasena, y el TOTP si Keycloak lo pide y hay semilla. Una sola pasada: cada intento fallido cuenta para la fuerza bruta."""
        redirect_path = str(params.pop("redirect_path", "/callback"))
        step = self.post(self.start(redirect_path, **params), {"username": username, "password": password})
        if step.location is None and 'name="otp"' in step.html and seed:
            step = self.post(step, {"otp": totp_code(seed)})
        return step

    def exchange(self, code: str) -> dict[str, Any]:
        response = self.http.post(
            f"/auth/realms/{REALM}/protocol/openid-connect/token",
            data={"grant_type": "authorization_code", "client_id": self.client_id, "code": code, "redirect_uri": self.redirect_uri, "code_verifier": self.verifier},
        )
        assert response.status_code == 200, response.text
        return dict(response.json())


def explain_failed_login(stack: Stack, username: str, step: Step) -> str:
    """Por que un login no llego al `redirect_uri`: el texto de la pagina y las lineas del log de Keycloak que lo explican."""
    log = stack.keycloak_log_lines("loaConditionConfig")[-1:] or stack.keycloak_log_lines("NullPointerException")[-1:]
    return (
        f"el login de {username} no llego al redirect_uri: HTTP {step.status}, pagina: «{page_text(step.html)}». "
        f"Log de Keycloak: {log[0].strip()[:400] if log else '(sin lineas de loaConditionConfig ni NullPointerException)'}"
    )


def claims(token: str) -> dict[str, Any]:
    return decode(token)


def code_of(location: str | None) -> str | None:
    return parse_qs(urlparse(location or "").query).get("code", [None])[0]


# --- lo que Keycloak guardo -----------------------------------------------------------------------------------------


@dataclass
class LinkReport:
    expected: int = 0  # ejecuciones que el YAML cita con configuracion
    linked: list[str] = field(default_factory=list)
    unlinked: list[str] = field(default_factory=list)
    wrong: list[str] = field(default_factory=list)  # enlazadas, pero con otros valores o alias
    misaligned: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.unlinked or self.wrong or self.misaligned) and len(self.linked) == self.expected

    def summary(self) -> str:
        return f"{len(self.linked)} de {self.expected} ejecuciones con authenticationConfig; sin ella: {len(self.unlinked)}; con otros valores: {len(self.wrong)}; desalineadas: {len(self.misaligned)}"


def read_links(stack: Stack, realm_file: Path) -> LinkReport:
    """Por la API de administracion: la configuracion de **cada** ejecucion que el YAML cita con una, comparada con la del YAML (el numero sale del YAML)."""
    text = realm_file.read_text(encoding="utf-8").replace("$(env:", "(env:")
    realm = yaml.safe_load(text)
    configs = {c["alias"]: c["config"] for c in realm["authenticatorConfig"]}
    report = LinkReport()
    for flow in realm["authenticationFlows"]:
        wanted = sorted(flow["authenticationExecutions"], key=lambda e: e["priority"])
        listing = stack.admin("GET", f"/authentication/flows/{quote(flow['alias'])}/executions")
        assert listing.status_code == 200, listing.text
        actual = [e for e in listing.json() if e.get("level") == 0]
        if len(actual) != len(wanted):
            report.misaligned.append(f"{flow['alias']}: Keycloak tiene {len(actual)} ejecuciones y el YAML {len(wanted)}")
            report.expected += sum("authenticatorConfig" in w for w in wanted)
            continue
        for found, intent in zip(actual, wanted, strict=True):
            alias = intent.get("authenticatorConfig")
            if not alias:
                continue
            report.expected += 1
            label = f"{flow['alias']}#{intent['priority']} ({intent.get('authenticator')}, alias {alias})"
            if not found.get("authenticationConfig"):
                report.unlinked.append(label)
                continue
            config = stack.admin("GET", f"/authentication/config/{found['authenticationConfig']}").json()
            if config["alias"] != alias or any(config["config"].get(k) != v for k, v in configs[alias].items()):
                report.wrong.append(f"{label}: Keycloak tiene alias {config['alias']!r}")
            else:
                report.linked.append(label)
    return report


def required_actions(stack: Stack) -> dict[str, dict[str, Any]]:
    response = stack.admin("GET", "/authentication/required-actions")
    assert response.status_code == 200, response.text
    return {a["alias"]: a for a in response.json()}


# --- arranque ------------------------------------------------------------------------------------------------------


def _wait_ready(base_url: str, ca_file: Path, container: DockerContainer) -> None:
    deadline = time.monotonic() + STARTUP_SECONDS
    context = ssl.create_default_context(cafile=str(ca_file))
    while True:
        try:
            with httpx.Client(verify=context, timeout=5) as client:
                if client.get(f"{base_url}/auth/realms/master").status_code == 200:
                    return
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError(f"Keycloak no arranco en {STARTUP_SECONDS} s:\n" + container.get_logs()[0].decode(errors="replace")[-2000:])
        time.sleep(2)


@contextmanager
def keycloak_stack() -> Iterator[Stack]:
    """Un Keycloak vacio (sin realm). Se borra con su volumen y sus archivos tambien si algo falla."""
    token = secrets.token_hex(4)
    workdir = SCRATCH / f"kc-{token}"
    workdir.mkdir(parents=True)
    port = free_port()
    pki = make_pki(workdir / "tls")
    host = f"127.0.0.1:{port}"
    variables = generate(realm_references(REALM_FILE, OLD_REALM_FILE), host)
    admin_password = secrets.token_urlsafe(18)
    base_url = f"https://{host}"
    container = (
        DockerContainer(keycloak_image())
        .with_name(f"u02t22-keycloak-{token}")
        .with_kwargs(mem_limit="1536m", labels=LABEL)
        .with_bind_ports(8443, ("127.0.0.1", port))
        .with_volume_mapping(str(KEYCLOAK_DIR / "themes" / "vectra"), "/opt/keycloak/themes/vectra", "ro")
        .with_volume_mapping(str(pki.cert_file.parent), "/etc/x509/https", "ro")
        .with_env("KC_HOSTNAME", f"{base_url}/auth")
        .with_env("KC_HTTP_RELATIVE_PATH", "/auth")
        .with_env("KC_HEALTH_ENABLED", "true")
        .with_env("JAVA_OPTS_APPEND", "-XX:MaxRAMPercentage=70")
        .with_env("KC_HTTPS_CERTIFICATE_FILE", "/etc/x509/https/tls.crt")
        .with_env("KC_HTTPS_CERTIFICATE_KEY_FILE", "/etc/x509/https/tls.key")
        .with_env("KC_BOOTSTRAP_ADMIN_USERNAME", "bootstrap")
        .with_env("KC_BOOTSTRAP_ADMIN_PASSWORD", admin_password)
        .with_command("start")
    )
    stack: Stack | None = None
    try:
        container.start()
        _wait_ready(base_url, pki.ca_file, container)
        stack = Stack(workdir, port, pki, variables, admin_password, container)
        yield stack
    finally:
        try:
            if stack:
                stack.close()
            container.stop(force=True, delete_volume=True)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
