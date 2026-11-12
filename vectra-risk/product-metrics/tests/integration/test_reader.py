"""Paso 4: `reader` y `state` con el doble de U3 (BR-U11-11; P-U11-01, 02, 04; NFR-U11-01, 02, 09..12).

Una prueba por vineta del plan: el doble falla con 2 conexiones simultaneas; una pagina fallida no avanza `last_seq`; 3 fallos
seguidos abren el breaker y 1 exito en semiabierto lo cierra; una entrada de 40 dias va a su contador de mes y no al estado de 35
dias; la lectura incremental con el candado tomado se omite sin leer; lo que sirve el doble valida contra `MetricsProjection`.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from entries import NOW, Spec, day_at, render, specs_on
from registry_double import FakeToken, RegistryDouble, SimultaneousConnections
from vectra_common import deps, process
from vectra_contracts.models.registry import MetricsProjection
from vectra_product import config
from vectra_product.compute import month_index
from vectra_product.reader import ENTRIES_PATH, ReadError, Reader, build_client
from vectra_product.state import DONE, SKIPPED, NoBaseline, ProductState, full_pass_start

pytestmark = pytest.mark.asyncio


class Clock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now
        self.mono = 0.0

    def wall(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return self.mono


def make(
    double: RegistryDouble, *, page_size: int = 3, clock: Clock | None = None
) -> tuple[ProductState, Reader, Clock]:
    process.init("service")
    clock = clock or Clock()
    client = build_client(
        "http://registry.invalid",
        token_source=FakeToken(),
        transport=double.transport(),
        clock=clock.monotonic,
    )
    reader = Reader(client, page_size=page_size)
    return ProductState(reader, clock.wall), reader, clock


def items(first: int, count: int, offset_days: int = 2) -> list[dict[str, Any]]:
    return [render(spec) for spec in specs_on(offset_days, count, first)]


def stub_client(handler: Any) -> deps.DependencyClient:
    process.init("service")
    return build_client(
        "http://registry.invalid", token_source=FakeToken(), transport=httpx.MockTransport(handler)
    )


async def test_path_comes_from_the_u0_route_contract() -> None:
    assert ENTRIES_PATH == "/v1/entries"


async def test_the_double_serves_what_metrics_projection_accepts() -> None:
    """El doble no diverge del contrato: cada item que sirve valida contra `MetricsProjection` (U0)."""
    double = RegistryDouble([*items(1, 3), *[render(s) for s in specs_on(2, 2, 10, rec=None)]])
    state, _reader, _clock = make(double)
    await state.full_pass()
    assert len(double.entries) == 5
    for item in double.entries:
        assert MetricsProjection.model_validate_json(json.dumps(item)).entry_type == "human_decision"
    assert any(i["recommendation"] is None for i in double.entries)
    assert any(i["recommendation"] is not None for i in double.entries)


async def test_full_pass_reads_in_seq_order_one_page_at_a_time_with_the_token() -> None:
    double = RegistryDouble(items(1, 8))
    state, _reader, _clock = make(double, page_size=3)
    await state.full_pass()
    assert double.max_active == 1
    firsts = [request.get("seq_after") for request in double.requests]
    # Pagina 1 sin `seq_after`; despues, cada `next_seq_after`; la pasada termina y una incremental desde su `last_seq`.
    assert firsts == [None, "3", "6", "8"]
    assert all(r["projection"] == "metrics" and r["entry_type"] == "human_decision" for r in double.requests)
    assert all(r["limit"] == "3" for r in double.requests)
    assert "recorded_from" in double.requests[0] and "recorded_from" not in double.requests[-1]
    assert state.last_seq == 8
    snapshot = state.snapshot()
    assert snapshot is not None and sorted(snapshot.entries) == list(range(1, 9))


async def test_full_pass_starts_at_day_1_of_the_sixth_closed_month_minus_1_day() -> None:
    assert full_pass_start(NOW) == datetime(
        2026, 3, 31, tzinfo=UTC
    )  # 6 de octubre: el sexto mes cerrado es abril
    assert full_pass_start(datetime(2026, 2, 1, tzinfo=UTC)) == datetime(2025, 7, 31, tzinfo=UTC)


async def test_the_double_fails_when_it_sees_two_simultaneous_connections() -> None:
    double = RegistryDouble(items(1, 3))
    double.latency = 0.05
    process.init("service")
    client = build_client("http://registry.invalid", token_source=FakeToken(), transport=double.transport())
    one, two = Reader(client), Reader(client)
    with pytest.raises(SimultaneousConnections):
        await asyncio.gather(one._fetch(None, None), two._fetch(None, None))  # noqa: SLF001
    assert double.max_active == 2


async def test_reader_never_has_two_pages_in_flight_with_a_full_pass_and_incrementals_racing() -> None:
    double = RegistryDouble(items(1, 30))
    double.latency = 0.001
    state, _reader, _clock = make(double, page_size=2)
    await state.full_pass()
    results = await asyncio.gather(state.full_pass(), *[state.incremental() for _ in range(5)])
    assert double.max_active == 1
    assert SKIPPED in results  # las incrementales que llegan con la pasada leyendo se omiten (P-U11-02)


async def test_a_failed_page_does_not_advance_last_seq_and_the_next_read_continues_from_there() -> None:
    double = RegistryDouble(items(1, 10))
    state, _reader, _clock = make(double, page_size=2)
    await state.full_pass()
    assert state.last_seq == 10
    double.add(items(11, 10))
    double.fail_requests = {double.calls + 3}  # la pagina 3 de 5 de la incremental
    with pytest.raises(ReadError, match="status_503"):
        await state.incremental()
    assert state.last_seq == 14  # paginas 1 y 2 aplicadas; la 3 (15 y 16) no
    double.fail_requests = set()
    double.requests.clear()
    assert await state.incremental() == DONE
    assert double.requests[0]["seq_after"] == "14"  # sigue desde la ultima pagina confirmada
    assert state.last_seq == 20
    snapshot = state.snapshot()
    assert snapshot is not None and sorted(snapshot.entries) == list(range(1, 21))


async def test_a_failed_full_pass_leaves_the_current_state_intact() -> None:
    double = RegistryDouble(items(1, 6))
    state, _reader, _clock = make(double, page_size=2)
    await state.full_pass()
    before = state.snapshot()
    assert before is not None
    seqs = sorted(before.entries)
    double.add(items(7, 6))
    double.fail_requests = {double.calls + 3}
    with pytest.raises(ReadError):
        await state.full_pass()
    after = state.snapshot()
    assert after is not None and sorted(after.entries) == seqs and state.last_seq == 6


async def test_timeouts_count_as_failures_and_do_not_advance() -> None:
    double = RegistryDouble(items(1, 4))
    state, _reader, _clock = make(double, page_size=2)
    await state.full_pass()
    double.add(items(5, 4))
    double.timeout_requests = {double.calls + 2}
    with pytest.raises(ReadError, match="DependencyTimeout"):
        await state.incremental()
    assert state.last_seq == 6


async def test_three_consecutive_failures_open_the_breaker_and_one_success_half_open_closes_it() -> None:
    double = RegistryDouble(items(1, 2))
    clock = Clock()
    state, reader, _ = make(double, clock=clock)
    await state.full_pass()
    assert reader.breaker_state is deps.CircuitState.CLOSED
    double.fail_all = True
    for _ in range(3):
        with pytest.raises(ReadError, match="status_503"):
            await state.incremental()
    assert reader.breaker_state is deps.CircuitState.OPEN
    reached = double.calls
    with pytest.raises(ReadError, match="DependencyUnavailable"):
        await state.incremental()  # con el breaker abierto no llega al doble
    assert double.calls == reached
    clock.mono += config.BREAKER_OPEN_FOR_SECONDS
    assert reader.breaker_state is deps.CircuitState.HALF_OPEN
    double.fail_all = False
    assert await state.incremental() == DONE
    assert reader.breaker_state is deps.CircuitState.CLOSED


async def test_two_failures_do_not_open_the_breaker() -> None:
    double = RegistryDouble(items(1, 2))
    state, reader, _clock = make(double)
    await state.full_pass()
    double.fail_requests = {double.calls + 1, double.calls + 2}
    for _ in range(2):
        with pytest.raises(ReadError):
            await state.incremental()
    assert reader.breaker_state is deps.CircuitState.CLOSED
    assert await state.incremental() == DONE


async def test_a_40_day_old_entry_goes_to_its_month_counter_and_not_to_the_35_day_state() -> None:
    old = specs_on(40, 1, 1)  # 27 de agosto: el sexto mes cerrado va de abril a septiembre
    recent = specs_on(3, 1, 2)
    double = RegistryDouble([render(s) for s in [*old, *recent]])
    state, _reader, _clock = make(double)
    await state.full_pass()
    snapshot = state.snapshot()
    assert snapshot is not None
    assert sorted(snapshot.entries) == [2]  # la de 40 dias no esta en el estado de 35 dias
    august = snapshot.months[month_index(old[0].decided.toordinal())]
    assert august  # pero si esta en el contador de su mes
    assert (
        sum(count for (tag, *_rest), count in august.items() if tag == 0) == 1
    )  # una decision atribuible (DEN)


async def test_incremental_with_the_lock_taken_is_skipped_without_reading() -> None:
    double = RegistryDouble(items(1, 4))
    state, reader, _clock = make(double)
    await state.full_pass()
    reached = double.calls
    async with reader.exclusive():
        assert reader.locked
        assert await state.incremental() == SKIPPED
    assert double.calls == reached
    assert await state.incremental() == DONE


async def test_incremental_without_a_full_pass_has_nowhere_to_continue_from() -> None:
    state, _reader, _clock = make(RegistryDouble())
    with pytest.raises(NoBaseline):
        await state.incremental()


async def test_pages_require_the_lock() -> None:
    _state, reader, _clock = make(RegistryDouble())
    with pytest.raises(RuntimeError):
        async for _page in reader.pages(None, None):
            pass


@pytest.mark.parametrize(
    "body",
    [
        b"no es json",
        b"[]",
        b'{"items": "x"}',
        b'{"next_seq_after": null}',
        b'{"items": [], "next_seq_after": "7"}',
        b'{"items": [], "next_seq_after": true}',
        b'{"items": [1]}',
        b'{"items": [{"entry_type": "human_decision"}]}',  # sin `seq`
        b'{"items": [{"seq": true}]}',
        b'{"items": [{"seq": 3}, {"seq": 2}]}',  # fuera de orden
        b'{"items": [{"seq": 0}], "next_seq_after": 0}',  # sin progreso
        b'{"items": [{"seq": 1}, {"seq": 2}, {"seq": 3}, {"seq": 4}]}',  # mas que `limit`
    ],
)
async def test_a_malformed_envelope_fails_the_read_and_moves_nothing(body: bytes) -> None:
    reader = Reader(stub_client(lambda request: httpx.Response(200, content=body)), page_size=3)
    state = ProductState(reader)
    with pytest.raises(ReadError):
        await state.full_pass()
    assert state.snapshot() is None and state.last_seq is None


async def test_non_200_non_5xx_is_a_read_error_and_does_not_open_the_breaker() -> None:
    reader = Reader(stub_client(lambda request: httpx.Response(403, json={})))
    for _ in range(5):
        with pytest.raises(ReadError, match="status_403"):
            await ProductState(reader).full_pass()
    assert reader.breaker_state is deps.CircuitState.CLOSED


async def test_the_double_rejects_requests_without_the_test_token_and_bad_limits() -> None:
    double = RegistryDouble(items(1, 2))
    process.init("service")
    breaker = deps.BreakerConfig(open_for=60, consecutive_failures=3)
    anonymous = deps.DependencyClient(
        "decision-registry", "http://registry.invalid", breaker, 1, transport=double.transport()
    )
    response = await deps.call(anonymous, "GET", f"{ENTRIES_PATH}?projection=metrics", timeout=1.0)
    assert response.status_code == 401
    token_client = build_client(
        "http://registry.invalid", token_source=FakeToken(), transport=double.transport()
    )
    for query in ("projection=metrics&limit=1001", "projection=full", "projection=metrics&limit=0"):
        response = await deps.call(token_client, "GET", f"{ENTRIES_PATH}?{query}", timeout=1.0)
        assert response.status_code == 422


async def test_the_full_pass_applies_recorded_from_and_invalid_entries_advance_last_seq() -> None:
    old = Spec(
        seq=1, decided=day_at(300), delay_s=0
    )  # fuera de la pasada: `recorded_at` anterior a `recorded_from`
    bad = Spec(seq=2, decided=day_at(2), flaw="decision")
    good = Spec(seq=3, decided=day_at(2))
    double = RegistryDouble([render(s) for s in (old, bad, good)])
    state, _reader, _clock = make(double)
    await state.full_pass()
    snapshot = state.snapshot()
    assert snapshot is not None
    assert sorted(snapshot.entries) == [2, 3]  # la vieja no se leyo; la invalida si, y no se vuelve a leer
    assert state.last_seq == 3
    double.requests.clear()
    await state.incremental()
    assert double.requests[0]["seq_after"] == "3"


async def test_the_seq_of_an_excluded_entry_goes_to_the_log(caplog: pytest.LogCaptureFixture) -> None:
    """El `seq` de una excluida va al log y a ninguna etiqueta (BR-U11-10)."""
    double = RegistryDouble([render(Spec(seq=7, decided=day_at(2), flaw="role"))])
    state, _reader, _clock = make(double)
    with caplog.at_level("WARNING", logger="vectra_product.state"):
        await state.full_pass()
    assert any("seq=7" in record.getMessage() for record in caplog.records)
