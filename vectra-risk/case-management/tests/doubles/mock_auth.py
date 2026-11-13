"""Tokens y autenticador de prueba para el mock del core (Paso 17): llaves RSA generadas en la prueba, ninguna toca Keycloak.

Patron de `contracts/tests/strategies/auth.py` (U0) y de `scoring-explainability/tests/doubles/auth.py`: ninguna unidad importa las
pruebas de otra.
"""

import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from vectra_common.authn import Authenticator
from vectra_common.jwks_cache import JwksCache

ISSUER = "https://keycloak.test/auth/realms/vectra"
KID = "k1"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks_document() -> dict[str, Any]:
    jwk = json.loads(RSAAlgorithm.to_jwk(KEY.public_key()))
    return {"keys": [{**jwk, "kid": KID, "alg": "RS256", "use": "sig"}]}


def authenticator(service: str = "core-banking-mock") -> Authenticator:
    async def fetch() -> Any:
        return jwks_document()

    return Authenticator(issuer=ISSUER, audience=service, jwks=JwksCache(fetch))


def bearer(
    scope: str, *, aud: str = "core-banking-mock", sub: str = "svc-case", key: Any = None
) -> dict[str, str]:
    """Token de cliente (sin `roles`), firmado con la llave de la prueba o con otra (`key`)."""
    now = int(time.time())
    claims = {"sub": sub, "iss": ISSUER, "aud": aud, "exp": now + 300, "scope": scope, "azp": "case-service"}
    token = jwt.encode(claims, key or KEY, algorithm="RS256", headers={"kid": KID})
    return {"authorization": f"Bearer {token}"}
