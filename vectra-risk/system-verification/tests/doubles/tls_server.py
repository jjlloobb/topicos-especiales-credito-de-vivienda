"""Un servidor HTTPS de prueba para la imagen (U12-T05, CA-5): su certificado lo firma una CA generada aqui, y sirve un formulario de login con un subrecurso (`/pixel.png`). El formulario hace lo de Keycloak que importa
al login de U12-T02: una **navegacion** (que pide Node, por `route.fetch`), un **subrecurso** (que pide Chromium) y una redireccion al `redirect_uri` con `code` y `state`.

Escucha en `127.0.0.1` con un puerto que pide el sistema; el contenedor (`--network host`) llega por la misma direccion."""

from __future__ import annotations

import datetime as dt
import http.server
import ipaddress
import ssl
import threading
from dataclasses import dataclass, field
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)


def _name(common: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common)])


def _pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


@dataclass
class Authority:
    """Una CA de prueba y los certificados que firma."""

    common: str
    key: ec.EllipticCurvePrivateKey = field(default_factory=lambda: ec.generate_private_key(ec.SECP256R1()))

    def __post_init__(self) -> None:
        now = dt.datetime.now(dt.UTC)
        self.certificate = (
            x509.CertificateBuilder()
            .subject_name(_name(self.common))
            .issuer_name(_name(self.common))
            .public_key(self.key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),  # fmt: skip
                critical=True,
            )
            .sign(self.key, hashes.SHA256())
        )

    def write_ca(self, path: Path) -> Path:
        path.write_bytes(_pem(self.certificate))
        return path

    def issue(self, directory: Path, *, ip: str | None, dns: list[str]) -> tuple[Path, Path]:
        """Un certificado de servidor con los nombres dados; devuelve (certificado, llave)."""
        key = ec.generate_private_key(ec.SECP256R1())
        now = dt.datetime.now(dt.UTC)
        names: list[x509.GeneralName] = [x509.DNSName(name) for name in dns]
        if ip:
            names.append(x509.IPAddress(ipaddress.ip_address(ip)))
        cert = (
            x509.CertificateBuilder()
            .subject_name(_name(dns[0] if dns else ip or "servidor"))
            .issuer_name(self.certificate.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=2))
            .add_extension(x509.SubjectAlternativeName(names), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(self.key, hashes.SHA256())
        )
        cert_path, key_path = directory / f"{self.common}-server.pem", directory / f"{self.common}-server.key"
        cert_path.write_bytes(_pem(cert))
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )
        return cert_path, key_path


class LoginServer:
    """El formulario. `pixel_hits` cuenta los GET de `/pixel.png` (lo que Chromium carga solo si confia en el certificado)."""

    def __init__(self, cert: Path, key: Path) -> None:
        self.pixel_hits = 0
        self.posts = 0
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                return None

            def do_GET(self) -> None:  # noqa: N802
                if self.path.startswith("/pixel.png"):
                    outer.pixel_hits += 1
                    self._send(200, PNG, "image/png")
                    return
                body = (
                    f'<html><body><img src="https://127.0.0.1:{outer.port}/pixel.png">'
                    '<form method="post" action="/auth"><input name="username"><input name="password" type="password">'
                    '<input type="submit" value="Entrar"></form></body></html>'
                ).encode()
                self._send(200, body, "text/html")

            def do_POST(self) -> None:  # noqa: N802
                outer.posts += 1
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.send_response(302)
                self.send_header("Location", f"https://127.0.0.1:{outer.port}/callback?code=c&state=s")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _send(self, status: int, body: bytes, kind: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        self._server.socket = context.wrap_socket(self._server.socket, server_side=True)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> LoginServer:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
