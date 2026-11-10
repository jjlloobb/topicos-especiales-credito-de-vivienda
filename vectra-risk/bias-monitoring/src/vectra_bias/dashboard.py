"""`get_disparity` (BR-U9-18; P-U9-03; US-307): el dashboard de disparidad de una version, con cache de 15 min.

Version: la que manda el BFF en `version`; si no llega, la de las recomendaciones mas recientes de la poblacion `modelo`
(`include_versions` de `daily:query`). bias no lee governance (X04). Ventana: `window` del filtro o `window_days` de la politica;
su inicio respeta BR-U9-08 con `vectra_bias.window` (la ultima `reactivar` de `GET /v1/monitoring/freezes`).

La disparidad la calcula `vectra_disparity` (supresion de celdas chicas, P-U9-04) con las funciones de `context`; este modulo no
construye ninguna celda. Solo la respuesta ya suprimida entra en la cache.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Final

from vectra_common import deps
from vectra_common.errors import DependencyUnavailable, NotFound
from vectra_contracts.models.monitoring import (
    DayRange,
    DisparityFilter,
    DisparityResult,
    DisparityView,
    MonitoringQuery,
    MonitoringRangeRequest,
)
from vectra_disparity import counts_from_marginals, quantize4

from vectra_bias import config
from vectra_bias.cache import SingleFlightCache
from vectra_bias.context import departure_rates, measure
from vectra_bias.registry_client import RegistryError, query_daily, read_freezes
from vectra_bias.window import Span, last_reactivation, version_ranges

DISCLAIMER: Final = "mide y alerta, no certifica"
MODEL: Final = "modelo"
HUMAN: Final = "humana"
DISCOVERY_ID: Final = "discovery"
Key = tuple[str | None, str | None, int]


def cache_key(filter_: DisparityFilter, policy: config.MonitoringPolicy) -> Key:
    """`(version, atributo, ventana)`. Sin version la llave lleva `None`; sin ventana, `window_days` de la politica."""
    return (filter_.version, filter_.attribute, filter_.window or policy.window_days)


def _only(result: DisparityResult, attribute: str) -> DisparityResult:
    """Deja un solo atributo; la agregada del modelo y su disparador pasan a ser los de ese atributo."""
    kept = [a for a in result.attributes if a.attribute == attribute]
    aggregate = kept[0].aggregate if kept else None
    return result.model_copy(
        update={
            "attributes": kept,
            "model_aggregate": aggregate,
            "trigger_attribute": attribute if aggregate is not None else None,
        }
    )


def _latest_version(versions: list) -> str | None:
    models = [v for v in versions if v.population == MODEL]
    return max(models, key=lambda v: (v.last_day, v.model_version_id)).model_version_id if models else None


async def compute(
    client: deps.DependencyClient,
    policy: config.MonitoringPolicy,
    filter_: DisparityFilter,
    now: datetime,
) -> DisparityView:
    """Lee el registro y calcula la vista. `DependencyUnavailable` si el registro falla (sin datos parciales)."""
    today = now.astimezone(UTC).date()
    window_days = filter_.window or policy.window_days
    nominal = Span(today - timedelta(days=window_days - 1), today)
    try:
        reactivated = last_reactivation(await read_freezes(client))
        discovery = await query_daily(
            client,
            MonitoringQuery(
                ranges=[
                    MonitoringRangeRequest(
                        range_id=DISCOVERY_ID,
                        population=MODEL,
                        from_day=nominal.from_day,
                        to_day=nominal.to_day,
                    )
                ],
                include_versions=True,
            ),
        )
        version = filter_.version or _latest_version(discovery.versions)
        if version is None:
            raise NotFound()
        first_days = [
            v.first_day for v in discovery.versions if v.model_version_id == version and v.population == MODEL
        ]
        first_day: date = min(first_days) if first_days else nominal.from_day
        ranges = version_ranges(today, window_days, first_day, reactivated.get(version))
        requests = [
            MonitoringRangeRequest(
                range_id=f"{population}",
                model_version_id=version,
                population=population,  # type: ignore[arg-type]
                from_day=span.from_day,
                to_day=span.to_day,
            )
            for population, span in ((MODEL, ranges.after), (HUMAN, ranges.human_after))
            if span is not None
        ]
        window = (
            await query_daily(client, MonitoringQuery(ranges=requests, include_versions=False))
            if requests
            else None
        )
    except RegistryError as error:
        raise DependencyUnavailable() from error
    span = ranges.after or nominal
    human_span = ranges.human_after or nominal
    marginals = {p: [c for c in (window.counts if window else []) if c.range_id == p] for p in (MODEL, HUMAN)}
    if filter_.attribute is not None:
        marginals = {
            p: [c for c in rows if c.attribute == filter_.attribute] for p, rows in marginals.items()
        }
    model = measure(
        counts_from_marginals(marginals[MODEL]), policy.n_min, MODEL, version, span.from_day, span.to_day
    )
    human = measure(
        counts_from_marginals(marginals[HUMAN]),
        policy.n_min,
        HUMAN,
        version,
        human_span.from_day,
        human_span.to_day,
        departure_rates(marginals[HUMAN], policy.n_min),
    )
    if filter_.attribute is not None:
        model, human = _only(model, filter_.attribute), _only(human, filter_.attribute)
    invalid = sum(t.invalid_entries for t in (window.totals if window else []))
    return DisparityView(
        model_version_id=version,
        window=DayRange(from_day=span.from_day, to_day=span.to_day),
        computed_at=now,
        model=model,
        human=human,
        threshold_pp=str(quantize4(policy.threshold_pp)),
        n_min=policy.n_min,
        window_days=policy.window_days,
        schedule=policy.schedule,
        stale_after_s=policy.stale_after_s,
        invalid_entries=invalid,
        disclaimer=DISCLAIMER,
    )


async def get_disparity(
    client: deps.DependencyClient,
    policy: config.MonitoringPolicy,
    cache: SingleFlightCache,
    filter_: DisparityFilter,
    clock: Callable[[], datetime],
) -> DisparityView:
    """La vista de la cache o, si no esta, la que calcula una sola consulta (single-flight)."""
    key = cache_key(filter_, policy)
    return await cache.get(key, lambda: compute(client, policy, filter_, clock()))


__all__ = ["DISCLAIMER", "cache_key", "compute", "get_disparity"]
