"""Publicacion al Pushgateway de U1 (BR-U9-20, F106; P-U9-05): grupos `run`, `success` y `freeze-<model_version_id>`.

Todo son gauges (un proceso que termina en cada corrida no acumula contadores). Las cifras estan en la escala de la libreria
(proporciones). Una celda insuficiente publica solo `vectra_bias_cell_size`, nunca una tasa (PBT-U9-03). Aqui viven tambien
los tipos del informe de una corrida (domain-entities §2.7), que `run` arma y esta publicacion consume.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Final

from vectra_common import deps
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_contracts.models.monitoring import DisparityResult

from vectra_bias import config
from vectra_bias.freeze_client import FAILED, FreezeOutcome
from vectra_bias.freeze_rule import FreezeDecision

JOB: Final = "bias-monitoring"
FREEZE_PREFIX: Final = "freeze-"
AGGREGATE_BAND: Final = "agregada"
NO_BANDS: Final = "sin_bandas"
POPULATIONS: Final = ("modelo", "humana")
HTTP_ACCEPTED_MAX: Final = 299


@dataclass(frozen=True)
class PopulationReport:
    result: DisparityResult
    limits: dict[str, Decimal | None]
    decision: FreezeDecision


@dataclass(frozen=True)
class VersionReport:
    model_version_id: str
    model: PopulationReport
    human: PopulationReport
    freeze: FreezeOutcome | None = None  # `None`: no hubo llamada a `freeze`


@dataclass(frozen=True)
class RunReport:
    started_at: datetime
    finished_at: datetime
    complete: bool
    failure_reason: str | None = None
    calculated: bool = False  # llego al calculo: solo entonces se tocan los grupos `freeze-<v>` (BR-U9-20)
    versions: tuple[VersionReport, ...] = ()
    invalid_entries: int | None = None
    total_entries: int | None = None


@dataclass(frozen=True)
class Series:
    name: str
    labels: tuple[tuple[str, str], ...]
    value: Decimal | int | str

    def line(self) -> str:
        labels = ",".join(f'{k}="{_escape(v)}"' for k, v in self.labels)
        return f"{self.name}{{{labels}}} {self.value}" if labels else f"{self.name} {self.value}"


@dataclass
class PublishResult:
    errors: list[str] = field(default_factory=list)
    deleted_stale: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _s(name: str, value: Decimal | int | str, **labels: str) -> Series:
    return Series(name, tuple(labels.items()), value)


def population_series(version: str, population: str, report: PopulationReport) -> list[Series]:
    """Series de una poblacion de una version: diferencias, agregada, limite R4, regla y tamanos de celda."""
    out: list[Series] = []
    for attribute in report.result.attributes:
        base = {"model_version_id": version, "population": population, "attribute": attribute.attribute}
        for band in attribute.bands:
            if band.difference is not None:
                out.append(_s("vectra_bias_disparity", band.difference, **base, band=band.band, partial="false"))
        if attribute.aggregate is not None:
            out.append(_s("vectra_bias_disparity", attribute.aggregate, **base, band=AGGREGATE_BAND, partial="false"))
        if attribute.population_difference is not None:
            partial = "true" if attribute.population_difference_partial else "false"
            out.append(_s("vectra_bias_disparity", attribute.population_difference, **base, band=NO_BANDS, partial=partial))
        limit = report.limits.get(attribute.attribute)
        if limit is not None:
            out.append(_s("vectra_bias_aggregate_lower", limit, **base))
        for cell in attribute.cells:
            out.append(_s("vectra_bias_cell_size", cell.n, **base, group=cell.group, band=cell.band))
    out.append(_s("vectra_bias_rule_met", int(report.decision.rule_met), model_version_id=version, population=population))
    return out


def run_series(report: RunReport) -> list[Series]:
    """Grupo `run`: las metricas de la corrida, completa o fallida."""
    out = [
        _s("vectra_bias_last_run_timestamp", int(report.finished_at.timestamp())),
        _s("vectra_bias_last_run_ok", int(report.complete)),
    ]
    if report.failure_reason is not None:
        out.append(_s("vectra_bias_last_run_failure", 1, reason=report.failure_reason))
    if report.invalid_entries is not None:
        out.append(_s("vectra_bias_invalid_entries", report.invalid_entries))
    if report.total_entries is not None:
        out.append(_s("vectra_bias_total_entries", report.total_entries))
    for version in report.versions:
        out += population_series(version.model_version_id, "modelo", version.model)
        out += population_series(version.model_version_id, "humana", version.human)
    return out


def render(series: Iterable[Series]) -> str:
    """Texto de exposicion de Prometheus; cada metrica con su `# TYPE ... gauge`."""
    lines: list[str] = []
    typed: set[str] = set()
    for s in series:
        if s.name not in typed:
            typed.add(s.name)
            lines.append(f"# TYPE {s.name} gauge")
        lines.append(s.line())
    return "\n".join(lines) + "\n"


def _path(group: str) -> str:
    return f"/metrics/job/{JOB}/group/{urllib.parse.quote(group, safe='')}"


async def _put(client: deps.DependencyClient, group: str, series: list[Series], timeout: float) -> str | None:
    return await _op(client, "PUT", _path(group), timeout, render(series).encode(), group)


async def _delete(client: deps.DependencyClient, group: str) -> str | None:
    return await _op(client, "DELETE", _path(group), config.GROUP_CALL_TIMEOUT_S, None, group)


async def _op(
    client: deps.DependencyClient, method: str, path: str, timeout: float, content: bytes | None, what: str
) -> str | None:
    """`None` si el Pushgateway respondio 2xx; si no, un codigo estable (sin texto de la respuesta)."""
    try:
        response = await deps.call(
            client, method, path, timeout=timeout, headers={"content-type": "text/plain; version=0.0.4"}, content=content
        )
    except (DependencyTimeout, DependencyUnavailable) as error:
        return f"{method}:{what}:{type(error).__name__}"
    return None if response.status_code <= HTTP_ACCEPTED_MAX else f"{method}:{what}:status_{response.status_code}"


async def list_groups(client: deps.DependencyClient) -> list[str] | str:
    """Los grupos `freeze-<v>` del job de bias (`GET /api/v1/metrics`); un codigo de error si la lectura falla."""
    try:
        response = await deps.call(
            client, "GET", "/api/v1/metrics", timeout=config.GROUP_CALL_TIMEOUT_S, headers={"accept": "application/json"}
        )
        data: Any = response.json() if response.status_code <= HTTP_ACCEPTED_MAX else None
    except (DependencyTimeout, DependencyUnavailable) as error:
        return f"GET:groups:{type(error).__name__}"
    except ValueError:
        return "GET:groups:invalid_json"
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return "GET:groups:invalid_response"
    groups = []
    for item in data["data"]:
        labels = item.get("labels", {}) if isinstance(item, dict) else {}
        group = labels.get("group", "")
        # Solo el job de bias: ningun DELETE toca un grupo de otro job (PBT-U9-05).
        if labels.get("job") == JOB and group.startswith(FREEZE_PREFIX):
            groups.append(group.removeprefix(FREEZE_PREFIX))
    return sorted(groups)


async def publish(client: deps.DependencyClient, report: RunReport) -> PublishResult:
    """Publica la corrida: `run` siempre; `success` solo si fue completa; los grupos `freeze-<v>` solo si llego al calculo.

    No reintenta: si el Pushgateway falla, el resultado trae los codigos y la corrida termina con codigo distinto de cero.
    """
    result = PublishResult()
    errors = [await _put(client, "run", run_series(report), config.PUSH_TIMEOUT_S)]
    if report.complete:
        success = [_s("vectra_bias_last_success_timestamp", int(report.finished_at.timestamp()))]
        errors.append(await _put(client, "success", success, config.PUSH_TIMEOUT_S))
    if report.calculated:
        errors += await _freeze_groups(client, report, result)
    result.errors = [e for e in errors if e is not None]
    return result


async def _freeze_groups(client: deps.DependencyClient, report: RunReport, result: PublishResult) -> list[str | None]:
    """Ciclo de vida del grupo `freeze-<v>` (BR-U9-20): `PUT` al fallar el `freeze`; `DELETE` con un `freeze` exitoso o 409, o en
    una corrida **completa** en la que `v` ya no cumple la regla o ya no se evalua (hasta `MAX_STALE_GROUP_DELETES`)."""
    errors: list[str | None] = []
    existing: set[str] | None = None
    evaluated = {v.model_version_id for v in report.versions}
    if report.complete:
        listed = await list_groups(client)
        if isinstance(listed, str):
            errors.append(listed)
        else:
            existing = set(listed)
    for version in report.versions:
        group = FREEZE_PREFIX + version.model_version_id
        if version.freeze is not None and version.freeze.outcome == FAILED:
            failed = [_s("vectra_bias_freeze_failed", 1, model_version_id=version.model_version_id)]
            errors.append(await _put(client, group, failed, config.GROUP_CALL_TIMEOUT_S))
            continue
        succeeded = version.freeze is not None  # no `FAILED` y hubo llamada: exito o 409
        resolved = report.complete and not version.model.decision.rule_met
        if (succeeded or resolved) and (existing is None or version.model_version_id in existing):
            errors.append(await _delete(client, group))
    if existing is not None:
        stale = sorted(existing - evaluated)[: config.MAX_STALE_GROUP_DELETES]
        for version_id in stale:
            error = await _delete(client, FREEZE_PREFIX + version_id)
            errors.append(error)
            if error is None:
                result.deleted_stale.append(version_id)
    return errors
