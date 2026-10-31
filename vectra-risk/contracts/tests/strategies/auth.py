"""Tokens de prueba y una app minima (solo pruebas)."""

import json
import time
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from vectra_common.app_factory import create_app
from vectra_common.authn import Authenticator
from vectra_common.jwks_cache import JwksCache
from vectra_contracts.models.api import DecisionRef
from vectra_contracts.routes import RouteContract

ISSUER = "https://keycloak.test/auth/realms/vectra"
AUDIENCE = "svc"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KID = "k1"


def jwks_document(kid: str = KID, key: Any = KEY) -> dict[str, Any]:
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    return {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}


def claims(**over: Any) -> dict[str, Any]:
    now = int(time.time())
    base = {"sub": "user-1", "iss": ISSUER, "aud": AUDIENCE, "exp": now + 300, "roles": ["analista"], "acr": "mfa", "auth_time": now}
    data = {**base, **over}
    return {k: v for k, v in data.items() if v is not None}


def token(key: Any = KEY, alg: str = "RS256", kid: str = KID, **over: Any) -> str:
    return jwt.encode(claims(**over), key, algorithm=alg, headers={"kid": kid})


def bearer(**over: Any) -> dict[str, str]:
    return {"authorization": f"Bearer {token(**over)}"}


def authenticator(fetch: Any = None) -> Authenticator:
    async def default() -> Any:
        return jwks_document()

    return Authenticator(issuer=ISSUER, audience=AUDIENCE, jwks=JwksCache(fetch or default))


async def ok_handler(ctx: Any) -> Any:
    from datetime import UTC, datetime
    from uuid import UUID

    return DecisionRef(case_id=UUID(int=1), registry_entry_id="1", recorded_at=datetime(2026, 1, 1, tzinfo=UTC))


def client_for(routes: list[RouteContract], handler: Any = ok_handler, auth: Any = None, **kwargs: Any) -> httpx.AsyncClient:
    handlers = {(r.method, r.path): handler for r in routes}
    app = create_app("svc", routes, handlers, authenticator=auth or authenticator(), **kwargs)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://svc")
