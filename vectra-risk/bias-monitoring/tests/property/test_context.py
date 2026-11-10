"""PBT-U9-08: el paquete de `freeze` (BR-U9-15) nunca trae la tasa de una celda insuficiente ni la tasa sin bandas de un grupo
con alguna celda insuficiente, ni campos fuera de §3.1; con menos de 7 dias de datos, `before = sin_datos`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from builders import full_catalog, small_tables
from hypothesis import assume, given
from hypothesis import strategies as st
from vectra_bias.context import MAX_PACKAGE_BYTES, build_context_package, measure, size_bytes
from vectra_bias.freeze_rule import attribute_limits, decide
from vectra_bias.window import version_ranges
from vectra_contracts.models.monitoring import AffectedVolume, FreezeContext
from vectra_disparity import ATTRIBUTES, UNINFORMED, CountTable
from vectra_disparity import __version__ as LIBRARY_VERSION

TODAY = date(2026, 11, 9)
N_MIN = 30
THRESHOLD = Decimal(5)
NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
FIELDS_3_1 = {
    "model_version_id", "computed_at", "threshold_pp", "n_min", "window_days", "schedule", "stale_after_s",
    "library_version", "window_start", "before", "after", "last_7_days", "trigger_attribute", "implicated",
    "affected_volume", "truncated",
}  # fmt: skip


def _package(counts, history_days, max_bytes=MAX_PACKAGE_BYTES, version="v1") -> FreezeContext | None:
    ranges = version_ranges(TODAY, 30, TODAY - timedelta(days=history_days - 1), None)
    if ranges.after is None:
        return None

    def result(span):
        return None if span is None else measure(counts, N_MIN, "modelo", version, span.from_day, span.to_day)

    after = result(ranges.after)
    if after.trigger_attribute is None:
        return None
    decision = decide("modelo", THRESHOLD, attribute_limits(counts, N_MIN))
    return build_context_package(
        model_version_id=version,
        computed_at=NOW,
        threshold_pp=THRESHOLD,
        n_min=N_MIN,
        window_days=30,
        schedule="2,17,32,47 * * * *",
        stale_after_s=3600,
        window_start=ranges.window_start,
        before=result(ranges.before),
        after=after,
        last_7_days=result(ranges.last_7_days),
        decision=decision,
        affected_volume=AffectedVolume(total=10, favorable=5),
        max_bytes=max_bytes,
    )


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)


def _population_difference_oracle(table: CountTable) -> tuple[str | None, bool]:
    """Diferencia sin bandas de la tabla excluyendo todo grupo con alguna celda insuficiente (BR-U9-06) y si fue parcial."""
    totals: dict[str, list[int]] = {}
    excluded: set[str] = set()
    for cell in table.cells:
        if cell.group == UNINFORMED:
            continue
        if cell.total < N_MIN:
            excluded.add(cell.group)
        acc = totals.setdefault(cell.group, [0, 0])
        acc[0] += cell.favorable
        acc[1] += cell.total
    rates = [f / n for g, (f, n) in totals.items() if g not in excluded and n > 0]
    if len(rates) < 2:
        return None, bool(excluded)
    return f"{Decimal(max(rates) - min(rates)):.4f}", bool(excluded)


@given(counts=small_tables(), history=st.integers(0, 40))
def test_the_package_never_carries_a_rate_of_an_insufficient_cell_or_fields_outside_3_1(counts, history):
    package = _package(counts, history)
    assume(package is not None)
    dumped = package.model_dump(mode="json")
    assert set(dumped) == FIELDS_3_1
    assert FreezeContext.model_validate_json(package.model_dump_json()) == package  # valida contra U0
    assert package.library_version == LIBRARY_VERSION

    sufficient_rates = {
        f"{c.favorable / c.total:.4f}" for t in counts.values() for c in t.cells if c.total >= N_MIN
    }
    for node in _walk(dumped):
        if node.get("status") == "muestra_insuficiente":
            assert node.get("rate") is None  # una celda insuficiente lleva solo su tamano
        if node.get("status") == "suficiente":
            assert node["rate"] in sufficient_rates or Decimal(node["rate"]) in {Decimal(r) for r in sufficient_rates}
        if "freeze_lower_limit" in node:
            assert set(node) == {"attribute", "freeze_lower_limit", "bands"}
            assert all(set(b) == {"band", "difference", "extreme_pair"} for b in node["bands"])
    for measurement in (package.before, package.after, package.last_7_days):
        if isinstance(measurement, str):
            continue
        for attribute in measurement.attributes:
            expected, partial = _population_difference_oracle(counts[attribute.attribute])
            assert attribute.population_difference_partial is partial
            # Rangos distintos suman lo mismo en este generador (mismas tablas): la diferencia sin bandas es la del oraculo.
            assert attribute.population_difference == expected


@given(counts=small_tables(), history=st.integers(0, 40))
def test_with_fewer_than_7_days_of_data_before_is_without_data(counts, history):
    package = _package(counts, history)
    assume(package is not None)
    if history <= 7:  # con 7 dias de datos el rango «antes» (que termina hoy - 7) cae entero antes del inicio de la ventana
        assert package.before == "sin_datos"
    else:
        assert package.before != "sin_datos"
    assert package.last_7_days != "sin_datos"
    assert package.window_start == TODAY - timedelta(days=history - 1)


def test_the_full_catalogs_fit_in_48_kib_or_are_truncated_with_the_aggregates_intact():
    counts = full_catalog()
    package = _package(counts, 40)
    assert package is not None
    assert size_bytes(package) <= MAX_PACKAGE_BYTES or package.truncated
    untrimmed = _package(counts, 40, max_bytes=10**9)
    print(f"full_catalog_package_bytes={size_bytes(untrimmed)} truncated={package.truncated}")
    assert _essentials(package) == _essentials(untrimmed)
    assert package.implicated == untrimmed.implicated


def _essentials(package: FreezeContext) -> dict[str, Any]:
    dumped = package.model_dump(mode="json")
    keep = {}
    for field in ("before", "after", "last_7_days"):
        m = dumped[field]
        keep[field] = (
            m
            if isinstance(m, str)
            else {
                "model_aggregate": m["model_aggregate"],
                "trigger_attribute": m["trigger_attribute"],
                "attributes": [
                    {k: a[k] for k in ("attribute", "bands", "aggregate", "aggregate_ci_95")} for a in m["attributes"]
                ],
            }
        )
    keep["trigger_attribute"] = dumped["trigger_attribute"]
    keep["implicated"] = dumped["implicated"]
    return keep


def test_the_cell_trimming_order_is_before_then_last_7_days_then_after_and_the_essentials_are_kept():
    counts = full_catalog()
    full = _package(counts, 40)
    assert full is not None and not full.truncated
    cells = lambda m: sum(len(a.cells) for a in m.attributes)  # noqa: E731
    size_full = size_bytes(full)
    # Un limite justo por debajo del tamano completo quita primero las celdas de `before`.
    first = _package(counts, 40, max_bytes=size_full - 1)
    assert first.truncated and cells(first.before) == 0 and cells(first.last_7_days) > 0 and cells(first.after) > 0
    # Un limite por debajo del tamano sin `before` quita tambien las de `last_7_days`.
    second = _package(counts, 40, max_bytes=size_bytes(first) - 1)
    assert cells(second.before) == 0 and cells(second.last_7_days) == 0 and cells(second.after) > 0
    # Y por debajo de ese, las de `after`; el paquete sale igual (el freeze nunca espera por el tamano).
    third = _package(counts, 40, max_bytes=size_bytes(second) - 1)
    assert cells(third.before) == cells(third.last_7_days) == cells(third.after) == 0
    forced = _package(counts, 40, max_bytes=1)
    assert forced.truncated
    for package in (first, second, third, forced):
        assert _essentials(package) == _essentials(full)
        assert package.implicated == full.implicated
        assert package.trigger_attribute == full.trigger_attribute
        assert all(a.bands for a in package.after.attributes)


def test_implicated_names_the_attribute_with_its_limit_and_its_bands_over_the_threshold():
    counts = full_catalog(rate_gap=0.2, n=2000)
    package = _package(counts, 40)
    assert package is not None
    assert package.implicated, "con 20 pp y 2 000 casos por celda la regla se cumple en todos los atributos"
    assert {i["attribute"] for i in package.implicated} == set(ATTRIBUTES)
    for item in package.implicated:
        assert Decimal(item["freeze_lower_limit"]) > Decimal("0.05")
        assert all(Decimal(b["difference"]) > Decimal("0.05") for b in item["bands"])
