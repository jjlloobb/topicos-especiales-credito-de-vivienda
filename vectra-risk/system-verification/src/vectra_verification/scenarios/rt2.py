"""`rt2-setup` y RT-2 / D2 (U12-T03, Paso 8; BR-U12-04, 06, 07, 10; NFR-U12-11; INF-U12-03). RT-2: un modelo con un sesgo se congela solo, dentro de 30 min, con su paquete completo.

`rt2-setup` (`ingeniero-1` registra y valida, `cro-1` aprueba) acepta de 1 a 5 versiones del proxy; la demo pasa 1 (DD-1) y el codigo no se recorta. `rt2` corre **una corrida por version recibida**, en fases; cada fase es un
sub-resultado con su codigo de «que falto». U12 no promueve, no sincroniza y no abre PR: donde el flujo necesita al operador (`mark_active`, rollback) la seccion **espera** lo observable con el reloj inyectado (P-8) y, si el plazo
vence, devuelve `no ejecutado` con la fase pendiente; la seccion se retoma con el `Rt2State` que devolvio. La reactivacion es un paso separable (`Reactivator`): el modo de la herramienta (`ToolReactivation`, `cumplimiento-1` con
step-up) y, despues, otro que espere al presentador; la **verificacion posterior** (`verify_reactivation`) es la misma. Una regla pura decide con las celdas de `stratified` si `rt2` corre.

Regla de las celdas (precisada en U12-T03, 2026-11-13; decision del usuario, `DECISIONES-LOOP.md` §10): `rt2` se niega **solo si queda corta una celda alcanzable**, una con 30 o mas filas disponibles en `test`; las
inalcanzables (menos de 30 disponibles) no bloquean: se informan con sus filas disponibles y tomadas. El volumen pedido es un piso (`CANDIDATAS.md`): el resultado registra el pedido y el enviado, sin tope.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Protocol

from pydantic import ValidationError
from vectra_contracts.models.governance import FrozenResolutionIn, ModelApprovalIn, ModelVersionDetail
from vectra_contracts.models.monitoring import FreezeContextPackage

from vectra_verification import guard, rt2_latency, sampler
from vectra_verification.clients._api import ApiError
from vectra_verification.clients.bff import BffClient
from vectra_verification.clients.prom import ObsError, PromClient
from vectra_verification.clients.registry import RegistryClient
from vectra_verification.clock import Clock
from vectra_verification.guard import Environment
from vectra_verification.report import FALLA, NO_EJECUTADO, PASA, Result
from vectra_verification.scenarios.common import ScenarioError, Sessions, registration_body
from vectra_verification.scenarios.outcome import Outcome, SubOutcome, combine, from_subresults
from vectra_verification.scenarios.rt5 import STEP, ranged
from vectra_verification.scenarios.waits import poll
from vectra_verification.simulator import SimulationResult

SETUP_ID: Final = "rt2-setup"
CELL_MIN: Final = sampler.MIN_PER_CELL
ENGINEER, APPROVER, COMPLIANCE, ANALYST = "ingeniero-1", "cro-1", "cumplimiento-1", "analista-1"
LIMIT_SECONDS: Final = rt2_latency.LIMIT.total_seconds()
BATCH_VOLUME: Final = 1500
PROBES: Final = 5
POLL: Final = 30.0
OPERATOR_TIMEOUT: Final = 3600.0
VALIDATION_TIMEOUT: Final = 1800.0
FREEZE_TIMEOUT: Final = 2700.0  # mas alla de 1 800 s para registrar la medicion real de una corrida lenta
BIAS_RUNS: Final = 3
BIAS_TIMEOUT: Final = 3600.0
RECONFREEZE_TIMEOUT: Final = 1800.0
SWEEP_SECONDS: Final = 300.0
SWEEP_MARGIN: Final = 120.0
PROBE_TIMEOUT: Final = 180.0
STATE_TIMEOUT: Final = 300.0
BIAS_TS: Final = "max(vectra_bias_last_run_timestamp)"
BIAS_OK: Final = "min(vectra_bias_last_run_ok)"
BIAS_FAILURE: Final = "vectra_bias_last_run_failure"
JUSTIFICATION: Final = "Reactivacion de verificacion (RT-2): version de prueba revisada"
FROZEN: Final = "congelado"
PACKAGE_FIELDS: Final = (
    "before",
    "after",
    "last_7_days",
    "trigger_attribute",
    "implicated",
    "affected_volume",
    "threshold_pp",
    "n_min",
)
PHASES: Final = (
    "celdas", "promocion", "lote", "freeze", "paquete", "congelado", "casos_nuevos", "sigue_congelada", "reactivacion", "no_recongela", "barrido",
)  # fmt: skip


# --- la regla de las celdas -------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CellCheck:
    reachable_short: tuple[sampler.CellReport, ...]
    unreachable_short: tuple[sampler.CellReport, ...]


def classify_cells(short: Sequence[sampler.CellReport], minimum: int = CELL_MIN) -> CellCheck:
    """Pura. De las celdas cortas (`taken < minimum`): las **alcanzables** (`available >= minimum`) bloquean; las inalcanzables se informan. (Precisada en U12-T03, 2026-11-13, `DECISIONES-LOOP.md` §10.)"""
    cut = tuple(c for c in short if c.taken < minimum)
    return CellCheck(
        tuple(c for c in cut if c.available >= minimum), tuple(c for c in cut if c.available < minimum)
    )


def _cell_text(cells: Sequence[sampler.CellReport]) -> str:
    return ", ".join(
        f"{c.attribute}/{c.group}/{c.band}: disponibles={c.available} tomadas={c.taken}" for c in cells
    )


def check_cells(short: Sequence[sampler.CellReport], minimum: int = CELL_MIN) -> CellCheck:
    """`rt2` se niega si queda corta una celda alcanzable (error con las celdas, 0 solicitudes); si no, devuelve las inalcanzables para informarlas."""
    check = classify_cells(short, minimum)
    if check.reachable_short:
        raise ScenarioError("rt2_celda_alcanzable_corta", _cell_text(check.reachable_short))
    return check


# --- el paquete del freeze ----------------------------------------------------------------------------------------------------


def judge_package(freeze: Mapping[str, Any]) -> tuple[str, ...]:
    """Los codigos de lo que le falta al `context_package` de una entrada `freeze` (vacio = completo): cada campo de `FreezeContext` del plan, `data_sources` (puede ir vacia) e `initial_disparity` no vacia."""
    package = freeze.get("context_package")
    if not isinstance(package, Mapping):
        return ("rt2_paquete_ausente",)
    missing = [f"rt2_paquete_{name}_ausente" for name in PACKAGE_FIELDS if name not in package]
    if "data_sources" not in package or not isinstance(package["data_sources"], list):
        missing.append("rt2_paquete_data_sources_ausente")
    initial = package.get("initial_disparity")
    if not isinstance(initial, Mapping) or not initial.get("attributes"):
        missing.append("rt2_paquete_initial_disparity_vacia")
    if missing:
        return tuple(missing)
    try:
        FreezeContextPackage.model_validate(package)
    except ValidationError as error:
        first = error.errors()[0]
        return (f"rt2_paquete_invalido:{'.'.join(str(p) for p in first['loc'])}:{first['type']}",)
    return ()


# --- las corridas de bias (P-5 (a)) -----------------------------------------------------------------------------------------


def count_bias_runs(
    timestamps: Sequence[tuple[float, float]], ok: Sequence[tuple[float, float]], after: float
) -> list[float]:
    """Pura. Las corridas de bias completas y posteriores a `after`: valores distintos de `vectra_bias_last_run_timestamp` mayores que `after`, con `vectra_bias_last_run_ok == 1` en el primer paso en que aparecen. Una corrida fallida no cuenta."""
    ok_at = dict(ok)
    seen: list[float] = []
    for moment, value in sorted(timestamps):
        if value > after and value not in seen and ok_at.get(moment) == 1.0:
            seen.append(value)
    return seen


def _flat(series: Mapping[str, list[tuple[float, float]]]) -> list[tuple[float, float]]:
    return [point for values in series.values() for point in values]


# --- rt2-setup ----------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ProxyVersion:
    """Una version del proxy: su carpeta (`reference-model/.out/proxy/run-N`) y el prefijo de sus archivos en el model-store (por omision, el `model_version_id`)."""

    run: int
    model_version_id: str
    package_dir: Path | None = None
    prefix: str | None = None


def check_versions(versions: Sequence[ProxyVersion]) -> None:
    """Antes de enviar nada: de 1 a 5 versiones y ninguna repetida."""
    if not 1 <= len(versions) <= len(rt2_latency.RUNS):
        raise ScenarioError("rt2_versiones_fuera_de_rango", str(len(versions)))
    ids = [v.model_version_id for v in versions]
    if len(set(ids)) != len(ids):
        raise ScenarioError("rt2_version_repetida", ",".join(sorted(i for i in set(ids) if ids.count(i) > 1)))


def _api_failure(error: ApiError, prefix: str) -> tuple[Result, str]:
    """(resultado, codigo) de un `ApiError`: sin respuesta o 5xx es `no ejecutado`; lo demas es `falla`."""
    if error.status == 0 or error.status >= 500:
        return NO_EJECUTADO, f"{prefix}_dependencia_no_responde"
    return FALLA, f"{prefix}_http_{error.status}_{error.code or 'sin_codigo'}"


def _state(bff: BffClient, model_id: str) -> ModelVersionDetail | None:
    try:
        return bff.get_model(model_id)
    except ApiError as error:
        if error.status == 404:
            return None
        raise


PATH_STATES: Final = ("registrado", "en_validacion", "lista_para_aprobacion", "aprobado")


def _validate_and_wait(
    sessions: Sessions, clock: Clock, version: ProxyVersion, timeout: float
) -> tuple[SubOutcome | None, ModelVersionDetail | None]:
    reader = sessions.reader(ENGINEER)
    model = _state(reader, version.model_version_id)
    name = f"v{version.run}"
    if model is None:
        if version.package_dir is None:
            return SubOutcome(
                name,
                FALLA,
                ("rt2_setup_sin_paquete",),
                "la version no existe y no hay carpeta de paquete para registrarla",
            ), None
        body = registration_body(version.package_dir, version.prefix)
        try:
            sessions.write(ENGINEER, lambda c: c.register_model(body))
        except ApiError as error:
            if error.status != 409:
                result, code = _api_failure(error, "rt2_setup_registro")
                return SubOutcome(name, result, (code,), f"registro: {error}"), None
        model = _state(
            reader, version.model_version_id
        )  # un 409 de una version que ya existe en el camino no es un fallo
        assert model is not None
    if model.state == "registrado":
        try:
            sessions.write(ENGINEER, lambda c: c.start_validation(version.model_version_id))
        except ApiError as error:
            if error.status == 409 and error.code == "conflict_state":
                return SubOutcome(
                    name,
                    NO_EJECUTADO,
                    ("rt2_setup_sin_politica_activa",),
                    "validar sin politica activa (409 conflict_state): falta aprobar una politica",
                ), model
            result, code = _api_failure(error, "rt2_setup_validacion")
            return SubOutcome(name, result, (code,), f"validacion: {error}"), model
    last: list[ModelVersionDetail | None] = [model]

    def done() -> tuple[bool, None]:
        last[0] = _state(reader, version.model_version_id)
        return last[0] is not None and last[0].state not in ("registrado", "en_validacion"), None

    waited = poll(clock, done, interval=POLL, timeout=timeout)
    if not waited.met:
        return SubOutcome(
            name,
            NO_EJECUTADO,
            ("rt2_setup_validacion_no_termina",),
            "la validacion no termino: falta el PR de los InferenceService de staging de la version",
        ), last[0]
    return None, last[0]


def rt2_setup(
    environment: Environment,
    sessions: Sessions,
    clock: Clock,
    versions: Sequence[ProxyVersion],
    *,
    validation_timeout: float = VALIDATION_TIMEOUT,
) -> Outcome:
    """`rt2-setup` (BR-U12-07): registra, valida y aprueba las versiones (de 1 a 5). Termina cuando todas estan `aprobado`; si una queda en `validacion_fallida`, se niega a seguir (0 aprobaciones). Retoma desde el estado de cada version."""
    guard.check_section(environment, SETUP_ID)
    check_versions(versions)
    subs: list[SubOutcome] = []
    readings: dict[str, Any] = {"versions": [v.model_version_id for v in versions]}
    models: dict[str, ModelVersionDetail] = {}
    for version in versions:
        try:
            problem, model = _validate_and_wait(sessions, clock, version, validation_timeout)
        except ApiError as error:
            result, code = _api_failure(error, "rt2_setup")
            problem, model = SubOutcome(f"v{version.run}", result, (code,), str(error)), None
        if problem is not None:
            subs.append(problem)
            continue
        assert model is not None
        models[version.model_version_id] = model
        if model.state == "validacion_fallida":
            subs.append(
                SubOutcome(
                    f"v{version.run}",
                    FALLA,
                    ("rt2_setup_validacion_fallida",),
                    "la version quedo en validacion_fallida (sync_check)",
                )
            )
    if subs:
        readings["approvals_sent"] = 0
        return _setup_outcome(subs, readings, models)
    approvals = 0
    for version in versions:
        model = models[version.model_version_id]
        name = f"v{version.run}"
        approval = ModelApprovalIn(
            decision="aprobado", justification="RT-2: version del proxy aprobada para la verificacion"
        )
        if model.state == "lista_para_aprobacion":
            try:
                sessions.write(APPROVER, _approve(version.model_version_id, approval))
                approvals += 1
            except ApiError as error:
                result, code = _api_failure(error, "rt2_setup_aprobacion")
                subs.append(SubOutcome(name, result, (code,), f"aprobacion: {error}"))
                break
        final = _state(sessions.reader(ENGINEER), version.model_version_id)
        assert final is not None
        if final.state != "aprobado" and final.state in PATH_STATES:
            subs.append(SubOutcome(name, FALLA, ("rt2_setup_no_quedo_aprobado",), f"estado {final.state}"))
        elif final.approved_by is not None and final.approved_by == final.registered_by:
            subs.append(
                SubOutcome(
                    name,
                    FALLA,
                    ("rt2_setup_aprobador_igual_al_registrante",),
                    "approved_by coincide con registered_by",
                )
            )
        else:
            report = final.validation_report
            empty = report is not None and not report.initial_disparity.attributes
            subs.append(
                SubOutcome(
                    name,
                    PASA,
                    readings={
                        "state": final.state,
                        "approved_by_differs": final.approved_by != final.registered_by,
                        "initial_disparity_vacia": empty,
                        "auc_meets_target": report.auc_meets_target if report else None,
                    },
                )
            )
    readings["approvals_sent"] = approvals
    return _setup_outcome(subs, readings, models)


def _approve(model_id: str, approval: ModelApprovalIn) -> Callable[[BffClient], None]:
    def call(client: BffClient) -> None:
        client.approve_model(model_id, approval)

    return call


def _setup_outcome(
    subs: list[SubOutcome], readings: dict[str, Any], models: Mapping[str, ModelVersionDetail]
) -> Outcome:
    readings["initial_disparity_vacia"] = [
        m
        for m, detail in models.items()
        if detail.validation_report is not None and not detail.validation_report.initial_disparity.attributes
    ]
    return from_subresults(
        SETUP_ID,
        "todas las versiones del proxy quedan aprobadas por un aprobador distinto de quien las registro",
        subs,
        readings=readings,
    )


# --- rt2 ----------------------------------------------------------------------------------------------------------------------------


class SimulatorLike(Protocol):
    def select(
        self, scenario: str, volume: int, seed: int, min_per_cell: int = ...
    ) -> tuple[tuple[int, ...], tuple[sampler.CellReport, ...]]: ...

    def run(
        self, scenario: str, volume: int, seed: int, *, rate: float = ..., section: str = ...
    ) -> SimulationResult: ...


class Reactivator(Protocol):
    """El paso de reactivar, separable (decision del usuario para U12-T04): la herramienta lo hace (`ToolReactivation`) o espera a que lo haga el presentador en la consola. La verificacion posterior es la misma."""

    def reactivate(self, model_version_id: str) -> SubOutcome | None:
        """`None` si la reactivacion se pidio; un `SubOutcome` (`falla` o `no ejecutado`) si no se pudo."""


class ToolReactivation:
    def __init__(self, sessions: Sessions) -> None:
        self._sessions = sessions

    def reactivate(self, model_version_id: str) -> SubOutcome | None:
        resolution = FrozenResolutionIn(action="reactivar", justification=JUSTIFICATION)
        try:
            self._sessions.write(COMPLIANCE, lambda c: c.resolve_frozen(model_version_id, resolution, "rt2"))
        except ApiError as error:
            result, code = _api_failure(error, "rt2_reactivacion")
            return SubOutcome("reactivacion", result, (code,), f"reactivacion: {error}")
        return None


@dataclass
class Rt2Params:
    reference_version_id: str
    versions: Sequence[ProxyVersion]
    seed: int
    volume: int = BATCH_VOLUME
    rate: float = 10.0
    probes: int = PROBES
    operator_timeout: float = OPERATOR_TIMEOUT
    freeze_timeout: float = FREEZE_TIMEOUT
    bias_timeout: float = BIAS_TIMEOUT
    wait_for_bias_runs: int = BIAS_RUNS


@dataclass
class Rt2Deps:
    environment: Environment
    clock: Clock
    sessions: Sessions
    simulator: SimulatorLike
    registry: RegistryClient
    prom: PromClient | None
    reactivator: Reactivator | None = None


@dataclass
class VersionState:
    """Lo que una version ya hizo: las fases pasadas y sus datos (para retomar y para el oraculo de latencia)."""

    done: dict[str, SubOutcome] = field(default_factory=dict)
    cells: CellCheck | None = None
    batch: Any = None  # RunReport
    freeze: dict[str, Any] | None = None
    probe_ids: tuple[str, ...] = ()
    reactivated_at: datetime | None = None
    measurement: rt2_latency.Rt2Measurement | None = None
    requested: int = 0
    sent: int = 0


@dataclass
class Rt2State:
    versions: dict[str, VersionState] = field(default_factory=dict)
    last_bias_run: str = ""


@dataclass
class Rt2Result:
    rt2: Outcome
    latency: Outcome
    closing: SubOutcome | None
    state: Rt2State
    pending: str | None  # la fase en que se paro (retomar desde ahi)
    unreachable_cells: tuple[sampler.CellReport, ...]


class Rt2Run:
    def __init__(self, deps: Rt2Deps, params: Rt2Params, state: Rt2State) -> None:
        self.d, self.p, self.state = deps, params, state
        self.queries: list[Any] = []

    # lecturas
    def model(self, model_id: str) -> ModelVersionDetail:
        found = _state(self.d.sessions.reader(COMPLIANCE), model_id)
        if found is None:
            raise ScenarioError("rt2_modelo_desconocido", model_id)
        return found

    def case_state(self, case_id: str) -> tuple[str, str | None]:
        detail = self.d.sessions.reader(ANALYST).get_case(case_id)
        return detail.state, detail.last_cause

    def wait_state(self, model_id: str, wanted: str, timeout: float) -> bool:
        return poll(
            self.d.clock, lambda: (self.model(model_id).state == wanted, None), interval=POLL, timeout=timeout
        ).met

    def freezes(self, model_id: str, since: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        items = self.d.registry.freezes_raw(recorded_from=since)
        mine = [i for i in items if i.get("model_version_id") == model_id]
        return [i for i in mine if "freeze_id" in i], [i for i in mine if "action" in i]

    def bias(self, since: datetime) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        prom = self.d.prom
        assert prom is not None
        end = max(self.d.clock.now(), since)
        ts, q_ts = ranged(prom, BIAS_TS, since, end, STEP)
        ok, q_ok = ranged(prom, BIAS_OK, since, end, STEP)
        self.queries = [q for q in self.queries if q.query not in (BIAS_TS, BIAS_OK)] + [q_ts, q_ok]
        return _flat(ts), _flat(ok)

    def last_bias_note(self) -> str:
        """El estado de la ultima corrida de bias, si Prometheus la tiene (diagnostico de un `freeze` ausente)."""
        if self.d.prom is None:
            return "sin Prometheus: no se puede decir como termino la ultima corrida de bias"
        try:
            now = self.d.clock.now()
            ok = self.d.prom.query(BIAS_OK, now)
            failure = self.d.prom.query(BIAS_FAILURE, now)
            self.queries += [ok, failure]
            value = ok.result[0]["value"][1] if ok.result else "sin dato"
            reasons = (
                ",".join(str(i["metric"].get("reason", "?")) for i in failure.result if i["value"][1] == "1")
                or "-"
            )
            return f"ultima corrida de bias: vectra_bias_last_run_ok={value}, vectra_bias_last_run_failure{{reason}}={reasons}"
        except ObsError:
            return "Prometheus no responde: no se puede decir como termino la ultima corrida de bias"


Phase = Callable[[Rt2Run, ProxyVersion, VersionState, int], SubOutcome]


def _celdas(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    _, short = run.d.simulator.select("stratified", run.p.volume, run.p.seed)
    vs.cells = check_cells(short)  # se niega (ScenarioError) si queda corta una alcanzable
    vs.requested = run.p.volume
    return SubOutcome(
        "celdas",
        PASA,
        readings={
            "unreachable": [_cell_dict(c) for c in vs.cells.unreachable_short],
            "requested": run.p.volume,
        },
    )


def _cell_dict(cell: sampler.CellReport) -> dict[str, Any]:
    return {
        "attribute": cell.attribute,
        "group": cell.group,
        "band": cell.band,
        "available": cell.available,
        "taken": cell.taken,
    }


def _promocion(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    waited = poll(
        run.d.clock,
        lambda: (run.model(version.model_version_id).state == "activo", None),
        interval=POLL,
        timeout=run.p.operator_timeout,
    )
    if not waited.met:
        return SubOutcome(
            "promocion",
            NO_EJECUTADO,
            ("rt2_operador_promocion_pendiente",),
            "el operador no promovio la version: falta mark_active de la version del proxy",
        )
    reference = run.model(run.p.reference_version_id).state
    if reference != "inactivo":
        return SubOutcome(
            "promocion", FALLA, ("rt2_referencia_no_inactiva",), f"la version de referencia quedo {reference}"
        )
    return SubOutcome("promocion", PASA)


def _lote(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    result = run.d.simulator.run("stratified", run.p.volume, run.p.seed, rate=run.p.rate, section="rt2")
    vs.batch = result.report
    vs.sent = result.report.sent
    if result.report.accepted == 0:
        return SubOutcome(
            "lote",
            FALLA,
            ("rt2_lote_sin_solicitudes_aceptadas",),
            f"enviadas {result.report.sent}, aceptadas 0: {result.report.rejected_by_code}",
        )
    return SubOutcome(
        "lote",
        PASA,
        readings={"requested": run.p.volume, "sent": result.report.sent, "accepted": result.report.accepted},
    )


def _freeze(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    started: datetime = vs.batch.started_at
    elapsed = (run.d.clock.now() - started).total_seconds()
    found: list[dict[str, Any]] = []

    def seen() -> tuple[bool, None]:
        freezes, _ = run.freezes(version.model_version_id, started)
        found[:] = [f for f in freezes if _at(f["recorded_at"]) >= started]
        return bool(found), None

    waited = poll(run.d.clock, seen, interval=POLL, timeout=max(0.0, run.p.freeze_timeout - elapsed))
    if not waited.met:
        return SubOutcome(
            "freeze",
            FALLA,
            ("rt2_freeze_ausente",),
            f"no hay entrada freeze de {version.model_version_id} tras {run.p.freeze_timeout:g} s; {run.last_bias_note()}",
        )
    vs.freeze = min(found, key=lambda f: _at(f["recorded_at"]))
    return SubOutcome("freeze", PASA, readings={"freeze_id": vs.freeze.get("freeze_id")})


def _at(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _paquete(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    assert vs.freeze is not None
    missing = judge_package(vs.freeze)
    if missing:
        return SubOutcome("paquete", FALLA, missing, f"al paquete del freeze le falta: {', '.join(missing)}")
    return SubOutcome("paquete", PASA)


def _congelado(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    if not run.wait_state(version.model_version_id, FROZEN, STATE_TIMEOUT):
        return SubOutcome(
            "congelado",
            FALLA,
            ("rt2_version_no_congelada",),
            f"la version esta {run.model(version.model_version_id).state}, no congelado",
        )
    return SubOutcome("congelado", PASA)


def _wait_cases(
    run: Rt2Run, ids: Sequence[str], leave: Sequence[str], timeout: float
) -> dict[str, tuple[str, str | None]]:
    seen: dict[str, tuple[str, str | None]] = {}

    def settled() -> tuple[bool, None]:
        for case in ids:
            seen[case] = run.case_state(case)
        return all(state not in leave for state, _ in seen.values()), None

    poll(run.d.clock, settled, interval=5.0, timeout=timeout)
    return seen


def _casos_nuevos(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    sent = run.d.simulator.run("normal", run.p.probes, run.p.seed + 1, rate=run.p.rate, section="rt2")
    ids = sent.report.case_ids
    vs.probe_ids = ids
    if sent.report.accepted < sent.report.sent or not ids:
        return SubOutcome(
            "casos_nuevos",
            FALLA,
            ("rt2_sonda_rechazada",),
            f"enviadas {sent.report.sent}, aceptadas {sent.report.accepted}: {sent.report.rejected_by_code}",
        )
    states = _wait_cases(run, ids, ("en_evaluacion",), PROBE_TIMEOUT)
    counts: dict[str, int] = {}
    for state, _ in states.values():
        counts[state] = counts.get(state, 0) + 1
    if "listo" in counts:
        return SubOutcome(
            "casos_nuevos",
            FALLA,
            ("rt2_caso_nuevo_en_listo",),
            f"un caso nuevo quedo listo con la version congelada: {counts}",
            readings={"states": counts},
        )
    if set(counts) != {"modelo_congelado"}:
        return SubOutcome(
            "casos_nuevos",
            FALLA,
            ("rt2_caso_nuevo_no_quedo_modelo_congelado",),
            f"estados: {counts}",
            readings={"states": counts},
        )
    return SubOutcome("casos_nuevos", PASA, readings={"states": counts})


def _sigue_congelada(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    if index != 0 or run.p.wait_for_bias_runs <= 0:
        return SubOutcome("sigue_congelada", PASA, readings={"omitida": "solo en la primera version"})
    if run.d.prom is None:
        return SubOutcome(
            "sigue_congelada",
            NO_EJECUTADO,
            ("rt2_prometheus_requerido",),
            "contar las corridas de bias necesita Prometheus (P-5)",
        )
    assert vs.freeze is not None
    recorded = _at(vs.freeze["recorded_at"])
    runs: list[float] = []
    early: list[str] = []

    def three() -> tuple[bool, None]:
        _, resolutions = run.freezes(version.model_version_id, recorded)
        state = run.model(version.model_version_id).state
        if resolutions:
            early[:] = ["rt2_resolucion_antes_de_las_corridas"]
        elif state != FROZEN:
            early[:] = ["rt2_version_dejo_de_estar_congelada"]
        if early:
            return True, None
        ts, ok = run.bias(recorded)
        runs[:] = count_bias_runs(ts, ok, recorded.timestamp())
        return len(runs) >= run.p.wait_for_bias_runs, None

    waited = poll(run.d.clock, three, interval=POLL * 2, timeout=run.p.bias_timeout)
    if early:
        return SubOutcome(
            "sigue_congelada",
            FALLA,
            tuple(early),
            "la version se reactivo o dejo de estar congelada antes de las corridas de bias",
        )
    if not waited.met:
        return SubOutcome(
            "sigue_congelada",
            NO_EJECUTADO,
            ("rt2_corridas_de_bias_pendientes",),
            f"solo {len(runs)} de {run.p.wait_for_bias_runs} corridas completas de bias en el plazo",
        )
    return SubOutcome("sigue_congelada", PASA, readings={"bias_runs": len(runs)})


def verify_reactivation(run: Rt2Run, version: ProxyVersion, vs: VersionState) -> SubOutcome:
    """La verificacion posterior de la reactivacion (la misma con la herramienta o con el presentador): version `activo` y una entrada `frozen_resolution` con `action = reactivar` en `monitoring_freezes`."""
    assert vs.freeze is not None
    recorded = _at(vs.freeze["recorded_at"])
    if not run.wait_state(version.model_version_id, "activo", STATE_TIMEOUT):
        return SubOutcome(
            "reactivacion",
            FALLA,
            ("rt2_version_no_quedo_activa",),
            f"la version esta {run.model(version.model_version_id).state}, no activo",
        )
    _, resolutions = run.freezes(version.model_version_id, recorded)
    mine = [r for r in resolutions if r.get("action") == "reactivar"]
    if not mine:
        return SubOutcome(
            "reactivacion",
            FALLA,
            ("rt2_sin_frozen_resolution_reactivar",),
            "monitoring_freezes no trae una frozen_resolution con action reactivar",
        )
    vs.reactivated_at = max(_at(r["recorded_at"]) for r in mine)
    return SubOutcome("reactivacion", PASA)


def _reactivacion(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    reactivator = run.d.reactivator or ToolReactivation(run.d.sessions)
    refused = reactivator.reactivate(version.model_version_id)
    if refused is not None:
        return refused
    return verify_reactivation(run, version, vs)


def _no_recongela(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    if run.d.prom is None:
        return SubOutcome(
            "no_recongela",
            NO_EJECUTADO,
            ("rt2_prometheus_requerido",),
            "esperar una corrida de bias necesita Prometheus (P-5)",
        )
    assert vs.reactivated_at is not None
    since = vs.reactivated_at
    refrozen: list[str] = []
    runs: list[float] = []

    def after_one_run() -> tuple[bool, None]:
        freezes, _ = run.freezes(version.model_version_id, since)
        if [f for f in freezes if _at(f["recorded_at"]) > since]:
            refrozen[:] = ["rt2_recongelada"]
            return True, None
        ts, ok = run.bias(since)
        runs[:] = count_bias_runs(ts, ok, since.timestamp())
        return len(runs) >= 1, None

    waited = poll(run.d.clock, after_one_run, interval=POLL * 2, timeout=RECONFREEZE_TIMEOUT)
    if refrozen:
        return SubOutcome(
            "no_recongela",
            FALLA,
            ("rt2_recongelada",),
            "un freeze nuevo de la version reactivada el mismo dia",
        )
    if not waited.met:
        return SubOutcome(
            "no_recongela",
            NO_EJECUTADO,
            ("rt2_corrida_de_bias_pendiente",),
            "no hubo una corrida completa de bias tras la reactivacion en el plazo",
        )
    state = run.model(version.model_version_id).state
    if state != "activo":
        return SubOutcome(
            "no_recongela", FALLA, ("rt2_recongelada",), f"tras la corrida de bias la version esta {state}"
        )
    return SubOutcome("no_recongela", PASA, readings={"bias_runs_after": len(runs)})


def _barrido(run: Rt2Run, version: ProxyVersion, vs: VersionState, index: int) -> SubOutcome:
    states = _wait_cases(run, vs.probe_ids, ("modelo_congelado",), SWEEP_SECONDS + SWEEP_MARGIN)
    stuck = [c for c, (state, _) in states.items() if state == "modelo_congelado"]
    if stuck:
        return SubOutcome(
            "barrido",
            FALLA,
            ("rt2_barrido_no_libero_casos",),
            f"{len(stuck)} de {len(states)} casos siguen en modelo_congelado tras el barrido de U8 (300 s mas un margen)",
        )
    return SubOutcome("barrido", PASA)


PHASE_FUNCTIONS: Final[Mapping[str, Phase]] = {
    "celdas": _celdas,
    "promocion": _promocion,
    "lote": _lote,
    "freeze": _freeze,
    "paquete": _paquete,
    "congelado": _congelado,
    "casos_nuevos": _casos_nuevos,
    "sigue_congelada": _sigue_congelada,
    "reactivacion": _reactivacion,
    "no_recongela": _no_recongela,
    "barrido": _barrido,
}


def _latency_phase(run: Rt2Run, version: ProxyVersion, vs: VersionState, number: int) -> SubOutcome:
    """Fase 12: las `recommendation` del lote (por sus `case_id`), todas de la version del proxy; la medicion sale de `rt2_latency.measure`."""
    assert vs.batch is not None and vs.freeze is not None
    cases = set(vs.batch.case_ids)
    items = [
        m
        for m in run.d.registry.metrics(entry_type="recommendation", recorded_from=vs.batch.started_at)
        if str(m.case_id) in cases
    ]
    if not items:
        return SubOutcome(
            "latencia",
            FALLA,
            ("rt2_sin_recommendation_del_lote",),
            "el registro no trae ninguna recommendation del lote",
        )
    others = sorted(
        {m.model_version_id or "-" for m in items if m.model_version_id != version.model_version_id}
    )
    if others:
        return SubOutcome(
            "latencia",
            FALLA,
            ("rt2_lote_puntuado_por_otra_version",),
            f"el lote lo puntuo {','.join(others)}: faltó mark_active de la version del proxy",
        )
    try:
        vs.measurement = rt2_latency.measure(
            number, [m.recorded_at for m in items], _at(vs.freeze["recorded_at"])
        )
    except ValueError as error:
        return SubOutcome("latencia", FALLA, ("rt2_freeze_anterior_al_lote",), str(error))
    return SubOutcome("latencia", PASA, readings={"latency_seconds": vs.measurement.latency_seconds})


def latency_outcome(measurements: Sequence[rt2_latency.Rt2Measurement]) -> Outcome:
    """`RT2-LATENCY` (P-12 (a)): `pasa` si el maximo de las corridas **hechas** es <= 1 800 s; la evidencia dice cuantas fueron (con 1, cita DD-1) y, si falla, trae la medicion."""
    count = len(measurements)
    suffix = f"{count} medicion(es)" + (" (DD-1: una version del proxy en la demo)" if count == 1 else "")
    expected = f"latencia de deteccion maxima <= {LIMIT_SECONDS:g} s; {suffix}"
    readings = {"measurements": [m for m in measurements], "runs": count}
    if not measurements:
        return Outcome(
            "RT2-LATENCY",
            NO_EJECUTADO,
            expected,
            "sin mediciones",
            ("rt2_latencia_sin_mediciones",),
            readings=readings,
        )
    worst = max(m.latency_seconds for m in measurements)
    readings["latency_seconds"] = worst
    if worst <= LIMIT_SECONDS:
        return Outcome("RT2-LATENCY", PASA, expected, expected, (), readings=readings)
    return Outcome(
        "RT2-LATENCY",
        FALLA,
        expected,
        f"latencia maxima {worst:g} s > {LIMIT_SECONDS:g} s; {suffix}",
        ("rt2_latencia_mayor_que_1800s",),
        readings=readings,
    )


def _wait_closing(run: Rt2Run) -> SubOutcome:
    """El cierre (BR-U12-10): el operador vuelve al modelo de referencia (rollback y mark_active). Un campo propio: no cambia el resultado de RT-2 (P-9 (a))."""
    last = run.p.versions[-1].model_version_id

    def back() -> tuple[bool, None]:
        return run.model(run.p.reference_version_id).state == "activo" and run.model(
            last
        ).state == "inactivo", None

    if poll(run.d.clock, back, interval=POLL, timeout=run.p.operator_timeout).met:
        return SubOutcome("cierre", PASA)
    return SubOutcome(
        "cierre",
        NO_EJECUTADO,
        ("rt2_cierre_rollback_pendiente",),
        "el operador no volvio al modelo de referencia: faltan el rollback y mark_active del modelo de referencia",
    )


def run_rt2(deps: Rt2Deps, params: Rt2Params, state: Rt2State | None = None) -> Rt2Result:
    """La seccion `rt2`. Una corrida por version, en fases; se para en la primera fase que falla o queda pendiente (el `Rt2State` devuelto permite retomar). `check_section` y las versiones se validan **antes** de enviar nada."""
    guard.check_section(deps.environment, "rt2")
    state = state or Rt2State()
    ids = [v.model_version_id for v in params.versions]
    try:
        check_versions(params.versions)
    except ScenarioError as error:
        bad = Outcome("RT-2", FALLA, "una corrida por version distinta", str(error), (error.code,))
        return Rt2Result(bad, latency_outcome([]), None, state, None, ())
    run = Rt2Run(deps, params, state)
    subs: list[SubOutcome] = []
    pending: str | None = None
    unreachable: tuple[sampler.CellReport, ...] = ()
    stopped = False
    for number, version in enumerate(params.versions, start=1):
        vs = state.versions.setdefault(version.model_version_id, VersionState())
        for phase in PHASES:
            if stopped:
                break
            name = f"v{version.run}:{phase}"
            if phase in vs.done and vs.done[phase].result == PASA:
                subs.append(_renamed(vs.done[phase], name))
                continue
            try:
                result = PHASE_FUNCTIONS[phase](run, version, vs, number - 1)
            except ApiError as error:
                code_result, code = _api_failure(error, "rt2")
                result = SubOutcome(phase, code_result, (code,), str(error))
            except ObsError as error:
                result = SubOutcome(phase, NO_EJECUTADO, ("rt2_prometheus_no_responde",), str(error))
            subs.append(_renamed(result, name))
            if result.result == PASA:
                vs.done[phase] = result
                continue
            stopped, pending = True, phase
        if vs.cells is not None:
            unreachable = vs.cells.unreachable_short
        if not stopped and vs.batch is not None and vs.freeze is not None:
            pass
        if stopped:
            break
    measurements: list[rt2_latency.Rt2Measurement] = []
    for number, version in enumerate(params.versions, start=1):
        known = state.versions.get(version.model_version_id)
        if known is None or known.batch is None or known.freeze is None:
            continue
        vs = known
        if vs.measurement is None:
            try:
                sub = _latency_phase(run, version, vs, number)
            except (ApiError, ObsError) as error:
                sub = SubOutcome("latencia", NO_EJECUTADO, ("rt2_registro_no_responde",), str(error))
            subs.append(_renamed(sub, f"v{version.run}:latencia"))
        if vs.measurement is not None:
            measurements.append(vs.measurement)
    closing: SubOutcome | None = None
    if not stopped and all(
        f"v{v.run}:barrido" in {s.name for s in subs if s.result == PASA} for v in params.versions
    ):
        closing = _wait_closing(run)
    result_value, missing = combine(subs)
    expected = "RT-2: el modelo con sesgo se congela con su paquete completo, se reactiva y no se recongela; la latencia de deteccion esta dentro del limite"
    readings = {
        "versions": ids,
        "requested": params.volume,
        "sent": [state.versions[i].sent for i in ids if i in state.versions],
        "unreachable_cells": [_cell_dict(c) for c in unreachable],
        "pending_phase": pending,
        "cierre": None if closing is None else {"result": closing.result, "missing": list(closing.missing)},
    }
    rt2 = Outcome(
        "RT-2",
        result_value,
        expected,
        expected
        if result_value == PASA
        else "; ".join(f"{s.name}={s.result}" for s in subs if s.result != PASA),
        missing,
        tuple(subs),
        tuple(run.queries),
        readings,
    )
    return Rt2Result(rt2, latency_outcome(measurements), closing, state, pending, unreachable)


def _renamed(sub: SubOutcome, name: str) -> SubOutcome:
    return SubOutcome(name, sub.result, sub.missing, sub.detail, sub.mandatory, sub.readings)
