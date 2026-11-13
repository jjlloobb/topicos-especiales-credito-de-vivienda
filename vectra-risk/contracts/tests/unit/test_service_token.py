"""`service_token`: client credentials con `private_key_jwt` (U2 BR-U2-09). Entra en la mutacion."""

import asyncio
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from vectra_common import service_token as st
from vectra_common.errors import DependencyUnavailable
from vectra_common.service_token import ServiceTokenProvider, provider_from_env

NOW = 1_800_000_000.0
URL = "https://kc/token"
AUD = "https://issuer.example/realms/vectra"  # emisor: distinto de la URL de token


def pem(key: Any) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


def public_pem(key: Any) -> str:
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


EC_KEY = ec.generate_private_key(ec.SECP256R1())


class Poster:
    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, dict[str, str], float]] = []

    async def __call__(self, url: str, data: Any, timeout: float) -> Any:
        self.calls.append((url, dict(data), timeout))
        return self.answers.pop(0)


def provider(poster: Any, now: dict[str, float] | None = None, **over: Any) -> ServiceTokenProvider:
    clock = now if now is not None else {"value": NOW}
    return ServiceTokenProvider(
        "case-worker",
        URL,
        pem(EC_KEY),
        "scoring-service",
        ("case:recommend", "otro:scope"),
        assertion_audience=AUD,
        poster=poster,
        clock=lambda: clock["value"],
        **over,
    )


def ok(token: str = "uno", expires: Any = 60) -> dict[str, Any]:
    return {"access_token": token, "expires_in": expires}


async def test_the_request_is_exactly_client_credentials_with_assertion():
    poster = Poster(ok())
    assert await provider(poster).token() == "uno"
    url, data, timeout = poster.calls[0]
    assert url == URL and timeout == st.TOKEN_TIMEOUT == 2.0
    assert set(data) == {"grant_type", "client_assertion_type", "client_assertion", "scope", "audience"}
    assert data["grant_type"] == "client_credentials"
    assert data["client_assertion_type"] == "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
    assert data["scope"] == "case:recommend otro:scope"
    assert data["audience"] == "scoring-service"


async def test_assertion_claims_and_signature():
    poster = Poster(ok())
    await provider(poster).token()
    assertion = poster.calls[0][1]["client_assertion"]
    assert jwt.get_unverified_header(assertion)["alg"] == "ES256"
    assert "kid" not in jwt.get_unverified_header(assertion)
    claims = jwt.decode(
        assertion,
        public_pem(EC_KEY),
        algorithms=["ES256"],
        audience=AUD,
        options={"verify_exp": False, "verify_iat": False, "verify_nbf": False},
    )
    assert claims["iss"] == claims["sub"] == "case-worker"
    assert claims["aud"] == AUD
    assert claims["iat"] == int(NOW)
    assert claims["exp"] == int(NOW) + st.ASSERTION_LIFETIME == int(NOW) + 60
    assert len(claims["jti"]) == 32
    assert set(claims) == {"iss", "sub", "aud", "jti", "iat", "exp"}


async def test_jti_changes_between_assertions_and_kid_is_sent():
    poster = Poster(ok("a", 0), ok("b", 0))
    source = provider(poster, key_id="k1")
    await source.token()
    await source.token()
    first, second = (call[1]["client_assertion"] for call in poster.calls)
    assert jwt.get_unverified_header(first)["kid"] == "k1"
    options = {"verify_signature": False}
    assert jwt.decode(first, options=options)["jti"] != jwt.decode(second, options=options)["jti"]


async def test_other_algorithm_is_honored():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    poster = Poster(ok())
    source = ServiceTokenProvider(
        "c",
        URL,
        pem(key),
        "a",
        ("s",),
        assertion_audience=AUD,
        algorithm="RS256",
        poster=poster,
        clock=lambda: NOW,
    )
    await source.token()
    assert jwt.get_unverified_header(poster.calls[0][1]["client_assertion"])["alg"] == "RS256"


async def test_token_is_cached_until_renew_before():
    now = {"value": NOW}
    poster = Poster(ok("uno", 60), ok("dos", 60))
    source = provider(poster, now)
    assert await source.token() == "uno"
    now["value"] = NOW + 60 - st.RENEW_BEFORE - 1
    assert await source.token() == "uno"
    assert len(poster.calls) == 1
    now["value"] = NOW + 60 - st.RENEW_BEFORE  # justo en el limite ya se renueva
    assert await source.token() == "dos"
    assert st.RENEW_BEFORE == 30


async def test_invalidate_forces_a_new_token():
    poster = Poster(ok("uno"), ok("dos"))
    source = provider(poster)
    await source.token()
    source.invalidate()
    assert await source.token() == "dos"


async def test_token_is_a_string_and_expiry_accepts_text():
    poster = Poster({"access_token": 123, "expires_in": "60"})
    assert await provider(poster).token() == "123"


async def test_concurrent_requests_ask_for_one_token():
    poster = Poster(ok())
    source = provider(poster)
    assert await asyncio.gather(source.token(), source.token(), source.token()) == ["uno"] * 3
    assert len(poster.calls) == 1


@pytest.mark.parametrize(
    "answer",
    [{"expires_in": 60}, {"access_token": "x"}, None, {"access_token": "x", "expires_in": "nunca"}],
)
async def test_malformed_answer_is_unavailable(answer):
    with pytest.raises(DependencyUnavailable):
        await provider(Poster(answer)).token()


