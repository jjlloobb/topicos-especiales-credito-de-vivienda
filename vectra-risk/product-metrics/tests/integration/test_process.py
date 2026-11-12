"""Paso 6 (proceso): arranque, readiness, plazo, reintentos, `SIGTERM`, desfase, ciclo omitido y logs (CA-1).

P-U11-02; INF-U11-01; NFR-U11-04, 07, 09, 22; BR-U11-10, 11. Todo con el doble de U3, reloj de pared, reloj monotono y espera simulados
(`virtual_time.VirtualClock`): ninguna prueba duerme minutos reales. Decisiones de las preguntas de la tarea (rige la opcion por
omision): P-1 (a) un fallo por intento, P-2 (b) sin pasada exitosa los reintentos no tienen tope, P-3 (a) la diaria corre en el
primer instante «02:30 UTC + desfase» posterior al arranque.
"""

from __future__ import annotations

import asyncio
import io
import json
import random
import socket
from collections.abc import AsyncIterator
from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
import pytest
import pytest_asyncio
from entries import NOW, Spec, day_at, render, specs_on
from process_world import PARAMS, World, scrape, value
from vectra_common.deps import CircuitState
from vectra_common.logging import LogContractViolation, configure, log_access
from vectra_common.metrics import REGISTRY
from vectra_contracts.catalog import LOG_RECORD_FIELDS
from vectra_product import config
from vectra_product.collector import Holder, Operations, register
from vectra_product.main import _amain, run
from vectra_product.scheduler import Scheduler, draw_jitter, next_daily_start


def items(count: int, *, first: int = 1, offset_days: int = 2, **changes: Any) -> list[dict[str, Any]]:
    return [render(spec) for spec in specs_on(offset_days, count, first, **changes)]


@pytest_asyncio.fixture
async def worlds() -> AsyncIterator[list[World]]:
    made: list[World] = []
    yield made
    for world in made:
        await world.close()


def make(worlds: list[World], *args: Any, **kwargs: Any) -> World:
    world = World(*args, **kwargs)
    worlds.append(world)
    return world


PRODUCT_NAMES = (
    "vectra_product_north_star_ratio",
    "vectra_product_north_star_decisions",
    "vectra_product_noise_days_below_floor",
    "vectra_product_metrics_last_success_timestamp",
    "vectra_product_target",
)


def product_series(samples: dict[str, Any]) -> list[str]:
    """Series de producto: toda `vectra_product_*` que no es de operacion del ciclo."""
    operation = {
        "vectra_product_cycle_duration_seconds_bucket",
        "vectra_product_cycle_duration_seconds_sum",
        "vectra_product_cycle_duration_seconds_count",
        "vectra_product_cycle_duration_seconds_created",
        "vectra_product_entries_read_total",
        "vectra_product_entries_read_created",
        "vectra_product_full_pass_in_progress",
        "vectra_product_cycles_skipped_total",
        "vectra_product_cycles_skipped_created",
        "vectra_product_last_full_recompute_timestamp",
    }
    return sorted(n for n in samples if n.startswith("vectra_product_") and n not in operation)


# --- arranque con U3 caido y readiness (NFR-U11-07; P-1 a) --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_with_u3_down_publishes_operation_series_but_no_product_series_and_readyz_follows_the_breaker(
    worlds: list[World],
) -> None:
    world = make(worlds, items(5))
    world.double.fail_all = True
    await world.start()

    # Primer intento fallido (1 fallo): breaker cerrado, sin instantanea -> 503.
    samples = world.metrics()
    assert product_series(samples) == []
    assert (
        "vectra_product_last_full_recompute_timestamp" not in samples
    )  # nunca 0 antes de la primera pasada exitosa
    assert value(samples, "vectra_product_full_pass_in_progress") == 0
    assert value(samples, "vectra_product_cycles_skipped_total") == 0
    assert value(samples, "vectra_circuit_state", dependency="decision-registry") == CircuitState.CLOSED
    assert world.ready() is False

    # P-1 (a): un fallo por intento; el breaker abre al tercero (a los 30 min) y la readiness pasa a 200.
    await world.advance(config.FULL_PASS_RETRY_SECONDS)  # 2.o fallo
    assert world.reader.breaker_state is CircuitState.CLOSED and world.ready() is False
    await world.advance(config.FULL_PASS_RETRY_SECONDS)  # 3.er fallo: abre
    assert world.reader.breaker_state is CircuitState.OPEN
    assert world.ready() is True
    assert product_series(world.metrics()) == []  # lista, pero sin series de producto (nunca ceros)

    # Semiabierto a los 60 s: sigue contando como «U3 no responde».
    await world.advance(config.BREAKER_OPEN_FOR_SECONDS + 1)
    assert world.reader.breaker_state is CircuitState.HALF_OPEN
    assert world.ready() is True

    # Un exito de transporte (404) cierra el breaker, pero la pasada falla y sigue sin instantanea: de vuelta a 503.
    world.double.fail_all = False
    world.double.status_all = 404
    await world.advance(config.FULL_PASS_RETRY_SECONDS)
    assert world.reader.breaker_state is CircuitState.CLOSED
    assert world.holder.current is None
    assert world.ready() is False
    assert "vectra_product_last_full_recompute_timestamp" not in world.metrics()


