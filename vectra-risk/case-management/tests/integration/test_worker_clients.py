"""Paso 14: clientes y cache de gobierno (BR-U8-05; P-U8-02, 09; NFR-U8-15, 24, 30..33). Sin base: dobles HTTP de governance y scoring."""

import asyncio
import time
from typing import Any

import httpx
import pytest
from scoring_double import ScoringDouble
from u8_support import FakeClock, GovernanceDouble
from vectra_case.config import GOVERNANCE_WORKER_POOL, SERVING_CONFIG_CACHE_TTL
from vectra_case.db import Database
from vectra_case.evaluation import (
    CONFIG_UNAVAILABLE,
    Evaluator,
    ScoringClient,
    ScoringRejected,
    ScoringUnreachable,
)
from vectra_case.governance_client import ServingConfigClient, ServingConfigInvalid
from vectra_common import deps, process
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_contracts.catalog import FailClosedCause
from vectra_contracts.models.features import FeatureSpec
from vectra_contracts.models.governance import ServingConfig
from vectra_contracts.outcome import RecommendResult
from worker_support import FakeToken, sample_request, sample_taken

pytestmark = pytest.mark.integration


def governance_client(gov: GovernanceDouble, clock: Any = None) -> ServingConfigClient:
    process.ensure_service()
    return ServingConfigClient(
        "http://governance",
        None,
        pool=GOVERNANCE_WORKER_POOL,
        transport=httpx.MockTransport(gov.handler),
        clock=clock or time.monotonic,
    )


def scoring_client(double: ScoringDouble, **kwargs: Any) -> ScoringClient:
    process.ensure_service()
    return ScoringClient("http://scoring", None, transport=double.transport(), **kwargs)


async def test_serving_config_reads_stay_under_50_ms_while_16_scoring_calls_hold_for_7_s() -> None:
    gov, double = GovernanceDouble(), ScoringDouble()
    double.delay = 7.0  # el doble retiene la respuesta hasta SCORING_TIMEOUT
    clock = FakeClock()
    governance = governance_client(gov, clock=lambda: clock().timestamp())
    scoring = scoring_client(double)
    request = sample_request()
    inflight = [asyncio.create_task(scoring.recommend(request)) for _ in range(16)]
    try:
        await asyncio.sleep(0.2)
        assert double.in_flight == 16  # las 16 conexiones del pool de scoring estan ocupadas
        durations = []
        for _ in range(5):
            clock.advance(
                seconds=SERVING_CONFIG_CACHE_TTL + 1
            )  # cada lectura sale a governance, no a la cache
            started = time.perf_counter()
            await governance.get()
            durations.append(time.perf_counter() - started)
        assert gov.calls == 5
        assert max(durations) < 0.05, durations
    finally:
        await asyncio.gather(*inflight, return_exceptions=True)
        await scoring.aclose()
        await governance.aclose()
    assert double.max_in_flight == 16


async def test_20_responses_422_from_scoring_leave_the_circuit_closed() -> None:
    double = ScoringDouble()
    double.default = ("status", 422)
    scoring = scoring_client(double)
    request = sample_request()
    try:
        for _ in range(21):
            with pytest.raises(ScoringRejected):
                await scoring.recommend(request)
        assert (
            double.calls == 21
        )  # un 4xx no cuenta para el breaker (NFR-U8-32): la llamada 21 sigue llegando
        assert (
            scoring._client.breaker is not None and scoring._client.breaker.state is deps.CircuitState.CLOSED
        )
    finally:
        await scoring.aclose()


async def test_scoring_down_opens_the_circuit_after_20_calls_and_attempts_end_in_under_50_ms() -> None:
    double = ScoringDouble()
    double.default = "drop"
    scoring = scoring_client(double)
    request = sample_request()
    try:
        for _ in range(20):
            with pytest.raises(ScoringUnreachable):
                await scoring.recommend(request)
        assert double.calls == 20
        for _ in range(5):  # E1 de P-U8-09: con el circuito abierto el intento falla sin tocar la red
            started = time.perf_counter()
            with pytest.raises(ScoringUnreachable):
                await scoring.recommend(request)
            assert time.perf_counter() - started < 0.05
        assert double.calls == 20
        assert scoring._client.breaker is not None and scoring._client.breaker.state is deps.CircuitState.OPEN
    finally:
        await scoring.aclose()


