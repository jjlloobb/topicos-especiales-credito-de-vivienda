"""Emisor OIDC de prueba (P-1 (a) de U10-T03; solo pruebas): lo minimo de Keycloak que usan la PoC del step-up y la SPA.

Vive bajo `/auth/realms/vectra/` (como el realm de U2, un solo origen con la SPA) y firma con la llave de
`contracts/tests/strategies/auth.py`. Sirve descubrimiento, JWKS, autorizacion (formulario **sin scripts** para elegir al usuario
de prueba), token con PKCE S256, refresh rotativo, `end_session`, `prompt=none`, `prompt=login`, `max_age` y `acr_values`.

Simplificaciones declaradas (no es Keycloak): el factor MFA se **simula** (`acr = mfa` si la solicitud pide `acr_values=mfa`,
`pwd` si no); no hay contrasenas; un solo cliente (`vectra-console`, publico) con dos `redirect_uri` (`/callback` y
`/stepup-callback`, como `realm.*.yaml` de U2); los tokens duran `access_ttl` segundos (300 por omision).

`GET /auth/__e2e/stats` cuenta las llamadas por endpoint (la PoC demuestra con eso que un mensaje ajeno no llego a canjear nada)
y `POST /auth/__e2e/reset` las pone en cero.
"""

import base64
import hashlib
import html
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final
from urllib.parse import parse_qs, urlencode

import jwt
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route
from strategies import auth as u0

REALM_PATH: Final = "/auth/realms/vectra"
OIDC_PATH: Final = f"{REALM_PATH}/protocol/openid-connect"
CLIENT_ID: Final = "vectra-console"
BFF_AUDIENCE: Final = "console-bff"
COOKIE: Final = "VECTRA_SSO"
#: usuario de prueba -> rol (los cuatro roles de la consola)
USERS: Final = {
    "analista": "analista",
    "ingeniero_riesgo": "ingeniero_riesgo",
    "cro": "cro",
    "cumplimiento": "cumplimiento",
}
DEFAULT_USER: Final = "analista"


@dataclass
class Session:
    user: str
    auth_time: int
    acr: str


@dataclass
class IssuedCode:
    redirect_uri: str
    challenge: str
    nonce: str | None
    session_id: str
    scope: str


@dataclass
class RefreshRecord:
    session_id: str
    scope: str
    used: bool = False


@dataclass
class Stats:
    discovery: int = 0
    authorize: int = 0
    token: int = 0
    token_authorization_code: int = 0
    token_refresh: int = 0
    end_session: int = 0

    def asdict(self) -> dict[str, int]:
        return dict(self.__dict__)