@pytest.mark.asyncio
async def test_without_a_successful_pass_the_retry_every_15_minutes_has_no_cap_and_the_first_success_publishes(
    worlds: list[World],
) -> None:
    """P-2 (b): el tope de 6 rige cuando ya hay estado; sin pasada exitosa el reintento no termina."""
    world = make(worlds, items(5))
    world.double.fail_all = True
    attempts: list[float] = []
    original = world.state.full_pass

    async def counting(checkpoint: Any = None) -> None:
        attempts.append(world.clock.monotonic())
        await original(checkpoint)

    world.state.full_pass = counting  # type: ignore[method-assign]
    await world.start()
    await world.advance(20 * config.FULL_PASS_RETRY_SECONDS)
    assert len(attempts) == 21  # el del arranque y 20 reintentos: mas de los 6 con estado
    assert {b - a for a, b in zip(attempts, attempts[1:], strict=False)} == {config.FULL_PASS_RETRY_SECONDS}
    assert world.ready() is True  # breaker abierto o semiabierto
    world.double.fail_all = False
    await world.advance(config.FULL_PASS_RETRY_SECONDS)
    assert len(attempts) == 22 and world.holder.current is not None
    samples = world.metrics()
    assert "vectra_product_last_full_recompute_timestamp" in samples
    assert world.ready() is True
    await world.advance(5 * config.FULL_PASS_RETRY_SECONDS)
    assert len(attempts) == 22  # con estado, ya no reintenta


# --- plazo de 75 min con U3 lento (reloj simulado) ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_pass_that_exceeds_its_75_min_deadline_with_slow_u3_leaves_readyz_503_and_frees_the_lock(
    worlds: list[World],
) -> None:
    world = make(worlds, items(20))  # 7 paginas de 3
    skip = config.FULL_PASS_DEADLINE_SECONDS // 4  # 18 min y 45 s por pagina: la 5.a ya pasa de los 75 min

    def slow(_number: int) -> None:
        world.clock.t += skip

    world.double.on_request = slow
    await world.start()
    # U3 respondio todas las paginas pedidas (sin 3 fallos seguidos), pero la pasada no termino a tiempo.
    assert world.double.calls == 5 and world.double.completed == [1, 2, 3, 4, 5]
    assert world.reader.breaker_state is CircuitState.CLOSED
    assert world.holder.current is None and world.state.snapshot() is None
    assert world.ready() is False
    assert value(world.metrics(), "vectra_product_full_pass_in_progress") == 0
    assert world.reader.locked is False
    assert "vectra_product_last_full_recompute_timestamp" not in world.metrics()