async def test_5xx_counts_as_a_breaker_failure_but_a_hard_timeout_is_unreachable() -> None:
    double = ScoringDouble()
    double.default = ("status", 503)
    scoring = scoring_client(double, timeout=0.05)
    request = sample_request()
    try:
        with pytest.raises(ScoringUnreachable):
            await scoring.recommend(request)
        double.default, double.delay = "ok", 1.0  # el doble tarda mas que el tope duro (2 x timeout)
        started = time.perf_counter()
        with pytest.raises(ScoringUnreachable):
            await scoring.recommend(request)
        assert time.perf_counter() - started < 0.5
    finally:
        await scoring.aclose()


async def test_a_200_that_is_not_a_recommend_result_or_a_non_200_2xx_is_unreachable() -> None:
    double = ScoringDouble()
    scoring = scoring_client(double)
    request = sample_request()
    try:
        double.default = "junk"
        with pytest.raises(ScoringUnreachable):
            await scoring.recommend(request)
        double.default = ("status", 204)
        with pytest.raises(ScoringUnreachable):
            await scoring.recommend(request)
    finally:
        await scoring.aclose()


async def test_feature_spec_cache_is_an_lru_of_4_and_discards_the_least_used() -> None:
    gov = GovernanceDouble()
    governance = governance_client(gov)
    try:
        for version in ("v1", "v2", "v3", "v4"):
            assert (await governance.feature_spec(version)).model_version_id == version
        await governance.feature_spec("v1")  # v1 se usa de nuevo: la menos usada pasa a ser v2
        await governance.feature_spec("v5")  # la quinta version expulsa a v2
        assert gov.spec_calls == ["v1", "v2", "v3", "v4", "v5"]
        for version in ("v1", "v3", "v4", "v5"):
            await governance.feature_spec(version)
        assert gov.spec_calls == [
            "v1",
            "v2",
            "v3",
            "v4",
            "v5",
        ]  # las cuatro siguen en cache: sin llamadas nuevas
        await governance.feature_spec("v2")
        assert gov.spec_calls[-1] == "v2" and len(gov.spec_calls) == 6  # v2 fue la descartada
    finally:
        await governance.aclose()


async def test_serving_config_cache_uses_if_none_match_and_a_304_renews_it() -> None:
    gov = GovernanceDouble()
    clock = FakeClock()
    governance = governance_client(gov, clock=lambda: clock().timestamp())
    try:
        first = await governance.get()
        await governance.get()
        assert gov.calls == 1  # dentro de los 5 s: cache
        clock.advance(seconds=SERVING_CONFIG_CACHE_TTL + 1)
        assert await governance.get() == first  # 304 con If-None-Match
        assert gov.calls == 2
    finally:
        await governance.aclose()


async def test_serving_config_cache_ttl_boundary_serves_at_exactly_5_s_and_rereads_just_after() -> None:
    """C-7 (U08-T05; `revisiones/U08-T04/ronda-4.md`, F-01): `ServingConfigClient` usa `edad <= SERVING_CONFIG_CACHE_TTL`. Con un reloj controlado: a los 5 s exactos la cache
    sirve (ninguna llamada nueva) y a los 5 s mas un instante vuelve a leer. La mutacion `<=` -> `<` en `governance_client.py` la hace fallar."""
    gov = GovernanceDouble()
    now = [1_000.0]
    governance = governance_client(gov, clock=lambda: now[0])
    try:
        first = await governance.get()
        assert gov.calls == 1
        now[0] += SERVING_CONFIG_CACHE_TTL - 0.001
        assert await governance.get() == first and gov.calls == 1  # dentro del plazo
        now[0] = 1_000.0 + SERVING_CONFIG_CACHE_TTL
        assert await governance.get() == first and gov.calls == 1  # a los 5 s exactos: la cache sirve
        now[0] = 1_000.0 + SERVING_CONFIG_CACHE_TTL + 0.001
        assert (
            await governance.get() == first and gov.calls == 2
        )  # 5 s y un instante: vuelve a leer (304 con If-None-Match)
    finally:
        await governance.aclose()


async def test_a_503_from_governance_makes_exactly_one_call_per_attempt() -> None:
    gov, double = GovernanceDouble(), ScoringDouble()
    gov.down = True
    governance = governance_client(gov)
    evaluator = Evaluator(Database("postgresql://sin-uso"), governance, scoring_client(double))
    try:
        assert await evaluator.attempt(sample_taken()) is CONFIG_UNAVAILABLE
        assert gov.calls == 1  # NFR-U8-33: ningun reintento dentro del intento
        assert double.calls == 0
    finally:
        await governance.aclose()
        await evaluator.scoring.aclose()


