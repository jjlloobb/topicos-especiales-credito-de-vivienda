"""Un gateway con Keycloak y consola falsos, por HTTP en localhost (U02-T15): para correr `identity.js` reducido con k6, sin clúster.

Solo lo que toca el script: pagina de login con formulario, `login-actions`, `token` (codigo con PKCE S256, refresh con rotacion y
`client_credentials` con la firma ES256 del `private_key_jwt` verificada con la llave publica del cliente), JWKS y `/api/console/**`
con un limite de 20 req/s (un solo contador: el script usa un solo `sub` en las rafagas) que responde 429 con `Retry-After`.
"""

import base64
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class FakeGateway:
    def __init__(
        self,
        public_keys: dict[str, ec.EllipticCurvePublicKey],
        password: str,
        limit: int,
        retry_after: str,
        overhead_delay_s: float = 0.0,
        limited_body: bytes | None = None,
        allowed_redirects: set[str] | None = None,
    ) -> None:
        self.public_keys, self.password, self.limit, self.retry_after = public_keys, password, limit, retry_after
        self.overhead_delay_s = overhead_delay_s  # espera antes de contestar /overhead: simula el sobrecosto de un tramo
        self.overhead_hits = 0
        self.limited_body = limited_body  # el cuerpo del 429 (None: el JSON `rate_limited`); b"" simula un 429 sin cuerpo
        self.allowed_redirects = allowed_redirects  # los redirect URI registrados del cliente (None: no se validan)
        self.redirects_seen: set[str] = set()
        self.sso_hits = 0  # peticiones de autorizacion que llegaron con la cookie SSO (Keycloak las autentica solas)
        self.paths: list[str] = []
        self.lock = threading.Lock()
        self.codes: dict[str, str] = {}
        self.redirects: dict[str, str] = {}
        self.refresh_tokens: set[str] = set()
        self.logins: set[str] = set()
        self.signed_clients: set[str] = set()
        self.bad_requests: list[str] = []
        self.console_hits: dict[int, int] = {}
        self.limited = 0
        handler = self._handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeGateway":
        self.thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.server.shutdown()
        self.server.server_close()

    def issue_code(self, challenge: str, redirect: str) -> str:
        with self.lock:
            code = f"code-{time.time_ns()}-{challenge[:8]}"
            self.codes[code] = challenge
            self.redirects[code] = redirect
        return code

    def check_redirect(self, redirect: str) -> None:
        """Keycloak responde 400 `Invalid redirect_uri` si no es uno de los registrados del cliente."""
        with self.lock:
            self.redirects_seen.add(redirect)
            if self.allowed_redirects is not None and redirect not in self.allowed_redirects:
                self.bad_requests.append(f"Invalid redirect_uri: {redirect}")

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                pass

            def reply(self, status: int, body: Any = b"", ctype: str = "application/json", headers: tuple = ()) -> None:
                data = json.dumps(body).encode() if isinstance(body, dict | list) else body.encode() if isinstance(body, str) else body
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                for name, value in headers:
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:
                parts = urlsplit(self.path)
                query = parse_qs(parts.query)
                if parts.path.endswith("/openid-connect/auth"):
                    if query.get("code_challenge_method") != ["S256"] or query.get("client_id") != ["vectra-console"]:
                        outer.bad_requests.append(f"auth sin PKCE S256: {query}")
                    redirect = query.get("redirect_uri", [""])[0]
                    outer.check_redirect(redirect)
                    if "KC_SSO=1" in self.headers.get("Cookie", ""):
                        # Como Keycloak: con la cookie SSO (Path=/auth/realms/vectra/) no pide credenciales y redirige con el codigo.
                        with outer.lock:
                            outer.sso_hits += 1
                        code = outer.issue_code(query["code_challenge"][0], redirect)
                        return self.reply(302, b"", "text/html", (("Location", f"{redirect}?code={code}&state=s"),))
                    action = (
                        f"{outer.url}/auth/realms/vectra/login-actions/authenticate"
                        f"?session_code=a&amp;tab_id=b&amp;challenge={query['code_challenge'][0]}"
                        f"&amp;redirect_uri={quote(redirect, safe='')}"
                    )
                    return self.reply(
                        200,
                        f'<form id="kc-form-login" action="{action}" method="post"><input type="hidden" name="credentialId" value=""/></form>',
                        "text/html",
                    )
                if parts.path.endswith("/openid-connect/certs"):
                    return self.reply(200, {"keys": [{"kid": "k", "alg": "ES256"}]})
                with outer.lock:
                    outer.paths.append(parts.path)
                if "/overhead" in parts.path:
                    with outer.lock:
                        outer.overhead_hits += 1
                    time.sleep(outer.overhead_delay_s)
                if parts.path.startswith("/api/console"):
                    if not self.headers.get("Authorization", "").startswith("Bearer access-"):
                        outer.bad_requests.append("consola sin Bearer")
                    with outer.lock:
                        second = int(time.time())
                        outer.console_hits[second] = outer.console_hits.get(second, 0) + 1
                        over = outer.console_hits[second] > outer.limit and "/overhead" not in parts.path
                        outer.limited += over
                    if over:
                        body = {"code": "rate_limited"} if outer.limited_body is None else outer.limited_body
                        return self.reply(429, body, "application/problem+json", (("Retry-After", outer.retry_after),))
                    return self.reply(200, {"ok": True})
                self.reply(404, {})

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode(), keep_blank_values=True).items()}
                parts = urlsplit(self.path)
                if "login-actions" in parts.path:
                    if form.get("password") != outer.password or "credentialId" not in form:
                        outer.bad_requests.append(f"login-actions: {sorted(form)}")
                    query = parse_qs(parts.query)
                    redirect = query.get("redirect_uri", [""])[0]
                    code = outer.issue_code(query["challenge"][0], redirect)
                    with outer.lock:
                        outer.logins.add(form.get("username", ""))
                    return self.reply(
                        302, b"", "text/html",
                        (("Location", f"{redirect}?code={code}&state=s"), ("Set-Cookie", "KC_SSO=1; Path=/auth/realms/vectra/; HttpOnly")),
                    )  # fmt: skip
                if parts.path.endswith("/openid-connect/token"):
                    return self.token(form)
                self.reply(404, {})

            def token(self, form: dict[str, str]) -> None:
                grant = form.get("grant_type")
                if grant == "authorization_code":
                    challenge = outer.codes.pop(form.get("code", ""), None)
                    outer.check_redirect(form.get("redirect_uri", ""))
                    if outer.redirects.get(form.get("code", "")) != form.get("redirect_uri"):
                        outer.bad_requests.append("token: el redirect_uri no es el de la autorizacion")
                    digest = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest()).rstrip(b"=").decode()
                    if challenge != digest:
                        outer.bad_requests.append("PKCE: el verifier no coincide con el challenge")
                        return self.reply(400, {"error": "invalid_grant"})
                elif grant == "refresh_token":
                    with outer.lock:
                        if form.get("refresh_token") not in outer.refresh_tokens:
                            return self.reply(400, {"error": "invalid_grant"})  # rotacion: un refresh token sirve una vez
                        outer.refresh_tokens.discard(form["refresh_token"])
                elif grant == "client_credentials":
                    return self.client_credentials(form)
                else:
                    return self.reply(400, {"error": "unsupported_grant_type"})
                refresh = f"refresh-{time.time_ns()}"
                with outer.lock:
                    outer.refresh_tokens.add(refresh)
                self.reply(200, {"access_token": f"access-{refresh}", "refresh_token": refresh, "expires_in": 300})

            def client_credentials(self, form: dict[str, str]) -> None:
                client = form.get("client_id", "")
                header, payload, signature = form["client_assertion"].split(".")
                claims, head = json.loads(_b64d(payload)), json.loads(_b64d(header))
                raw = _b64d(signature)
                valid = (
                    head.get("alg") == "ES256" and claims["iss"] == claims["sub"] == client and claims["exp"] > claims["iat"]
                    and claims["aud"].endswith("/openid-connect/token") and len(raw) == 64
                )  # fmt: skip
                if valid:
                    r, s = int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
                    try:
                        outer.public_keys[client].verify(
                            utils.encode_dss_signature(r, s), f"{header}.{payload}".encode(), ec.ECDSA(hashes.SHA256())
                        )
                    except Exception:  # noqa: BLE001 - cualquier fallo de firma invalida la aserción
                        valid = False
                if not valid:
                    return self.reply(401, {"error": "invalid_client"})
                with outer.lock:
                    outer.signed_clients.add(client)
                self.reply(200, {"access_token": f"access-svc-{client}", "expires_in": 300})

        return Handler
