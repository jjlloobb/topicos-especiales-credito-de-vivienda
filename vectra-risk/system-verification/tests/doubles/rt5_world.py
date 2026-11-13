"""El mundo de RT-5 para las pruebas (U12-T03): el JSON de un Job `batch/v1`, un ejecutor de `kubectl` guionizado y un doble de la API de Prometheus.

`Rt5Spec` describe un caso (el Job, su log y las muestras de cada serie). Lo usan dos consumidores con la misma descripcion: el doble (`PromDouble`, que evalua las consultas del oraculo como Prometheus: el ultimo
valor de hasta 5 min antes de cada paso) y la prueba contra un Prometheus real (`test_rt5_promql.py`, que la vuelca a OpenMetrics y la importa con `promtool`). Asi «los mismos casos» son los mismos.
El doble solo acepta las expresiones literales del oraculo y rechaza, como Prometheus, una ventana de mas de 11 000 puntos: una expresion distinta o un rango dentro de PromQL es un error de la prueba.
"""

from __future__ import annotations

import bisect
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from vectra_verification.clients.k8s_read import Completed
from vectra_verification.scenarios import rt5

RUN_ID = "20261113-1000"
JOB = f"rt5-demo-{RUN_ID}"
LOOKBACK = 300.0
MAX_POINTS = 11_000
PROXY_LOG = "rt5-demo: POST http://core-banking-mock.vectra-mock:8080/v1/credits/c1/status -> 403 l5d-proxy-error: unauthorized\n"
APP_LOG = "rt5-demo: POST http://core-banking-mock.vectra-mock:8080/v1/credits/c1/status -> 403 l5d-proxy-error: None\n"


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def job_json(
    name: str = JOB,
    *,
    start: datetime | None,
    completion: datetime | None,
    succeeded: int = 0,
    failed: int = 0,
    conditions: Sequence[tuple[str, str]] = (),
) -> str:
    status: dict[str, Any] = {
        "succeeded": succeeded,
        "failed": failed,
        "conditions": [{"type": t, "status": s} for t, s in conditions],
    }
    if start is not None:
        status["startTime"] = iso(start)
    if completion is not None:
        status["completionTime"] = iso(completion)
    return json.dumps(
        {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": name, "namespace": "vectra-app"},
            "status": status,
        }
    )


def completed_job(start: datetime, completion: datetime, name: str = JOB) -> str:
    return job_json(name, start=start, completion=completion, succeeded=1, conditions=[("Complete", "True")])


def failed_job(start: datetime, name: str = JOB) -> str:
    return job_json(name, start=start, completion=None, failed=1, conditions=[("Failed", "True")])


def active_job(start: datetime, name: str = JOB) -> str:
    return job_json(name, start=start, completion=None)


class JobKubectl:
    """Un ejecutor de `kubectl` (la interfaz `Runner`): el Job, su pod y su log. `job` puede ser una lista (una respuesta por lectura: el Job que sigue activo y despues termina)."""

    def __init__(
        self,
        job: str | list[str] | Completed | None,
        log: str = PROXY_LOG,
        pods: int = 1,
        logs_error: str | None = None,
    ) -> None:
        self.jobs = [job] if isinstance(job, (str, Completed)) or job is None else list(job)
        self.log, self.pods, self.logs_error = log, pods, logs_error
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: Sequence[str]) -> Completed:
        self.calls.append(tuple(args))
        verb, resource = args[1], args[2]
        if verb == "get" and resource.startswith("job/"):
            current = self.jobs[0] if len(self.jobs) == 1 else self.jobs.pop(0)
            if current is None:
                return Completed(
                    1, "", f'Error from server (NotFound): jobs.batch "{resource[4:]}" not found'
                )
            if isinstance(current, Completed):
                return current
            return Completed(0, current, "")
        if verb == "get" and resource == "pods":
            items = [{"metadata": {"name": f"{JOB}-{'abcde'[i]}"}} for i in range(self.pods)]
            return Completed(0, json.dumps({"items": items}), "")
        if verb == "logs":
            if self.logs_error:
                return Completed(1, "", self.logs_error)
            return Completed(0, self.log, "")
        raise AssertionError(f"verbo fuera del oraculo: {args}")

    def start(self, args: Sequence[str]) -> Any:  # pragma: no cover - RT-5 no hace port-forward
        raise AssertionError("RT-5 no abre port-forward con este doble")