@dataclass
class OidcIssuer:
    """El estado del emisor (sesiones, codigos, refresh tokens) y su aplicacion ASGI."""

    origin: str
    clock: Callable[[], float] = time.time
    access_ttl: int = 300
    sessions: dict[str, Session] = field(default_factory=dict)
    codes: dict[str, IssuedCode] = field(default_factory=dict)
    refresh_tokens: dict[str, RefreshRecord] = field(default_factory=dict)
    stats: Stats = field(default_factory=Stats)

    @property
    def issuer(self) -> str:
        return f"{self.origin}{REALM_PATH}"

    @property
    def redirect_uris(self) -> frozenset[str]:
        return frozenset({f"{self.origin}/callback", f"{self.origin}/stepup-callback"})

    # ---- tokens -------------------------------------------------------------------------------------------------------
    def _sign(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, u0.KEY, algorithm="RS256", headers={"kid": u0.KID})

    def tokens(self, session_id: str, scope: str, nonce: str | None) -> dict[str, Any]:
        session = self.sessions[session_id]
        now = int(self.clock())
        common = {
            "iss": self.issuer,
            "sub": session.user,
            "iat": now,
            "exp": now + self.access_ttl,
            "auth_time": session.auth_time,
            "acr": session.acr,
            "azp": CLIENT_ID,
        }
        access = {**common, "aud": BFF_AUDIENCE, "roles": [USERS[session.user]], "typ": "Bearer"}
        identity = {**common, "aud": CLIENT_ID, "preferred_username": session.user, "typ": "ID"}
        if nonce is not None:
            identity["nonce"] = nonce
        refresh = secrets.token_urlsafe(32)
        self.refresh_tokens[refresh] = RefreshRecord(session_id, scope)
        return {
            "access_token": self._sign(access),
            "id_token": self._sign(identity),
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": self.access_ttl,
            "scope": scope,
        }

    # ---- endpoints ----------------------------------------------------------------------------------------------------
    async def discovery(self, _: Request) -> Response:
        self.stats.discovery += 1
        base = f"{self.origin}{OIDC_PATH}"
        return _json(
            {
                "issuer": self.issuer,
                "authorization_endpoint": f"{base}/auth",
                "token_endpoint": f"{base}/token",
                "jwks_uri": f"{base}/certs",
                "end_session_endpoint": f"{base}/logout",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "refresh_token"],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
                "scopes_supported": ["openid"],
                "acr_values_supported": ["pwd", "mfa"],
            }
        )

    async def certs(self, _: Request) -> Response:
        return _json(u0.jwks_document())

    async def authorize(self, request: Request) -> Response:
        self.stats.authorize += 1
        params = {
            key: values[0] for key, values in parse_qs(request.url.query, keep_blank_values=True).items()
        }
        error = self._check_request(params)
        if error is not None:
            return HTMLResponse(f"<p>invalid_request: {html.escape(error)}</p>", status_code=400)
        session_id = request.cookies.get(COOKIE)
        session = self.sessions.get(session_id) if session_id else None
        prompts = set(params.get("prompt", "").split())
        interactive = session is None or "login" in prompts or not self._satisfies(session, params)
        if "none" in prompts:
            if interactive:
                reason = "login_required" if session is None else "interaction_required"
                return self._error_redirect(params, reason)
            assert session_id is not None
            return self._code_redirect(params, session_id)
        if not interactive:
            assert session_id is not None
            return self._code_redirect(params, session_id)
        return HTMLResponse(self._form(params))

    async def login_action(self, request: Request) -> Response:
        form = {key: values[0] for key, values in parse_qs((await request.body()).decode()).items()}
        params = {key: values[0] for key, values in parse_qs(form.get("query", "")).items()}
        user = form.get("username", "")
        if self._check_request(params) is not None or user not in USERS:
            return HTMLResponse("<p>invalid_request</p>", status_code=400)
        acr = "mfa" if "mfa" in params.get("acr_values", "").split() else "pwd"
        session_id = secrets.token_urlsafe(24)
        self.sessions[session_id] = Session(user, int(self.clock()), acr)
        response = self._code_redirect(params, session_id)
        response.set_cookie(COOKIE, session_id, path="/auth", httponly=True, samesite="lax")
        return response

    async def token(self, request: Request) -> Response:
        self.stats.token += 1
        form = {key: values[0] for key, values in parse_qs((await request.body()).decode()).items()}
        grant = form.get("grant_type")
        if form.get("client_id") != CLIENT_ID:
            return _oauth_error("invalid_client", 401)
        if grant == "authorization_code":
            self.stats.token_authorization_code += 1
            return self._exchange_code(form)
        if grant == "refresh_token":
            self.stats.token_refresh += 1
            return self._exchange_refresh(form)
        return _oauth_error("unsupported_grant_type")

    async def end_session(self, request: Request) -> Response:
        self.stats.end_session += 1
        session_id = request.cookies.get(COOKIE)
        if session_id:
            self._drop_session(session_id)
        target = request.query_params.get("post_logout_redirect_uri", "")
        if target and target.rstrip("/") == self.origin:
            state = request.query_params.get("state")
            response: Response = RedirectResponse(
                target + (f"?{urlencode({'state': state})}" if state else ""), 302
            )
        else:
            response = HTMLResponse("<p>logged_out</p>")
        response.delete_cookie(COOKIE, path="/auth")
        return response

    async def read_stats(self, _: Request) -> Response:
        return _json(self.stats.asdict())

    async def reset(self, _: Request) -> Response:
        self.stats = Stats()
        return _json({})

    # ---- internos -----------------------------------------------------------------------------------------------------
    def _check_request(self, params: dict[str, str]) -> str | None:
        if params.get("client_id") != CLIENT_ID:
            return "client_id"
        if params.get("redirect_uri") not in self.redirect_uris:
            return "redirect_uri"
        if params.get("response_type") != "code":
            return "response_type"
        if params.get("code_challenge_method") != "S256" or not params.get("code_challenge"):
            return "pkce"
        return None

    def _satisfies(self, session: Session, params: dict[str, str]) -> bool:
        """La sesion existente sirve si cumple `acr_values` y `max_age` de la solicitud."""
        if "mfa" in params.get("acr_values", "").split() and session.acr != "mfa":
            return False
        max_age = params.get("max_age")
        return max_age is None or 0 < int(max_age) and int(self.clock()) - session.auth_time <= int(max_age)

    def _code_redirect(self, params: dict[str, str], session_id: str) -> RedirectResponse:
        code = secrets.token_urlsafe(24)
        self.codes[code] = IssuedCode(
            params["redirect_uri"],
            params["code_challenge"],
            params.get("nonce"),
            session_id,
            params.get("scope", "openid"),
        )
        query = {"code": code, **({"state": params["state"]} if "state" in params else {})}
        return RedirectResponse(f"{params['redirect_uri']}?{urlencode(query)}", 303)

    def _error_redirect(self, params: dict[str, str], error: str) -> RedirectResponse:
        query = {"error": error, **({"state": params["state"]} if "state" in params else {})}
        return RedirectResponse(f"{params['redirect_uri']}?{urlencode(query)}", 303)

    def _form(self, params: dict[str, str]) -> str:
        step_up = "mfa" in params.get("acr_values", "").split()
        title = "Verificacion en dos pasos (simulada)" if step_up else "Inicio de sesion"
        options = "".join(f'<option value="{name}">{name}</option>' for name in USERS)
        query = html.escape(urlencode(params), quote=True)
        return (
            "<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Emisor de prueba</title></head><body>"
            f"<h1>{title}</h1>"
            f"<form method='post' action='{OIDC_PATH}/login-actions/authenticate'>"
            f"<input type='hidden' name='query' value='{query}'>"
            f"<label for='username'>Usuario</label><select id='username' name='username'>{options}</select>"
            f"<button type='submit' id='kc-login'>{'Verificar' if step_up else 'Entrar'}</button>"
            "</form></body></html>"
        )

    def _exchange_code(self, form: dict[str, str]) -> Response:
        issued = self.codes.pop(form.get("code", ""), None)  # un codigo sirve una sola vez
        if issued is None or issued.redirect_uri != form.get("redirect_uri"):
            return _oauth_error("invalid_grant")
        verifier = form.get("code_verifier", "")
        digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        if not secrets.compare_digest(digest, issued.challenge):
            return _oauth_error("invalid_grant")
        return _json(self.tokens(issued.session_id, issued.scope, issued.nonce))

    def _exchange_refresh(self, form: dict[str, str]) -> Response:
        record = self.refresh_tokens.get(form.get("refresh_token", ""))
        if record is None:
            return _oauth_error("invalid_grant")
        if record.used:  # reuso de un token rotado: se revoca toda la familia (la sesion)
            self._drop_session(record.session_id)
            return _oauth_error("invalid_grant")
        record.used = True
        if record.session_id not in self.sessions:
            return _oauth_error("invalid_grant")
        return _json(self.tokens(record.session_id, record.scope, None))

    def _drop_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        for token in [t for t, r in self.refresh_tokens.items() if r.session_id == session_id]:
            del self.refresh_tokens[token]

    def app(self) -> Starlette:
        return Starlette(
            routes=[
                Route(f"{REALM_PATH}/.well-known/openid-configuration", self.discovery),
                Route(f"{OIDC_PATH}/certs", self.certs),
                Route(f"{OIDC_PATH}/auth", self.authorize),
                Route(f"{OIDC_PATH}/login-actions/authenticate", self.login_action, methods=["POST"]),
                Route(f"{OIDC_PATH}/token", self.token, methods=["POST"]),
                Route(f"{OIDC_PATH}/logout", self.end_session),
                Route("/auth/__e2e/stats", self.read_stats),
                Route("/auth/__e2e/reset", self.reset, methods=["POST"]),
            ]
        )


def _json(data: dict[str, Any], status: int = 200) -> Response:
    return JSONResponse(data, status_code=status, headers={"cache-control": "no-store"})


def _oauth_error(error: str, status: int = 400) -> Response:
    return _json({"error": error}, status)


def decode_claims(token: str) -> dict[str, Any]:
    """Los claims de un JWT sin verificar (para las pruebas)."""
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


__all__ = ["CLIENT_ID", "OIDC_PATH", "REALM_PATH", "USERS", "OidcIssuer", "decode_claims"]