async def test_default_poster_is_the_one_from_deps(monkeypatch):
    poster = Poster(ok())
    monkeypatch.setattr(st.deps, "post_form_once", poster)
    source = ServiceTokenProvider("c", URL, pem(EC_KEY), "a", ("s",), assertion_audience=AUD)
    assert await source.token() == "uno"
    assert poster.calls[0][0] == URL


async def test_default_clock_is_real_time():
    poster = Poster(ok("uno", 3600), ok("dos", 3600))
    source = ServiceTokenProvider("c", URL, pem(EC_KEY), "a", ("s",), assertion_audience=AUD, poster=poster)
    assert await source.token() == "uno"
    assert await source.token() == "uno"


async def test_provider_from_env_reads_everything(tmp_path, monkeypatch):
    path = tmp_path / "key.pem"
    path.write_text(pem(EC_KEY), encoding="utf-8")
    monkeypatch.setenv("VECTRA_CLIENT_ID", "case-worker")
    monkeypatch.setenv("VECTRA_TOKEN_URL", URL)
    monkeypatch.setenv("VECTRA_ASSERTION_AUDIENCE", AUD)
    monkeypatch.setenv("VECTRA_CLIENT_KEY_PATH", str(path))
    monkeypatch.setenv("VECTRA_CLIENT_KEY_ID", "k9")
    poster = Poster(ok())
    monkeypatch.setattr(st.deps, "post_form_once", poster)
    source = provider_from_env("scoring-service", ("case:recommend",))
    await source.token()
    url, data, _ = poster.calls[0]
    assert url == URL and data["audience"] == "scoring-service" and data["scope"] == "case:recommend"
    header = jwt.get_unverified_header(data["client_assertion"])
    assert header["kid"] == "k9"
    assert jwt.decode(data["client_assertion"], options={"verify_signature": False})["iss"] == "case-worker"


async def test_key_id_is_optional_in_the_environment(tmp_path, monkeypatch):
    path = tmp_path / "key.pem"
    path.write_text(pem(EC_KEY), encoding="utf-8")
    monkeypatch.setenv("VECTRA_CLIENT_ID", "c")
    monkeypatch.setenv("VECTRA_TOKEN_URL", URL)
    monkeypatch.setenv("VECTRA_ASSERTION_AUDIENCE", AUD)
    monkeypatch.setenv("VECTRA_CLIENT_KEY_PATH", str(path))
    monkeypatch.delenv("VECTRA_CLIENT_KEY_ID", raising=False)
    poster = Poster(ok())
    monkeypatch.setattr(st.deps, "post_form_once", poster)
    source = provider_from_env("a", ("s",))
    await source.token()
    assert "kid" not in jwt.get_unverified_header(poster.calls[0][1]["client_assertion"])


# --- U00-T04: la `aud` de la asercion es el emisor configurado, no la URL a la que se envia ---


async def test_assertion_audience_is_the_configured_one_and_not_the_token_url():
    poster = Poster(ok())
    await provider(poster).token()
    claims = jwt.decode(poster.calls[0][1]["client_assertion"], options={"verify_signature": False})
    assert claims["aud"] == AUD and claims["aud"] != URL


async def test_assertion_audience_request_goes_to_the_token_url():
    poster = Poster(ok())
    await provider(poster).token()
    assert poster.calls[0][0] == URL != AUD


async def test_assertion_audience_claims_and_form_are_unchanged():
    poster = Poster(ok())
    await provider(poster).token()
    data = poster.calls[0][1]
    claims = jwt.decode(data["client_assertion"], options={"verify_signature": False})
    assert set(claims) == {"iss", "sub", "aud", "jti", "iat", "exp"}
    assert data["audience"] == "scoring-service" != AUD  # la del access token no cambia


def _env(tmp_path, monkeypatch, audience: str | None) -> None:
    path = tmp_path / "key.pem"
    path.write_text(pem(EC_KEY), encoding="utf-8")
    monkeypatch.setenv("VECTRA_CLIENT_ID", "c")
    monkeypatch.setenv("VECTRA_TOKEN_URL", URL)
    monkeypatch.setenv("VECTRA_CLIENT_KEY_PATH", str(path))
    if audience is None:
        monkeypatch.delenv("VECTRA_ASSERTION_AUDIENCE", raising=False)
    else:
        monkeypatch.setenv("VECTRA_ASSERTION_AUDIENCE", audience)


async def test_assertion_audience_is_read_from_the_environment(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, AUD)
    poster = Poster(ok())
    monkeypatch.setattr(st.deps, "post_form_once", poster)
    await provider_from_env("a", ("s",)).token()
    url, data, _ = poster.calls[0]
    assert url == URL
    assert jwt.decode(data["client_assertion"], options={"verify_signature": False})["aud"] == AUD


def test_assertion_audience_missing_in_the_environment_fails_when_building(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, None)
    with pytest.raises(KeyError, match="VECTRA_ASSERTION_AUDIENCE"):
        provider_from_env("a", ("s",))


def test_assertion_audience_empty_in_the_environment_fails_when_building(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, "")
    with pytest.raises(ValueError, match="assertion_audience"):
        provider_from_env("a", ("s",))


def test_assertion_audience_empty_is_a_value_error():
    with pytest.raises(ValueError, match="assertion_audience"):
        ServiceTokenProvider("c", URL, pem(EC_KEY), "a", ("s",), assertion_audience="")


def test_assertion_audience_is_required_by_name():
    with pytest.raises(TypeError, match="assertion_audience"):
        ServiceTokenProvider("c", URL, pem(EC_KEY), "a", ("s",))  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        ServiceTokenProvider("c", URL, pem(EC_KEY), "a", ("s",), AUD)  # type: ignore[misc]
