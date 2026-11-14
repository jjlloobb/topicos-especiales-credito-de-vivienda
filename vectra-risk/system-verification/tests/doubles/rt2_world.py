"""El mundo de RT-2, `rt2-setup`, RT-3 y `SIM-NORMAL` para las pruebas (U12-T03): el BFF **real** en proceso (`RealBff`, con los dobles de U10) con la lista de modelos, la validacion y la aprobacion con estado; un registro con
`recommendation`, `freeze` y `frozen_resolution` que crecen con el tiempo; un Prometheus de bias; un simulador falso; y un reloj que dispara los eventos del operador y del sistema en su instante (nunca duerme).

Los eventos programados (`world.at(segundos, funcion)`) hacen de operador (promover, volver al modelo de referencia) y de sistema (el `freeze` a los 1 500 s, las corridas de bias cada 900 s, el barrido de 300 s). Cada escenario
de prueba cambia una sola cosa del mundo correcto, y el resto sigue igual (NFR-U12-42).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from contract_world import case_detail_json, problem
from fake_clock import FakeClock
from real_bff import RealBff
from registry_read_double import ENTRIES_PARAMS, freeze_item

from vectra_verification import sampler
from vectra_verification.clients._api import RunTag
from vectra_verification.clients.prom import PromClient
from vectra_verification.clients.registry import RegistryClient
from vectra_verification.guard import KIND
from vectra_verification.scenarios import rt2 as rt2_module
from vectra_verification.scenarios.common import Sessions
from vectra_verification.simulator import RunReport, SimulationResult

import bff_builders as b  # noqa: E402, I001  (los dobles de U10: `external_paths.use_u10_doubles` ya los puso en `sys.path`)
import bff_tokens  # noqa: E402

REFERENCE, PROXY = "mv-ref", "mv-proxy"
TAG = RunTag("rt2", "3fa9c2d1")
ROLES = {
    "analista-1": "analista",
    "ingeniero-1": "ingeniero_riesgo",
    "cro-1": "cro",
    "cumplimiento-1": "cumplimiento",
}
SHA = "a" * 64
ATTRIBUTES = [
    {
        "attribute": "sexo",
        "cells": [{"group": "F", "band": "lt_20", "n": 100, "rate": "0.5000", "status": "suficiente"}],
        "bands": [{"band": "lt_20", "difference": "0.0100", "n_band": 100}],
        "aggregate": "0.0100",
        "population_difference_partial": False,
    }
]  # un `AttributeResult` valido (la entrega de U10 trae `attributes` vacio)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class WorldClock(FakeClock):
    """Un reloj falso que dispara los eventos programados en su instante al avanzar."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[datetime, int, Callable[[], None]]] = []
        self._order = 0

    def at(self, delay: float, action: Callable[[], None]) -> None:
        self._order += 1
        self.events.append((self._now + timedelta(seconds=delay), self._order, action))

    def advance(self, seconds: float) -> None:
        target = self._now + timedelta(seconds=seconds)
        while True:
            due = sorted(e for e in self.events if e[0] <= target)
            if not due:
                break
            event = due[0]
            self.events.remove(event)
            delta = (event[0] - self._now).total_seconds()
            super().advance(max(delta, 0.0))
            event[2]()
        super().advance((target - self._now).total_seconds())


class WorldSession:
    """Una sesion de prueba: tokens del emisor de prueba de U0 con el rol del usuario; `auth_time` es del reloj de la prueba."""

    def __init__(self, world: Rt2World, user: str, step_up: bool) -> None:
        self.user, self.step_up = user, step_up
        self.auth_time: datetime | None = world.clock.now() if step_up else None
        self._roles = (ROLES[user],)

    def bearer(self) -> str:
        return bff_tokens.bearer(self._roles, sub=self.user)["authorization"].removeprefix("Bearer ")

    def refresh(self) -> None:
        return None


class WorldOidc:
    def __init__(self, world: Rt2World) -> None:
        self.world = world
        self.logins: list[str] = []
        self.step_ups: list[str] = []
        self.step_up_flag = True  # `False`: un `step_up` que devuelve una sesion sin MFA

    def login(self, user: str) -> WorldSession:
        self.logins.append(user)
        return WorldSession(self.world, user, False)

    def step_up(self, user: str) -> WorldSession:
        self.step_ups.append(user)
        return WorldSession(self.world, user, self.step_up_flag)


