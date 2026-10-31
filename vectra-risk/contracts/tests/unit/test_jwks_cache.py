"""P-U0-06, NFR-U0-11, 12."""

import asyncio

import pytest
from strategies.auth import KID, jwks_document

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
