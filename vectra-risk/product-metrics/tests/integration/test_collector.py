"""Paso 6 (publicacion): allowlist (PBT-U11-05), PBT-U11-07 sobre las series, `month`, scrape durante el reemplazo y readiness (CA-2).

P-U11-03; NFR-U11-07, 08, 10, 40; domain-entities §5; US-503, US-505. El oraculo de la allowlist es la **transcripcion** de las dos
tablas de domain-entities §5 que esta mas abajo, no la constante del `collector`: si alguien cambia una sin la otra, la prueba falla.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from entries import (
    CHANNELS,
    MODELS,
    NOW,
    OUTCOMES,
    RecSpec,
    Spec,
    day_at,
    render,
    spec_lists,
    specs_on,
    us503_specs,
)
from hypothesis import given
from hypothesis import strategies as st
from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.parser import text_string_to_metric_families
from process_world import PARAMS, World, ops_get, scrape, value
from vectra_common.deps import CircuitState
from vectra_common.metrics import REGISTRY
from vectra_common.ops_server import create_ops_app
from vectra_product import collector as collector_module
from vectra_product.collector import (
    CYCLE_BUCKETS,
    OPERATION_SERIES,
    PRODUCT_SERIES,
    TARGET_METRICS,
    Collector,
    Holder,
    Operations,
    Published,
    register,
)
from vectra_product.compute import (
    BusinessMetrics,
    ExplanationView,
    NorthStar,
    PeriodKey,
    PeriodMetrics,
    Ratio,
    Sustained,
    compute,
    snapshot_of,
)
from vectra_product.main import make_readiness
from vectra_product.model import parse_entry

# --- el oraculo: domain-entities §5, transcrito ----------------------------------------------------------------------------

ORACLE_PRODUCT: dict[str, set[str]] = {
    "vectra_product_north_star_decisions": {
        "period",
        "month",
        "part",
        "channel",
        "outcome",
        "model_version_id",
    },
    "vectra_product_north_star_ratio": {"period", "month", "channel", "outcome", "model_version_id"},
    "vectra_product_north_star_breakdown": {"period", "month", "kind", "channel", "outcome"},
    "vectra_product_explanation_view_decisions": {"period", "part", "channel"},
    "vectra_product_explanation_view_ratio": {"period", "channel"},
    "vectra_product_noise_days_below_floor": set(),
    "vectra_product_sustained_decisions": {"period", "month", "part", "channel", "outcome"},
    "vectra_product_recommendation_sustained_ratio": {"period", "month", "channel", "outcome"},
    "vectra_product_origination_seconds": {"quantile", "standard"},
    "vectra_product_origination_standard_under_target_ratio": set(),
    "vectra_product_unattributable_decisions": {"period"},
    "vectra_product_invalid_entries": set(),
    "vectra_product_metrics_degraded": set(),
    "vectra_product_metrics_last_success_timestamp": set(),
    "vectra_product_target": {"metric"},
}
ORACLE_OPERATION: dict[str, set[str]] = {
    "vectra_product_cycle_duration_seconds": {"kind"},
    "vectra_product_entries_read_total": {"kind"},
    "vectra_product_last_full_recompute_timestamp": set(),
    "vectra_product_full_pass_in_progress": set(),
    "vectra_product_cycles_skipped_total": set(),
    "vectra_circuit_state": {"dependency"},
}
ORACLE_BUCKETS = (1, 5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600)
#: Valores cerrados de las etiquetas (domain-entities §5 y BR-U11-03, 04, 08).
PERIODS_WITH_RATIO = {"day", "30d", "month_to_date", "month"}
CLOSED_VALUES: dict[str, set[str]] = {
    "part": {"numerator", "denominator"},
    "kind": {"sustentada", "cambiada", "revision_resuelta", "incremental", "full"},
    "quantile": {"0.5", "0.8", "0.95"},
    "standard": {"true"},
    "outcome": {*OUTCOMES, "all"},
    "metric": {
        "complete_response",
        "origination_hours",
        "origination_ratio",
        "sustained_ratio_month6",
        "north_star",
        "noise_floor",
    },
    "dependency": {"decision-registry"},
}
PERIODS_BY_SERIES = {
    "vectra_product_explanation_view_decisions": {"7d"},
    "vectra_product_explanation_view_ratio": {"7d"},
    "vectra_product_unattributable_decisions": {"day", "30d", "month_to_date"},
}
MONTH = re.compile(r"^\d{4}-\d{2}$")
HISTOGRAM_PARTS = ("_bucket", "_sum", "_count", "_created")
PRODUCT_NAMES = set(ORACLE_PRODUCT)
#: Lo que publica el `collector` aparte de las series de producto: `…_last_full_recompute_timestamp` (operacion, con instantanea).
COLLECTOR_NAMES = PRODUCT_NAMES | {"vectra_product_last_full_recompute_timestamp"}


def base_name(name: str) -> str:
    """El nombre de la serie en domain-entities §5: el histograma sin su sufijo estandar; `_created` de un contador, aparte."""
    for suffix in HISTOGRAM_PARTS:
        if name.endswith(suffix) and name.removesuffix(suffix) in ORACLE_OPERATION:
            return name.removesuffix(suffix)
    if name.endswith("_created") and name.removesuffix("_created") + "_total" in ORACLE_OPERATION:
        return name.removesuffix("_created") + "_total"
    return name


def published_of(
    specs: list[Spec],
    *,
    now: datetime = NOW,
    full: bool = True,
    items: list[dict[str, Any]] | None = None,
) -> Published:
    parsed = [
        parse_entry(s.seq, item) for s, item in zip(specs, items or [render(s) for s in specs], strict=True)
    ]
    return Published(
        compute(snapshot_of(parsed, now), PARAMS, now),
        PARAMS,
        now,
        now - timedelta(minutes=1),
        now - timedelta(hours=3) if full else None,
    )


def exposition(published: Published | None) -> dict[str, list[tuple[dict[str, str], float]]]:
    """Lo que Prometheus lee de un registro propio con solo el `collector` de producto."""
    holder = Holder()
    if published is not None:
        holder.replace(published)
    registry = CollectorRegistry()
    registry.register(Collector(holder))
    return scrape(registry)


# --- PBT-U11-05 -----------------------------------------------------------------------------------------------------------


def with_identifiers(specs: list[Spec]) -> tuple[list[dict[str, Any]], set[str]]:
    """Los items crudos, con identificadores a su alcance: `case_id`, `seq`, `recommendation_entry_id` y campos de mas con forma de
    identificador de usuario (`actor_id`, `analyst_email`, `user_id`). Devuelve tambien el conjunto de lo que no puede ser una etiqueta."""
    raw: list[dict[str, Any]] = []
    forbidden: set[str] = set()
    for spec in specs:
        item = render(spec)
        extras = {
            "actor_id": f"usr-{spec.seq:08d}-analista",
            "analyst_email": f"analista{spec.seq}@banco.example",
            "user_id": f"00000000-0000-4000-9000-{spec.seq:012d}",
        }
        raw.append({**item, **extras})
        forbidden |= {item["case_id"], str(item["seq"]), item["recommendation_entry_id"], *extras.values()}
    return raw, forbidden


def check_labels(name: str, labels: dict[str, str], allowed_free: dict[str, set[str]]) -> None:
    allowed = ORACLE_PRODUCT.get(name) if name in ORACLE_PRODUCT else ORACLE_OPERATION[name]
    assert allowed is not None
    assert set(labels) <= allowed | {"le"}, f"{name}: etiquetas fuera de la allowlist {set(labels) - allowed}"
    if "month" in allowed:  # `month` si y solo si `period="month"`
        assert ("month" in labels) == (labels.get("period") == "month"), (name, labels)
    for key, label_value in labels.items():
        if key == "month":
            assert MONTH.match(label_value)
        elif key == "period":
            assert label_value in PERIODS_BY_SERIES.get(name, PERIODS_WITH_RATIO), (name, labels)
        elif key in ("channel", "model_version_id"):
            assert label_value == "all" or label_value in allowed_free[key], (name, key, label_value)
        elif key == "le":
            continue
        else:
            assert label_value in CLOSED_VALUES[key], (name, key, label_value)


@given(spec_lists(NOW))
def test_pbt_u11_05_no_series_or_label_outside_the_allowlist_and_no_identifier_as_a_label_value(
    specs: list[Spec],
) -> None:
    raw, forbidden = with_identifiers(specs)
    samples = exposition(published_of(specs, items=raw))
    free = {
        "channel": {s.rec.channel for s in specs if s.rec},
        "model_version_id": {s.rec.model for s in specs if s.rec},
    }
    assert free["channel"] <= set(CHANNELS) and free["model_version_id"] <= set(MODELS)
    for name, rows in samples.items():
        assert name in COLLECTOR_NAMES, f"serie fuera de la allowlist: {name}"
        for labels, _ in rows:
            check_labels(name, labels, free)
            assert not forbidden & set(labels.values()), f"identificador en una etiqueta de {name}: {labels}"
            assert not {"seq", "case_id", "user_id", "actor_id", "recommendation_entry_id"} & set(labels)


# --- PBT-U11-07 sobre lo publicado -----------------------------------------------------------------------------------------


def sums(rows: list[tuple[dict[str, str], float]], **match: str) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for labels, count in rows:
        if all(labels.get(k) == v for k, v in match.items()):
            out[labels["part"]] += count
    return out


@given(spec_lists(NOW))
def test_pbt_u11_07_published_counts_by_cut_add_up_to_the_total_and_the_published_ratios(
    specs: list[Spec],
) -> None:
    samples = exposition(published_of(specs))
    for series, ratio_name, dims in (
        (
            "vectra_product_north_star_decisions",
            "vectra_product_north_star_ratio",
            ("channel", "outcome", "model_version_id"),
        ),
        (
            "vectra_product_sustained_decisions",
            "vectra_product_recommendation_sustained_ratio",
            ("channel", "outcome"),
        ),
    ):
        keys = {(labels["period"], labels.get("month")) for labels, _ in samples.get(series, [])} | {
            (labels["period"], labels.get("month")) for labels, _ in samples.get(ratio_name, [])
        }
        for period, month in keys:
            scope = {"period": period, **({"month": month} if month else {})}
            rows = [
                (lab, v)
                for lab, v in samples.get(series, [])
                if all(lab.get(k) == x for k, x in scope.items())
            ]
            totals = sums(rows)
            ratio_rows = [
                (lab, v)
                for lab, v in samples.get(ratio_name, [])
                if all(lab.get(k) == x for k, x in scope.items())
            ]
            all_all = {d: "all" for d in dims}
            total_ratio = [v for lab, v in ratio_rows if all(lab.get(d) == "all" for d in dims)]
            if totals.get("denominator"):
                assert total_ratio == [totals["numerator"] / totals["denominator"]]
            else:
                assert total_ratio == []  # denominador 0: la razon no se emite
            # una razon por un solo corte: la suma de los conteos de ese valor, nunca un promedio de razones
            for lab, rate in ratio_rows:
                cut = [d for d in dims if lab.get(d) != "all"]
                assert len(cut) <= 1, f"razon con dos cortes a la vez: {lab}"
                if cut:
                    part = sums(rows, **{cut[0]: lab[cut[0]]})
                    assert rate == part["numerator"] / part["denominator"]
            assert set(all_all) == set(dims)
    # El oraculo de la North Star y la sostenida del dia, por definicion y sobre las `Spec`, nunca sobre `compute` (BR-U11-03, 04):
    yesterday = (NOW - timedelta(days=1)).date()
    mine = [s for s in specs if s.valid and s.rec is not None and s.decided.date() == yesterday]
    expected = {
        "vectra_product_north_star_decisions": (
            sum(1 for s in mine if s.viewed and s.factors != ("ninguno",)),
            len(mine),
        ),
        "vectra_product_sustained_decisions": (sum(1 for s in mine if s.decision == "sigue"), len(mine)),
    }
    for series, (numerator, denominator) in expected.items():
        rows = [(lab, v) for lab, v in samples.get(series, []) if lab["period"] == "day"]
        got = sums(rows)
        assert (got.get("numerator", 0), got.get("denominator", 0)) == (numerator, denominator)


# --- /metrics del `ops_server` real con instantanea -------------------------------------------------------------------------


@pytest_asyncio.fixture
async def worlds() -> Any:
    made: list[World] = []
    yield made
    for world in made:
        await world.close()


def make(worlds: list[World], *args: Any, **kwargs: Any) -> World:
    world = World(*args, **kwargs)
    worlds.append(world)
    return world


@pytest.mark.asyncio
async def test_us_503_example_end_to_end_gives_0_4_with_breakdown_2_1_1(worlds: list[World]) -> None:
    world = make(worlds, [render(s) for s in us503_specs()])
    await world.start()
    samples = world.metrics()
    total = {"period": "day", "channel": "all", "outcome": "all", "model_version_id": "all"}
    assert value(samples, "vectra_product_north_star_ratio", **total) == 0.4
    kinds = {
        labels["kind"]: sum(
            v
            for lab, v in samples["vectra_product_north_star_breakdown"]
            if lab["kind"] == labels["kind"] and lab["period"] == "day"
        )
        for labels, _ in samples["vectra_product_north_star_breakdown"]
    }
    assert kinds == {"sustentada": 2, "cambiada": 1, "revision_resuelta": 1}
    # y por HTTP, lo que sirve el `ops_server` real
    body = (await ops_get(create_ops_app(world.ready), "/metrics")).text
    assert (
        'vectra_product_north_star_ratio{channel="all",model_version_id="all",outcome="all",period="day"} 0.4'
        in body
    )


@pytest.mark.asyncio
async def test_metrics_of_the_real_ops_app_with_a_snapshot_only_adds_allowlisted_series_with_exact_labels(
    worlds: list[World],
) -> None:
    before = {
        family.name for family in REGISTRY.collect()
    }  # lo que ya publica U0, antes de registrar nada de U11
    world = make(worlds, [render(s) for s in us503_specs()])
    await world.start()
    families = list(
        text_string_to_metric_families((await ops_get(create_ops_app(world.ready), "/metrics")).text)
    )
    names_seen: set[str] = set()
    for family in families:
        for sample in family.samples:
            name = base_name(sample.name)
            if (
                name.endswith("_created")
                or family.name in before
                and not family.name.startswith("vectra_product_")
            ):
                continue  # series de U0 o `_created` de un contador: las controla la allowlist de U0
            names_seen.add(name)
            assert name in ORACLE_PRODUCT or name in ORACLE_OPERATION, (
                f"serie fuera de la allowlist: {sample.name}"
            )
            allowed = ORACLE_PRODUCT.get(name) if name in ORACLE_PRODUCT else ORACLE_OPERATION[name]
            assert set(sample.labels) <= (allowed or set()) | {"le"}, (sample.name, sample.labels)
    # la allowlist se publica entera: todas las series de producto y de operacion (salvo las que dependen de datos)
    assert (
        set(ORACLE_PRODUCT)
        - {
            "vectra_product_origination_seconds",
            "vectra_product_origination_standard_under_target_ratio",
            "vectra_product_unattributable_decisions",
        }
        <= names_seen
    )
    assert set(ORACLE_OPERATION) - {"vectra_circuit_state"} <= names_seen
    assert (
        value(scrape(), "vectra_circuit_state", dependency="decision-registry") == CircuitState.CLOSED
    )  # de U0
    # `vectra_product_*` solo las de la allowlist
    assert all(
        base_name(n) in ORACLE_PRODUCT or base_name(n) in ORACLE_OPERATION
        for n in scrape()
        if n.startswith("vectra_product_")
    )


def test_the_allowlist_constants_equal_the_transcribed_tables() -> None:
    assert {k: set(v) for k, v in PRODUCT_SERIES.items()} == ORACLE_PRODUCT
    assert {k: set(v) for k, v in OPERATION_SERIES.items()} == ORACLE_OPERATION
    assert tuple(CYCLE_BUCKETS) == tuple(float(b) for b in ORACLE_BUCKETS)
    assert set(TARGET_METRICS) == CLOSED_VALUES["metric"]
    assert collector_module.PRODUCT_SERIES is PRODUCT_SERIES


# --- `month` y los meses cerrados (NFR-U11-10) ----------------------------------------------------------------------------


def seven_months() -> list[Spec]:
    """Datos en los 6 meses cerrados anteriores a octubre (abril a septiembre), en marzo (el septimo) y en octubre (el mes en curso)."""
    moments = [datetime(2026, m, 15, 12, tzinfo=UTC) for m in (3, 4, 5, 6, 7, 8, 9)] + [
        datetime(2026, 10, 2, 12, tzinfo=UTC)
    ]
    return [
        Spec(seq=i + 1, decided=moment, rec=RecSpec(evaluated=moment - timedelta(hours=2)))
        for i, moment in enumerate(moments)
    ] + specs_on(1, 2, 100)  # ayer (5 de octubre)


def test_with_7_months_of_data_exactly_the_6_closed_months_are_published() -> None:
    samples = exposition(published_of(seven_months()))
    months = {
        lab["month"]
        for name in (
            "vectra_product_north_star_decisions",
            "vectra_product_north_star_ratio",
            "vectra_product_north_star_breakdown",
            "vectra_product_sustained_decisions",
            "vectra_product_recommendation_sustained_ratio",
        )
        for lab, _ in samples[name]
        if lab["period"] == "month"
    }
    assert months == {
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    }  # ni 2026-03 ni 2026-10
    # cada serie con `period="month"` lleva `month`, y ninguna otra `period` lo lleva
    for name, rows in samples.items():
        for lab, _ in rows:
            assert ("month" in lab) == (lab.get("period") == "month"), (name, lab)
            if "month" in lab:
                assert MONTH.match(lab["month"])
    # las de consulta de explicacion: `period="7d"` y nunca `month`; sin series `unattributable` con `month`
    for name in ("vectra_product_explanation_view_decisions", "vectra_product_explanation_view_ratio"):
        assert samples[name] and all(lab["period"] == "7d" and "month" not in lab for lab, _ in samples[name])
    assert all(lab["period"] != "month" for lab, _ in samples["vectra_product_unattributable_decisions"])


def test_series_of_period_day_carry_no_month_key_even_empty() -> None:
    text = generate_latest(register_into(published_of(specs_on(1, 3, 1)))).decode()
    day_lines = [line for line in text.splitlines() if 'period="day"' in line]
    assert day_lines and all("month" not in line for line in day_lines)
    assert 'month=""' not in text


def register_into(published: Published) -> CollectorRegistry:
    holder = Holder()
    holder.replace(published)
    registry = CollectorRegistry()
    registry.register(Collector(holder))
    return registry


# --- denominador 0, sin instantanea, operacion ---------------------------------------------------------------------------


def test_a_ratio_with_denominator_0_is_not_published_but_its_counts_are() -> None:
    empty = Ratio(0, 0)
    period = PeriodMetrics(
        NorthStar(
            {("web", "favorable", "model-a"): empty},
            {},
            empty,
            {"web": empty},
            {"favorable": empty},
            {"model-a": empty},
        ),
        Sustained({("web", "favorable"): empty}, empty, {"web": empty}, {"favorable": empty}),
        0,
    )
    metrics = BusinessMetrics(
        {PeriodKey("day"): period}, ExplanationView({"web": empty}, empty), {}, 0, {}, 0, False
    )
    samples = exposition(Published(metrics, PARAMS, NOW, NOW, NOW))
    assert "vectra_product_north_star_ratio" not in samples
    assert "vectra_product_recommendation_sustained_ratio" not in samples
    assert "vectra_product_explanation_view_ratio" not in samples
    counts = samples["vectra_product_north_star_decisions"]
    assert sorted((lab["part"], v) for lab, v in counts) == [("denominator", 0.0), ("numerator", 0.0)]
    assert len(samples["vectra_product_sustained_decisions"]) == 2
    assert value(samples, "vectra_product_unattributable_decisions", period="day") == 0


def test_a_day_without_decisions_publishes_no_rate_for_that_day() -> None:
    samples = exposition(published_of(specs_on(5, 4, 1)))  # decisiones, pero ayer ninguna
    assert not [
        lab for lab, _ in samples.get("vectra_product_north_star_ratio", []) if lab["period"] == "day"
    ]
    assert any(lab["period"] == "30d" for lab, _ in samples["vectra_product_north_star_ratio"])


@pytest.mark.asyncio
async def test_without_a_snapshot_no_product_series_and_the_operation_series_have_the_exact_buckets(
    worlds: list[World],
) -> None:
    world = make(worlds, [])
    world.double.fail_all = True
    await world.start()
    samples = world.metrics()
    assert [n for n in samples if n.startswith("vectra_product_") and base_name(n) in PRODUCT_NAMES] == []
    assert "vectra_product_metrics_last_success_timestamp" not in samples
    assert "vectra_product_last_full_recompute_timestamp" not in samples
    for kind in ("incremental", "full"):
        les = sorted(
            float(lab["le"])
            for lab, _ in samples["vectra_product_cycle_duration_seconds_bucket"]
            if lab["kind"] == kind and lab["le"] != "+Inf"
        )
        assert les == [float(b) for b in ORACLE_BUCKETS]
        assert value(samples, "vectra_product_entries_read_total", kind=kind) == 0
    assert value(samples, "vectra_product_full_pass_in_progress") == 0
    assert value(samples, "vectra_product_cycles_skipped_total") == 0
    assert value(samples, "vectra_circuit_state", dependency="decision-registry") == CircuitState.CLOSED


def test_last_success_is_published_with_a_snapshot_and_last_full_recompute_only_after_a_full_pass() -> None:
    with_full = exposition(published_of(specs_on(1, 3, 1)))
    assert (
        value(with_full, "vectra_product_last_full_recompute_timestamp")
        == (NOW - timedelta(hours=3)).timestamp()
    )
    assert (
        value(with_full, "vectra_product_metrics_last_success_timestamp")
        == (NOW - timedelta(minutes=1)).timestamp()
    )
    without_full = exposition(published_of(specs_on(1, 3, 1), full=False))
    assert "vectra_product_last_full_recompute_timestamp" not in without_full  # nunca 0


def test_targets_origination_and_unattributable_follow_the_decisions_of_the_questions() -> None:
    """P-4 (a): la originacion del dia de ayer; P-5 (a): los `metric` de `vectra_product_target`."""
    yesterday_spec = specs_on(1, 2, 1, rec=RecSpec(elapsed_s=600, evaluated=day_at(1, 8)))
    older = specs_on(3, 2, 10, rec=RecSpec(elapsed_s=7200, evaluated=day_at(3, 8)))  # otro dia: no se publica
    samples = exposition(published_of([*yesterday_spec, *older]))
    assert {lab["quantile"] for lab, _ in samples["vectra_product_origination_seconds"]} == {
        "0.5",
        "0.8",
        "0.95",
    }
    assert all(v == 600 for _, v in samples["vectra_product_origination_seconds"])
    assert value(samples, "vectra_product_origination_standard_under_target_ratio") == 1.0
    assert {lab["metric"] for lab, _ in samples["vectra_product_target"]} == CLOSED_VALUES["metric"] - {
        "north_star"
    }
    no_standard = exposition(published_of(specs_on(1, 2, 1, rec=RecSpec(channel="manual"))))
    assert "vectra_product_origination_seconds" not in no_standard  # sin casos estandar ayer: ausente, no 0
    agreed = replace(published_of(specs_on(1, 1, 1)), params=replace(PARAMS, target_north_star=0.5))
    assert value(exposition(agreed), "vectra_product_target", metric="north_star") == 0.5


# --- un scrape durante el reemplazo: solo valores de un ciclo ----------------------------------------------------------------


class SwappingHolder(Holder):
    """Reemplaza lo publicado justo despues de la primera lectura de la referencia: lo que `collect()` lea despues es de otro ciclo."""

    def __init__(self, first: Published, second: Published) -> None:
        super().__init__()
        self.replace(first)
        self._second = second
        self.reads = 0

    @property
    def current(self) -> Published | None:  # type: ignore[override]
        self.reads += 1
        value_now = super().current
        if self.reads == 1:
            self.replace(self._second)
        return value_now


def test_a_scrape_during_the_replacement_is_entirely_cycle_a_or_entirely_cycle_b() -> None:
    a = published_of(specs_on(1, 3, 1), now=NOW)
    b = replace(
        published_of(specs_on(1, 5, 1, decision="se_aparta"), now=NOW + timedelta(minutes=5)),
        last_full_recompute_at=None,
    )
    only_a, only_b = exposition(a), exposition(b)
    assert only_a != only_b
    holder = SwappingHolder(a, b)
    registry = CollectorRegistry()
    registry.register(Collector(holder))
    first = scrape(registry)
    assert holder.reads == 1  # la referencia se lee una sola vez por scrape
    assert first == only_a  # entero del ciclo A, sin mezclar ni un valor de B
    assert scrape(registry) == only_b  # el scrape siguiente es entero del ciclo B


# --- readiness (NFR-U11-07) ---------------------------------------------------------------------------------------------------


class FakeReader:
    def __init__(self, state: CircuitState = CircuitState.CLOSED) -> None:
        self.breaker_state = state


@pytest.mark.parametrize(
    ("snapshot", "breaker", "expected"),
    [
        (False, CircuitState.CLOSED, 503),  # sin instantanea y breaker cerrado
        (False, CircuitState.OPEN, 200),  # sin instantanea y abierto
        (False, CircuitState.HALF_OPEN, 200),  # sin instantanea y semiabierto
        (True, CircuitState.CLOSED, 200),  # con instantanea, cualquier estado
        (True, CircuitState.OPEN, 200),
        (True, CircuitState.HALF_OPEN, 200),
    ],
)
@pytest.mark.asyncio
async def test_readiness_table_through_the_real_ops_app(
    snapshot: bool, breaker: CircuitState, expected: int
) -> None:
    holder = Holder()
    if snapshot:
        holder.replace(published_of(specs_on(1, 2, 1)))
    ready = make_readiness(holder, FakeReader(breaker))  # type: ignore[arg-type]
    assert (await ops_get(create_ops_app(ready), "/readyz")).status_code == expected


@pytest.mark.asyncio
async def test_a_breaker_that_closes_without_a_snapshot_goes_back_to_503_and_a_raising_predicate_is_503() -> (
    None
):
    holder, reader = Holder(), FakeReader(CircuitState.OPEN)
    app = create_ops_app(make_readiness(holder, reader))  # type: ignore[arg-type]
    assert (await ops_get(app, "/readyz")).status_code == 200
    reader.breaker_state = CircuitState.CLOSED  # el breaker se cierra y sigue sin instantanea
    assert (await ops_get(app, "/readyz")).status_code == 503

    def boom() -> bool:
        raise RuntimeError("el predicado falla")

    assert (await ops_get(create_ops_app(boom), "/readyz")).status_code == 503


def test_published_is_immutable_and_the_collector_describes_no_fixed_names() -> None:
    published = published_of(specs_on(1, 1, 1))
    with pytest.raises(AttributeError):
        published.now = NOW  # type: ignore[misc]
    assert list(Collector(Holder()).describe()) == []
    assert Operations is collector_module.Operations and register is collector_module.register
    assert st  # el modulo de estrategias se usa en los generadores de arriba
