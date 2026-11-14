"""La seccion `u11` y la evidencia `dashboard` (U12-T04, P-4; BR-U12-06; US-503, 504, 505): ningun paso del plan la define. Con `PromClient` lee **las mismas expresiones que los paneles** de `product.json`
(la prueba las compara con el archivo, por su titulo) y la alerta `ProductMetricsStale`.

`pasa` si las cuatro tienen valor y `ProductMetricsStale` no esta en `firing`. Una serie ausente es `falla` con su nombre, salvo antes de las 02:40 UTC del dia D + 1 mas el plazo de la pasada
(`product-metrics/src/vectra_product/config.py`: la pasada completa es a las 02:30 UTC con hasta 10 min de desfase), que es `no ejecutado`. Antes del dia D + 1 (el dia UTC en que termino `decisions`) la
seccion se niega con `no ejecutado` (`u11_antes_de_d_mas_1`). **No** verifica `RuidoExplicacion`: se verifica con `promtool` (BR-U12-06), no en kind; la evidencia lo dice.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any, Final

from vectra_verification import guard
from vectra_verification.clients.prom import ObsError, PromClient, QueryResult
from vectra_verification.guard import Environment
from vectra_verification.report import FALLA, NO_EJECUTADO, PASA
from vectra_verification.scenarios.outcome import Outcome

# Titulo del panel de `product-metrics/observability/dashboards/product.json` -> las expresiones de sus `targets`, tal cual.
PANELS: Final = {
    "North Star de ayer": (
        'vectra:product_north_star_ratio:dedup{period="day", channel="all", outcome="all", model_version_id="all"}',
    ),
    "Recomendaciones sostenidas (aproximación)": (
        'vectra:product_recommendation_sustained_ratio:dedup{period="30d", channel="all", outcome="all"}',
        'vectra:product_target:dedup{metric="sustained_ratio_month6"}',
    ),
    "Tasa de consulta de la explicación y piso F": (
        'vectra:product_explanation_view_ratio:dedup{period="7d", channel="all"}',
        'vectra:product_target:dedup{metric="noise_floor"}',
    ),
    "Días bajo el piso": ("vectra:product_noise_days_below_floor:dedup",),
}
STALE: Final = 'ALERTS{alertname="ProductMetricsStale", alertstate="firing"}'
PASS_AT: Final = time(2, 40)  # 02:30 UTC de la pasada mas hasta 10 min de desfase
PASS_WINDOW: Final = timedelta(minutes=10)
EXPECTED: Final = (
    "los cuatro paneles del dashboard Producto tienen valor y ProductMetricsStale no esta en firing"
)
NOT_VERIFIED: Final = "RuidoExplicacion no se verifica en kind: se verifica con promtool (BR-U12-06)"


def _no(
    code: str, obtained: str, readings: dict[str, Any], queries: list[QueryResult] | None = None
) -> Outcome:
    return Outcome(
        "dashboard",
        NO_EJECUTADO,
        EXPECTED,
        obtained,
        (code,),
        readings=readings,
        queries=tuple(queries or ()),
    )


def pass_deadline(decisions_finished_at: datetime, window: timedelta = PASS_WINDOW) -> datetime:
    """El instante desde el que una serie ausente ya es `falla`: las 02:40 UTC del dia D + 1, mas el plazo de la pasada."""
    day = decisions_finished_at.astimezone(UTC).date() + timedelta(days=1)
    return datetime.combine(day, PASS_AT, tzinfo=UTC) + window


def _has_value(result: QueryResult) -> bool:
    for item in result.result:
        try:
            value = float(item["value"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if value == value:  # no NaN
            return True
    return False


def u11(
    environment: Environment,
    prom: PromClient,
    now: datetime,
    decisions_finished_at: datetime | None,
    *,
    window: timedelta = PASS_WINDOW,
) -> Outcome:
    """La seccion `u11`. `guard.check_section` antes de la primera solicitud."""
    guard.check_section(environment, "u11")
    readings: dict[str, Any] = {"not_verified": NOT_VERIFIED}
    if decisions_finished_at is None:
        return _no("u11_decisions_no_corrio", "`decisions` no termino: no hay dia D", readings)
    if now.astimezone(UTC).date() <= decisions_finished_at.astimezone(UTC).date():
        return _no(
            "u11_antes_de_d_mas_1",
            "el dia UTC actual no es posterior al de `decisions`: la pasada completa de U11 es a las 02:30 UTC del dia D + 1",
            readings,
        )
    queries: list[QueryResult] = []
    missing: list[str] = []
    try:
        for title, expressions in PANELS.items():
            for expression in expressions:
                answer = prom.query(expression, now)
                queries.append(answer)
                readings[f"{title}: {expression}"] = "con valor" if _has_value(answer) else "ausente"
                if not _has_value(answer):
                    missing.append(f"{title} ({expression})")
        stale = prom.query(STALE, now)
        queries.append(stale)
    except ObsError as error:
        return _no("u11_prometheus_no_responde", f"Prometheus no responde: {error}", readings, queries)
    firing = bool(stale.result)
    readings["product_metrics_stale_firing"] = firing
    if missing and now < pass_deadline(decisions_finished_at, window):
        return _no(
            "u11_pasada_pendiente",
            "faltan series y la pasada de U11 aun no ha terminado: " + "; ".join(missing),
            readings,
            queries,
        )
    if missing or firing:
        codes = tuple(f"u11_serie_ausente:{name}" for name in missing) + (
            ("u11_product_metrics_stale_firing",) if firing else ()
        )
        what = ("series ausentes: " + "; ".join(missing)) if missing else ""
        what += ("; " if what and firing else "") + ("ProductMetricsStale en firing" if firing else "")
        return Outcome("dashboard", FALLA, EXPECTED, what, codes, readings=readings, queries=tuple(queries))
    return Outcome("dashboard", PASA, EXPECTED, EXPECTED, (), readings=readings, queries=tuple(queries))