# --- SIGTERM durante una pasada ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sigterm_during_a_pass_takes_no_new_cycles_finishes_the_page_and_discards_the_pass(
    worlds: list[World],
) -> None:
    world = make(worlds, items(20))
    await world.start()
    # Hasta un instante antes de la diaria: los ciclos de 5 min corren sin novedades.
    await world.advance((world.scheduler.next_daily - world.clock.wall()).total_seconds() - 10)
    published = world.holder.current
    assert published is not None
    last_seq = world.state.last_seq
    before = world.metrics()

    # La diaria lee con paginas de 2 min; el SIGTERM llega mientras lee la 2.a pagina de la pasada.
    world.double.latency = 120.0
    seen_before = world.double.calls
    world.double.add(items(10, first=100, offset_days=1))

    def term(number: int) -> None:
        if number == seen_before + 2:
            world.stop.set()

    world.double.on_request = term
    await world.advance(10 + 3600)
    assert world.task is not None
    await asyncio.wait_for(world.task, 5)  # el planificador termino solo, sin cancelarlo
    assert (
        world.double.completed[-1] == seen_before + 2
    )  # la pagina en vuelo termino: el doble la vio completa
    assert world.double.calls == seen_before + 2  # y no se pidio ninguna mas
    assert world.holder.current is published  # lo publicado, intacto
    assert world.state.last_seq == last_seq  # el estado vigente, intacto: la pasada a medias se descarto
    assert value(world.metrics(), "vectra_product_full_pass_in_progress") == 0
    assert world.reader.locked is False
    after = world.metrics()
    assert value(after, "vectra_product_metrics_last_success_timestamp") == value(
        before, "vectra_product_metrics_last_success_timestamp"
    )

    # Sin ciclos nuevos: nadie vuelve a leer, por mucho que pase el tiempo.
    calls = world.double.calls
    await world.advance(3 * config.CYCLE_SECONDS)
    assert world.double.calls == calls


@pytest.mark.asyncio
async def test_sigterm_between_cycles_stops_both_loops(worlds: list[World]) -> None:
    world = make(worlds, items(5))
    await world.start()
    await world.shutdown()
    calls = world.double.calls
    await world.advance(30 * 60)
    assert world.double.calls == calls


# --- desfase de la pasada diaria (NFR-U11-04), sin umbrales estadisticos -----------------------------------------------------


def test_the_daily_jitter_of_10_000_draws_is_in_0_600_seconds() -> None:
    rng = random.Random(20261012)
    draws = [draw_jitter(rng) for _ in range(10_000)]
    assert all(0.0 <= d <= config.FULL_PASS_JITTER_MAX_SECONDS == 600 for d in draws)


def test_the_daily_start_is_between_02_30_and_02_40_utc_and_after_the_reference_instant() -> None:
    rng = random.Random(7)
    clock = random.Random(99)
    base = datetime(2026, 10, 1, tzinfo=UTC)
    for _ in range(10_000):
        after = base + timedelta(seconds=clock.randrange(0, 40 * 86400))
        start = next_daily_start(after, rng)
        assert start > after
        assert time(2, 30) <= start.time() <= time(2, 40)
        assert start - after <= timedelta(days=1, seconds=config.FULL_PASS_JITTER_MAX_SECONDS)


def test_two_fixed_seeds_give_different_offsets_and_the_same_seed_repeats_its_sequence() -> None:
    day = NOW
    first = [next_daily_start(day, random.Random(1)) for _ in range(3)]
    other = [next_daily_start(day, random.Random(2)) for _ in range(3)]
    assert first[0] != other[0]  # dos replicas con semillas distintas, el mismo dia simulado
    assert len(set(first)) == 1  # la misma semilla, la misma secuencia
    a, b = random.Random(5), random.Random(5)
    assert [next_daily_start(NOW, a) for _ in range(20)] == [next_daily_start(NOW, b) for _ in range(20)]
    c, d = random.Random(5), random.Random(6)
    assert [draw_jitter(c) for _ in range(20)] != [draw_jitter(d) for _ in range(20)]


@pytest.mark.asyncio
async def test_two_scheduled_replicas_with_different_seeds_get_different_daily_starts(
    worlds: list[World],
) -> None:
    world = make(worlds, [])

    def replica(seed: int) -> Scheduler:
        return Scheduler(
            world.state,
            PARAMS,
            world.holder,
            world.operations,
            wall=world.clock.wall,
            monotonic=world.clock.monotonic,
            sleep=world.clock.sleep,
            rng=random.Random(seed),
            stop=asyncio.Event(),
        )

    one, two, again = replica(1), replica(2), replica(1)
    assert one.next_daily != two.next_daily
    assert one.next_daily == again.next_daily


