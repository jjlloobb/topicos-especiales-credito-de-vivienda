"""Login OIDC con PKCE y redirect loopback contra Keycloak (cliente `promotion-tool`, U2; NFR-U4-20).

El token vive solo en memoria: no se escribe en ningun archivo, ni se registra, ni se pone en un mensaje de error. El navegador lo abre
una funcion inyectable (en las pruebas, un doble del IdP que sigue la redireccion).
"""

import base64
import hashlib
import secrets
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from vectra_promotion.errors import PromotionError

CLIENT_ID = "promotion-tool"
SCOPE = "openid governance:promotion"
OIDC = "/protocol/openid-connect"


class _Callback(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        query = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        self.server.result = query  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Login completo. Puedes cerrar esta ventana.\n")
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return  # sin registro de la URL: lleva el codigo de autorizacion


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def login(
    issuer: str,
    open_browser: Callable[[str], object],
    *,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 300.0,
) -> str:
    """Devuelve el `access_token` (solo en memoria). `issuer` es la URL del realm (`https://host/auth/realms/vectra`)."""
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    server = HTTPServer(("127.0.0.1", 0), _Callback)
    server.result = {}  # type: ignore[attr-defined]
    redirect_uri = f"http://127.0.0.1:{server.server_port}"  # sin ruta: como el diseno de U2 y el realm
    url = f"{issuer}{OIDC}/auth?" + urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        open_browser(url)
        thread.join(timeout)
        result: dict[str, str] = server.result  # type: ignore[attr-defined]
    finally:
        server.shutdown()
        server.server_close()
    if result.get("state") != state or "code" not in result:
        raise PromotionError("login_failed")
    with httpx.Client(transport=transport, timeout=10.0) as http:
        response = http.post(
            f"{issuer}{OIDC}/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": result["code"],
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
        )
    if response.status_code != 200 or "access_token" not in response.json():
        raise PromotionError("token_exchange_failed")
    return str(response.json()["access_token"])
