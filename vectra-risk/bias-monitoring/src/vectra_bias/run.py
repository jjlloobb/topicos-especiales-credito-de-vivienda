"""Una corrida del CronJob (BR-U9-08..14, 20; P-U9-01, P-U9-07; NFR-U9-01, NFR-U9-20 y NFR-U9-21). `python -m vectra_bias.run`.

Trazabilidad: P-U9-01 (corrida todo o nada con todas las versiones), P-U9-07 (escenarios E1, E3, E4, E5 y E7, en
`tests/integration/test_run.py`), NFR-U9-01 (duracion de una corrida), NFR-U9-20 (escenarios de resiliencia) y NFR-U9-21
(nunca congela con datos parciales ni con conteos atrasados; `tests/property/test_run_machine.py`).

Orden de P-U9-01: token -> lectura (atraso del agregador e invalidas) -> calculo de **todas** las versiones evaluadas ->
`freeze` en **todas** las que cumplan la regla (R4 sobre todos los atributos, BR-U9-11), aunque falle una -> publicacion.
Todo o nada sobre los datos: nunca congela con una lectura parcial ni con invalidas por encima del 1 %. Solo este modulo
llama a `freeze`, y nunca para la poblacion `humana`.

Entorno (lo fija el chart, Paso 12): `VECTRA_REGISTRY_URL`, `VECTRA_GOVERNANCE_URL`, `VECTRA_PUSHGATEWAY_URL`,
`VECTRA_TOKEN_URL`, `VECTRA_ASSERTION_AUDIENCE`, `VECTRA_CLIENT_ID`, `VECTRA_CLIENT_KEY_PATH` (y `VECTRA_CLIENT_KEY_ID`), y `VECTRA_POLICY_PATH` si el
`ConfigMap` no esta en la ruta por omision de `config.POLICY_PATH`.

Codigo de salida: 0 corrida completa; 1 corrida fallida (lectura, libreria, invalidas, agregador atrasado, token o `freeze`);
2 el Pushgateway no acepto la publicacion (BR-U9-20; prevalece sobre 0 y 1: el `freeze` ya aplicado no cambia).
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from vectra_common import process
from vectra_common.deps import DependencyClient, TokenSource
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_common.logging import configure as configure_logging
from vectra_common.logging import log_access
from vectra_common.service_token import provider_from_env
from vectra_contracts.catalog import Scope
from vectra_contracts.models.monitoring import (
    AffectedVolume,
    DayRange,
    FreezeContext,
    MonitoringQuery,
    MonitoringRangeRequest,
    MonitoringWindow,
)
from vectra_disparity import CountTable, counts_from_marginals

from vectra_bias import config
from vectra_bias.context import build_context_package, departure_rates, measure
from vectra_bias.freeze_client import FreezeOutcome, Sleep, freeze
from vectra_bias.freeze_rule import HUMAN, MODEL, attribute_limits, decide
from vectra_bias.publish import PopulationReport, PublishResult, RunReport, VersionReport, publish
from vectra_bias.registry_client import RegistryError, plan_queries, query_daily, read_freezes
from vectra_bias.window import Span, VersionRanges, evaluated_versions, last_reactivation, version_ranges

SERVICE: Final = "bias-monitoring-job"
REGISTRY_AUDIENCE: Final = "decision-registry-service"
GOVERNANCE_AUDIENCE: Final = "governance-service"
REGISTRY_SCOPE: Final = Scope.REGISTRY_READ_MONITORING.value
FREEZE_SCOPE: Final = Scope.GOVERNANCE_FREEZE.value
DISCOVERY_ID: Final = "discovery"
EXIT_OK, EXIT_FAILED, EXIT_PUSH = 0, 1, 2

READING, LIBRARY, INVALID, LAGGING, TOKEN, FREEZE = (
    "lectura", "libreria", "invalidas", "agregador_atrasado", "token", "freeze"
)  # fmt: skip


@dataclass
class Deps:
    """Los clientes y el reloj de una corrida; las pruebas inyectan dobles y un `sleep` virtual."""

    registry: DependencyClient
    governance: DependencyClient
    pushgateway: DependencyClient
    policy: config.MonitoringPolicy
    sleep: Sleep = asyncio.sleep
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)  # noqa: E731


@dataclass
class Outcome:
    report: RunReport
    published: PublishResult | None = None
    seqs: list[int] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        if self.published is not None and not self.published.ok:
            return EXIT_PUSH
        return EXIT_OK if self.report.complete else EXIT_FAILED


class RunFailure(Exception):
    def __init__(self, reason: str, invalid: tuple[int, int] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.invalid = invalid


@dataclass
class Evaluated:
    version: str
    ranges: VersionRanges
    report: VersionReport
    package: FreezeContext | None = None


def _range_id(version: str, kind: str) -> str:
    return f"{version}:{kind}"


def _requests(version: str, ranges: VersionRanges) -> list[MonitoringRangeRequest]:
    wanted = (
        ("antes", MODEL, ranges.before),
        ("despues", MODEL, ranges.after),
        ("7d", MODEL, ranges.last_7_days),
        ("humana", HUMAN, ranges.human_after),
    )
    return [
        MonitoringRangeRequest(
            range_id=_range_id(version, kind),
            model_version_id=version,
            population=population,  # type: ignore[arg-type]
            from_day=span.from_day,
            to_day=span.to_day,
        )
        for kind, population, span in wanted
        if span is not None
    ]


async def acquire_tokens(sources: Sequence[TokenSource | None]) -> None:
    """Paso 1: un token por audiencia, con `TOKEN_ATTEMPTS` intentos (1 reintento inmediato). Sin token: `reason=token` (E7)."""
    for source in sources:
        if source is None:
            continue
        for attempt in range(config.TOKEN_ATTEMPTS):
            try:
                await source.token()
                break
            except (DependencyUnavailable, DependencyTimeout):
                if attempt == config.TOKEN_ATTEMPTS - 1:
                    raise RunFailure(TOKEN) from None


@dataclass
class Reading:
    freezes_reactivated: dict[str, datetime]
    versions: list[str]
    first_day: dict[str, date]
    windows: list[MonitoringWindow]
    totals: dict[str, tuple[int, int]]
    by_range: dict[str, list[Any]]


async def read(deps: Deps, today: date) -> Reading:
    """Paso 2: congelamientos, `versions` y los rangos por version, en solicitudes de <= 12. La **primera** solicitud (la de
    `versions`, que siempre existe) lleva `unattributable_range`: las decisiones sin recomendacion cuentan una sola vez, aunque
    despues haya varias solicitudes de rangos, y tambien sin versiones evaluadas. Una lectura incompleta es `RegistryError`."""
    policy = deps.policy
    reactivated = last_reactivation(await read_freezes(deps.registry))
    horizon = today - timedelta(days=policy.window_days - 1 + 7)
    window = DayRange(from_day=today - timedelta(days=policy.window_days - 1), to_day=today)
    discovery = MonitoringQuery(
        ranges=[
            MonitoringRangeRequest(range_id=DISCOVERY_ID, population="modelo", from_day=horizon, to_day=today)
        ],
        include_versions=True,
        unattributable_range=window,
    )
    windows = [await query_daily(deps.registry, discovery)]
    versions = evaluated_versions(windows[0].versions, today)
    first_day = {
        v: min(w.first_day for w in windows[0].versions if w.model_version_id == v) for v in versions
    }
    requests: list[MonitoringRangeRequest] = []
    for v in versions:
        requests += _requests(v, version_ranges(today, policy.window_days, first_day[v], reactivated.get(v)))
    for query in plan_queries(requests, None):
        windows.append(await query_daily(deps.registry, query))
    totals = {t.range_id: (t.total_entries, t.invalid_entries) for w in windows for t in w.totals}
    if not {r.range_id for r in requests} <= set(totals):
        raise RegistryError("incomplete")
    by_range: dict[str, list[Any]] = defaultdict(list)
    for w in windows:
        for c in w.counts:
            by_range[c.range_id].append(c)
    return Reading(reactivated, versions, first_day, windows, totals, by_range)


def check_reading(reading: Reading, policy: config.MonitoringPolicy) -> tuple[int, int]:
    """Atraso del agregador e invalidas (BR-U9-09, 10). Devuelve `(invalidas, total)` y falla si corresponde."""
    # Una sola vez: bias envia `unattributable_range` solo en la primera solicitud (windows[0], la de `versions`).
    unattributable = reading.windows[0].unattributable_invalid
    invalid = total = unattributable
    for v in reading.versions:
        for kind in ("despues", "humana"):
            t = reading.totals.get(_range_id(v, kind))
            if t is not None:
                total += t[0]
                invalid += t[1]
    counts = (invalid, total)
    if max(w.lag_seconds for w in reading.windows) > config.AGGREGATOR_MAX_LAG_S:
        raise RunFailure(LAGGING, counts)
    if total and Decimal(invalid) > Decimal(total) * config.INVALID_FAIL_RATIO:
        raise RunFailure(INVALID, counts)
    return counts


def _tables(reading: Reading, version: str, kind: str, span: Span | None) -> dict[str, CountTable]:
    return (
        counts_from_marginals(reading.by_range.get(_range_id(version, kind), []))
        if span
        else counts_from_marginals([])
    )


def _affected(counts: dict[str, CountTable]) -> AffectedVolume:
    """Recomendaciones de la version en la ventana y cuantas fueron `favorable`: cada entrada suma una vez en cada atributo."""
    sums = [(sum(c.total for c in t.cells), sum(c.favorable for c in t.cells)) for t in counts.values()]
    total, favorable = max(sums, default=(0, 0))
    return AffectedVolume(total=total, favorable=favorable)


def evaluate(reading: Reading, version: str, today: date, deps: Deps, now: datetime) -> Evaluated:
    """Paso 3 de una version: el modelo y las decisiones humanas con la libreria; el paquete si la regla manda congelar."""
    policy = deps.policy
    ranges = version_ranges(
        today, policy.window_days, reading.first_day[version], reading.freezes_reactivated.get(version)
    )
    nominal = Span(today - timedelta(days=policy.window_days - 1), today)
    after_span = ranges.after or nominal

    def result(population: str, counts: dict[str, CountTable], span: Span, departure: Any = None):
        return measure(counts, policy.n_min, population, version, span.from_day, span.to_day, departure)

    model_counts = _tables(reading, version, "despues", ranges.after)
    model_after = result(MODEL, model_counts, after_span)
    model_limits = attribute_limits(model_counts, policy.n_min)
    model_decision = decide(MODEL, policy.threshold_pp, model_limits)

    human_marginals = reading.by_range.get(_range_id(version, "humana"), []) if ranges.human_after else []
    human_counts = counts_from_marginals(human_marginals)
    human_span = ranges.human_after or nominal
    human_result = result(HUMAN, human_counts, human_span, departure_rates(human_marginals, policy.n_min))
    human_limits = attribute_limits(human_counts, policy.n_min)
    human_decision = decide(HUMAN, policy.threshold_pp, human_limits)

    package = None
    if model_decision.freeze:
        before = ranges.before
        recent = ranges.last_7_days
        package = build_context_package(
            model_version_id=version,
            computed_at=now,
            threshold_pp=policy.threshold_pp,
            n_min=policy.n_min,
            window_days=policy.window_days,
            schedule=policy.schedule,
            stale_after_s=policy.stale_after_s,
            window_start=ranges.window_start,
            before=None
            if before is None
            else result(MODEL, _tables(reading, version, "antes", before), before),
            after=model_after,
            last_7_days=None
            if recent is None
            else result(MODEL, _tables(reading, version, "7d", recent), recent),
            decision=model_decision,
            affected_volume=_affected(model_counts),
        )
    report = VersionReport(
        version,
        PopulationReport(model_after, model_limits, model_decision),
        PopulationReport(human_result, human_limits, human_decision),
    )
    return Evaluated(version, ranges, report, package)


async def run_once(deps: Deps) -> Outcome:
    """Una corrida completa. No lanza: toda falla queda en `Outcome.report`."""
    now = deps.clock()
    today = now.astimezone(UTC).date()
    invalid: tuple[int, int] | None = None
    evaluated: list[Evaluated] = []
    reason: str | None = None
    seqs: list[int] = []
    try:
        await acquire_tokens([deps.registry.token_source, deps.governance.token_source])
        try:
            reading = await read(deps, today)
            seqs = sorted({s for w in reading.windows for s in w.invalid_seqs})
            invalid = check_reading(reading, deps.policy)
        except RunFailure as failure:
            invalid = failure.invalid
            raise
        except Exception:  # noqa: BLE001 - lectura fallida o incompleta (RegistryError) o respuesta inesperada
            raise RunFailure(READING) from None
        try:
            evaluated = [evaluate(reading, v, today, deps, now) for v in reading.versions]
        except Exception:  # noqa: BLE001 - cualquier falla de la libreria o del paquete: corrida fallida, sin `freeze`
            raise RunFailure(LIBRARY, invalid) from None
    except RunFailure as failure:
        reason = failure.reason
        invalid = invalid or failure.invalid
    done: list[VersionReport] = []
    if reason is None:
        done = await _freeze_all(deps, evaluated)
        if any(v.freeze is not None and not v.freeze.ok for v in done):
            reason = FREEZE
    report = RunReport(
        started_at=now,
        finished_at=deps.clock(),
        complete=reason is None,
        failure_reason=reason,
        calculated=reason is None or reason == FREEZE,
        versions=tuple(done),
        invalid_entries=None if invalid is None else invalid[0],
        total_entries=None if invalid is None else invalid[1],
    )
    return Outcome(report, await publish(deps.pushgateway, report), seqs)


async def _freeze_all(deps: Deps, evaluated: list[Evaluated]) -> list[VersionReport]:
    """Paso 4: `freeze` en cada version del modelo que cumple la regla, aunque falle otra. La poblacion `humana` nunca llama."""
    done: list[VersionReport] = []
    for item in evaluated:
        outcome: FreezeOutcome | None = None
        if item.package is not None:
            outcome = await freeze(deps.governance, item.version, item.package, deps.sleep)
        done.append(VersionReport(item.version, item.report.model, item.report.human, outcome))
    return done


def log_outcome(outcome: Outcome, duration_ms: int) -> None:
    """Logs de la corrida solo con campos de `LOG_RECORD_FIELDS`; las invalidas, solo con `seq` (BR-U9-09; NFR-U9-33)."""
    for seq in outcome.seqs:
        log_access(seq=seq)  # las invalidas, solo con `seq` (BR-U9-09; NFR-U9-33)
    for version in outcome.report.versions:
        if version.freeze is not None:
            fields: dict[str, Any] = {
                "model_version_id": version.model_version_id,
                "status": version.freeze.outcome,
                "attempt": version.freeze.attempts,
            }
            if version.freeze.reason:
                fields["error_code"] = version.freeze.reason
            log_access(**fields)
    for error in () if outcome.published is None else outcome.published.errors:
        log_access(error_code="pushgateway", http_method=error.split(":", 1)[0])
    fields = {"status": "completa" if outcome.report.complete else "fallida", "duration_ms": duration_ms}
    if outcome.report.failure_reason:
        fields["error_code"] = outcome.report.failure_reason
    log_access(**fields)


def build_deps(env: dict[str, str]) -> Deps:
    """Clientes del CronJob: `DependencyClient(breaker="disabled")` tras `process.init("batch")` (P-U9-02), con el token de
    `bias-monitoring-job` para el registro y para governance. El Pushgateway va sin token."""
    policy = config.load_policy(Path(env.get("VECTRA_POLICY_PATH", str(config.POLICY_PATH))))
    registry_token = provider_from_env(REGISTRY_AUDIENCE, (REGISTRY_SCOPE,))
    governance_token = provider_from_env(GOVERNANCE_AUDIENCE, (FREEZE_SCOPE,))
    return Deps(
        registry=DependencyClient(
            "registry", env["VECTRA_REGISTRY_URL"], "disabled", 4, token_source=registry_token
        ),
        governance=DependencyClient(
            "governance", env["VECTRA_GOVERNANCE_URL"], "disabled", 2, token_source=governance_token
        ),
        pushgateway=DependencyClient("pushgateway", env["VECTRA_PUSHGATEWAY_URL"], "disabled", 2),
        policy=policy,
    )


async def _main(deps: Deps) -> int:
    began = time.monotonic()
    try:
        outcome = await run_once(deps)
    finally:
        for client in (deps.registry, deps.governance, deps.pushgateway):
            await client.aclose()
    log_outcome(outcome, int((time.monotonic() - began) * 1000))
    return outcome.exit_code


def main(env: dict[str, str] | None = None) -> int:
    process.init("batch")
    configure_logging(SERVICE)
    try:
        deps = build_deps(dict(os.environ if env is None else env))
    except (config.PolicyError, KeyError, OSError) as error:
        log_access(error_code="configuracion", exception_type=type(error).__name__)
        return EXIT_FAILED
    return asyncio.run(_main(deps))


if __name__ == "__main__":
    sys.exit(main())