# --- reintentos de la pasada completa (NFR-U11-09) --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_daily_pass_retries_6_times_every_15_minutes_and_then_waits_for_the_next_daily(
    worlds: list[World],
) -> None:
    world = make(worlds, items(5))
    await world.start()
    published = world.holder.current
    assert published is not None
    last_seq = world.state.last_seq
    attempts: list[float] = []
    incrementals: list[float] = []
    full, incremental = world.state.full_pass, world.state.incremental

    async def counting_full(checkpoint: Any = None) -> None:
        attempts.append(world.clock.monotonic())
        await full(checkpoint)

    async def counting_incremental(checkpoint: Any = None) -> Any:
        incrementals.append(world.clock.monotonic())
        return await incremental(checkpoint)

    world.state.full_pass = counting_full  # type: ignore[method-assign]
    world.state.incremental = counting_incremental  # type: ignore[method-assign]

    world.double.fail_all = True  # con estado vigente: el tope de 6 si rige
    first_daily = world.scheduler.next_daily
    start = world.clock.monotonic()
    await world.advance((first_daily - world.clock.wall()).total_seconds() + 3 * 3600)
    daily_at = start + (first_daily - NOW).total_seconds()
    assert [round(t - daily_at) for t in attempts] == [i * config.FULL_PASS_RETRY_SECONDS for i in range(7)]
    # los ciclos de 5 min siguieron durante todo ese tiempo, con el estado incremental intacto
    during = [t for t in incrementals if t >= daily_at]
    assert len(during) >= (3 * 3600) // config.CYCLE_SECONDS
    assert world.holder.current is published and world.state.last_seq == last_seq
    assert world.state.last_full_recompute_at == NOW  # la del arranque; ninguna posterior
    # nada mas hasta la diaria siguiente (una por dia, con su propio desfase)
    second_daily = world.scheduler.next_daily
    assert second_daily > first_daily
    await world.advance((second_daily - world.clock.wall()).total_seconds() - 60)
    assert len(attempts) == 7
    await world.advance(120)
    assert len(attempts) == 8


# --- C-3 (F-02 de U11-T02): el borde del plazo de 75 min y los reintentos de la segunda pasada diaria ------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("elapsed_before_last_page", "completes"),
    [(75 * 60 - 1, True), (75 * 60 + 1, False)],
    ids=["justo-por-debajo-de-75-min-termina", "justo-por-encima-de-75-min-vence"],
)
async def test_a_pass_just_under_75_minutes_completes_and_one_just_over_expires(
    worlds: list[World], elapsed_before_last_page: int, completes: bool
) -> None:
    """P-U11-02: el plazo de 75 min se comprueba entre paginas. Los minutos van **literales** (no `config.FULL_PASS_DEADLINE_SECONDS`): si alguien cambia el
    plazo a 90 min, el caso de «vence» deja de vencer y la prueba falla (con la constante en la prueba, el borde se movia con ella)."""
    world = make(worlds, items(5))  # dos paginas de 3 y 2
    spent: list[int] = []

    def slow(number: int) -> None:
        if number == 1 and not spent:
            spent.append(number)
            world.clock.t += elapsed_before_last_page  # lo que tarda la primera pagina; el reloj monotono sigue al de pared

    world.double.on_request = slow
    await world.start()
    assert (world.holder.current is not None) is completes
    assert (world.state.snapshot() is not None) is completes
    assert value(world.metrics(), "vectra_product_full_pass_in_progress") == 0
    assert world.reader.locked is False
    assert ("vectra_product_last_full_recompute_timestamp" in world.metrics()) is completes


@pytest.mark.asyncio
async def test_a_second_daily_pass_that_also_fails_makes_its_own_6_retries(worlds: list[World]) -> None:
    """NFR-U11-09: cada diaria tiene sus 6 reintentos; sin el reinicio diario de `_retries`, la segunda fallida no reintenta nada."""
    world = make(worlds, items(5))
    await world.start()
    assert world.holder.current is not None
    attempts: list[float] = []
    full = world.state.full_pass

    async def counting_full(checkpoint: Any = None) -> None:
        attempts.append(world.clock.monotonic())
        await full(checkpoint)

    world.state.full_pass = counting_full  # type: ignore[method-assign]
    world.double.fail_all = True
    first_daily = world.scheduler.next_daily
    await world.advance((first_daily - world.clock.wall()).total_seconds() + 3 * 3600)
    assert len(attempts) == 1 + config.FULL_PASS_RETRIES  # la diaria y sus 6 reintentos
    second_daily = world.scheduler.next_daily
    assert second_daily > first_daily
    await world.advance((second_daily - world.clock.wall()).total_seconds() + 3 * 3600)
    assert len(attempts) == 2 * (1 + config.FULL_PASS_RETRIES), "la segunda diaria no hizo sus 6 reintentos"


