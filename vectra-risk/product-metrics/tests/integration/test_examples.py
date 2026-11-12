"""Paso 7: las pruebas de ejemplo de business-logic-model §3 que dependen de E/S (CA-4; BR-U11-01, 07, 11; US-505).

Todas con el doble de U3 y reloj simulado: reinicio a mitad de un ciclo, una decision sobre una recomendacion de hace 60 dias (y otra
sobre una `freeze`) y el registro caido 31 minutos. La prueba de volumen (INF-U11-06) esta diferida por la demo (T3) y no se escribe.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
import pytest_asyncio
from entries import NOW, RecSpec, Spec, day_at, render, specs_on
from process_world import World, value
from vectra_common.deps import CircuitState
from vectra_product import config

STALE_AFTER_SECONDS = (
    1800  # la condicion que lee `ProductMetricsStale`: `time() - last_success > 1800` (NFR-U11-08)
)


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


def viewed_burst(offset: int, total: int, viewed: int, first_seq: int) -> list[Spec]:
    """`total` decisiones atribuibles un dia, `viewed` con la explicacion vista (como `tests/unit/test_compute_examples.py`)."""
    return [
        *specs_on(offset, viewed, first_seq, viewed=True),
        *specs_on(offset, total - viewed, first_seq + viewed, viewed=False),
    ]


# --- reinicio a mitad (BR-U11-07) -------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restart_in_the_middle_of_a_cycle_publishes_the_same_noise_days_below_floor(
    worlds: list[World],
) -> None:
    """Tres ventanas moviles de 7 dias bajo el piso (la candidata 1 de U11-T01 explica la lectura del ejemplo): 3 antes y 3 despues."""
    first = make(worlds, [render(s) for s in viewed_burst(3, 50, 25, 1)])
    await first.start()
    assert value(first.metrics(), "vectra_product_noise_days_below_floor") == 3

    # El proceso muere a mitad de un ciclo: la lectura incremental esta en vuelo cuando se descarta.
    first.double.latency = 100.0
    first.double.add([render(s) for s in specs_on(1, 2, 500)])
    await first.advance(config.CYCLE_SECONDS + 10)
    assert first.reader.locked  # a mitad del ciclo
    first.kill()
    await first.close()

    # Uno nuevo arranca contra los mismos datos (el mismo doble): el valor sale de los datos, no del tiempo que lleva el proceso.
    second = make(worlds, double=first.double)
    first.double.latency = 0.0
    second.clock.t = first.clock.t
    await second.start()
    assert value(second.metrics(), "vectra_product_noise_days_below_floor") == 3
    assert second.state.last_full_recompute_at is not None


# --- una decision sobre una recomendacion de hace 60 dias (BR-U11-01) --------------------------------------------------------


@pytest.mark.asyncio
async def test_a_decision_on_a_60_day_old_recommendation_is_attributable_and_one_on_a_freeze_is_not(
    worlds: list[World],
) -> None:
    old = Spec(
        seq=1, decided=day_at(1), rec=RecSpec(seq=900, evaluated=day_at(60))
    )  # evaluada hace 60 dias (fuera de los 35)
    on_freeze = render(Spec(seq=2, decided=day_at(1), rec=None))
    on_freeze["recommendation_entry_id"] = (
        "901"  # apunta a una `freeze`: U3 la sirve con `recommendation: null`
    )
    freeze = {
        "entry_type": "freeze",
        "seq": 901,
        "recorded_at": day_at(60).isoformat().replace("+00:00", "Z"),
    }
    stale_recommendation = {
        "entry_type": "recommendation",
        "seq": 900,
        "recorded_at": day_at(60).isoformat().replace("+00:00", "Z"),
    }
    world = make(worlds, [stale_recommendation, freeze, render(old), on_freeze])
    await world.start()
    samples = world.metrics()
    day = {"period": "day"}
    # el doble solo sirve `human_decision`: ni la recomendacion vieja ni la `freeze` llegan al proceso
    assert all(
        item["entry_type"] == "human_decision" for item in world.double.entries if item["seq"] in (1, 2)
    )
    denominators = [
        v
        for lab, v in samples["vectra_product_north_star_decisions"]
        if lab["period"] == "day" and lab["part"] == "denominator"
    ]
    assert denominators == [1]  # solo la atribuible entra en el denominador de `day`
    assert (
        value(samples, "vectra_product_unattributable_decisions", **day) == 1
    )  # la de la `freeze` se cuenta aparte
    # y en ningun cociente: el total de `day` es 1 de 1 (la atribuible, con la explicacion vista y factores)
    assert (
        value(
            samples,
            "vectra_product_north_star_ratio",
            period="day",
            channel="all",
            outcome="all",
            model_version_id="all",
        )
        == 1.0
    )
    assert world.state.snapshot() is not None
    assert 1 in world.state.snapshot().entries and 900 not in world.state.snapshot().entries  # type: ignore[union-attr]


# --- registro caido 31 min (BR-U11-11; E1 y E6) -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registry_down_31_minutes_keeps_the_values_last_success_goes_stale_and_the_incremental_resumes_from_last_seq(
    worlds: list[World],
) -> None:
    world = make(worlds, [render(s) for s in specs_on(1, 6, 1)])
    await world.start()
    before = world.metrics()
    product_before = {
        n: rows
        for n, rows in before.items()
        if n.startswith("vectra_product_")
        and "last_success" not in n
        and "cycle" not in n
        and "entries_read" not in n
    }
    last_success = value(before, "vectra_product_metrics_last_success_timestamp")
    last_seq = world.state.last_seq
    assert last_seq == 6

    world.double.fail_all = True
    await world.advance(30 * 60 + 30)  # el ultimo ciclo fallido fue el de los 30 min
    assert world.reader.breaker_state is CircuitState.OPEN
    await world.advance(30)  # 31 min sin respuesta de U3
    during = world.metrics()
    for name, rows in product_before.items():  # los valores de producto siguen iguales
        if name in ("vectra_product_full_pass_in_progress",):
            continue
        assert during[name] == rows, name
    assert value(during, "vectra_product_metrics_last_success_timestamp") == last_success  # no avanza
    assert (
        world.clock.wall().timestamp() - last_success > STALE_AFTER_SECONDS
    )  # la condicion de `ProductMetricsStale`
    assert value(during, "vectra_product_full_pass_in_progress") == 0
    assert value(during, "vectra_circuit_state", dependency="decision-registry") in (
        CircuitState.OPEN,
        CircuitState.HALF_OPEN,
    )
    assert world.state.last_seq == last_seq and world.ready() is True

    # U3 vuelve: la incremental sigue desde `last_seq` (el breaker pasa por semiabierto y cierra con un exito).
    world.double.fail_all = False
    world.double.add([render(s) for s in specs_on(1, 2, 50)])
    requests = len(world.double.requests)
    await world.advance(config.CYCLE_SECONDS)
    resumed = world.double.requests[requests:]
    assert resumed and resumed[0]["seq_after"] == str(last_seq) and "recorded_from" not in resumed[0]
    after = world.metrics()
    assert value(after, "vectra_product_metrics_last_success_timestamp") > last_success
    assert (
        world.clock.wall().timestamp() - value(after, "vectra_product_metrics_last_success_timestamp")
        < STALE_AFTER_SECONDS
    )
    assert world.reader.breaker_state is CircuitState.CLOSED
    assert world.state.last_seq == 51
    assert world.clock.wall() - NOW > timedelta(minutes=31)