@dataclass
class CaseRecord:
    created: datetime
    kind: str  # `lot`, `probe` o `normal`
    frozen_at_creation: bool


class RegistryWorld(httpx.BaseTransport):
    """`GET /v1/entries` con las proyecciones `metrics` y `monitoring_freezes`; los parametros son los del OpenAPI."""

    def __init__(self, world: Rt2World) -> None:
        self.world = world
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        names = set(request.url.params.keys())
        assert names <= ENTRIES_PARAMS, f"parametros fuera del contrato: {sorted(names - ENTRIES_PARAMS)}"
        params = request.url.params
        projection = params["projection"]
        since = datetime.fromisoformat(params["recorded_from"]) if "recorded_from" in params else None
        until = datetime.fromisoformat(params["recorded_to"]) if "recorded_to" in params else None
        pool = self.world.recommendations if projection == "metrics" else self.world.freeze_entries
        if projection == "metrics":
            assert params.get("entry_type", "recommendation") == "recommendation", (
                "la proyeccion metrics no trae fail_closed"
            )
        items = [
            i
            for i in pool
            if (since is None or datetime.fromisoformat(i["recorded_at"].replace("Z", "+00:00")) >= since)
            and (until is None or datetime.fromisoformat(i["recorded_at"].replace("Z", "+00:00")) <= until)
        ]
        after = int(params.get("seq_after", "-1"))
        items = [i for i in items if i["seq"] > after]
        limit = int(params.get("limit", "1000"))
        page = items[:limit]
        following = page[-1]["seq"] if len(items) > limit else None
        return httpx.Response(200, json={"items": page, "next_seq_after": following})


class BiasProm(httpx.BaseTransport):
    """Prometheus con las corridas de bias que dejo el cron de U9 (Pushgateway: el ultimo valor se queda)."""

    def __init__(self, world: Rt2World) -> None:
        self.world = world
        self.requests: list[httpx.Request] = []
        self.down = False

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("sin conexion")
        params = request.url.params
        expression = params["query"]
        runs = sorted(self.world.bias_runs)
        if request.url.path.endswith("query_range"):
            start, end, step = float(params["start"]), float(params["end"]), float(params["step"])
            assert (end - start) / step <= 11_000, "mas de 11 000 puntos"
            index = 0 if expression == rt2_module.BIAS_TS else 1
            values: list[list[Any]] = []
            moment = start
            while moment <= end + 1e-9:
                seen = [r for r in runs if r[0] <= moment]
                if seen:
                    values.append([moment, repr(seen[-1][index])])
                moment += step
            result = [{"metric": {}, "values": values}] if values else []
            return httpx.Response(
                200, json={"status": "success", "data": {"resultType": "matrix", "result": result}}
            )
        if expression == "max(vectra_cases_failclosed_persistent)":
            result = (
                [{"metric": {}, "value": [0, repr(self.world.gauge)]}] if self.world.gauge is not None else []
            )
        elif expression.startswith("ALERTS{"):
            result = (
                [{"metric": {"alertname": "FailClosedPersistente"}, "value": [0, "1"]}]
                if self.world.alert_firing
                else []
            )
        elif expression == rt2_module.BIAS_OK:
            result = [{"metric": {}, "value": [0, repr(runs[-1][1])]}] if runs else []
        else:
            result = (
                [{"metric": {"reason": self.world.bias_failure_reason}, "value": [0, "1"]}]
                if self.world.bias_failure_reason
                else []
            )
        return httpx.Response(
            200, json={"status": "success", "data": {"resultType": "vector", "result": result}}
        )


