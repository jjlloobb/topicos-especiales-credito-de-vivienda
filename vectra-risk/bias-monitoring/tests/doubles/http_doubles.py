"""Dobles HTTP **reales** (sockets en `127.0.0.1`, no `MockTransport`) para el subproceso de `python -m vectra_bias.app` (CA-2).

- `Keycloak`: sirve el JWKS de U0 (`/jwks`) y el endpoint de token (`/token`, `private_key_jwt`): verifica la asercion del cliente con la
  llave publica de `world.PRIVATE_KEY_PEM` y entrega `tok|<audiencia>|<scope>|<cliente>`.
- `RegistryU3`: las dos rutas de U3 que lee el servicio, con `Bearer` obligatorio; guarda cada token que recibe.
Siguen los contratos de `vectra_contracts` (`MonitoringWindow`, `FreezeRecord`).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs

import jwt
from cryptography.hazmat.primitives import serialization
from strategies import auth as u0_auth
from vectra_contracts.models.monitoring import MonitoringWindow
from world import _KEY

PUBLIC_KEY = _KEY.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
)
Reply = tuple[int, Any]


class HttpDouble:
    """Un servidor HTTP en un hilo. `handle(method, path, headers, body) -> (estado, json)`."""

    def __init__(self, handle: Callable[[str, str, dict[str, str], bytes], Reply]) -> None:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _serve(self) -> None:
                length = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(length) if length else b""
                status, payload = handle(
                    self.command, self.path, {k.lower(): v for k, v in self.headers.items()}, body
                )
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = _serve  # noqa: N815

            def log_message(self, *_: Any) -> None:  # sin ruido en la salida de pytest
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._outer = outer

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> HttpDouble:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


class Keycloak(HttpDouble):
    def __init__(self) -> None:
        self.requests: list[dict[str, str]] = []
        super().__init__(self._handle)

    def _handle(self, method: str, path: str, headers: dict[str, str], body: bytes) -> Reply:
        if method == "GET" and path == "/jwks":
            return 200, u0_auth.jwks_document()
        if method == "POST" and path == "/token":
            form = {k: v[0] for k, v in parse_qs(body.decode()).items()}
            claims = jwt.decode(
                form["client_assertion"], PUBLIC_KEY, algorithms=["ES256"], audience=self.url + "/token"
            )
            self.requests.append(
                {"client_id": claims["sub"], "audience": form["audience"], "scope": form["scope"]}
            )
            token = f"tok|{form['audience']}|{form['scope']}|{claims['sub']}"
            return 200, {"access_token": token, "expires_in": 300}
        return 404, {"code": "not_found"}


class RegistryU3(HttpDouble):
    def __init__(self, freezes: list[dict[str, Any]]) -> None:
        self.freezes = freezes
        self.tokens: list[tuple[str, str, str]] = []  # (cliente, audiencia, scope) de cada llamada
        super().__init__(self._handle)

    def _handle(self, method: str, path: str, headers: dict[str, str], body: bytes) -> Reply:
        auth = headers.get("authorization", "")
        if not auth.startswith("Bearer tok|"):
            return 401, {"code": "unauthenticated"}
        _, audience, scope, client = auth.removeprefix("Bearer ").split("|")
        self.tokens.append((client, audience, scope))
        if scope != "registry:read:monitoring":
            return 403, {"code": "forbidden"}
        if method == "GET" and path == "/v1/monitoring/freezes":
            return 200, self.freezes
        if method == "POST" and path == "/v1/monitoring/daily:query":
            empty = MonitoringWindow(
                versions=[],
                counts=[],
                totals=[],
                unattributable_invalid=0,
                invalid_seqs=[],
                watermark_seq=1,
                lag_seconds=0,
            )
            return 200, json.loads(empty.model_dump_json())
        return 404, {"code": "not_found"}
