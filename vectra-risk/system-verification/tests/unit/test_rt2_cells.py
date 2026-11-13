"""CA-8 (U12-T03): la regla de las celdas alcanzables (NFR-U12-11 precisada en U12-T03, 2026-11-13, decision del usuario, `DECISIONES-LOOP.md` §10; BR-U12-06).

`rt2` se niega **solo si queda corta una celda alcanzable** (30 o mas filas disponibles en `test`); las inalcanzables se informan y no bloquean. La regla es una funcion pura sobre la tabla de celdas, separada del muestreo.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from rt2_world import PROXY, REFERENCE, Rt2World
from vectra_verification import sampler
from vectra_verification.guard import KIND
from vectra_verification.scenarios import rt2
from vectra_verification.scenarios.common import ScenarioError

Cell = sampler.CellReport


def cell(attribute: str, group: str, band: str, available: int, taken: int) -> Cell:
    return Cell(attribute, group, band, available, taken)


@pytest.fixture
def world() -> Iterator[Rt2World]:
    built = Rt2World()
    built.add_model(REFERENCE, "activo")
    built.add_model(PROXY, "aprobado", registered_by="ingeniero-1", approved_by="cro-1")
    built.operator_promotes(60.0)
    built.operator_rolls_back(6000.0)
    built.start_bias()
    yield built
    built.close()


def run(world: Rt2World, short: tuple[Cell, ...]) -> rt2.Rt2Result:
    world.simulator.short = short
    deps = rt2.Rt2Deps(KIND, world.clock, world.sessions, world.simulator, world.registry, world.prom)
    return rt2.run_rt2(deps, rt2.Rt2Params(REFERENCE, [rt2.ProxyVersion(1, PROXY)], 7))


def test_rt2_cells_a_reachable_short_cell_with_40_available_and_12_taken_refuses_and_sends_nothing(
    world: Rt2World,
) -> None:
    with pytest.raises(ScenarioError, match="rt2_celda_alcanzable_corta") as error:
        run(world, (cell("sexo", "F", "lt_20", 40, 12),))
    assert "sexo/F/lt_20: disponibles=40 tomadas=12" in str(error.value)
    assert [r for r in world.simulator.runs if r[0] == "stratified"] == [] and world.simulator.runs == []
    assert world.oidc.logins == [] and world.bff.doubles.governance.calls == []


def test_rt2_cells_only_unreachable_short_cells_runs_and_reports_them_with_their_fields(
    world: Rt2World,
) -> None:
    short = (
        cell("estrato", "6", "lt_20", 12, 12),
        cell("rango_edad", "56-65", "lt_20", 21, 21),
        cell("rango_edad", "66+", "20_30", 4, 4),
        cell("rango_edad", "66+", "gt_30", 10, 10),
    )
    result = run(world, short)
    assert result.rt2.result == "pasa" and result.unreachable_cells == short
    assert result.rt2.readings["unreachable_cells"] == [
        {
            "attribute": c.attribute,
            "group": c.group,
            "band": c.band,
            "available": c.available,
            "taken": c.taken,
        }
        for c in short
    ]


def test_rt2_cells_none_short_runs_and_the_unreachable_list_is_empty(world: Rt2World) -> None:
    result = run(world, ())
    assert (
        result.rt2.result == "pasa"
        and result.rt2.readings["unreachable_cells"] == []
        and result.unreachable_cells == ()
    )


def test_rt2_cells_a_reachable_short_and_several_unreachable_refuses_and_the_error_lists_only_the_reachable(
    world: Rt2World,
) -> None:
    short = (
        cell("sexo", "F", "lt_20", 40, 12),
        cell("estrato", "6", "lt_20", 12, 12),
        cell("rango_edad", "66+", "20_30", 4, 4),
    )
    with pytest.raises(ScenarioError) as error:
        run(world, short)
    assert (
        "sexo/F/lt_20" in str(error.value)
        and "estrato/6" not in str(error.value)
        and "66+" not in str(error.value)
    )


def test_rt2_cells_the_frontier_30_available_29_taken_refuses_29_29_runs_and_30_30_runs() -> None:
    with pytest.raises(ScenarioError, match="rt2_celda_alcanzable_corta"):
        rt2.check_cells((cell("sexo", "F", "lt_20", 30, 29),))
    assert rt2.check_cells((cell("sexo", "F", "lt_20", 29, 29),)).unreachable_short == (
        cell("sexo", "F", "lt_20", 29, 29),
    )
    assert rt2.check_cells((cell("sexo", "F", "lt_20", 30, 30),)) == rt2.CellCheck((), ())


def test_rt2_cells_the_rule_is_a_pure_function_of_the_table() -> None:
    table = (cell("a", "x", "lt_20", 100, 30), cell("a", "y", "lt_20", 45, 20), cell("a", "z", "lt_20", 7, 7))
    check = rt2.classify_cells(table)
    assert [c.group for c in check.reachable_short] == ["y"] and [
        c.group for c in check.unreachable_short
    ] == ["z"]


def population_with_a_tiny_cell() -> list[sampler.Row]:
    rows = []
    for n in range(900):
        groups = {
            "sexo": "FM"[n % 2],
            "rango_edad": ("18-25", "26-35", "36-45")[n % 3],
            "region": "AB"[(n // 2) % 2],
            "estrato": ("1", "2", "3")[(n // 3) % 3],
        }
        rows.append(sampler.Row(str(n), groups, sampler.BANDS[n % 3]))
    for n in range(
        900, 905
    ):  # solo 5 filas con estrato 6: una celda que no llega a 30 por mas que se muestree
        rows.append(
            sampler.Row(str(n), {"sexo": "F", "rango_edad": "18-25", "region": "A", "estrato": "6"}, "lt_20")
        )
    return rows


def test_rt2_cells_the_real_sampler_with_a_population_that_has_a_5_row_cell_runs_and_reports_that_cell(
    world: Rt2World,
) -> None:
    """La prueba de NFR-U12-11 con su precision: `sampler.stratified` real + la regla."""
    sample = sampler.stratified(population_with_a_tiny_cell(), 400, 3)
    tiny = [c for c in sample.short if c.attribute == "estrato" and c.group == "6"]
    assert tiny and tiny[0].available == 5 and tiny[0].taken == 5
    assert all(
        c.available < sampler.MIN_PER_CELL for c in sample.short
    )  # el muestreo nunca deja corta una alcanzable
    result = run(world, sample.short)
    assert result.rt2.result == "pasa" and {(c.attribute, c.group) for c in result.unreachable_cells} == {
        ("estrato", "6")
    }


def test_rt2_cells_the_requested_and_the_sent_volume_are_in_the_result(world: Rt2World) -> None:
    result = run(world, ())
    assert result.rt2.readings["requested"] == 1500 and result.rt2.readings["sent"] == [1500]
    assert next(s for s in result.rt2.subresults if s.name == "v1:celdas").readings["requested"] == 1500


def test_rt2_cells_the_precision_is_in_the_docstring_of_the_rule() -> None:
    for text in (rt2.__doc__ or "", rt2.classify_cells.__doc__ or ""):
        assert "alcanzable" in text and "2026-11-13" in text and "DECISIONES-LOOP.md" in (rt2.__doc__ or "")