async def test_serving_config_with_the_old_shape_ends_the_attempt_as_unavailable_without_calling_scoring() -> (
    None
):
    gov, double = GovernanceDouble(), ScoringDouble()
    gov.old_shape = (
        True  # sin `cutoff`, `low_confidence_threshold` ni `channel_rules` (U04-T09, orden de despliegue)
    )
    governance = governance_client(gov)
    evaluator = Evaluator(Database("postgresql://sin-uso"), governance, scoring_client(double))
    try:
        with pytest.raises(ServingConfigInvalid):
            await governance.get()
        outcome = await evaluator.attempt(sample_taken())
        assert outcome is CONFIG_UNAVAILABLE and outcome.result == "serving_config_unavailable"
        assert double.calls == 0  # falla cerrado
    finally:
        await governance.aclose()
        await evaluator.scoring.aclose()


async def test_an_invalid_or_missing_feature_spec_also_ends_the_attempt_as_unavailable() -> None:
    gov, double = GovernanceDouble(), ScoringDouble()
    governance = governance_client(gov)
    evaluator = Evaluator(Database("postgresql://sin-uso"), governance, scoring_client(double))
    try:
        gov.spec_override = {"model_version_id": "mv-1"}  # sin `features`: no es un `FeatureSpec`
        with pytest.raises(ServingConfigInvalid):
            await governance.feature_spec("mv-1")
        assert await evaluator.attempt(sample_taken()) is CONFIG_UNAVAILABLE
        gov.spec_override, gov.spec_status = None, 404  # un 4xx tampoco es un `FeatureSpec`
        with pytest.raises(DependencyUnavailable):
            await governance.feature_spec("mv-2")
        gov.spec_status = 200
        gov.spec_override = {  # un `FeatureSpec` valido que `derive` no puede usar
            "model_version_id": "mv-1",
            "features": [{"feature_id": "no_existe", "origin": "derived"}],
        }
        assert await evaluator.attempt(sample_taken()) is CONFIG_UNAVAILABLE
        assert double.calls == 0
    finally:
        await governance.aclose()
        await evaluator.scoring.aclose()


async def test_a_governance_4xx_does_not_count_for_the_breaker() -> None:
    gov = GovernanceDouble()
    gov.spec_status = 404
    governance = governance_client(gov)
    try:
        for i in range(21):
            with pytest.raises(DependencyUnavailable):
                await governance.feature_spec(f"v{i}")
        assert len(gov.spec_calls) == 21  # el circuito sigue cerrado
    finally:
        await governance.aclose()


async def test_the_401_retry_with_a_fresh_token_happens_inside_the_same_call() -> None:
    double = ScoringDouble()
    token = FakeToken()
    double.reject_token = "t1"
    process.ensure_service()
    scoring = ScoringClient("http://scoring", token, transport=double.transport())
    try:
        result = await scoring.recommend(sample_request())
        assert result.kind == "recommendation"  # type: ignore[union-attr]
        assert token.invalidated == 1 and double.calls == 2
        assert [h["authorization"] for h in double.headers] == ["Bearer t1", "Bearer t2"]
    finally:
        await scoring.aclose()


async def test_a_second_401_is_a_rejection() -> None:
    double = ScoringDouble()
    double.default = ("status", 401)
    scoring = scoring_client(double)
    try:
        with pytest.raises(ScoringRejected):
            await scoring.recommend(sample_request())
    finally:
        await scoring.aclose()


async def test_what_the_doubles_serve_validates_against_the_contracts_of_u0() -> None:
    gov, double = GovernanceDouble(), ScoringDouble()
    config = ServingConfig.model_validate_json(httpx.Response(200, json=gov.config()).content)
    spec = FeatureSpec.model_validate_json(httpx.Response(200, json=gov.spec("mv-1")).content)
    assert config.model_version_id == spec.model_version_id == "mv-1"
    request = sample_request()
    scoring = scoring_client(double)
    try:
        for behavior in (
            "ok",
            ("ok", None),
            ("fail", FailClosedCause.TIMEOUT),
        ):
            double.queue.append(behavior)
            result = await scoring.recommend(request)
            assert RecommendResult.from_wire(result.model_dump_json()) == result
    finally:
        await scoring.aclose()
    assert double.requests[0].case_id == request.case_id


async def test_a_governance_read_that_outlasts_its_hard_timeout_is_a_dependency_timeout() -> None:
    process.ensure_service()

    async def slow(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(2.0)
        return httpx.Response(200, json={})

    governance = ServingConfigClient("http://governance", None, transport=httpx.MockTransport(slow))
    try:
        started = time.perf_counter()
        with pytest.raises(DependencyTimeout):
            await governance.get()  # tope duro de 500 ms: `MockTransport` no aplica el timeout de `httpx`
        assert time.perf_counter() - started < 1.0
        with pytest.raises(DependencyTimeout):
            await governance.feature_spec("mv-1")  # y de 1 s
    finally:
        await governance.aclose()
