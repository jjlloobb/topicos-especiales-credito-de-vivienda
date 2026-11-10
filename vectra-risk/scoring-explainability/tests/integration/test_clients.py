"""Paso 10 (CA-3): clientes por dependencia y cache de `serving-config` (P-U7-04, 05; NFR-U7-11; AUTONOMIA-04)."""

import asyncio
import time
from collections.abc import AsyncIterator

import pytest
from doubles.explainability import ExplainabilityDouble
from doubles.governance import GovernanceDouble
from doubles.kserve import KServeDouble
from doubles.registry import RegistryDouble
from doubles.samples import ISVC, explain_request, scoring_request, vector
from doubles.servers import Server
from doubles.worlds import ScoringWorld, StaticPolicy, scoring_world
from scoring import config
from scoring.app import Settings, build_deps
from vectra_common.deps import CircuitState
from vectra_common.metrics import REGISTRY as METRICS
from vectra_contracts.catalog import FailClosedCause
from vectra_contracts.models.explanation import FailClosed
from vectra_contracts.outcome import Recommendation


class Clock:
    """Un reloj monotonico a mano para el vencimiento de los 5 s sin esperar."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
async def world() -> AsyncIterator[ScoringWorld]:
    built = scoring_world()
    yield built
    await built.aclose()


def with_clock(world: ScoringWorld) -> Clock:
    clock = Clock()
    world.deps.orchestrator._serving._clock = clock  # noqa: SLF001
    return clock


async def test_each_dependency_has_its_own_pool_and_breaker(world: ScoringWorld) -> None:
    by_name = {}
    for client in world.deps.clients:
        pool = client._client._transport  # noqa: SLF001
        by_name[client.breaker._dependency] = client  # type: ignore[union-attr]  # noqa: SLF001
        assert pool is not None
    assert set(by_name) == {"predict", "explainability", "registry", "serving_config"}
    assert len({id(client.breaker) for client in by_name.values()}) == 4
    assert len({id(client._client) for client in by_name.values()}) == 4  # noqa: SLF001
    for client in by_name.values():
        assert client.breaker._config == config.BREAKER  # type: ignore[union-attr]  # noqa: SLF001
    assert (
        config.PREDICT_POOL,
        config.EXPLAINABILITY_POOL,
        config.REGISTRY_POOL,
        config.SERVING_CONFIG_POOL,
    ) == (20, 20, 10, 5)
    assert config.BREAKER.open_for == 10 and config.BREAKER.window_size == 20
    assert config.BREAKER.failure_ratio == 0.5 and config.BREAKER.window_seconds == 30


async def test_p_u7_05_serving_config_is_cached_for_5_s_and_revalidated_with_if_none_match(
    world: ScoringWorld,
) -> None:
    clock = with_clock(world)
    for _ in range(3):
        assert isinstance(await world.recommend(scoring_request()), Recommendation)
    assert world.gov.recorder.count("serving-config") == 1  # la cache sirve
    clock.now += 5.1
    assert isinstance(await world.recommend(scoring_request()), Recommendation)
    revalidation = world.gov.calls[-1]
    assert revalidation.headers["if-none-match"] == '"etag-1"'  # 304: misma entrada, sin descargar otra vez
    assert world.gov.recorder.count("serving-config") == 2


async def test_after_freezing_in_governance_the_next_requests_are_model_frozen_within_6_s(
    world: ScoringWorld,
) -> None:
    clock = with_clock(world)
    assert isinstance(await world.recommend(scoring_request()), Recommendation)
    world.gov.freeze()
    clock.now += 4.9  # aun dentro de la cache: se ve la vieja, pero nunca una entrada vencida
    assert isinstance(await world.recommend(scoring_request()), Recommendation)
    clock.now += 0.3  # 5,2 s: vencida
    started = time.perf_counter()
    result = await world.recommend(scoring_request())
    assert (
        isinstance(result, FailClosed)
        and result.cause is FailClosedCause.MODEL_FROZEN
        and not result.retryable
    )
    assert result.status == "modelo_congelado"
    assert time.perf_counter() - started < 1.0  # 5,2 s de cache + una llamada <= 6 s


async def test_an_expired_cache_with_governance_down_is_serving_config_unavailable_never_a_stale_entry(
    world: ScoringWorld,
) -> None:
    clock = with_clock(world)
    assert isinstance(await world.recommend(scoring_request()), Recommendation)
    clock.now += 5.1
    world.gov.config_faults.status = 503
    kserve_calls = len(world.kserve.recorder.calls)
    result = await world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.SERVING_CONFIG_UNAVAILABLE
    assert len(world.kserve.recorder.calls) == kserve_calls  # sin entrada vigente no se llama a KServe
    world.gov.config_faults.status = None  # governance vuelve: el etag sigue igual -> 304
    assert isinstance(await world.recommend(scoring_request()), Recommendation)


async def test_a_serving_config_timeout_is_counted_and_is_no_disponible(world: ScoringWorld) -> None:
    world.gov.config_faults.delay = 2.0
    before = METRICS.get_sample_value("vectra_deadline_exhausted_total", {"stage": "serving_config"}) or 0.0
    started = time.perf_counter()
    result = await world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.SERVING_CONFIG_UNAVAILABLE
    assert time.perf_counter() - started < 0.7
    assert (
        METRICS.get_sample_value("vectra_deadline_exhausted_total", {"stage": "serving_config"}) == before + 1
    )


async def test_with_explainability_down_after_20_calls_the_circuit_opens_and_fail_closed_takes_under_50_ms(
    world: ScoringWorld,
) -> None:
    world.transports["explainability"].fault = "connect"
    for _ in range(20):
        result = await world.recommend(scoring_request())
        assert isinstance(result, FailClosed) and result.cause is FailClosedCause.EXPLAINER_UNAVAILABLE
    breaker = world.deps.clients[1].breaker
    assert breaker is not None and breaker.state is CircuitState.OPEN
    world.transports["explainability"].fault = None  # aunque volviera, el circuito abierto no llama
    started = time.perf_counter()
    result = await world.recommend(scoring_request())
    elapsed = time.perf_counter() - started
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.EXPLAINER_UNAVAILABLE
    assert elapsed < 0.05, elapsed
    assert world.explain.calls == []
    assert METRICS.get_sample_value("vectra_circuit_state", {"dependency": "explainability"}) == 2


async def test_the_registry_breaker_open_means_no_retry_of_the_append() -> None:
    world = scoring_world()
    world.registry.faults.status = 503
    for _ in range(
        9
    ):  # cada solicitud: 2 intentos + el fail_closed = 3 fallos -> se abre dentro de la 7.a solicitud
        await world.recommend(scoring_request())
    assert world.deps.clients[2].breaker.state is CircuitState.OPEN  # type: ignore[union-attr]
    posts = len([call for call in world.registry.calls if call.method == "POST"])
    result = await world.recommend(scoring_request())
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.REGISTRY_UNAVAILABLE
    assert (
        len([call for call in world.registry.calls if call.method == "POST"]) == posts
    )  # nada llego al registro
    await world.aclose()


# --- el bulkhead necesita sockets reales: el limite de conexiones es del pool de httpx --------------------------------------


async def test_a_hung_kserve_exhausts_its_20_connections_and_an_explanation_in_parallel_answers_in_normal_time() -> (
    None
):
    kserve, explain, gov, registry = (
        KServeDouble(),
        ExplainabilityDouble(),
        GovernanceDouble(),
        RegistryDouble(),
    )
    kserve.predict_faults.delay = 3.0  # colgado
    servers = [Server(app).start() for app in (kserve.app, explain.app, gov.app, registry.app)]
    try:
        deps = build_deps(
            Settings(
                servers[2].url, servers[1].url, servers[3].url, servers[0].url
            ),  # la plantilla sin marcador: un solo host
            StaticPolicy(),
        )
        orchestrator = deps.orchestrator
        hung = [
            asyncio.create_task(orchestrator._predictor.predict(ISVC, vector(), _in(10)))  # noqa: SLF001
            for _ in range(30)
        ]
        await asyncio.sleep(0.15)
        arrived = kserve.recorder.count("predict")
        started = time.perf_counter()
        explained = await orchestrator._explainer.explain(explain_request(), _in(10))  # noqa: SLF001
        elapsed = time.perf_counter() - started
        assert (
            arrived == config.PREDICT_POOL == 20
        )  # el resto espera una conexion libre: nunca mas de 20 a KServe
        assert not isinstance(explained, str) and elapsed < 0.2, elapsed  # otro pool: su tiempo normal
        results = await asyncio.gather(*hung)
        assert (
            results == [None] * 30
        )  # el timeout de 300 ms los corta (y el del pool, para los que esperaban)
        for client in deps.clients:
            await client.aclose()
    finally:
        for server in servers:
            server.stop()


def _in(seconds: float):  # type: ignore[no-untyped-def]
    from datetime import UTC, datetime, timedelta

    return datetime.now(UTC) + timedelta(seconds=seconds)
