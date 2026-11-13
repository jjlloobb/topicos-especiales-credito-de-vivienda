"""Mide el `iss` de los tokens de un Keycloak real (U02-T21). No entra en `make check` ni en `identity-edge/tests/`.

Levanta UN contenedor `u02t21-<azar>` con la imagen de `identity-edge/keycloak/Dockerfile` y las variables de hostname del
render de kind, publicado solo en 127.0.0.1:<puerto libre>. Ninguna solicitud sale de la maquina: el nombre interno de
Keycloak se desvia al contenedor (`curl --connect-to` / SNI + Host en httpx) y `vectra.localtest.me` solo viaja en
`KC_HOSTNAME` y en `X-Forwarded-Host`. Imprime la orden, el HTTP y los claims `iss`, `azp` y `aud` decodificados; nunca
el token, la asercion, la llave ni la contrasena. Borra el contenedor y sus volumenes al terminar, tambien si falla.

Uso: `uv run python identity-edge/tools/measure_issuer.py [--backchannel-dynamic]` (la bandera es la medida extra M-e de P-2).
"""

# ruff: noqa: S603, S607, T201, S105 - herramienta de medicion local: orden fija a docker y curl, imprime la evidencia
import argparse
import datetime
import json
import re
import secrets
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import jwt
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from vectra_common.service_token import ServiceTokenProvider

ROOT = Path(__file__).resolve().parents[2]
KEYCLOAK = ROOT / "identity-edge" / "keycloak"
PUBLIC_HOST = "vectra.localtest.me"  # solo en KC_HOSTNAME y X-Forwarded-Host: nunca como host de una URL
TOKEN_PATH = "/auth/realms/vectra/protocol/openid-connect/token"
WELL_KNOWN = "/auth/realms/vectra/.well-known/openid-configuration"
ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"


def image_from_dockerfile() -> str:
    match = re.search(r"^FROM\s+(\S+)", (KEYCLOAK / "Dockerfile").read_text(encoding="utf-8"), re.MULTILINE)
    assert match, "sin FROM en el Dockerfile"
    return match.group(1)


