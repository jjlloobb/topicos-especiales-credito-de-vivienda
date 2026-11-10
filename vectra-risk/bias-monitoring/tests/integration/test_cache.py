"""Paso 9: la cache del dashboard (P-U9-03; NFR-U9-02): LRU de 64 entradas y 15 min, single-flight y errores sin guardar."""

from __future__ import annotations

import asyncio

import pytest
from scenario import seed
from service_support import TODAY as TODAY_SEED
from service_support import Service
from vectra_bias import config
from vectra_bias.cache import ENTRIES, HIT, LOOKUPS, MISS, SingleFlightCache
from world import World


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def run(coro):
    return asyncio.run(coro)


class Loader:
    """Un `load` que cuenta sus llamadas y puede esperar o fallar."""

    def __init__(self, value="v", fail: Exception | None = None, gate: asyncio.Event | None = None) -> None:
        self.calls = 0
        self.value = value
        self.fail = fail
        self.gate = gate

    async def __call__(self):
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        if self.fail is not None:
            raise self.fail
        return self.value


def test_the_defaults_are_the_constants_of_the_design():
    cache = SingleFlightCache()
    assert (cache._max, cache._ttl) == (config.CACHE_ENTRIES, config.CACHE_TTL_S) == (64, 900)


def test_ten_concurrent_lookups_with_the_same_key_make_one_load():
    async def go():
        gate = asyncio.Event()
        load = Loader(gate=gate)
        cache = SingleFlightCache()
        tasks = [asyncio.ensure_future(cache.get(("v1", None, 30), load)) for _ in range(10)]
        await asyncio.sleep(0)
        gate.set()
        results = await asyncio.gather(*tasks)
        return load.calls, results

    calls, results = run(go())
    assert calls == 1 and results == ["v"] * 10


def test_an_error_reaches_every_waiter_and_is_not_stored():
    async def go():
        gate = asyncio.Event()
        boom = Loader(fail=RuntimeError("x"), gate=gate)
        cache = SingleFlightCache()
        tasks = [asyncio.ensure_future(cache.get("k", boom)) for _ in range(3)]
        await asyncio.sleep(0)
        gate.set()
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        assert all(isinstance(o, RuntimeError) for o in outcomes) and boom.calls == 1
        assert "k" not in cache and len(cache) == 0
        good = Loader(value="ok")
        assert await cache.get("k", good) == "ok" and good.calls == 1  # la segunda consulta vuelve a leer
        return cache

    assert "k" in run(go())


def test_the_65th_entry_evicts_the_least_recently_used():
    async def go():
        cache = SingleFlightCache()
        for i in range(64):
            await cache.get(("v", None, i), Loader(i))
        await cache.get(("v", None, 0), Loader("nuevo"))  # usa la 0: ahora la menos usada es la 1
        await cache.get(("v", None, 64), Loader(64))  # la entrada 65
        return cache

    cache = run(go())
    assert len(cache) == 64
    assert ("v", None, 1) not in cache
    assert ("v", None, 0) in cache and ("v", None, 64) in cache
    assert ENTRIES._value.get() == 64


def test_an_entry_expires_after_15_minutes_of_the_simulated_clock():
    async def go():
        clock = Clock()
        cache = SingleFlightCache(clock=clock)
        first = Loader("a")
        assert await cache.get("k", first) == "a"
        clock.now += config.CACHE_TTL_S - 1
        assert await cache.get("k", Loader("b")) == "a"  # aun vigente
        clock.now += 1
        second = Loader("b")
        assert await cache.get("k", second) == "b" and second.calls == 1  # a los 15 min vence
        return cache

    assert len(run(go())) == 1


def test_lookups_are_counted_by_result_without_identifiers():
    before = {r: LOOKUPS.labels(result=r)._value.get() for r in (HIT, MISS)}

    async def go():
        cache = SingleFlightCache()
        await cache.get("k", Loader())
        await cache.get("k", Loader())

    run(go())
    assert LOOKUPS.labels(result=MISS)._value.get() == before[MISS] + 1
    assert LOOKUPS.labels(result=HIT)._value.get() == before[HIT] + 1


# --- por HTTP: el servicio con el doble del registro ------------------------------------------------------------------------


def _world() -> World:
    world = World()
    seed(world, "v1", TODAY_SEED, days=3, model="low", human="low")
    return world


def test_ten_concurrent_queries_with_the_same_key_read_the_registry_once():
    one = _world()
    service = Service(one)
    run(service.get("/v1/disparity?version=v1"))
    reads_for_one = len(one.registry.calls)
    assert reads_for_one == 3  # freezes + descubrimiento + rangos

    world = _world()
    service = Service(world)

    async def go():
        return await asyncio.gather(*[service.get("/v1/disparity?version=v1") for _ in range(10)])

    responses = run(go())
    assert [r.status_code for r in responses] == [200] * 10
    assert len(world.registry.calls) == reads_for_one  # una sola lectura, no diez
    assert len({r.text for r in responses}) == 1


def test_a_registry_error_is_not_cached_and_the_next_query_reads_again():
    world = _world()
    service = Service(world)
    world.registry.status = 500
    assert run(service.get("/v1/disparity?version=v1")).status_code == 503
    failed_reads = len(world.registry.calls)
    world.registry.status = None
    assert run(service.get("/v1/disparity?version=v1")).status_code == 200
    assert len(world.registry.calls) > failed_reads
    reads = len(world.registry.calls)
    assert run(service.get("/v1/disparity?version=v1")).status_code == 200
    assert len(world.registry.calls) == reads  # esta si salio de la cache


@pytest.mark.parametrize(
    "second", ["/v1/disparity?version=v1&window=7", "/v1/disparity?version=v1&attribute=region"]
)
def test_a_different_window_or_attribute_is_a_different_key(second):
    world = _world()
    service = Service(world)
    run(service.get("/v1/disparity?version=v1"))
    reads = len(world.registry.calls)
    assert run(service.get(second)).status_code == 200
    assert len(world.registry.calls) > reads