@dataclass
class FakeSimulator:
    """Un simulador falso con la forma de `Simulator`: crea los casos del lote y de las sondas en el mundo y avanza el reloj lo que tardaria el envio."""

    world: Rt2World
    short: tuple[sampler.CellReport, ...] = ()
    runs: list[tuple[str, int, int, str]] = field(default_factory=list)
    accepted_ratio: float = 1.0

    def select(
        self, scenario: str, volume: int, seed: int, min_per_cell: int = 30
    ) -> tuple[tuple[int, ...], tuple[sampler.CellReport, ...]]:
        return tuple(range(volume)), self.short

    def run(
        self, scenario: str, volume: int, seed: int, *, rate: float = 10.0, section: str = "decisions"
    ) -> SimulationResult:
        self.runs.append((scenario, volume, seed, section))
        world = self.world
        started = world.clock.now()
        accepted = int(volume * self.accepted_ratio)
        ids = [world.new_case("lot" if scenario == "stratified" else "probe") for _ in range(accepted)]
        if scenario == "stratified":
            world.on_batch(started, ids, volume / rate)
        world.clock.sleep(volume / rate)
        if scenario == "normal" and world.on_probe is not None:
            world.on_probe()
        report = RunReport(
            scenario=scenario, sent=volume, accepted=accepted, rejected_by_code={"validation_error": volume - accepted} if accepted < volume else {},
            case_ids=tuple(ids), started_at=started, finished_at=world.clock.now(), generator_version="g", seed=1, sampling_seed=seed, rate=rate,
            run_prefix="3fa9c2d1", test_rows=18000, parquet_sha256="0" * 64, resends=0, short_cells=self.short,
        )  # fmt: skip
        return SimulationResult(report, tuple(range(volume)))


