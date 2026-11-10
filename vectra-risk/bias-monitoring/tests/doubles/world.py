"""Dobles HTTP del Bloque C que siguen los contratos de `vectra_contracts`: registro de U3, governance de U4, Keycloak y Pushgateway.

Cada doble es un `httpx.MockTransport` (sin red): el registro responde `monitoring/freezes` y `monitoring/daily:query` con la
suma por rango que hace U3 en el servidor; governance responde `freeze` con su 409 y el limite de 64 KiB; el Pushgateway
guarda los grupos (`PUT`/`DELETE`/`GET /api/v1/metrics`) y registra cada operacion. Un doble «lento» duerme el tiempo que se
le pide con un reloj virtual y, si supera el timeout que el cliente puso en la solicitud, falla como `httpx.ReadTimeout`.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from vectra_common.errors import DependencyUnavailable
from vectra_common.service_token import ServiceTokenProvider
from vectra_contracts.catalog import Decision
from vectra_contracts.models.monitoring import (
    FreezeContext,
    MonitoringMarginalCount,
    MonitoringQuery,
    MonitoringWindow,
    RangeTotals,
    VersionWindow,
)
from vectra_disparity import CountTable

_KEY = ec.generate_private_key(ec.SECP256R1())
PRIVATE_KEY_PEM = _KEY.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
).decode()

REGISTRY_URL = "http://registry.test"
GOVERNANCE_URL = "http://governance.test"
PUSHGATEWAY_URL = "http://pushgateway.test"
TOKEN_URL = "http://keycloak.test/token"
CLIENT_ID = "bias-monitoring-job"


class VirtualClock:
    """Duerme sin esperar: acumula el tiempo dormido (los dobles lentos y los reintentos de `freeze`)."""

    def __init__(self) -> None:
        self.slept: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)

    @property
    def total(self) -> float:
        return sum(self.slept)


def problem(status: int, code: str = "conflict_state") -> httpx.Response:
    return httpx.Response(status, json={"type": f"urn:vectra:problem:{code}", "status": status, "code": code})


class Keycloak:
    """Doble del endpoint de tokens: `private_key_jwt` del cliente `bias-monitoring-job`; `down` lo deja sin responder."""

    def __init__(self) -> None:
        self.down = False
        self.requests: list[dict[str, str]] = []

    async def post(self, url: str, data: Mapping[str, str], timeout: float) -> Any:
        self.requests.append(dict(data))
        if self.down or url != TOKEN_URL:
            raise DependencyUnavailable()
        assert data["grant_type"] == "client_credentials"
        assert data["client_assertion"]
        return {"access_token": f"tok|{data['audience']}|{data['scope']}", "expires_in": 300}

    def provider(self, audience: str, scopes: tuple[str, ...]) -> ServiceTokenProvider:
        return ServiceTokenProvider(CLIENT_ID, TOKEN_URL, PRIVATE_KEY_PEM, audience, scopes, poster=self.post)


def _scopes_of(request: httpx.Request) -> tuple[str, set[str]] | None:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer tok|"):
        return None
    # `tok|<audiencia>|<scopes>` (el doble en proceso) o `tok|<audiencia>|<scopes>|<cliente>` (el Keycloak HTTP de `http_doubles`, U09-T04).
    _, audience, scopes, *_client = header.removeprefix("Bearer ").split("|")
    return audience, set(scopes.split())


@dataclass
class Daily:
    population: str
    version: str
    day: date
    attribute: str
    group: str
    band: str
    result: str
    decision: str | None
    count: int


@dataclass
class Call:
    method: str
    path: str
    body: Any = None
    timeout: float | None = None
    status: int | None = None


class _Slow:
    """`delay`: segundos que el doble tarda en responder; si superan el timeout del cliente, `ReadTimeout`."""

    def __init__(self, clock: VirtualClock) -> None:
        self.clock = clock
        self.delay = 0.0
        self.calls: list[Call] = []

    async def _wait(self, request: httpx.Request, delay: float | None = None) -> float:
        timeout = request.extensions["timeout"]["read"]
        delay = self.delay if delay is None else delay
        if delay > timeout:
            self._record(request, timeout, self._timeout_body(request))
            await self.clock.sleep(timeout)
            raise httpx.ReadTimeout("slow double", request=request)
        if delay:
            await self.clock.sleep(delay)
        return timeout

    def _timeout_body(self, request: httpx.Request) -> Any:
        return None

    def _record(self, request: httpx.Request, timeout: float, body: Any = None) -> Call:
        call = Call(request.method, request.url.path, body, timeout)
        self.calls.append(call)
        return call


class Registry(_Slow):
    """U3: `GET /v1/monitoring/freezes` y `POST /v1/monitoring/daily:query` (suma por rango, `versions`, totales, no atribuibles)."""

    def __init__(self, clock: VirtualClock) -> None:
        super().__init__(clock)
        self.rows: list[Daily] = []
        self.entries: dict[tuple[str, str, date], list[int]] = defaultdict(lambda: [0, 0])  # total, invalid
        self.unattributable: dict[date, int] = defaultdict(int)
        self.invalid_seqs: list[int] = []
        self.lag_seconds = 0
        self.watermark_seq = 100
        self.freezes: list[dict[str, Any]] = []
        self.status: int | None = None  # fuerza una respuesta de error en todo

    def add_day(
        self,
        version: str,
        population: str,
        day: date,
        tables: Mapping[str, CountTable],
        *,
        invalid: int = 0,
        decisions: bool = False,
    ) -> None:
        sizes = []
        for attribute, table in tables.items():
            sizes.append(sum(c.total for c in table.cells))
            for c in table.cells:
                for result, count in (("favorable", c.favorable), ("desfavorable", c.total - c.favorable)):
                    if count:
                        decision = ("sigue" if result == "favorable" else "se_aparta") if decisions else None
                        self.rows.append(
                            Daily(
                                population, version, day, attribute, c.group, c.band, result, decision, count
                            )
                        )
        entry = self.entries[(version, population, day)]
        entry[0] += max(sizes, default=0) + invalid
        entry[1] += invalid

    async def handle(self, request: httpx.Request) -> httpx.Response:
        timeout = await self._wait(request)
        scopes = _scopes_of(request)
        if scopes is None:
            self._record(request, timeout)
            return problem(401, "unauthenticated")
        if "registry:read:monitoring" not in scopes[1]:
            self._record(request, timeout)
            return problem(403, "forbidden")
        if self.status is not None:
            self._record(request, timeout)
            return httpx.Response(self.status)
        if request.method == "GET" and request.url.path == "/v1/monitoring/freezes":
            self._record(request, timeout)
            return httpx.Response(200, json=self.freezes)
        if request.method == "POST" and request.url.path == "/v1/monitoring/daily:query":
            try:
                query = MonitoringQuery.model_validate_json(request.content)
            except ValueError:
                self._record(request, timeout, request.content)
                return problem(422, "validation_error")
            self._record(request, timeout, query)
            return httpx.Response(200, content=self._query(query).model_dump_json())
        return problem(404, "not_found")

    def _query(self, query: MonitoringQuery) -> MonitoringWindow:
        counts: list[MonitoringMarginalCount] = []
        totals: list[RangeTotals] = []
        invalid_days: set[date] = set()
        for r in query.ranges:
            sums: dict[tuple[str, str, str, str, str, str | None, str], int] = defaultdict(int)
            for d in self.rows:
                if (
                    d.population == r.population
                    and r.from_day <= d.day <= r.to_day
                    and (r.model_version_id is None or d.version == r.model_version_id)
                ):
                    sums[(d.version, d.attribute, d.group, d.band, d.result, d.decision, d.population)] += (
                        d.count
                    )
            counts += [
                MonitoringMarginalCount(
                    population=pop,  # type: ignore[arg-type]
                    model_version_id=v,
                    range_id=r.range_id,
                    attribute=a,  # type: ignore[arg-type]
                    group=g,
                    band=b,  # type: ignore[arg-type]
                    result=res,
                    decision=None if dec is None else Decision(dec),
                    count=n,
                )
                for (v, a, g, b, res, dec, pop), n in sorted(sums.items(), key=lambda kv: str(kv[0]))
            ]
            total = invalid = 0
            for (v, pop, day), (t, i) in self.entries.items():
                if (
                    pop == r.population
                    and r.from_day <= day <= r.to_day
                    and (r.model_version_id in (None, v))
                ):
                    total += t
                    invalid += i
                    if i:
                        invalid_days.add(day)
            totals.append(RangeTotals(range_id=r.range_id, total_entries=total, invalid_entries=invalid))
        unattributable = 0
        if query.unattributable_range is not None:
            window = query.unattributable_range
            unattributable = sum(
                n for d, n in self.unattributable.items() if window.from_day <= d <= window.to_day
            )
        versions: list[VersionWindow] = []
        if query.include_versions:
            low = min(
                [r.from_day for r in query.ranges]
                + ([query.unattributable_range.from_day] if query.unattributable_range else [])
            )
            high = max(
                [r.to_day for r in query.ranges]
                + ([query.unattributable_range.to_day] if query.unattributable_range else [])
            )
            spans: dict[tuple[str, str], list[date]] = defaultdict(list)
            for d in self.rows:
                if low <= d.day <= high:
                    spans[(d.version, d.population)].append(d.day)
            versions = [
                VersionWindow(model_version_id=v, population=p, first_day=min(days), last_day=max(days))  # type: ignore[arg-type]
                for (v, p), days in sorted(spans.items())
            ]
        return MonitoringWindow(
            versions=versions,
            counts=counts,
            totals=totals,
            unattributable_invalid=unattributable,
            invalid_seqs=self.invalid_seqs[:100],
            watermark_seq=self.watermark_seq,
            lag_seconds=self.lag_seconds,
        )

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


class Governance(_Slow):
    """U4: `POST /v1/models/{id}/freeze`. 204; 409 si ya esta congelada; 413 sobre 64 KiB; respuestas guionadas por version."""

    MAX_BODY = 64 * 1024

    def _timeout_body(self, request: httpx.Request) -> Any:
        match = re.fullmatch(r"/v1/models/([^/]+)/freeze", request.url.path)
        return match.group(1) if match else None

    def __init__(self, clock: VirtualClock, on_freeze: Callable[[str], None] | None = None) -> None:
        super().__init__(clock)
        self.frozen: set[str] = set()
        self.script: dict[str, list[str]] = defaultdict(
            list
        )  # por version: "ok" | "409" | "5xx" | "timeout" | "403" | "400"
        self.on_freeze = on_freeze
        self.packages: list[FreezeContext] = []

    async def handle(self, request: httpx.Request) -> httpx.Response:
        match = re.fullmatch(r"/v1/models/([^/]+)/freeze", request.url.path)
        if request.method != "POST" or match is None:
            self._record(request, request.extensions["timeout"]["read"])
            return problem(404, "not_found")
        model_id = match.group(1)
        action = self.script[model_id].pop(0) if self.script[model_id] else "ok"
        timeout = await self._wait(request, 10_000.0 if action == "timeout" else None)
        scopes = _scopes_of(request)
        call = self._record(request, timeout, model_id)
        if scopes is None:
            call.status = 401
            return problem(401, "unauthenticated")
        if "governance:freeze" not in scopes[1] or action == "403":
            call.status = 403
            return problem(403, "forbidden")
        if len(request.content) > self.MAX_BODY:
            call.status = 413
            return problem(413, "payload_too_large")
        try:
            context = FreezeContext.model_validate_json(request.content)
        except ValueError:
            call.status = 422
            return problem(422, "validation_error")
        if action == "5xx":
            call.status = 503
            return problem(503, "dependency_unavailable")
        if action == "400":
            call.status = 400
            return problem(400, "malformed_request")
        if action == "409" or model_id in self.frozen or context.model_version_id != model_id:
            call.status = 409
            return problem(409)
        self.frozen.add(model_id)
        self.packages.append(context)
        call.status = 204
        if self.on_freeze is not None:
            self.on_freeze(model_id)
        return httpx.Response(204)

    def freeze_calls(self, version: str | None = None) -> list[Call]:
        return [c for c in self.calls if c.method == "POST" and (version is None or c.body == version)]

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


_LINE = re.compile(r"^([a-z_:][a-z0-9_:]*)(\{(.*)\})? (\S+)$")
_LABEL = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')


class Pushgateway(_Slow):
    """El Pushgateway: grupos por `job/group`, `PUT` los reemplaza, `DELETE` los borra y `GET /api/v1/metrics` los lista."""

    def __init__(self, clock: VirtualClock) -> None:
        super().__init__(clock)
        self.groups: dict[tuple[tuple[str, str], ...], list[tuple[str, dict[str, str], str]]] = {}
        self.down = False
        self.failing_paths: set[str] = set()

    @staticmethod
    def _labels(path: str) -> tuple[tuple[str, str], ...]:
        parts = path.removeprefix("/metrics/").split("/")
        return tuple((parts[i], parts[i + 1]) for i in range(0, len(parts), 2))

    async def handle(self, request: httpx.Request) -> httpx.Response:
        timeout = await self._wait(request)
        self._record(request, timeout, request.content.decode() if request.method == "PUT" else None)
        if self.down or request.url.path in self.failing_paths:
            raise httpx.ConnectError("pushgateway down", request=request)
        if request.method == "GET" and request.url.path == "/api/v1/metrics":
            data = []
            for labels, series in self.groups.items():
                families: dict[str, Any] = {"labels": dict(labels), "last_push_successful": True}
                for name, lab, value in series:
                    families.setdefault(name, {"type": "GAUGE", "metrics": []})["metrics"].append(
                        {"labels": lab, "value": value}
                    )
                data.append(families)
            return httpx.Response(200, json={"status": "success", "data": data})
        if not request.url.path.startswith("/metrics/job/"):
            return problem(404, "not_found")
        key = self._labels(request.url.path)
        if request.method == "PUT":
            series = []
            for line in request.content.decode().splitlines():
                if not line or line.startswith("#"):
                    continue
                m = _LINE.match(line)
                if m is None:
                    return httpx.Response(400, text="bad exposition")
                labels = dict(_LABEL.findall(m.group(3) or ""))
                series.append((m.group(1), labels, m.group(4)))
            self.groups[key] = series
            return httpx.Response(200)
        if request.method == "DELETE":
            self.groups.pop(key, None)
            return httpx.Response(202)
        return problem(405, "method_not_allowed")

    def group(self, job: str, group: str) -> list[tuple[str, dict[str, str], str]] | None:
        return self.groups.get((("job", job), ("group", group)))

    def names(self, job: str = "bias-monitoring") -> set[str]:
        return {dict(k).get("group", "") for k in self.groups if dict(k).get("job") == job}

    def value(self, group: str, name: str, **labels: str) -> str | None:
        for series_name, lab, value in self.group("bias-monitoring", group) or []:
            if series_name == name and all(lab.get(k) == v for k, v in labels.items()):
                return value
        return None

    def put_group(self, job: str, group: str, name: str = "dummy") -> None:
        self.groups[(("job", job), ("group", group))] = [(name, {}, "1")]

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


def freeze_record(
    version: str, frozen_at: datetime, resolutions: Iterable[tuple[str, datetime]] = ()
) -> dict[str, Any]:
    """Un `FreezeRecord` de U3 valido contra U0, con un paquete minimo."""
    empty = {
        "population": "modelo",
        "model_version_id": version,
        "window_from": "2026-10-11",
        "window_to": "2026-11-09",
        "attributes": [],
        "model_aggregate": None,
        "trigger_attribute": "region",
        "departure_rates": None,
    }
    package = {
        "model_version_id": version,
        "computed_at": frozen_at.isoformat(),
        "threshold_pp": "5.0000",
        "n_min": 30,
        "window_days": 30,
        "schedule": "2,17,32,47 * * * *",
        "stale_after_s": 3600,
        "library_version": "1.0.0",
        "window_start": "2026-10-11",
        "before": "sin_datos",
        "after": empty,
        "last_7_days": "sin_datos",
        "trigger_attribute": "region",
        "implicated": [],
        "affected_volume": {"total": 1, "favorable": 1},
        "truncated": False,
        "data_sources": [],
        "initial_disparity": {"attributes": []},
    }
    return {
        "freeze_id": f"freeze-{version}",
        "model_version_id": version,
        "frozen_at": frozen_at.isoformat(),
        "context_package": package,
        "resolutions": [{"action": a, "recorded_at": t.astimezone(UTC).isoformat()} for a, t in resolutions],
    }


@dataclass
class World:
    """Los cuatro dobles juntos, con sus transportes y un reloj virtual."""

    clock: VirtualClock = field(default_factory=VirtualClock)
    keycloak: Keycloak = field(default_factory=Keycloak)

    def __post_init__(self) -> None:
        self.registry = Registry(self.clock)
        self.governance = Governance(self.clock)
        self.pushgateway = Pushgateway(self.clock)
