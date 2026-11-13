"""Un emisor OIDC de prueba para los casos sin Keycloak (U12-T02, CA-4 y CA-5): firma tokens ES256, sirve el JWKS y atiende el endpoint de token.

Es un doble escrito a mano: lo que hace (PKCE S256, `refresh_token` rotativo que rechaza uno ya usado, aserciones `private_key_jwt` con `aud` = el emisor) esta medido contra el Keycloak real
en `test_oidc_headless.py`. Cuenta las solicitudes al endpoint de token y guarda los formularios recibidos (solo en memoria de la prueba).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from vectra_verification.clients.oidc import FormDriver
from vectra_verification.credentials import Secret


def _b64(number: int) -> str:
    return base64.urlsafe_b64encode(number.to_bytes(32, "big")).rstrip(b"=").decode()


def jwk_of(key: ec.EllipticCurvePrivateKey, kid: str) -> dict[str, str]:
    numbers = key.public_key().public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64(numbers.x),
        "y": _b64(numbers.y),
        "use": "sig",
        "alg": "ES256",
        "kid": kid,
    }


def pem_of(key: ec.EllipticCurvePrivateKey) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


class FakeIdp(httpx.BaseTransport):
    def __init__(self, issuer: str, now: Any, *, lifetime: int = 300) -> None:
        self.issuer = issuer
        self.now = now  # `() -> datetime`
        self.lifetime = lifetime
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.other_key = ec.generate_private_key(ec.SECP256R1())
        self.codes: dict[str, dict[str, Any]] = {}
        self.refresh_tokens: dict[str, dict[str, Any]] = {}
        self.service_keys: dict[str, ec.EllipticCurvePublicKey] = {}
        self.token_requests: list[dict[str, str]] = []
        self.jwks_requests = 0
        self.reject_refresh = False
        self.id_overrides: dict[str, Any] = {}
        self.access_overrides: dict[str, Any] = {}
        self.sign_with_other_key = False
        self.last_assertion_claims: dict[str, Any] = {}
        self.service_audience_policy = (
            "issuer"  # Keycloak 26.8.1 con `KC_HOSTNAME` completo: solo el emisor publico (U02-T21)
        )

    # ---- tokens ----------------------------------------------------------------------------------------------------------------------------------
    def _sign(self, claims: dict[str, Any]) -> str:
        key = self.other_key if self.sign_with_other_key else self.key
        return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "idp-1"})

    def _ts(self, delta: int = 0) -> int:
        at: datetime = self.now()
        return int(at.timestamp()) + delta

    def user_tokens(self, code: dict[str, Any]) -> dict[str, Any]:
        base = {
            "iss": self.issuer,
            "sub": code["user"],
            "iat": self._ts(),
            "exp": self._ts(self.lifetime),
            "acr": code["acr"],
            "auth_time": code["auth_time"],
            "azp": "vectra-console",
        }
        access = {
            **base,
            "aud": ["console-bff"],
            "roles": code["roles"],
            "typ": "Bearer",
            **self.access_overrides,
        }
        id_token = {**base, "aud": "vectra-console", "nonce": code["nonce"], "typ": "ID", **self.id_overrides}
        refresh = secrets.token_urlsafe(24)
        self.refresh_tokens[refresh] = {"code": code}
        return {
            "access_token": self._sign(access),
            "id_token": self._sign(id_token),
            "refresh_token": refresh,
            "expires_in": self.lifetime,
            "token_type": "Bearer",
        }

    # ---- transporte ------------------------------------------------------------------------------------------------------------------------------
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/protocol/openid-connect/certs"):
            self.jwks_requests += 1
            return httpx.Response(
                200, json={"keys": [jwk_of(self.key if not self.sign_with_other_key else self.key, "idp-1")]}
            )
        if request.method == "POST" and request.url.path.endswith("/protocol/openid-connect/token"):
            form = {k: v[-1] for k, v in parse_qs(request.content.decode()).items()}
            self.token_requests.append(form)
            return self._token(form)
        return httpx.Response(404, json={})

    def _error(self, description: str) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant", "error_description": description})

    def _token(self, form: dict[str, str]) -> httpx.Response:
        grant = form.get("grant_type")
        if grant == "authorization_code":
            code = self.codes.pop(form.get("code", ""), None)
            if (
                code is None
                or form.get("redirect_uri") != code["redirect_uri"]
                or form.get("client_id") != "vectra-console"
            ):
                return self._error("Code not valid")
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(form.get("code_verifier", "").encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            if challenge != code["code_challenge"]:
                return self._error("PKCE verification failed")
            return httpx.Response(200, json=self.user_tokens(code))
        if grant == "refresh_token":
            record = (
                None if self.reject_refresh else self.refresh_tokens.pop(form.get("refresh_token", ""), None)
            )
            if record is None:
                return self._error(
                    "Token is not active"
                )  # un refresh token ya usado: el realm los rota (`refreshTokenMaxReuse: 0`)
            return httpx.Response(200, json=self.user_tokens(record["code"]))
        if grant == "client_credentials":
            return self._client_credentials(form)
        return httpx.Response(400, json={"error": "unsupported_grant_type"})

    def _client_credentials(self, form: dict[str, str]) -> httpx.Response:
        client = form.get("client_id", "")
        public = self.service_keys.get(client)
        if public is None:
            return httpx.Response(401, json={"error": "invalid_client"})
        try:
            claims = jwt.decode(
                form.get("client_assertion", ""),
                public,
                algorithms=["ES256"],
                options={"verify_aud": False, "verify_exp": False, "verify_iat": False, "verify_nbf": False},
            )
        except jwt.PyJWTError:
            return httpx.Response(
                401,
                json={
                    "error": "invalid_client",
                    "error_description": "Invalid client or Invalid client credentials",
                },
            )
        self.last_assertion_claims = claims
        if (
            claims.get("aud") != self.issuer
            or claims.get("iss") != client
            or claims.get("sub") != client
            or int(claims["exp"]) - int(claims["iat"]) > 60
        ):
            return httpx.Response(
                400, json={"error": "invalid_client", "error_description": "Invalid token audience"}
            )
        scopes = form.get("scope", "").split()
        audience = ["decision-registry-service"] if "registry:read:metrics" in scopes else []
        token = {
            "iss": self.issuer,
            "azp": client,
            "sub": f"service-account-{client}",
            "aud": audience,
            "scope": " ".join(scopes),
            "iat": self._ts(),
            "exp": self._ts(self.lifetime),
        }
        return httpx.Response(
            200, json={"access_token": self._sign(token), "expires_in": self.lifetime, "token_type": "Bearer"}
        )


class ScriptedForm(FormDriver):
    """Hace de Keycloak y de Chromium: lee `state`, `nonce` y `code_challenge` de la URL de autorizacion, registra un `code` en el emisor y devuelve la URL de retorno."""

    def __init__(self, idp: FakeIdp, *, acr: str = "mfa", roles: dict[str, list[str]] | None = None) -> None:
        self.idp = idp
        self.acr = acr
        self.roles = roles or {}
        self.calls = 0
        self.authorize_urls: list[str] = []
        self.otp_codes: list[str] = []
        self.tamper_state = False
        self.tamper_nonce = False
        self.reject = False
        self.auth_time_offset = 0
        self.returned_urls: list[str] = []

    def submit(self, authorize_url: str, redirect_uri: str, username: str, password: Secret, otp: Any) -> str:
        self.calls += 1
        self.authorize_urls.append(authorize_url)
        query = {k: v[-1] for k, v in parse_qs(urlsplit(authorize_url).query).items()}
        assert (
            query["client_id"] == "vectra-console"
            and query["code_challenge_method"] == "S256"
            and query["redirect_uri"] == redirect_uri
        )
        if self.reject:
            from vectra_verification.clients.oidc import OidcError

            raise OidcError("login_rejected")
        self.otp_codes.append(otp())
        code = secrets.token_urlsafe(16)
        auth_time = self.idp._ts(self.auth_time_offset)
        nonce = "otro-nonce" if self.tamper_nonce else query["nonce"]
        self.idp.codes[code] = {
            "user": username,
            "acr": self.acr,
            "auth_time": auth_time,
            "nonce": nonce,
            "redirect_uri": redirect_uri,
            "code_challenge": query["code_challenge"],
            "roles": self.roles.get(username, ["analista"]),
        }
        state = "alterado" if self.tamper_state else query["state"]
        url = f"{redirect_uri}?state={state}&session_state=sesion&code={code}"
        self.returned_urls.append(url)
        return url


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True)