@dataclass
class Rt5Spec:
    """Las muestras de cada serie (cada 15 s) y lo que Prometheus sabe de si mismo."""

    started_at: datetime
    alert: list[datetime] = field(default_factory=list)
    deny: list[tuple[datetime, float]] = field(default_factory=list)
    counter: list[tuple[datetime, float]] = field(default_factory=list)
    lowest: datetime | None = None
    other_family: list[tuple[str, str]] = field(
        default_factory=list
    )  # series de `inbound_http_authz_deny_total` con otras etiquetas
    other_until: datetime | None = (
        None  # hasta cuando tienen muestras (cada 15 s, los 10 min previos); `None` = siempre visibles (pruebas unitarias)
    )


def every(start: datetime, end: datetime, step: float = 15.0) -> list[datetime]:
    out, moment = [], start
    while moment <= end:
        out.append(moment)
        moment += timedelta(seconds=step)
    return out


def _evaluate(
    samples: list[tuple[datetime, float]], start: float, end: float, step: float
) -> list[list[Any]]:
    """El valor de cada paso: la ultima muestra de hasta 5 min antes (el `lookback` de Prometheus)."""
    ordered = sorted(samples)
    stamps = [t.timestamp() for t, _ in ordered]
    points: list[list[Any]] = []
    moment = start
    while moment <= end + 1e-9:
        index = bisect.bisect_right(stamps, moment) - 1
        if index >= 0 and moment - stamps[index] <= LOOKBACK:
            points.append([moment, f"{ordered[index][1]:g}"])
        moment += step
    return points


class PromDouble(httpx.BaseTransport):
    def __init__(self, spec: Rt5Spec, *, down: bool = False) -> None:
        self.spec, self.down = spec, down
        self.requests: list[httpx.Request] = []

    def _error(self, text: str) -> httpx.Response:
        return httpx.Response(400, json={"status": "error", "errorType": "bad_data", "error": text})

    def _series(self, expression: str) -> list[dict[str, Any]] | None:
        s = self.spec
        if expression == rt5.ALERT:
            data = [(t, 1.0) for t in s.alert]
            metric = {"alertname": "CoreWriteAttempt", "alertstate": "firing", "severity": "SEV2"}
        elif expression == rt5.DENY:
            data, metric = s.deny, {}
        elif expression == rt5.COUNTER:
            data, metric = s.counter, {}
        else:
            return None
        return [{"metric": metric, "samples": data}] if data else []

    def _family_pairs(self, at: float) -> list[tuple[str, str]]:
        """Las series de la familia visibles en `at` (una muestra de hasta 5 min antes)."""
        s = self.spec
        others = (
            list(s.other_family)
            if s.other_until is None or s.other_until.timestamp() >= at - LOOKBACK
            else []
        )
        mine = (
            [("vectra-mock", "core-mock-catch-all")]
            if any(t.timestamp() <= at and at - t.timestamp() <= LOOKBACK for t, _ in s.deny)
            else []
        )
        return others + mine

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("conexion rechazada")
        params = request.url.params
        expression = params["query"]
        if "[" in expression or "increase(" in expression:
            return self._error("un rango o increase() dentro de PromQL: no lo usa el oraculo")
        if request.url.path.endswith("query_range"):
            start, end, step = float(params["start"]), float(params["end"]), float(params["step"])
            if (end - start) / step > MAX_POINTS:
                return self._error(
                    "exceeded maximum resolution of 11,000 points per timeseries. Try decreasing the query resolution (?step=XX)"
                )
            series = self._series(expression)
            if series is None:
                return self._error(f"expresion fuera de las del oraculo: {expression}")
            result = [
                {"metric": item["metric"], "values": _evaluate(item["samples"], start, end, step)}
                for item in series
            ]
            result = [r for r in result if r["values"]]
            return httpx.Response(
                200, json={"status": "success", "data": {"resultType": "matrix", "result": result}}
            )
        at = float(params.get("time", datetime.now(UTC).timestamp()))
        s = self.spec
        if expression == rt5.RETENTION:
            result = [{"metric": {}, "value": [at, f"{s.lowest.timestamp():g}"]}] if s.lowest else []
        elif expression == rt5.FAMILY_COUNT:
            n = len(self._family_pairs(at))
            result = [{"metric": {}, "value": [at, str(n)]}] if n else []
        elif expression == rt5.FAMILY_LABELS:
            pairs = self._family_pairs(at)
            result = [{"metric": {"namespace": n, "route_name": r}, "value": [at, "1"]} for n, r in pairs]
        else:
            return self._error(f"expresion fuera de las del oraculo: {expression}")
        return httpx.Response(
            200, json={"status": "success", "data": {"resultType": "vector", "result": result}}
        )