def render() -> tuple[dict[str, str], list[str], int]:
    """`env` del StatefulSet de kind (valores literales), SAN de `keycloak-tls` y puerto https."""
    docs = list(
        yaml.safe_load_all((KEYCLOAK / "rendered" / "kind" / "keycloak.yaml").read_text(encoding="utf-8"))
    )
    sts = next(d for d in docs if d and d.get("kind") == "StatefulSet")
    env = {
        e["name"]: e["value"] for e in sts["spec"]["template"]["spec"]["containers"][0]["env"] if "value" in e
    }
    cert = next(
        d for d in docs if d and d.get("kind") == "Certificate" and d["metadata"]["name"] == "keycloak-tls"
    )
    return env, list(cert["spec"]["dnsNames"]), 8443


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def make_cert(directory: Path, names: list[str]) -> Path:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=2))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in names]), critical=False)
        .sign(key, hashes.SHA256())
    )  # fmt: skip
    (directory / "tls.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (directory / "tls.key").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    for f in directory.iterdir():
        f.chmod(0o644)
    directory.chmod(0o755)
    return directory / "tls.crt"


def claims(token: str) -> dict[str, Any]:
    body = jwt.decode(token, options={"verify_signature": False})
    return {k: body.get(k) for k in ("iss", "azp", "aud")}


class Probe:
    def __init__(self, port: int, cafile: Path, internal: str, san_host: str) -> None:
        self.port, self.cafile, self.internal, self.san_host = port, cafile, internal, san_host
        self.headers_public = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": PUBLIC_HOST}

    def http(
        self, method: str, path: str, *, host: str | None = None, sni: str | None = None, **kw: Any
    ) -> httpx.Response:
        """Siempre contra 127.0.0.1:<puerto>; `host` y `sni` hacen de nombre de servicio."""
        headers = {**kw.pop("headers", {}), "Host": host or f"127.0.0.1:{self.port}"}
        ctx = ssl.create_default_context(cafile=str(self.cafile))
        with httpx.Client(verify=ctx, timeout=20) as client:
            return client.request(
                method,
                f"https://127.0.0.1:{self.port}{path}",
                headers=headers,
                extensions={"sni_hostname": sni or self.san_host},
                **kw,
            )

    def curl(self, resolve_host: str, path: str, data: list[str], headers: list[str]) -> tuple[int, str]:
        """El mismo POST con curl: `--connect-to` desvia el nombre al contenedor (la URL conserva el nombre de servicio)."""
        cmd = [
            "curl",
            "-sS",
            "--cacert",
            str(self.cafile),
            "--connect-to",
            f"{resolve_host}:8443:127.0.0.1:{self.port}",
            "-w",
            "\n%{http_code}",
        ]
        for h in headers:
            cmd += ["-H", h]
        for d in data:
            cmd += ["--data-urlencode", d]
        cmd.append(f"https://{resolve_host}:8443{path}")
        out = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout
        body, _, code = out.rpartition("\n")
        return int(code or 0), body


def show(label: str, order: str, status: int, extra: str) -> None:
    print(f"\n### {label}\n- orden: `{order}`\n- HTTP: {status}\n- {extra}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backchannel-dynamic",
        action="store_true",
        help="medida extra M-e (P-2 a): KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true",
    )
    args = parser.parse_args()
    image = image_from_dockerfile()
    env, sans, _ = render()
    admin_pw = secrets.token_urlsafe(18)
    name = f"u02t21-{secrets.token_hex(3)}"
    port = free_port()
    scratch = ROOT / "platform" / ".tools" / "tmp" / name  # ignorado por git; nunca /tmp
    scratch.mkdir(parents=True)
    certdir = scratch / "tls"
    certdir.mkdir()
    cafile = make_cert(certdir, sans)
    kc_env = {
        "KC_HTTP_RELATIVE_PATH": env["KC_HTTP_RELATIVE_PATH"], "KC_PROXY_HEADERS": env["KC_PROXY_HEADERS"],
        "KC_HOSTNAME": env["KC_HOSTNAME"], "KC_HOSTNAME_ADMIN": env["KC_HOSTNAME_ADMIN"],
        "KC_HEALTH_ENABLED": "true", "JAVA_OPTS_APPEND": "-XX:MaxRAMPercentage=70",
        "KC_HTTPS_CERTIFICATE_FILE": "/etc/x509/https/tls.crt", "KC_HTTPS_CERTIFICATE_KEY_FILE": "/etc/x509/https/tls.key",
        "KC_BOOTSTRAP_ADMIN_USERNAME": "bootstrap", "KC_BOOTSTRAP_ADMIN_PASSWORD": admin_pw,
    }  # fmt: skip
    if args.backchannel_dynamic:
        kc_env["KC_HOSTNAME_BACKCHANNEL_DYNAMIC"] = "true"
    print(
        f"## Contenedor\n- imagen: `{image}`\n- nombre: `{name}`, puerto 127.0.0.1:{port}\n- env de Keycloak: "
        + ", ".join(f"{k}={v}" for k, v in kc_env.items() if "PASSWORD" not in k)
    )
    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        name,
        "-m",
        "1536m",
        "-p",
        f"127.0.0.1:{port}:8443",
        "-v",
        f"{certdir}:/etc/x509/https:ro",
    ]
    for k, v in kc_env.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += [image, "start"]
    internal = urlhost(kc_env["KC_HOSTNAME_ADMIN"])
    san_host = sans[0]
    probe = Probe(port, cafile, internal, san_host)
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        deadline = time.time() + 240
        while True:
            try:
                if probe.http("GET", "/auth/realms/master", headers=probe.headers_public).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.time() > deadline:
                print(
                    subprocess.run(
                        ["docker", "logs", "--tail", "30", name], capture_output=True, text=True, check=False
                    ).stdout
                )
                raise SystemExit("Keycloak no arranco en 240 s")
            time.sleep(3)
        print(f"- arranco; uptime: {Path('/proc/loadavg').read_text().strip()}")
        measure(probe, admin_pw, scratch)
    finally:
        subprocess.run(["docker", "rm", "-f", "-v", name], capture_output=True, check=False)
        subprocess.run(["rm", "-rf", str(scratch)], check=False)
    return 0


def urlhost(url: str) -> str:
    return url.split("://", 1)[1].split("/", 1)[0].split(":", 1)[0]


