"""RT-5 / D3 (U12-T03, Paso 8; BR-U12-04; INF-U12-02; NFR-U12-50): el core bancario es de solo lectura. Oraculo del Job `rt5-demo-<runId>` de U8, de su log y de Prometheus.

Lectura (`read`, con `K8sRead` y `PromClient`) y juicio (`judge`, puro) van separados. El oraculo no consulta «ahora»: ancla las consultas a `t0 = status.startTime` y
`t1 = status.completionTime` del Job con `query_range` (`step = 15 s`, expresiones instantaneas validas) y calcula en Python la presencia y el maximo de los puntos. Las expresiones son las del plan, literales.

Lo que se lee de verdad (verificado sobre el codigo, ver `code/scenarios.md`): el Job sale con 0 ante **cualquier** 403 (`rt5-demo-job.yaml`), asi que un Job `Complete` no prueba nada: el log es
`rt5-demo: POST <url> -> <codigo> l5d-proxy-error: <valor>`, con `None` si la cabecera no viene (el 403 es entonces de la aplicacion). Buscar el texto `l5d-proxy-error` no sirve: la linea lo trae siempre.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from vectra_verification import guard
from vectra_verification.clients.k8s_read import K8sError, K8sRead
from vectra_verification.clients.prom import ObsError, PromClient, QueryResult
from vectra_verification.clock import Clock
from vectra_verification.guard import Environment
from vectra_verification.report import FALLA, NO_EJECUTADO, PASA
from vectra_verification.scenarios.outcome import Outcome
from vectra_verification.scenarios.waits import poll

NAMESPACE: Final = "vectra-app"
JOB_PREFIX: Final = "rt5-demo-"
RUN_ID: Final = re.compile(r"^[0-9]{8}-[0-9]{4}$")
STEP: Final = 15.0
POLL_SECONDS: Final = 15.0
WINDOW_AFTER: Final = timedelta(minutes=15)
ACTIVE_DEADLINE: Final = 300.0  # `rt5.activeDeadlineSeconds` de `case-management/chart/values.yaml`
JOB_MARGIN: Final = 60.0
MAX_POINTS: Final = 10_000  # Prometheus rechaza mas de 11 000 puntos por serie en `query_range`

ALERT: Final = 'ALERTS{alertname="CoreWriteAttempt", alertstate="firing"}'
DENY_LABELS: Final = 'namespace="vectra-mock", route_name="core-mock-catch-all"'
DENY_FAMILY: Final = "inbound_http_authz_deny_total"
DENY: Final = f"sum({DENY_FAMILY}{{{DENY_LABELS}}})"
COUNTER_NAME: Final = "vectra_core_write_attempts_total"
COUNTER: Final = f"sum({COUNTER_NAME})"
RETENTION: Final = "prometheus_tsdb_lowest_timestamp_seconds"
FAMILY_COUNT: Final = f"count({DENY_FAMILY})"
FAMILY_LABELS: Final = f"count by (namespace, route_name) ({DENY_FAMILY})"
SERIES_FULL: Final = f"{DENY_FAMILY}{{{DENY_LABELS}}}"

LOG_LINE: Final = re.compile(r"rt5-demo: POST (?P<url>\S+) -> (?P<code>\d{3}) l5d-proxy-error: (?P<value>.*)")
NO_RESPONSE: Final = "rt5-demo: sin respuesta"

_EXPECTED: Final = (
    "403 de Linkerd (l5d-proxy-error con valor) en el log del Job; CoreWriteAttempt en firing; "
    f"{DENY_FAMILY} con maximo >= 1; {COUNTER_NAME} sin superar 0"
)
Point = tuple[float, float]
Series = dict[str, list[Point]]


@dataclass(frozen=True)
class LogLine:
    """El analisis del log del Job. `kind`: `proxy` (403 con `l5d-proxy-error` de Linkerd), `application` (403 con `None`), `other_code`, `no_response` o `absent`."""

    kind: str
    code: int | None = None
    value: str | None = None


def parse_log(text: str) -> LogLine:
    found = None
    for line in text.splitlines():
        match = LOG_LINE.search(line)
        if match:
            found = match
    if found is None:
        return LogLine("no_response" if NO_RESPONSE in text else "absent")
    code, value = int(found.group("code")), found.group("value").strip()
    if code != 403:
        return LogLine("other_code", code, value)
    return LogLine("application" if value in ("", "None") else "proxy", code, value)


@dataclass(frozen=True)
class JobState:
    """Lo que el oraculo lee del Job: nombre, tiempos, contadores y condiciones (`batch/v1`)."""

    name: str
    start: datetime | None
    completion: datetime | None
    succeeded: int
    failed: int
    conditions: tuple[str, ...]  # los tipos con estado `True`


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def parse_job(document: str) -> JobState:
    body = json.loads(document)
    status = body.get("status") or {}
    return JobState(
        name=str((body.get("metadata") or {}).get("name", "")),
        start=_time(status.get("startTime")),
        completion=_time(status.get("completionTime")),
        succeeded=int(status.get("succeeded") or 0),
        failed=int(status.get("failed") or 0),
        conditions=tuple(
            str(c.get("type")) for c in status.get("conditions") or [] if c.get("status") == "True"
        ),
    )


@dataclass
class Readings:
    """Todo lo que `judge` necesita. `None` en un campo = no se pudo leer (con su codigo en `errors`)."""

    job: JobState | None = None
    job_error: str | None = None  # `rt5_job_inexistente`, `rt5_k8s_forbidden` o `rt5_k8s_no_responde`
    job_active_timeout: bool = False
    log: LogLine | None = None
    log_error: str | None = None
    alert: Series = field(default_factory=dict)
    deny: Series = field(default_factory=dict)
    counter: Series = field(default_factory=dict)
    lowest_timestamp: float | None = None
    family_count: float | None = None
    label_pairs: tuple[tuple[str, str], ...] = ()
    prom_error: str | None = None
    queries: list[QueryResult] = field(default_factory=list)


def _points(series: Series) -> list[float]:
    return [v for values in series.values() for _, v in values]


def _max(series: Series) -> float | None:
    values = _points(series)
    return max(values) if values else None


def judge(run_id: str, started_at: datetime, readings: Readings) -> Outcome:
    """Puro: el resultado de RT-5 con lo leido. `falla` = el sistema respondio y no cumplio; `no ejecutado` = faltaba un prerrequisito."""
    expected = _EXPECTED
    queries = tuple(readings.queries)
    log_text = readings.log.kind if readings.log else "sin log"
    base = {"run_id": run_id, "log": log_text}

    def verdict(
        result: str, missing: Sequence[str], obtained: str, extra: Mapping[str, Any] | None = None
    ) -> Outcome:
        return _make(result, missing, expected, obtained, queries, {**base, **(extra or {})})

    job = readings.job
    if readings.job_error:
        return verdict(NO_EJECUTADO, [readings.job_error], readings.job_error)
    assert job is not None
    if job.name != f"{JOB_PREFIX}{run_id}":
        return verdict(NO_EJECUTADO, ["rt5_job_otro_runid"], f"job={job.name}")
    failed = job.failed >= 1 or "Failed" in job.conditions
    if failed:
        if job.start is None or job.start < started_at:
            return verdict(NO_EJECUTADO, ["rt5_job_anterior_al_inicio"], f"startTime={job.start}")
        line = readings.log
        return verdict(
            FALLA,
            ["rt5_job_fallido"],
            f"Job fallido (failed={job.failed}); log={line.kind if line else 'sin log'} codigo={line.code if line else None}",
            {"failed": job.failed},
        )
    if job.completion is None:
        code = "rt5_job_no_termina" if readings.job_active_timeout else "rt5_job_sin_completion"
        return verdict(NO_EJECUTADO, [code], "Job sin completionTime")
    if job.completion <= started_at:
        return verdict(
            NO_EJECUTADO, ["rt5_job_anterior_al_inicio"], f"completionTime={job.completion.isoformat()}"
        )
    if readings.log_error:
        return verdict(NO_EJECUTADO, [readings.log_error], readings.log_error)
    if readings.prom_error:
        return verdict(NO_EJECUTADO, [readings.prom_error], readings.prom_error)
    t0 = job.start or job.completion
    lowest = readings.lowest_timestamp
    if lowest is None:
        return verdict(NO_EJECUTADO, ["rt5_retencion_sin_dato"], f"sin {RETENTION}")
    if lowest > t0.timestamp():
        return verdict(
            NO_EJECUTADO,
            ["rt5_retencion_no_cubre_t0"],
            f"{RETENTION}={datetime.fromtimestamp(lowest, UTC).isoformat()} > t0={t0.isoformat()}",
        )
    missing: list[str] = []
    notes: list[str] = []
    line = readings.log
    assert line is not None
    if line.kind == "application":
        missing.append("rt5_403_de_la_aplicacion")
        notes.append("403 con l5d-proxy-error: None: Linkerd dejo pasar la llamada y respondio la aplicacion")
    elif line.kind == "other_code":
        missing.append("rt5_log_codigo_distinto_de_403")
        notes.append(f"el log trae el codigo {line.code}")
    elif line.kind in ("no_response", "absent"):
        missing.append("rt5_log_sin_linea" if line.kind == "absent" else "rt5_log_sin_respuesta")
        notes.append(f"el log no trae la linea del Job ({line.kind})")
    deny_max = _max(readings.deny)
    alert_present = any(readings.alert.values())
    if deny_max is None or deny_max < 1:
        missing.append(
            "rt5_serie_denegaciones_ausente" if deny_max is None else "rt5_serie_denegaciones_menor_que_1"
        )
        notes.append(_deny_message(readings, deny_max))
    if not alert_present:
        missing.append("rt5_alerta_core_write_attempt_ausente")
        notes.append(_alert_message(readings, deny_max))
    counter_max = _max(readings.counter)
    if counter_max is None:
        missing.append("rt5_serie_contador_del_mock_ausente")
        notes.append(f"no hay ningun punto de {COUNTER_NAME} desde started_at: no se puede afirmar que sea 0")
    elif counter_max > 0:
        missing.append("rt5_contador_del_mock_mayor_que_0")
        notes.append(f"{COUNTER_NAME} llego a {counter_max:g}: el mock recibio una escritura")
    extra = {
        "log_code": line.code,
        "log_proxy_error_present": line.kind == "proxy",
        "alert_points": sum(len(v) for v in readings.alert.values()),
        "deny_max": deny_max,
        "counter_max": counter_max,
        "t0": t0.isoformat(),
        "t1": job.completion.isoformat(),
    }
    if missing:
        return verdict(FALLA, missing, " | ".join(notes), extra)
    return verdict(PASA, [], expected, extra)


def _make(
    result: str,
    missing: Sequence[str],
    expected: str,
    obtained: str,
    queries: tuple[QueryResult, ...],
    readings: Mapping[str, Any],
) -> Outcome:
    return Outcome(
        "RT-5",
        result,  # type: ignore[arg-type]
        expected,
        expected if result == PASA else obtained,
        tuple(missing),
        (),
        queries,
        dict(readings),
    )


def _deny_message(readings: Readings, deny_max: float | None) -> str:
    if deny_max is not None:
        return f"la serie {SERIES_FULL} llego a {deny_max:g} y se esperaba >= 1"
    full = f"la serie {SERIES_FULL} no tiene puntos en la ventana [t0, t1 + 15 min]"
    if readings.family_count is None or readings.family_count == 0:
        return f"{full}; Prometheus no tiene ninguna serie {DENY_FAMILY}: nadie raspa el proxy de Linkerd de vectra-mock (U01-T09)"
    pairs = (
        ", ".join(f'namespace="{n}", route_name="{r}"' for n, r in readings.label_pairs)
        or "(sin esas etiquetas)"
    )
    return f"{full}; la familia existe con otras etiquetas: {pairs}"


def _alert_message(readings: Readings, deny_max: float | None) -> str:
    base = 'la alerta CoreWriteAttempt (alertstate="firing") no tiene ningun punto en la ventana [t0, t1 + 15 min]'
    if deny_max is None:
        return f"{base}; causa probable: la alerta depende de {DENY_FAMILY}, que tampoco tiene puntos"
    return base


# --- lectura -----------------------------------------------------------------------------------------------------------------


def _matrix(result: QueryResult) -> Series:
    series: Series = {}
    for item in result.result:
        key = json.dumps(item.get("metric", {}), sort_keys=True)
        series.setdefault(key, []).extend((float(ts), float(val)) for ts, val in item.get("values", []))
    return series


def ranged(
    prom: PromClient, expression: str, start: datetime, end: datetime, step: float = STEP
) -> tuple[Series, QueryResult]:
    """`query_range` partida en tramos de a lo sumo `MAX_POINTS` puntos si la ventana es mas larga (Prometheus rechaza mas de 11 000); une los puntos."""
    span = timedelta(seconds=step * (MAX_POINTS - 1))
    merged: Series = {}
    cursor = start
    last: QueryResult | None = None
    while True:
        chunk_end = min(end, cursor + span)
        last = prom.query_range(expression, cursor, chunk_end, step)
        for key, points in _matrix(last).items():
            known = merged.setdefault(key, [])
            seen = {t for t, _ in known}
            known.extend(p for p in points if p[0] not in seen)
        if chunk_end >= end:
            break
        cursor = chunk_end + timedelta(seconds=step)
        if (
            cursor > end
        ):  # lo que sobra es menor que `step`: no hay otro punto que pedir (Prometheus real responde `bad_data` si `start > end`)
            break
    assert last is not None
    return merged, QueryResult(
        expression,
        start,
        end,
        step,
        last.result_type,
        [{"metric": json.loads(k), "values": v} for k, v in merged.items()],
    )


def _scalar(result: QueryResult) -> float | None:
    for item in result.result:
        value = item.get("value")
        if value:
            return float(value[1])
    return None


def read(
    k8s: K8sRead,
    prom: PromClient,
    clock: Clock,
    run_id: str,
    started_at: datetime,
    *,
    environment: Environment,
    after_job: timedelta = WINDOW_AFTER,
) -> Readings:
    """Lee el Job, su log y Prometheus (con el reloj inyectado). No juzga."""
    guard.check_section(environment, "rt5")
    readings = Readings()
    name = f"{JOB_PREFIX}{run_id}"
    waited = poll(
        clock,
        lambda: _job_done(k8s, name, readings),
        interval=POLL_SECONDS,
        timeout=ACTIVE_DEADLINE + JOB_MARGIN,
    )
    if readings.job_error:
        return readings
    job = readings.job
    assert job is not None
    if not waited.met:
        readings.job_active_timeout = True
        return readings
    if job.name != name or (job.completion is not None and job.completion <= started_at):
        return readings
    try:
        pods = json.loads(k8s.get("pods", NAMESPACE, selector=f"job-name={name}")).get("items", [])
        if not pods:
            readings.log_error = "rt5_pod_inexistente"
        else:
            pod = sorted(str(p["metadata"]["name"]) for p in pods)[-1]
            readings.log = parse_log(k8s.logs(pod, NAMESPACE))
    except (K8sError, ValueError, KeyError, TypeError) as error:
        readings.log_error = _k8s_code(error, "rt5_log")
    if job.failed >= 1 or "Failed" in job.conditions or job.completion is None:
        return readings
    t0, t1 = job.start or job.completion, job.completion
    try:
        _read_prometheus(prom, clock, readings, t0, t1, started_at, after_job)
    except ObsError:
        readings.prom_error = "rt5_prometheus_no_responde"
    return readings


def _k8s_code(error: Exception, prefix: str) -> str:
    text = str(error).lower()
    if "forbidden" in text:
        return f"{prefix}_k8s_forbidden" if prefix != "rt5_job" else "rt5_k8s_forbidden"
    return f"{prefix}_no_leido"


def _job_done(k8s: K8sRead, name: str, readings: Readings) -> tuple[bool, None]:
    try:
        readings.job = parse_job(k8s.get(f"job/{name}", NAMESPACE))
    except K8sError as error:
        text = str(error).lower()
        if "notfound" in text or "not found" in text:
            readings.job_error = "rt5_job_inexistente"
        elif "forbidden" in text:
            readings.job_error = "rt5_k8s_forbidden"
        else:
            readings.job_error = "rt5_k8s_no_responde"
        return True, None
    except (ValueError, TypeError, AttributeError):
        readings.job_error = "rt5_k8s_no_responde"
        return True, None
    job = readings.job
    return job.completion is not None or job.failed >= 1 or "Failed" in job.conditions, None


def _read_prometheus(
    prom: PromClient,
    clock: Clock,
    readings: Readings,
    t0: datetime,
    t1: datetime,
    started_at: datetime,
    after_job: timedelta,
) -> None:
    window_end = t1 + after_job

    def sample() -> tuple[bool, None]:
        readings.queries = []
        readings.alert, q_alert = ranged(prom, ALERT, t0, window_end)
        readings.deny, q_deny = ranged(prom, DENY, t0, window_end)
        readings.queries += [q_alert, q_deny]
        return any(readings.alert.values()) and (_max(readings.deny) or 0) >= 1, None

    timeout = max(0.0, (window_end - clock.now()).total_seconds())
    poll(clock, sample, interval=POLL_SECONDS, timeout=timeout)
    now = clock.now()
    readings.counter, q_counter = ranged(prom, COUNTER, started_at, max(now, started_at))
    retention = prom.query(RETENTION, now)
    readings.lowest_timestamp = _scalar(retention)
    readings.queries += [q_counter, retention]
    if _max(readings.deny) is None:
        family = prom.query(FAMILY_COUNT, now)
        readings.family_count = _scalar(family) or 0.0
        readings.queries.append(family)
        if readings.family_count:
            labels = prom.query(FAMILY_LABELS, now)
            readings.label_pairs = tuple(
                sorted(
                    {
                        (str(i["metric"].get("namespace", "")), str(i["metric"].get("route_name", "")))
                        for i in labels.result
                    }
                )
            )
            readings.queries.append(labels)


def run(
    k8s: K8sRead,
    prom: PromClient,
    clock: Clock,
    run_id: str,
    started_at: datetime,
    *,
    environment: Environment,
    after_job: timedelta = WINDOW_AFTER,
) -> Outcome:
    """La seccion `rt5`: lee y juzga. `guard.check_section` se llama antes de cualquier solicitud."""
    guard.check_section(environment, "rt5")
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("run_id_invalid")
    try:
        readings = read(k8s, prom, clock, run_id, started_at, environment=environment, after_job=after_job)
    except K8sError as error:  # F-05 (ronda 2): un `port-forward` caido o un `kubectl` que no responde no es un incumplimiento
        code = (
            "rt5_port_forward_caido" if str(error).startswith("port_forward") else "rt5_kubectl_no_responde"
        )
        return Outcome("RT-5", NO_EJECUTADO, _EXPECTED, f"{code}: {str(error)[:200]}", (code,))
    return judge(run_id, started_at, readings)


__all__ = ["Readings", "judge", "parse_job", "parse_log", "ranged", "read", "run"]