class Rt2World:
    def __init__(
        self,
        *,
        freeze_after: float | None = 1500.0,
        validation_seconds: float = 120.0,
        sweep_seconds: float = 300.0,
    ) -> None:
        self.clock = WorldClock()
        self.bff = RealBff()
        self.oidc = WorldOidc(self)
        self.sessions = Sessions(KIND, self.oidc, self.clock, TAG, transport=self.bff.transport, verify=False)
        self.cases: dict[str, CaseRecord] = {}
        self.recommendations: list[dict[str, Any]] = []
        self.freeze_entries: list[dict[str, Any]] = []
        self.bias_runs: list[tuple[float, float]] = []
        self.bias_failure_reason = ""
        self.freeze_after, self.validation_seconds, self.sweep_seconds = (
            freeze_after,
            validation_seconds,
            sweep_seconds,
        )
        self.package_variant: Callable[[dict[str, Any]], None] | None = None
        self.validation_outcome = "lista_para_aprobacion"
        self.no_policy = False
        self.empty_disparity = False
        self.register_overrides: dict[str, Callable[[Any], tuple[int, Any]]] = {}
        self.gauge: float | None = None
        self.on_probe: Callable[[], None] | None = None
        self.alert_firing = False
        self.freeze_freezes_model = True
        self.reactivation_status = 204
        self.refreeze_after: float | None = None
        self.probe_listo = False
        self.sweep_works = True
        self.recommendation_version: str | None = None
        self.frozen_resolutions_early = False
        self.bias_ok = 1.0
        self.freeze_fraction = 0.3  # segundos de fraccion del `recorded_at` del freeze sobre el reloj (entero)
        self.run_delay = 0.05  # lo que tarda la corrida de bias entre el `freeze` y su marca de fin
        self.registrations: list[tuple[str, str]] = []
        self.approvals: list[tuple[str, str]] = []
        self.validation_calls: list[str] = []
        self.state_cases: Callable[[str, CaseRecord], tuple[str, str | None, int]] | None = None
        self._seq = 0
        self.registry_transport = RegistryWorld(self)
        self.prom_transport = BiasProm(self)
        self.registry = RegistryClient(
            "http://registry.test", lambda: "token", transport=self.registry_transport
        )
        self.prom = PromClient("http://prom.test", transport=self.prom_transport)
        self.simulator = FakeSimulator(self)
        self._install()

    # ---- estado ---------------------------------------------------------------------------------------------------------------------------------
    @property
    def models(self) -> dict[str, dict[str, Any]]:
        return self.bff.doubles.governance.models

    def add_model(self, model_id: str, state: str, **over: Any) -> None:
        self.models[model_id] = b.model_version(model_id, state, **over)

    def state_of(self, model_id: str) -> str:
        return str(self.models[model_id]["state"])

    def set_state(self, model_id: str, state: str) -> None:
        self.models[model_id]["state"] = state
        self.models[model_id]["updated_at"] = b.ts()

    def seq(self) -> int:
        self._seq += 1
        return self._seq

    def new_case(self, kind: str) -> str:
        case_id = b.uuid_of(10_000 + len(self.cases))
        frozen = PROXY in self.models and self.state_of(PROXY) == "congelado"
        self.cases[case_id] = CaseRecord(self.clock.now(), kind, frozen)
        return case_id

    def at(self, delay: float, action: Callable[[], None]) -> None:
        self.clock.at(delay, action)

    # ---- el sistema ----------------------------------------------------------------------------------------------------------------------------
    def on_batch(self, started: datetime, ids: list[str], seconds: float) -> None:
        """El lote: las `recommendation` (repartidas durante el envio) con el modelo activo; el `freeze` a `freeze_after` s del inicio."""
        scorer = self.recommendation_version or next(
            (m for m, d in self.models.items() if d["state"] == "activo"), REFERENCE
        )
        step = seconds / max(len(ids), 1)
        for number, case_id in enumerate(ids):
            at = started + timedelta(seconds=number * step)
            self.recommendations.append(
                {
                    "entry_type": "recommendation",
                    "seq": self.seq(),
                    "recorded_at": iso(at),
                    "case_id": case_id,
                    "outcome": "favorable",
                    "model_version_id": scorer,
                }
            )
        if self.freeze_after is not None:
            self.clock.at(self.freeze_after - (self.clock.now() - started).total_seconds(), self.freeze)

    def freeze(self) -> None:
        item = freeze_item(self.seq())
        item["model_version_id"] = PROXY
        item["context_package"]["model_version_id"] = PROXY
        item["freeze_id"] = f"freeze-{PROXY}-{item['seq']}"
        recorded = self.clock.now() + timedelta(seconds=self.freeze_fraction)  # el `recorded_at` real lleva microsegundos
        item["frozen_at"] = item["recorded_at"] = recorded.isoformat().replace("+00:00", "Z")
        item["context_package"]["initial_disparity"] = {"attributes": ATTRIBUTES}
        if self.package_variant is not None:
            self.package_variant(item)
        self.freeze_entries.append(item)
        if self.freeze_freezes_model:
            self.set_state(PROXY, "congelado")
        # U9 escribe el `freeze` dentro de la corrida y publica la marca de fin **truncada al segundo** (`publish.py`: `int(finished_at.timestamp())`):
        # un entero, casi siempre del mismo segundo que el `recorded_at`, es decir **por debajo** de el
        finished = recorded + timedelta(seconds=self.run_delay)
        self.bias_runs.append((float(int(finished.timestamp())), self.bias_ok))

    def start_bias(self, every: float = 900.0, first: float = 120.0, runs: int = 40) -> None:
        for number in range(runs):
            self.clock.at(first + number * every, self._bias_run)

    def _bias_run(self) -> None:
        self.bias_runs.append((float(int(self.clock.now().timestamp())), self.bias_ok))
        if (
            self.refreeze_after is not None
            and PROXY in self.models
            and self.state_of(PROXY) == "activo"
            and self._reactivated is not None
        ):
            self.refreeze_after = None
            self.freeze()

    _reactivated: datetime | None = None

    def reactivate(self) -> None:
        self._reactivated = self.clock.now()
        self.set_state(PROXY, "activo")
        self.freeze_entries.append(
            {
                "seq": self.seq(),
                "model_version_id": PROXY,
                "action": "reactivar",
                "recorded_at": iso(self.clock.now()),
            }
        )

    def operator_promotes(self, after: float = 60.0) -> None:
        def promote() -> None:
            self.set_state(PROXY, "activo")
            self.set_state(REFERENCE, "inactivo")

        self.at(after, promote)

    def operator_rolls_back(self, after: float) -> None:
        def back() -> None:
            self.set_state(REFERENCE, "activo")
            self.set_state(PROXY, "inactivo")

        self.at(after, back)

    # ---- los casos que lee el BFF -------------------------------------------------------------------------------------------------------------
    def case_state(self, case_id: str) -> tuple[str, str | None, int]:
        record = self.cases[case_id]
        if self.state_cases is not None:
            return self.state_cases(case_id, record)
        age = (self.clock.now() - record.created).total_seconds()
        if (
            age < 10
        ):  # U8 escribe `attempts` al tomar el trabajo: el caso sigue en `en_evaluacion` con `attempts >= 1` mientras dura la llamada a scoring
            return "en_evaluacion", None, 1
        if record.kind == "probe" and record.frozen_at_creation and not self.probe_listo:
            reactivated = self._reactivated
            if (
                self.sweep_works
                and reactivated is not None
                and (self.clock.now() - reactivated).total_seconds() >= self.sweep_seconds
            ):
                return "listo", None, 1
            return "modelo_congelado", None, 0
        return "listo", None, 1

    def _case(self, call: Any) -> tuple[int, Any]:
        case_id = call.params["id"]
        if case_id not in self.cases:
            return 404, problem(404, "not_found")
        state, cause, attempts = self.case_state(case_id)
        detail = case_detail_json(case_id, state, "favorable")
        detail["attempts"] = attempts
        if cause:
            detail["last_cause"] = cause
        return 200, detail

    # ---- el servicio de gobierno ----------------------------------------------------------------------------------------------------------------
    def _caller(self, call: Any) -> str:
        import jwt

        token = call.headers.get("authorization", "").removeprefix("Bearer ")
        return str(jwt.decode(token, options={"verify_signature": False})["sub"])

    def _register(self, call: Any) -> tuple[int, Any]:
        body = call.json()
        model_id = body["artifact_uri"].split("/")[-2]
        if model_id in self.register_overrides:
            return self.register_overrides[model_id](call)
        if model_id in self.models:
            return 409, problem(409, "conflict_state")
        self.registrations.append((model_id, self._caller(call)))
        self.add_model(model_id, "registrado", registered_by=self._caller(call))
        return 200, self.models[model_id]

    def _validate(self, call: Any) -> tuple[int, Any]:
        model_id = call.params["id"]
        if self.no_policy:
            return 409, problem(409, "conflict_state")
        self.validation_calls.append(model_id)
        self.set_state(model_id, "en_validacion")

        def done() -> None:
            self.set_state(model_id, self.validation_outcome)
            self.models[model_id]["validation_report"] = {
                "auc_roc": "0.8250", "auc_target": "0.8500", "auc_meets_target": False,
                "initial_disparity": {"attributes": [] if self.empty_disparity else ATTRIBUTES},
                "sync_check": {"passed": self.validation_outcome != "validacion_fallida", "predictor_version": model_id, "explainer_version": model_id, "samples_checked": 100},
                "dataset_ref": "ref", "disclaimer": "d",
            }  # fmt: skip

        self.at(self.validation_seconds, done)
        return 200, b.validation_run(model_id)

    def _approve(self, call: Any) -> tuple[int, Any]:
        model_id, caller = call.params["id"], self._caller(call)
        if self.models[model_id].get("registered_by") == caller:
            return 409, problem(409, "conflict_state")
        self.approvals.append((model_id, caller))
        self.models[model_id]["approved_by"] = caller
        self.set_state(model_id, "aprobado")
        return 204, None

    def _frozen_resolution(self, call: Any) -> tuple[int, Any]:
        if self.reactivation_status != 204:
            return self.reactivation_status, problem(self.reactivation_status, "forbidden")
        self.reactivation_calls.append(call.json())
        self.reactivate()
        return 204, None

    reactivation_calls: list[Any] = []

    def _model(self, call: Any) -> tuple[int, Any]:
        found = self.models.get(call.params["id"])
        return (200, found) if found is not None else (404, problem(404, "not_found"))

    def _list(self, call: Any) -> tuple[int, Any]:
        items = list(self.models.values())
        return 200, b.page(items)

    def _install(self) -> None:
        self.reactivation_calls = []
        case = self.bff.doubles.case.responders
        case[("GET", "/v1/cases/{id}")] = self._case
        gov = self.bff.doubles.governance.responders
        gov[("POST", "/v1/models")] = self._register
        gov[("POST", "/v1/models/{id}/validations")] = self._validate
        gov[("POST", "/v1/models/{id}/approval")] = self._approve
        gov[("POST", "/v1/models/{id}/frozen-resolution")] = self._frozen_resolution
        gov[("GET", "/v1/models/{id}")] = self._model
        gov[("GET", "/v1/models")] = self._list

    def close(self) -> None:
        self.bff.close()


def make_package(base: Path, model_id: str) -> Path:
    """Un paquete de U5 chico (los archivos de `manifest.json`): lo que `registro-cuerpo.sh` y `registration_body` leen."""
    directory = base / model_id
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for name in ("predictor.json", "explainer.json", "feature_dictionary.json", "feature_spec.json"):
        data = json.dumps({"model_version_id": model_id, "name": name}).encode()
        (directory / name).write_bytes(data)
        files.append({"name": name, "sha256": hashlib.sha256(data).hexdigest(), "model_version_id": model_id})
    (directory / "manifest.json").write_text(
        json.dumps({"model_version_id": model_id, "files": files}), encoding="utf-8"
    )
    return directory