def measure(probe: Probe, admin_pw: str, scratch: Path) -> None:
    internal_url = f"https://{probe.internal}:8443{TOKEN_PATH}"
    public_url = f"https://{PUBLIC_HOST}{TOKEN_PATH}"
    tok = probe.http(
        "POST",
        "/auth/realms/master/protocol/openid-connect/token",
        headers=probe.headers_public,
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "bootstrap",
            "password": admin_pw,
        },
    )
    assert tok.status_code == 200, f"admin: {tok.status_code}"
    admin = {"Authorization": f"Bearer {tok.json()['access_token']}", **probe.headers_public}
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": "probe-1", "use": "sig", "alg": "ES256"})
    user_pw = secrets.token_urlsafe(12)
    steps = [
        ("/auth/admin/realms", {"realm": "vectra", "enabled": True}),
        ("/auth/admin/realms/vectra/clients", {"clientId": "probe-public", "publicClient": True, "directAccessGrantsEnabled": True, "standardFlowEnabled": False}),
        ("/auth/admin/realms/vectra/clients", {
            "clientId": "probe-svc", "publicClient": False, "serviceAccountsEnabled": True, "standardFlowEnabled": False,
            "clientAuthenticatorType": "client-jwt",
            "attributes": {"use.jwks.string": "true", "jwks.string": json.dumps({"keys": [jwk]}), "token.endpoint.auth.signing.alg": "ES256"},
        }),
        ("/auth/admin/realms/vectra/users", {"username": "probe", "enabled": True, "emailVerified": True, "firstName": "Probe", "lastName": "Probe", "email": "probe@example.invalid", "credentials": [{"type": "password", "value": user_pw, "temporary": False}]}),
    ]  # fmt: skip
    for path, body in steps:
        r = probe.http("POST", path, headers=admin, json=body)
        assert r.status_code in (201, 204), f"{path}: {r.status_code} {r.text[:200]}"
    print(
        "- realm `vectra` minimo creado: cliente publico `probe-public` (direct grant), cliente `probe-svc` (client-jwt ES256), usuario `probe`"
    )

    # M-a: token de usuario "por el gateway".
    form = {"grant_type": "password", "client_id": "probe-public", "username": "probe", "password": user_pw}
    r = probe.http("POST", TOKEN_PATH, headers=probe.headers_public, data=form)
    show(
        "M-a",
        f"POST https://127.0.0.1:<puerto>{TOKEN_PATH} -H 'X-Forwarded-Proto: https' -H 'X-Forwarded-Host: {PUBLIC_HOST}' (grant password, cliente publico)",
        r.status_code,
        f"claims: `{json.dumps(claims(r.json()['access_token']) if r.status_code == 200 else r.json())}`",
    )

    def assertion(aud: str) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "iss": "probe-svc",
                "sub": "probe-svc",
                "aud": aud,
                "jti": secrets.token_hex(16),
                "iat": now,
                "exp": now + 60,
            },
            pem,
            algorithm="ES256",
            headers={"kid": "probe-1"},
        )

    # M-b: token de servicio por el host interno, sin X-Forwarded-*.
    auds = (
        ("aud = URL de token interna", internal_url),
        ("aud = URL de token publica", public_url),
        ("aud = emisor publico", f"https://{PUBLIC_HOST}/auth/realms/vectra"),
        ("aud = emisor interno", f"https://{probe.internal}:8443/auth/realms/vectra"),
    )
    for aud_label, aud in auds:
        afile = scratch / "assertion.jwt"
        afile.write_text(assertion(aud), encoding="utf-8")
        code, body = probe.curl(
            probe.internal,
            TOKEN_PATH,
            [
                "grant_type=client_credentials",
                f"client_assertion_type={ASSERTION_TYPE}",
                f"client_assertion@{afile}",
            ],
            [],
        )
        parsed = json.loads(body)
        order = f"curl --cacert <ca> --connect-to {probe.internal}:8443:127.0.0.1:<puerto> --data-urlencode grant_type=client_credentials --data-urlencode client_assertion_type=<jwt-bearer> --data-urlencode client_assertion@<archivo> https://{probe.internal}:8443{TOKEN_PATH}"
        show(
            f"M-b ({aud_label})",
            order,
            code,
            f"claims: `{json.dumps(claims(parsed['access_token']))}`"
            if code == 200
            else f"error: `{parsed.get('error')}: {parsed.get('error_description')}`",
        )

    # M-c: la asercion la construye ServiceTokenProvider (U0), aud = URL interna.
    seen: dict[str, Any] = {}

    async def poster(url: str, form: Any, timeout: float) -> Any:
        resp = probe.http(
            "POST", urlpath(url), host=f"{probe.internal}:8443", sni=probe.internal, data=dict(form)
        )
        seen["status"], seen["body"] = resp.status_code, resp.json()
        if resp.status_code != 200:
            raise RuntimeError("rechazada")
        return resp.json()

    import asyncio

    provider = ServiceTokenProvider(
        "probe-svc", internal_url, pem, "probe-audience", ("openid",), key_id="probe-1", poster=poster
    )
    try:
        token = asyncio.run(provider.token())
        extra = f"claims: `{json.dumps(claims(token))}`"
    except RuntimeError:
        extra = f"error: `{seen['body'].get('error')}: {seen['body'].get('error_description')}`"
    show(
        "M-c",
        f"ServiceTokenProvider(client_id=probe-svc, token_url={internal_url}).token() (aud de la aserción = esa URL)",
        seen["status"],
        extra,
    )

    # M-d: lo que anuncia Keycloak, de las dos formas.
    for label, kwargs in (
        ("como M-a", {"headers": probe.headers_public}),
        ("como M-b", {"host": f"{probe.internal}:8443", "sni": probe.internal}),
    ):
        r = probe.http("GET", WELL_KNOWN, **kwargs)
        doc = r.json()
        show(
            f"M-d ({label})",
            f"GET {WELL_KNOWN} ({'X-Forwarded-*' if 'headers' in kwargs else 'Host: ' + probe.internal + ':8443'})",
            r.status_code,
            "`" + json.dumps({k: doc[k] for k in ("issuer", "token_endpoint", "jwks_uri")}) + "`",
        )
    print(f"\nuptime: {Path('/proc/loadavg').read_text().strip()}")


def urlpath(url: str) -> str:
    return "/" + url.split("://", 1)[1].split("/", 1)[1]


if __name__ == "__main__":
    sys.exit(main())
