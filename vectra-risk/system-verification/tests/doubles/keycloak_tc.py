"""Keycloak y keycloak-config-cli reales en Testcontainers, con el realm de kind (U12-T02, P-1 de la tarea).

Lo que es igual a kind: la imagen de Keycloak es la de la linea `FROM` de `identity-edge/keycloak/Dockerfile` (por digest), con el tema `vectra` y la ruta `/auth`;
el realm es `identity-edge/keycloak/realm/realm.kind.yaml`, leido y sin editar, y lo aplica keycloak-config-cli (el digest sale de `values/kind.yaml`) con las
variables `IMPORT_VARSUBSTITUTION_*` y `PUBLIC_HOSTNAME` del Job de kind. `KC_HOSTNAME` es una URL completa, como en kind (asi Keycloak publica un solo emisor).

Lo que cambia (decision del usuario, 2026-11-13, P-1 opcion (b)): el host es dinamico, `127.0.0.1:<puerto aleatorio>`, no `vectra.localtest.me`. El emisor y los
`redirect_uri` reales de kind se atan con una prueba unitaria (`test_oidc_flow.py`). Nunca se abre una conexion a `vectra.localtest.me` ni a un cluster.

Las 36 variables `$(env:...)` las genera este modulo (contrasenas al azar, semillas Base32 al azar y un JWKS ES256 por cliente); llegan al codigo de U12 por un
`Credentials` real sobre el doble de la boveda. Todo temporal vive en una carpeta del worktree (ignorada por git), nunca en `/tmp`.
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
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from testcontainers.core.container import DockerContainer

from vault_double import VaultDouble

ROOT = Path(__file__).resolve().parents[3]  # vectra-risk/
KEYCLOAK_DIR = ROOT / "identity-edge" / "keycloak"
REALM_FILE = KEYCLOAK_DIR / "realm" / "realm.kind.yaml"
SCRATCH = ROOT / "platform" / ".tools" / "tmp" / "u12t02"
STARTUP_SECONDS = 300
ENV_REF = re.compile(r"\$\(env:([A-Z0-9_]+)\)")
ALPHANUMERIC = string.ascii_letters + string.digits
LABEL = {"vectra.u12t02": "1"}


def keycloak_image() -> str:
    match = re.search(
        r"^FROM\s+(\S+)", (KEYCLOAK_DIR / "Dockerfile").read_text(encoding="utf-8"), re.MULTILINE
    )
    assert match, "sin FROM en identity-edge/keycloak/Dockerfile"
    return match.group(1)


def config_cli_image() -> str:
    """El digest de `values/kind.yaml`; la imagen es `adorsys/keycloak-config-cli` (docs/paso-16-kind.md, §3), espejada en kind-registry con el mismo digest."""
    values = yaml.safe_load((KEYCLOAK_DIR / "values" / "kind.yaml").read_text(encoding="utf-8"))
    return f"adorsys/keycloak-config-cli@{values['vectra']['configCli']['image']['digest']}"


def config_cli_env_from_chart() -> dict[str, str]:
    """Las variables `IMPORT_*` del Job de kind (plantilla del chart), para no inventarlas."""
    template = (KEYCLOAK_DIR / "values" / "common.yaml").read_text(encoding="utf-8")
    found = dict(re.findall(r"\{ name: (IMPORT_VARSUBSTITUTION_\w+), value: \"(\w+)\" \}", template))
    assert set(found) == {"IMPORT_VARSUBSTITUTION_ENABLED", "IMPORT_VARSUBSTITUTION_UNDEFINEDISERROR"}, found
    return found


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    assert port not in (443, 8080, 8081, 8200, 8443)
    return port


def realm_references() -> set[str]:
    return set(ENV_REF.findall(REALM_FILE.read_text(encoding="utf-8")))


def b64url(number: int) -> str:
    return base64.urlsafe_b64encode(number.to_bytes(32, "big")).rstrip(b"=").decode()


def jwks_for(key: ec.EllipticCurvePrivateKey) -> str:
    numbers = key.public_key().public_numbers()
    kid = hashlib.sha256(f"{numbers.x}:{numbers.y}".encode()).hexdigest()[:16]
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": b64url(numbers.x),
        "y": b64url(numbers.y),
        "use": "sig",
        "alg": "ES256",
        "kid": kid,
    }
    return json.dumps({"keys": [jwk]}, separators=(",", ":"), sort_keys=True)


def private_pem(key: ec.EllipticCurvePrivateKey) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


@dataclass
class Generated:
    """Todo lo que se genera para el realm: nombre de variable -> valor, y las llaves privadas por cliente."""

    variables: dict[str, str] = field(default_factory=dict)
    client_keys: dict[str, str] = field(default_factory=dict)  # cliente -> PEM
    client_jwks: dict[str, str] = field(
        default_factory=dict
    )  # cliente -> JWKS como lo guarda la boveda (JSON)

    def synthetic(self) -> dict[str, str]:
        return {k: v for k, v in self.variables.items() if k.startswith("SYNTH_")}


def generate(references: set[str], hostname: str) -> Generated:
    out = Generated()
    for name in sorted(references):
        if name == "PUBLIC_HOSTNAME":
            out.variables[name] = hostname
        elif name == "NOMBRE":
            out.variables[name] = (
                "NOMBRE"  # la linea 3 del realm cita `$(env:NOMBRE)` en un comentario (candidata ya registrada)
            )
        elif name.endswith("_PASSWORD"):
            out.variables[name] = secrets.choice(string.ascii_letters) + "".join(
                secrets.choice(ALPHANUMERIC) for _ in range(19)
            )
        elif name.endswith("_TOTP_SEED"):
            out.variables[name] = base64.b32encode(secrets.token_bytes(20)).decode()
        elif name.startswith("CLIENT_") and name.endswith("_JWKS"):
            key = ec.generate_private_key(ec.SECP256R1())
            client = name.removeprefix("CLIENT_").removesuffix("_JWKS").lower().replace("_", "-")
            out.client_jwks[client] = jwks_for(key)
            # El Job de kind entrega el JWKS como cadena JSON (`toJson` en el ExternalSecret): sin las comillas, la sustitucion de texto lo vuelve un mapa YAML.
            out.variables[name] = json.dumps(out.client_jwks[client])
            out.client_keys[client] = private_pem(key)
        else:
            raise AssertionError(f"variable del realm sin generador: {name}")
    return out


@dataclass(frozen=True)
class Pki:
    ca_file: Path
    cert_file: Path
    key_file: Path
    truststore: Path
    truststore_password: str
    spki_sha256: str  # base64 de SHA-256 de la llave publica del certificado del servidor (`--ignore-certificate-errors-spki-list`)


def make_pki(directory: Path) -> Pki:
    """Una CA y un certificado de servidor para `127.0.0.1` y `localhost`, con `cryptography`, dentro del worktree."""
    now = datetime.datetime.now(datetime.UTC)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "u12t02-test-ca")])
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
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.DNSName("localhost")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )  # fmt: skip
    directory.mkdir(parents=True, exist_ok=True)
    ca_file, cert_file, key_file, truststore = (
        directory / "ca.crt",
        directory / "tls.crt",
        directory / "tls.key",
        directory / "truststore.p12",
    )
    ca_file.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_file.write_bytes(
        leaf.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM)
    )
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    password = secrets.token_hex(8)
    truststore.write_bytes(
        pkcs12.serialize_java_truststore(
            [pkcs12.PKCS12Certificate(ca, b"u12t02-ca")],
            serialization.BestAvailableEncryption(password.encode()),
        )
    )
    spki = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    for path in (ca_file, cert_file, key_file, truststore):
        path.chmod(0o644)  # el usuario del contenedor no es el del anfitrion; el contenido es desechable
    directory.chmod(0o755)
    return Pki(
        ca_file,
        cert_file,
        key_file,
        truststore,
        password,
        base64.b64encode(hashlib.sha256(spki).digest()).decode(),
    )


@dataclass
class KeycloakStack:
    port: int
    issuer: str
    base_url: str
    host: str  # `127.0.0.1:<puerto>`
    pki: Pki
    generated: Generated
    admin_password: str
    workdir: Path
    container: DockerContainer
    started_at: float

    @property
    def token_url(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/token"

    def ssl_context(self) -> ssl.SSLContext:
        return ssl.create_default_context(cafile=str(self.pki.ca_file))

    def vault(self, mount: str = "secret") -> VaultDouble:
        """El doble de la boveda con lo generado: asi las credenciales llegan por `Credentials`, no por variables de la prueba."""
        double = VaultDouble(mount, {"identity/synthetic-users": self.generated.synthetic()})
        for client, pem in self.generated.client_keys.items():
            if client in ("channel-simulator", "verification-reader"):
                double.secrets[f"identity/clients/{client}"] = {
                    "private-key": pem,
                    "jwks": self.generated.client_jwks[client],
                }
        return double

    def container_name(self) -> str:
        return str(self.container.get_wrapped_container().name)


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
            raise RuntimeError(
                f"Keycloak no arranco en {STARTUP_SECONDS} s:\n"
                + container.get_logs()[0].decode(errors="replace")[-2000:]
            )
        time.sleep(2)


def _apply_realm(stack_port: int, pki: Pki, generated: Generated, admin_password: str, workdir: Path) -> None:
    """keycloak-config-cli, como el Job de kind: mismo YAML, misma sustitucion, `KEYCLOAK_SSLVERIFY=true` con la CA de la prueba."""
    lines = {
        "KEYCLOAK_URL": f"https://127.0.0.1:{stack_port}/auth",
        "KEYCLOAK_SSLVERIFY": "true",
        "KEYCLOAK_USER": "bootstrap",
        "KEYCLOAK_PASSWORD": admin_password,
        "KEYCLOAK_AVAILABILITYCHECK_ENABLED": "true",
        "KEYCLOAK_AVAILABILITYCHECK_TIMEOUT": "120s",
        "IMPORT_FILES_LOCATIONS": "file:/config/realm.kind.yaml",
        **config_cli_env_from_chart(),
        "JAVA_OPTS": f"-XX:MaxRAMPercentage=70 -Djavax.net.ssl.trustStore=/trust/truststore.p12 -Djavax.net.ssl.trustStoreType=PKCS12 -Djavax.net.ssl.trustStorePassword={pki.truststore_password}",
        **generated.variables,
    }
    cli = (
        DockerContainer(config_cli_image())
        .with_kwargs(network_mode="host", mem_limit="768m", labels=LABEL)
        .with_volume_mapping(str(REALM_FILE), "/config/realm.kind.yaml", "ro")
        .with_volume_mapping(str(pki.truststore.parent), "/trust", "ro")
    )
    for key, value in lines.items():
        cli.with_env(key, value)
    try:
        cli.start()
        result = cli.get_wrapped_container().wait(timeout=240)
        (workdir / "config-cli.log").write_text(
            cli.get_logs()[0].decode(errors="replace"), encoding="utf-8"
        )  # sin secretos: solo el progreso de la importacion
        if result.get("StatusCode") != 0:
            tail = cli.get_logs()[0].decode(errors="replace")[-3000:]
            raise RuntimeError(f"keycloak-config-cli termino con {result.get('StatusCode')}:\n{tail}")
    finally:
        cli.stop(force=True, delete_volume=True)


@contextmanager
def keycloak_stack() -> Iterator[KeycloakStack]:
    """Una instancia: Keycloak + el realm de kind aplicado. Se borra (con su volumen y sus archivos) tambien si algo falla."""
    started = time.monotonic()
    token = secrets.token_hex(4)
    workdir = SCRATCH / f"kc-{token}"
    workdir.mkdir(parents=True)
    port = free_port()
    host = f"127.0.0.1:{port}"
    pki = make_pki(workdir / "tls")
    generated = generate(realm_references(), host)
    admin_password = secrets.token_urlsafe(18)
    base_url = f"https://{host}"
    container = (
        DockerContainer(keycloak_image())
        .with_name(f"u12t02-keycloak-{token}")
        .with_kwargs(mem_limit="1g", labels=LABEL)
        .with_bind_ports(8443, (("127.0.0.1", port)))
        .with_volume_mapping(str(KEYCLOAK_DIR / "themes" / "vectra"), "/opt/keycloak/themes/vectra", "ro")
        .with_volume_mapping(str(pki.cert_file.parent), "/etc/x509/https", "ro")
        .with_env("KC_HOSTNAME", f"{base_url}/auth")  # URL completa, como en kind: un solo emisor, el publico
        .with_env("KC_HTTP_RELATIVE_PATH", "/auth")
        .with_env("KC_HEALTH_ENABLED", "true")
        .with_env("JAVA_OPTS_APPEND", "-XX:MaxRAMPercentage=70")
        .with_env("KC_HTTPS_CERTIFICATE_FILE", "/etc/x509/https/tls.crt")
        .with_env("KC_HTTPS_CERTIFICATE_KEY_FILE", "/etc/x509/https/tls.key")
        .with_env("KC_BOOTSTRAP_ADMIN_USERNAME", "bootstrap")
        .with_env("KC_BOOTSTRAP_ADMIN_PASSWORD", admin_password)
        .with_command("start")
    )
    try:
        container.start()
        _wait_ready(base_url, pki.ca_file, container)
        _apply_realm(port, pki, generated, admin_password, workdir)
        yield KeycloakStack(
            port,
            f"{base_url}/auth/realms/vectra",
            base_url,
            host,
            pki,
            generated,
            admin_password,
            workdir,
            container,
            started,
        )
    finally:
        try:
            container.stop(force=True, delete_volume=True)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