@pytest.mark.asyncio
async def test_a_failed_incremental_read_right_after_a_complete_full_pass_keeps_the_pass_and_the_next_cycle_resumes(
    worlds: list[World],
) -> None:
    """C-5 (F-04 de U11-T02): la rama `incremental_after_full_failed` de `state.py`, de forma determinista. La pasada completa termina (2 paginas) y la lectura incremental
    que sigue, con el candado tomado, falla (solicitud 3): la pasada se conserva y el siguiente ciclo sigue desde `last_seq`. La cobertura de `state.py` no depende del azar."""
    world = make(worlds, items(5))  # dos paginas de 3 y 2: las solicitudes 1 y 2 son la pasada
    world.double.fail_requests = {3}  # la lectura incremental inmediata
    await world.state.full_pass()
    assert world.double.calls == 3
    assert world.state.snapshot() is not None and world.state.last_seq is not None
    assert (
        world.state.last_full_recompute_at is not None
        and world.state.last_success_at == world.state.last_full_recompute_at
    )
    assert world.reader.locked is False
    last_seq = world.state.last_seq
    await world.state.incremental()  # el ciclo siguiente: la solicitud 4 no falla y sigue desde `last_seq`
    assert world.double.calls == 4 and world.state.last_seq == last_seq


# --- un ciclo durante la pasada: omitido y contado --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_cycle_during_the_pass_is_skipped_and_counted_and_u3_receives_no_extra_request(
    worlds: list[World],
) -> None:
    world = make(worlds, items(11))  # 4 paginas de 3
    await world.start()
    assert world.holder.current is not None
    skipped = value(world.metrics(), "vectra_product_cycles_skipped_total")
    assert skipped == 0
    window: list[float] = []
    full = world.state.full_pass

    async def timed(checkpoint: Any = None) -> None:
        window.append(world.clock.monotonic())
        await full(checkpoint)
        window.append(world.clock.monotonic())

    world.state.full_pass = timed  # type: ignore[method-assign]
    world.double.latency = 400.0  # cada pagina tarda 6 min 40 s simulados
    requests_before = len(world.double.requests)
    await world.advance((world.scheduler.next_daily - world.clock.wall()).total_seconds() + 3600)
    start, end = window
    ticks = [k * config.CYCLE_SECONDS for k in range(1, int(end // config.CYCLE_SECONDS) + 1)]
    inside = [t for t in ticks if start < t <= end]
    assert len(inside) >= 3
    assert value(world.metrics(), "vectra_product_cycles_skipped_total") == len(inside)
    # Mientras el candado estuvo tomado, U3 solo recibio las 4 paginas de la pasada, seguidas (ningun ciclo omitido leyo), y despues
    # la incremental desde `last_seq`.
    during = world.double.requests[requests_before:]
    first = next(i for i, r in enumerate(during) if "recorded_from" in r)
    assert [("recorded_from" in r) for r in during[first : first + 5]] == [True, True, True, True, False]
    assert during[first + 4]["seq_after"] == "11"


@pytest.mark.asyncio
async def test_without_a_baseline_the_5_minute_cycle_does_not_read_count_or_publish(
    worlds: list[World],
) -> None:
    world = make(worlds, items(5))
    world.double.fail_all = True
    await world.start()
    calls = world.double.calls
    await world.advance(
        10 * 60
    )  # dos ciclos sin baseline (la unica lectura que ocurre es el reintento a los 15 min, aun no)
    assert world.double.calls == calls
    assert value(world.metrics(), "vectra_product_cycles_skipped_total") == 0
    assert world.holder.current is None


# --- el servidor y el apagado en el mismo proceso ----------------------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
async def test_run_serves_the_three_ops_routes_and_stops_with_the_event(worlds: list[World]) -> None:
    world = make(worlds, items(5))  # solo para el doble y el lector: el planificador de `run` es otro
    world.release_series()  # el `World` registra sus series; `run` registra las suyas
    stop = asyncio.Event()
    port = free_port()
    task = asyncio.ensure_future(
        run(
            world.reader,
            PARAMS,
            stop=stop,
            port=port,
            host="127.0.0.1",
            wall=world.clock.wall,
            monotonic=world.clock.monotonic,
            sleep=world.clock.sleep,
            rng=random.Random(3),
        )
    )
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            for _ in range(200):
                try:
                    if (await http.get("/healthz")).status_code == 200:
                        break
                except httpx.TransportError:
                    await asyncio.sleep(0.05)
            await world.clock.settle()
            assert (await http.get("/readyz")).status_code == 200  # la pasada del arranque ya publico
            body = (await http.get("/metrics")).text
            assert (
                "vectra_product_north_star_ratio" in body or "vectra_product_noise_days_below_floor" in body
            )
            assert (await http.get("/v1/entries")).status_code == 404
    finally:
        stop.set()
        await asyncio.wait_for(task, 10)


@pytest.mark.asyncio
async def test_amain_without_the_registry_url_exits_without_serving(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VECTRA_REGISTRY_URL", raising=False)
    assert await _amain(asyncio.Event(), free_port()) == 3


@pytest.mark.asyncio
async def test_amain_with_invalid_params_exits_nonzero_without_serving(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text("noise_floor: 7\n", encoding="utf-8")
    monkeypatch.setenv("VECTRA_REGISTRY_URL", "http://registry.invalid")
    monkeypatch.setenv("VECTRA_POLICY_PATH", str(bad))
    port = free_port()
    assert await _amain(asyncio.Event(), port) == 2
    with socket.socket() as sock:  # el puerto sigue libre: no se sirvio nada
        sock.bind(("127.0.0.1", port))


# --- PBT-U0-07 en modo strict sobre los logs ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strict_logs_keep_only_allowlisted_keys_and_the_seq_of_excluded_entries(
    worlds: list[World], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    stream = io.StringIO()
    configure("product-metrics", stream)
    flawed = [
        render(Spec(seq=seq, decided=day_at(2), flaw="role", rec=None)) for seq in (101, 102)
    ]  # excluidas (BR-U11-10)
    world = make(worlds, [*items(4), *flawed])
    await world.start()  # pasada con entradas excluidas
    assert world.holder.current is not None
    world.double.fail_all = True  # fallos de lectura, hasta abrir el breaker
    await world.advance(30 * 60)
    assert world.reader.breaker_state in (CircuitState.OPEN, CircuitState.HALF_OPEN)
    world.double.fail_all = False
    world.double.fail_requests = {world.double.calls + 2}  # un fallo suelto a mitad de una pasada
    await world.advance(config.FULL_PASS_RETRY_SECONDS)
    await world.shutdown()  # apagado

    lines = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    assert lines, "el recorrido no dejo ningun log"
    assert all(set(line) <= LOG_RECORD_FIELDS for line in lines)  # solo claves del catalogo
    assert sorted(line["seq"] for line in lines if "seq" in line)[:2] == [101, 102]
    assert any(line.get("error_code") for line in lines)  # los fallos de lectura dejan su codigo
    assert not any("msg" in line or "message" in line for line in lines)  # ningun texto libre


@pytest.mark.asyncio
async def test_a_failed_log_field_outside_the_allowlist_would_raise_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La guarda de la prueba anterior: en modo strict un campo fuera de la allowlist hace fallar (no se descarta en silencio)."""
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    configure("product-metrics", io.StringIO())
    with pytest.raises(LogContractViolation):
        log_access(texto_libre="entry_excluded seq=7")


def test_the_module_level_pieces_register_and_unregister_cleanly() -> None:
    """`Holder`, `Operations` y `register` se pueden crear dos veces seguidas en el registro de U0 (no queda nada colgado)."""
    for _ in range(2):
        operations = Operations()
        collector = register(Holder())
        scrape()
        REGISTRY.unregister(collector)
        operations.close()
    assert "vectra_product_cycles_skipped_total" not in scrape()
