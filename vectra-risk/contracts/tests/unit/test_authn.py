"""BR-U0-70, NFR-U0-10."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from strategies import auth as a

from vectra_common.authn import authenticator_from_env, principal_from_claims
from vectra_common.errors import Unauthenticated
from vectra_contracts.catalog import Role, Scope
from vectra_contracts.errors import ContractViolation


async def check(value):
    return await a.authenticator().authenticate(value)


async def test_br_u0_70_valid_token_with_many_audiences():
    principal = await check(f"Bearer {a.token(aud=['console-bff', a.AUDIENCE])}")
    assert principal.subject == "user-1" and principal.roles == {Role.ANALISTA} and principal.kind == "user"


@pytest.mark.parametrize("value", [None, "", "Basic abc", "Bearer no-es-jwt"])
async def test_br_u0_70_missing_or_malformed(value):
    with pytest.raises(Unauthenticated):
        await check(value)


async def test_nfr_u0_10_alg_none():
    forged = jwt.encode(a.claims(), key=None, algorithm="none", headers={"kid": a.KID})
    with pytest.raises(Unauthenticated):
        await check(f"Bearer {forged}")


async def test_nfr_u0_10_hs256_signed_with_public_key():
    public = a.KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    import base64
    import hashlib
    import hmac
    import json

    def seg(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=")

    head = seg(json.dumps({"alg": "HS256", "kid": a.KID}).encode())
    body = seg(json.dumps(a.claims()).encode())
    signature = seg(hmac.new(public, head + b"." + body, hashlib.sha256).digest())
    with pytest.raises(Unauthenticated):
        await check(f"Bearer {(head + b'.' + body + b'.' + signature).decode()}")


@pytest.mark.parametrize(
    "over",
    [{"aud": "otro"}, {"iss": "https://otro"}, {"sub": None}, {"exp": None}, {"exp": -31}, {"nbf": 60}],
)
async def test_nfr_u0_10_claims_rejected(over):
    now = int(time.time())
    relative = {k: now + v if k in ("exp", "nbf") and v is not None else v for k, v in over.items()}
    with pytest.raises(Unauthenticated):
        await check(f"Bearer {a.token(**relative)}")


async def test_nfr_u0_10_clock_tolerance():
    assert await check(f"Bearer {a.token(exp=int(time.time()) - 20)}")
    assert await check(f"Bearer {a.token(nbf=int(time.time()) + 20)}")


async def test_wrong_signature():
    with pytest.raises(Unauthenticated):
        await check(f"Bearer {a.token(key=a.OTHER_KEY)}")


async def test_kid_missing():
    raw = jwt.encode(a.claims(), a.KEY, algorithm="RS256")
    with pytest.raises(Unauthenticated):
        await check(f"Bearer {raw}")


def test_principal_ignores_unknown_values():
    principal = principal_from_claims({"sub": "s", "exp": 1, "scope": "registry:read:metrics inventado"})
    assert principal.kind == "service" and principal.scopes == {Scope.REGISTRY_READ_METRICS} and principal.acr is None


def test_authenticator_from_env_requires_ca_for_https(monkeypatch):
    monkeypatch.setenv("VECTRA_OIDC_ISSUER", a.ISSUER)
    monkeypatch.setenv("VECTRA_JWKS_URL", "https://keycloak/certs")
    monkeypatch.delenv("VECTRA_CA_BUNDLE", raising=False)
    with pytest.raises(ContractViolation):
        authenticator_from_env("svc")


async def test_authenticator_from_env_uses_url(monkeypatch):
    monkeypatch.setenv("VECTRA_OIDC_ISSUER", a.ISSUER)
    monkeypatch.setenv("VECTRA_JWKS_URL", "http://keycloak/certs")
    auth = authenticator_from_env("svc")
    assert auth.audience == "svc" and auth.issuer == a.ISSUER
    calls = []

    async def fake(url, timeout):
        calls.append((url, timeout))
        return a.jwks_document()

    monkeypatch.setattr("vectra_common.deps.fetch_json_once", fake)
    assert await auth.jwks.get_key(a.KID)
    assert calls == [("http://keycloak/certs", 2.0)]
