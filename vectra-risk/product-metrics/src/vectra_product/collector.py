"""Publicacion en `/metrics` (P-U11-03; NFR-U11-07, 08, 10, 40; domain-entities §5).

- Lo publicado es **una** instantanea inmutable (`Published`): el `BusinessMetrics` de `compute`, los `Params` y las marcas de tiempo
  del ciclo. `Holder` guarda una sola referencia que el `scheduler` reemplaza al final de cada lectura exitosa; `Collector.collect()`
  la lee **una sola vez** al entrar y arma todas las familias desde esa copia local: un scrape nunca mezcla dos ciclos.
- Sin instantanea no hay series de producto ni `…_last_success_timestamp` (nunca ceros). `…_last_full_recompute_timestamp` tampoco
  se emite hasta la primera pasada completa exitosa.
- Las series de operacion del ciclo (`Operations`) existen desde el arranque.
- `PRODUCT_SERIES` y `OPERATION_SERIES` son la allowlist de domain-entities §5 como dato: la usan este modulo, las pruebas y, en el
  Paso 12, `tools/gen_rules.py`. Ninguna etiqueta lleva `case_id`, `seq` ni un identificador de usuario (SECURITY-03; NFR-U11-22).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client.metrics_core import Metric
from vectra_common.metrics import REGISTRY, histogram

from vectra_product.compute import ALL, QUANTILES, BusinessMetrics, PeriodKey, PeriodMetrics, Ratio
from vectra_product.model import Params

#: Etiquetas de cada serie de producto (primera tabla de domain-entities §5). `month` (`AAAA-MM`) solo la lleva el `period="month"`.
PRODUCT_SERIES: Final[Mapping[str, frozenset[str]]] = {
    "vectra_product_north_star_decisions": frozenset(
        {"period", "month", "part", "channel", "outcome", "model_version_id"}
    ),
    "vectra_product_north_star_ratio": frozenset(
        {"period", "month", "channel", "outcome", "model_version_id"}
    ),
    "vectra_product_north_star_breakdown": frozenset({"period", "month", "kind", "channel", "outcome"}),
    "vectra_product_explanation_view_decisions": frozenset({"period", "part", "channel"}),
    "vectra_product_explanation_view_ratio": frozenset({"period", "channel"}),
    "vectra_product_noise_days_below_floor": frozenset(),
    "vectra_product_sustained_decisions": frozenset({"period", "month", "part", "channel", "outcome"}),
    "vectra_product_recommendation_sustained_ratio": frozenset({"period", "month", "channel", "outcome"}),
    "vectra_product_origination_seconds": frozenset({"quantile", "standard"}),
    "vectra_product_origination_standard_under_target_ratio": frozenset(),
    "vectra_product_unattributable_decisions": frozenset({"period"}),
    "vectra_product_invalid_entries": frozenset(),
    "vectra_product_metrics_degraded": frozenset(),
    "vectra_product_metrics_last_success_timestamp": frozenset(),
    "vectra_product_target": frozenset({"metric"}),
}

#: Series de operacion del ciclo (segunda tabla de §5; NFR-U11-40). Los contadores van con `_total`; del histograma salen
#: `_bucket` (con `le`), `_sum`, `_count` y `_created`.
OPERATION_SERIES: Final[Mapping[str, frozenset[str]]] = {
    "vectra_product_cycle_duration_seconds": frozenset({"kind"}),
    "vectra_product_entries_read_total": frozenset({"kind"}),
    "vectra_product_last_full_recompute_timestamp": frozenset(),
    "vectra_product_full_pass_in_progress": frozenset(),
    "vectra_product_cycles_skipped_total": frozenset(),
    "vectra_circuit_state": frozenset({"dependency"}),
}

#: Buckets del histograma de duracion de un ciclo (domain-entities §5), en segundos.
CYCLE_BUCKETS: Final = (1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1200.0, 1800.0, 3600.0)
KINDS: Final = ("incremental", "full")

#: `metric` de `vectra_product_target` (P-5, opcion a). `north_star` solo si hay target acordado.
TARGET_METRICS: Final = (
    "complete_response",
    "origination_hours",
    "origination_ratio",
    "sustained_ratio_month6",
    "north_star",
    "noise_floor",
)

#: Los `period` sin `month` y las ventanas de consulta de explicacion (BR-U11-08; sin `month`, domain-entities §5).
VIEW_PERIOD: Final = "7d"
MONTH_PERIOD: Final = "month"
#: `vectra_product_unattributable_decisions` no tiene serie en los meses cerrados.
UNATTRIBUTABLE_PERIODS: Final = ("day", "30d", "month_to_date")


@dataclass(frozen=True, slots=True)
class Published:
    """La instantanea inmutable que se publica (P-U11-03): `compute` mas las marcas de tiempo del ciclo y los parametros."""

    metrics: BusinessMetrics
    params: Params
    now: datetime  # el `now` con el que se calculo; fija el «ayer» de la originacion
    last_success_at: datetime
    last_full_recompute_at: datetime | None  # `None` hasta la primera pasada completa exitosa


class Holder:
    """Una sola referencia a lo publicado. `replace` es una asignacion: el reemplazo es atomico para quien lea `current`."""

    def __init__(self) -> None:
        self._current: Published | None = None

    @property
    def current(self) -> Published | None:
        return self._current

    def replace(self, published: Published) -> None:
        self._current = published


class Operations:
    """Series de operacion del ciclo (NFR-U11-40), registradas en el registro de U0. Existen desde el arranque, con sus dos `kind`."""

    def __init__(self) -> None:
        self.cycle_duration: Histogram = histogram(
            "vectra_product_cycle_duration_seconds",
            "Duracion de una lectura (incremental o pasada completa)",
            ["kind"],
            CYCLE_BUCKETS,
        )
        self.entries_read = Counter(
            "vectra_product_entries_read_total", "Entradas leidas de U3", ["kind"], registry=REGISTRY
        )
        self.full_pass_in_progress = Gauge(
            "vectra_product_full_pass_in_progress",
            "1 mientras la pasada completa espera el candado o lee",
            registry=REGISTRY,
        )
        self.cycles_skipped = Counter(
            "vectra_product_cycles_skipped_total",
            "Ciclos incrementales omitidos porque el candado estaba tomado",
            registry=REGISTRY,
        )
        for kind in KINDS:  # las series existen desde el arranque, en 0
            self.cycle_duration.labels(kind=kind)
            self.entries_read.labels(kind=kind)

    def observe(self, kind: str, seconds: float) -> None:
        self.cycle_duration.labels(kind=kind).observe(seconds)

    def read(self, kind: str, entries: int) -> None:
        self.entries_read.labels(kind=kind).inc(entries)

    def close(self) -> None:
        for item in (self.cycle_duration, self.entries_read, self.full_pass_in_progress, self.cycles_skipped):
            REGISTRY.unregister(item)


def _labels(key: PeriodKey, **more: str) -> dict[str, str]:
    """`period` y, solo con `period="month"`, `month`. Las demas series no llevan la clave `month`, ni vacia."""
    labels = {"period": key.period}
    if key.period == MONTH_PERIOD:
        assert key.month is not None  # `compute` siempre fija el mes de un `period="month"`
        labels["month"] = key.month
    labels.update(more)
    return labels


class _Family:
    """Una familia `gauge` con las etiquetas de cada muestra por separado (`GaugeMetricFamily` las fija para toda la familia)."""

    def __init__(self, name: str, documentation: str) -> None:
        self.metric = Metric(name, documentation, "gauge")
        self.name = name

    def add(self, labels: Mapping[str, str], value: float) -> None:
        self.metric.add_sample(self.name, dict(labels), float(value))

    def ratio(self, labels: Mapping[str, str], ratio: Ratio) -> None:
        if ratio.rate is not None:  # denominador 0: la razon no se emite (BR-U11-03)
            self.add(labels, ratio.rate)

    def counts(self, labels: Mapping[str, str], ratio: Ratio) -> None:
        self.add({**labels, "part": "numerator"}, ratio.numerator)
        self.add({**labels, "part": "denominator"}, ratio.denominator)


def _north_star(
    key: PeriodKey, period: PeriodMetrics, decisions: _Family, ratio: _Family, breakdown: _Family
) -> None:
    north = period.north_star
    for (channel, outcome, model), cell in north.cells.items():  # conteos: todos los cortes, sin filas `all`
        decisions.counts(_labels(key, channel=channel, outcome=outcome, model_version_id=model), cell)
    for (kind, channel, outcome), count in north.breakdown.items():
        breakdown.add(_labels(key, kind=kind, channel=channel, outcome=outcome), count)
    every = {"channel": ALL, "outcome": ALL, "model_version_id": ALL}
    ratio.ratio(_labels(key, **every), north.total)  # razones: el total y un solo corte, nunca dos a la vez
    for cut, values in (
        ("channel", north.by_channel),
        ("outcome", north.by_outcome),
        ("model_version_id", north.by_model),
    ):
        for value, cell in values.items():
            ratio.ratio(_labels(key, **{**every, cut: value}), cell)


def _sustained(key: PeriodKey, period: PeriodMetrics, decisions: _Family, ratio: _Family) -> None:
    sustained = period.sustained
    for (channel, outcome), cell in sustained.cells.items():
        decisions.counts(_labels(key, channel=channel, outcome=outcome), cell)
    ratio.ratio(_labels(key, channel=ALL, outcome=ALL), sustained.total)
    for value, cell in sustained.by_channel.items():
        ratio.ratio(_labels(key, channel=value, outcome=ALL), cell)
    for value, cell in sustained.by_outcome.items():
        ratio.ratio(_labels(key, channel=ALL, outcome=value), cell)


def _targets(params: Params) -> Iterator[tuple[str, float]]:
    yield "complete_response", params.target_complete_response
    yield "origination_hours", params.target_origination_hours
    yield "origination_ratio", params.target_origination_ratio
    yield "sustained_ratio_month6", params.target_sustained_ratio_month6
    if params.target_north_star is not None:  # ausente quiere decir «sin target acordado»
        yield "north_star", params.target_north_star
    yield "noise_floor", params.noise_floor


def _timestamp(moment: datetime) -> float:
    return moment.astimezone(UTC).timestamp()


def yesterday(now: datetime) -> date:
    """El dia que publica la originacion (P-4, opcion a): el `day` de BR-U11-08, dias UTC completos sin el dia en curso."""
    return now.astimezone(UTC).date() - timedelta(days=1)


class Collector:
    """`Collector` de `prometheus-client` sobre la instantanea inmutable."""

    def __init__(self, holder: Holder) -> None:
        self._holder = holder

    def describe(self) -> Iterable[Metric]:
        return []  # sin nombres fijos: lo que se emite depende de la instantanea (y no hay que leerla al registrar)

    def collect(self) -> Iterable[Metric]:
        published = self._holder.current  # UNA sola lectura de la referencia: todo sale de esta copia local
        if published is None:
            return []
        return self._families(published)

    @staticmethod
    def _families(published: Published) -> list[Metric]:
        metrics = published.metrics
        north_decisions = _Family(
            "vectra_product_north_star_decisions", "Decisiones de la North Star (conteos)"
        )
        north_ratio = _Family(
            "vectra_product_north_star_ratio", "Tasa de decisiones donde la explicacion pesa"
        )
        north_breakdown = _Family(
            "vectra_product_north_star_breakdown", "Desglose del numerador de la North Star (conteos)"
        )
        sustained_decisions = _Family("vectra_product_sustained_decisions", "Decisiones sostenidas (conteos)")
        sustained_ratio = _Family(
            "vectra_product_recommendation_sustained_ratio", "Tasa de recomendaciones sostenidas"
        )
        unattributable = _Family("vectra_product_unattributable_decisions", "Decisiones no atribuibles")
        for key, period in metrics.periods.items():
            _north_star(key, period, north_decisions, north_ratio, north_breakdown)
            _sustained(key, period, sustained_decisions, sustained_ratio)
            if period.unattributable is not None and key.period in UNATTRIBUTABLE_PERIODS:
                unattributable.add({"period": key.period}, period.unattributable)

        view_decisions = _Family(
            "vectra_product_explanation_view_decisions",
            "Decisiones con la explicacion vista (ventana de 7 dias)",
        )
        view_ratio = _Family("vectra_product_explanation_view_ratio", "Tasa de consulta de la explicacion")
        view = metrics.explanation_view
        for channel, cell in view.cells.items():
            view_decisions.counts({"period": VIEW_PERIOD, "channel": channel}, cell)
            view_ratio.ratio({"period": VIEW_PERIOD, "channel": channel}, cell)
        view_ratio.ratio({"period": VIEW_PERIOD, "channel": ALL}, view.total)

        families = [
            north_decisions,
            north_ratio,
            north_breakdown,
            view_decisions,
            view_ratio,
            sustained_decisions,
            sustained_ratio,
            unattributable,
        ]
        out = [family.metric for family in families if family.metric.samples]

        def single(name: str, documentation: str, value: float) -> None:
            family = _Family(name, documentation)
            family.add({}, value)
            out.append(family.metric)

        single(
            "vectra_product_noise_days_below_floor",
            "Dias seguidos bajo el piso de consulta",
            metrics.noise_days_below_floor,
        )
        day = metrics.origination.get(
            yesterday(published.now)
        )  # P-4: ayer; sin casos estandar, no se emite (no 0)
        if day is not None:
            seconds = _Family("vectra_product_origination_seconds", "Tiempo de originacion de casos estandar")
            for (_percent, label), value in zip(QUANTILES, (day.p50, day.p80, day.p95), strict=True):
                seconds.add({"quantile": label, "standard": "true"}, value)
            out.append(seconds.metric)
            single(
                "vectra_product_origination_standard_under_target_ratio",
                "Casos estandar por debajo del target de originacion",
                day.under_target_ratio,
            )
        single("vectra_product_invalid_entries", "Entradas excluidas en 30 dias", metrics.invalid_entries)
        single(
            "vectra_product_metrics_degraded",
            "1 con mas del 1 % de entradas excluidas",
            int(metrics.degraded),
        )
        single(
            "vectra_product_metrics_last_success_timestamp",
            "Ultima lectura exitosa",
            _timestamp(published.last_success_at),
        )
        if published.last_full_recompute_at is not None:  # nunca 0: ausente hasta la primera pasada completa
            single(
                "vectra_product_last_full_recompute_timestamp",
                "Ultima pasada completa exitosa",
                _timestamp(published.last_full_recompute_at),
            )
        targets = _Family("vectra_product_target", "Targets y piso, para las lineas de referencia")
        for metric, value in _targets(published.params):
            targets.add({"metric": metric}, value)
        out.append(targets.metric)
        return out


def register(holder: Holder, registry: CollectorRegistry = REGISTRY) -> Collector:
    collector = Collector(holder)
    registry.register(collector)
    return collector
