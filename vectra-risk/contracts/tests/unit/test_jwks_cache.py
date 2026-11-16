"""P-U0-06, NFR-U0-11, 12."""

import asyncio

import pytest
from strategies.auth import ENC_KID, KID, jwks_document, keycloak_jwks_document

from vectra_common.errors import DependencyUnavailable, Unauthenticated
from vectra_common.jwks_cache import JwksCache


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Fetch:
    def __init__(self):
        self.calls, self.fail = 0, False

    async def __call__(self):
        self.calls += 1
        await asyncio.sleep(0)
        if self.fail:
            raise DependencyUnavailable()
        return jwks_document()


async def test_cached_for_10_minutes():
    clock, fetch = Clock(), Fetch()
    cache = JwksCache(fetch, clock)
    await cache.get_key(KID)
    clock.t += 599
    await cache.get_key(KID)
    assert fetch.calls == 1
    clock.t += 2
    await cache.get_key(KID)
    assert fetch.calls == 2


async def test_100_concurrent_unknown_kid_one_refresh():
    clock, fetch = Clock(), Fetch()
    cache = JwksCache(fetch, clock)
    results = await asyncio.gather(*(cache.get_key("falso") for _ in range(100)), return_exceptions=True)
    assert fetch.calls == 1
    assert all(isinstance(r, Unauthenticated) for r in results)


async def test_refresh_limited_to_one_per_30s():
    clock, fetch = Clock(), Fetch()
    cache = JwksCache(fetch, clock)
    await cache.get_key(KID)
    for _ in range(100):
        with pytest.raises(Unauthenticated):
            await cache.get_key("falso")
    assert fetch.calls == 1
    clock.t += 31
    with pytest.raises(Unauthenticated):
        await cache.get_key("falso")
    assert fetch.calls == 2


async def test_jwks_down_with_expired_cache_is_503():
    clock, fetch = Clock(), Fetch()
    cache = JwksCache(fetch, clock)
    await cache.get_key(KID)
    fetch.fail = True
    clock.t += 601
    with pytest.raises(DependencyUnavailable):
        await cache.get_key(KID)


async def test_jwks_down_with_valid_cache_still_verifies():
    clock, fetch = Clock(), Fetch()
    cache = JwksCache(fetch, clock)
    await cache.get_key(KID)
    fetch.fail = True
    clock.t += 31
    with pytest.raises(Unauthenticated):
        await cache.get_key("otro")
    assert await cache.get_key(KID)


async def test_no_cache_and_keycloak_down_is_503():
    fetch = Fetch()
    fetch.fail = True
    with pytest.raises(DependencyUnavailable):
        await JwksCache(fetch, Clock()).get_key(KID)


async def test_malformed_document_is_503_without_cache():
    async def bad():
        return {"sin": "keys"}

    with pytest.raises(DependencyUnavailable):
        await JwksCache(bad, Clock()).get_key(KID)


async def _keycloak_fetch():
    return keycloak_jwks_document()


async def test_jwks_keycloak_shape_encryption_key_does_not_break_the_cache():
    cache = JwksCache(_keycloak_fetch, Clock())
    assert (await cache.get_key(KID)).key is not None
    assert cache._valid()


async def test_jwks_encryption_kid_is_unauthenticated():
    cache = JwksCache(_keycloak_fetch, Clock())
    await cache.get_key(KID)
    with pytest.raises(Unauthenticated):
        await cache.get_key(ENC_KID)


async def test_jwks_unreadable_signing_key_is_skipped_and_others_load():
    broken = {"kid": "bad", "kty": "RSA", "alg": "RSA-OAEP", "use": "sig", "n": "AQAB", "e": "AQAB"}

    async def fetch():
        doc = keycloak_jwks_document()
        return {"keys": [broken, *doc["keys"]]}

    cache = JwksCache(fetch, Clock())
    assert (await cache.get_key(KID)).key is not None
    with pytest.raises(Unauthenticated):
        await cache.get_key("bad")


async def test_jwks_without_any_readable_signing_key_is_a_refresh_error():
    async def fetch():
        return {"keys": [k for k in keycloak_jwks_document()["keys"] if k["use"] == "enc"]}

    cache = JwksCache(fetch, Clock())
    with pytest.raises(DependencyUnavailable):
        await cache.get_key(KID)
    with pytest.raises(DependencyUnavailable):
        await cache.get_key(ENC_KID)
