"""RT-3 / D1 (U12-T03, Paso 8; BR-U12-04, 10): un paquete de modelo alterado no llega a servir, y con F22 apagado no sale ninguna `recommendation`.

Sub-resultados: `RT3-a`, `RT3-c` y `RT3-d` (422 de U4 al registrar, con el `reason_code` de la tabla, y la lista de modelos igual antes y despues), `RT3-a-desplegado` y `RT3-d-desplegado`, `RT3-b` y `F22`. P-2 (a), decision del
usuario: RT-3 `pasa` con RT3-a, c, d (y «sin cambio») mas F22; los otros tres se calculan siempre y salen en la evidencia: un `no ejecutado` suyo **no** baja RT-3, un `falla` suyo **si**. Cual es obligatorio es la constante
`MANDATORY`: pasar a P-2 (b) o (c) es cambiar esa constante, no los oraculos.

Sustitutos (P-3 (a)): «sin cambio en `serving-config`» = la lista de modelos del BFF antes y despues (el BFF no expone `governance:read-serving`); la causa del fail-closed = `CaseDetail.last_cause` (la proyeccion `metrics` no trae `fail_closed`).
Lectura (`Rt3Run`) y juicio (funciones `judge_*`, puras) van separados. Las esperas usan el reloj inyectado; el operador (PR de F22, promocion de RT3-b, rollback) se espera, no se sustituye.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from vectra_contracts.catalog import FailClosedCause, LocalCause
from vectra_contracts.models.governance import ModelApprovalIn

from vectra_verification import guard
from vectra_verification.clients._api import ApiError
from vectra_verification.clients.k8s_read import K8sError, K8sRead
from vectra_verification.clients.prom import ObsError, PromClient
from vectra_verification.clients.registry import RegistryClient
from vectra_verification.clock import Clock
from vectra_verification.guard import Environment
from vectra_verification.report import FALLA, NO_EJECUTADO, PASA, Result
from vectra_verification.scenarios.common import (
    INFRA_ERRORS,
    ScenarioError,
    Sessions,
    infra_failure,
    list_all_models,
    registration_body,
    snapshot,
)
from vectra_verification.scenarios.outcome import Outcome, SubOutcome, from_subresults
from vectra_verification.scenarios.rt2 import SimulatorLike, _api_failure
from vectra_verification.scenarios.waits import poll
from vectra_verification.simulator import RunReport

ENGINEER, APPROVER, ANALYST = "ingeniero-1", "cro-1", "analista-1"
REGISTRY_CASES: Final = ("RT3-a", "RT3-c", "RT3-d")
EXPECTED_REASON: Final = {
    "RT3-a": "model_version_id_mismatch_inside:explainer.json",
    "RT3-c": "model_version_id_mismatch_inside:feature_dictionary.json",
    "RT3-d": "model_version_id_mismatch:explainer.json",
}
MANDATORY: Final = frozenset({"RT3-a", "RT3-c", "RT3-d", "sin_cambio_en_modelos", "F22"})  # P-2 (a)
F22_CAUSES: Final = frozenset({FailClosedCause.TIMEOUT.value, FailClosedCause.EXPLAINER_UNAVAILABLE.value})
RT3B_CAUSES: Final = frozenset(
    {FailClosedCause.EXPLAINER_ERROR.value, FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE.value}
)
CATALOG_CAUSES: Final = frozenset(c.value for c in FailClosedCause) | frozenset(c.value for c in LocalCause)
FAIL_CLOSED_STATES: Final = ("en_sincronizacion", "no_disponible")
STAGING: Final = "vectra-staging"
PROBES: Final = 5
POLL: Final = 15.0
ATTEMPTS_TIMEOUT: Final = 900.0
ESCALATION_TIMEOUT: Final = 1500.0  # no_disponible tras 12,4 a 19,3 min (backoff de U8): mas el margen
DEPLOYED_TIMEOUT: Final = 300.0
VALIDATION_TIMEOUT: Final = 1800.0
OPERATOR_TIMEOUT: Final = 3600.0
GAUGE: Final = "max(vectra_cases_failclosed_persistent)"
ALERT: Final = 'ALERTS{alertname="FailClosedPersistente", alertstate="firing"}'


@dataclass(frozen=True)
class Rt3Package:
    """Un paquete RT-3 (`reference-model/.out/adversarial/rt3/<caso>/`) y su prefijo en el model-store: los cuatro llevan el `model_version_id` del modelo de referencia, asi que la convencion `<model_version_id>/` no sirve."""

    case_id: str
    package_dir: Path
    prefix: str


@dataclass
class Rt3Params:
    packages: Mapping[str, Rt3Package]
    seed: int
    deployed: Mapping[str, str] = field(
        default_factory=dict
    )  # `RT3-a` / `RT3-d` -> nombre del InferenceService de `vectra-staging`
    probes: int = PROBES
    wait_for_escalation: bool = False
    attempts_timeout: float = ATTEMPTS_TIMEOUT
    escalation_timeout: float = ESCALATION_TIMEOUT
    deployed_timeout: float = DEPLOYED_TIMEOUT
    operator_timeout: float = OPERATOR_TIMEOUT


@dataclass
class Rt3Deps:
    environment: Environment
    clock: Clock
    sessions: Sessions
    simulator: SimulatorLike
    registry: RegistryClient
    k8s: K8sRead | None = None
    prom: PromClient | None = None


# --- juicios puros ------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RegistrationReading:
    """Lo que respondio el BFF al registrar: `status` 200 = aceptado por U4."""

    status: int
    code: str | None = None
    invalid_params: tuple[tuple[str, str], ...] | None = None


def judge_registration(case_id: str, reading: RegistrationReading) -> SubOutcome:
    """RT3-a, c y d: cumple solo un 422 `validation_error` con `invalid_params` de `name = package` y el `reason_code` de la tabla."""
    name, mandatory = case_id, case_id in MANDATORY
    seen = {"status": reading.status, "code": reading.code, "invalid_params": reading.invalid_params}
    if reading.status == 200:
        return SubOutcome(
            name, FALLA, (f"rt3_{case_id}_aceptado_por_u4",), "U4 acepto un paquete alterado", mandatory, seen
        )
    if reading.status == 0 or reading.status >= 500:
        return SubOutcome(
            name,
            NO_EJECUTADO,
            ("rt3_dependencia_no_responde",),
            f"estado {reading.status} {reading.code}",
            mandatory,
            seen,
        )
    if reading.status != 422 or reading.code != "validation_error":
        return SubOutcome(
            name,
            FALLA,
            (f"rt3_{case_id}_estado_{reading.status}_{reading.code or 'sin_codigo'}",),
            f"se esperaba 422 validation_error y llego {reading.status} {reading.code}",
            mandatory,
            seen,
        )
    packages = [reason for param, reason in reading.invalid_params or () if param == "package"]
    if not packages:
        return SubOutcome(
            name,
            FALLA,
            (f"rt3_{case_id}_sin_invalid_params_package",),
            "el 422 no trae invalid_params con name package",
            mandatory,
            seen,
        )
    if EXPECTED_REASON[case_id] not in packages:
        return SubOutcome(
            name,
            FALLA,
            (f"rt3_{case_id}_reason_code_distinto",),
            f"reason_code {packages}, se esperaba {EXPECTED_REASON[case_id]}",
            mandatory,
            seen,
        )
    return SubOutcome(name, PASA, mandatory=mandatory, readings=seen)


def judge_unchanged(
    before: Mapping[str, str], after: Mapping[str, str], active_before: str | None, active_after: str | None
) -> SubOutcome:
    """«Sin cambio en `serving-config`» (P-3): el mismo conjunto de `model_version_id`, cada uno con su `state`, y la misma version `activo`."""
    name = "sin_cambio_en_modelos"
    added = sorted(set(after) - set(before))
    changed = sorted(m for m in before if m in after and before[m] != after[m])
    removed = sorted(set(before) - set(after))
    if added or removed or changed or active_before != active_after:
        return SubOutcome(
            name,
            FALLA,
            ("rt3_lista_de_modelos_cambio",),
            f"nuevas={added} quitadas={removed} cambiaron={changed} activa {active_before}->{active_after}",
            True,
            {"added": added, "changed": changed},
        )
    return SubOutcome(name, PASA, mandatory=True)


def active_model(models: Mapping[str, str]) -> str | None:
    active = sorted(m for m, state in models.items() if state == "activo")
    return active[0] if active else None


@dataclass(frozen=True)
class CaseReading:
    case_id: str
    state: str
    last_cause: str | None
    attempts: int


@dataclass(frozen=True)
class RecommendationReading:
    case_id: str
    model_version_id: str | None


def judge_f22(cases: Sequence[CaseReading], recommendations: Sequence[RecommendationReading]) -> SubOutcome:
    """F22 apagado: todos los casos de sonda `en_sincronizacion` o `no_disponible`, al menos uno con `timeout` o `explainer_unavailable`, y **ninguna** `recommendation` de ninguna version en la ventana."""
    name = "F22"
    mandatory = name in MANDATORY
    missing: list[str] = []
    notes: list[str] = []
    causes = sorted({c.last_cause or "-" for c in cases})
    counts: dict[str, int] = {}
    for c in cases:
        counts[c.state] = counts.get(c.state, 0) + 1
    readings = {"states": counts, "causes": causes, "recommendations": len(recommendations)}
    if not cases:
        return SubOutcome(
            name,
            FALLA,
            ("rt3_f22_sin_casos_de_sonda",),
            "no hay casos de sonda que leer",
            mandatory,
            readings,
        )
    if any(c.state == "listo" for c in cases):
        missing.append("rt3_f22_caso_en_listo")
        notes.append("un caso de sonda llego a listo con F22 apagado")
    if any(c.state == "en_evaluacion" and c.attempts < 1 for c in cases):
        missing.append("rt3_f22_caso_sin_intentos")
        notes.append("un caso sigue en_evaluacion sin intentos tras el plazo")
    odd = sorted({c.state for c in cases} - {"listo", "en_evaluacion", *FAIL_CLOSED_STATES})
    if odd:
        missing.append("rt3_f22_estado_inesperado")
        notes.append(f"estados fuera del fail-closed: {odd}")
    if not missing and any(c.state == "en_evaluacion" for c in cases):
        missing.append("rt3_f22_caso_sin_estado_final")
        notes.append("hay casos todavia en_evaluacion al vencer el plazo")
    elif not missing and not any(c.state in FAIL_CLOSED_STATES and c.last_cause in F22_CAUSES for c in cases):
        missing.append("rt3_f22_sin_causa_timeout_o_explainer_unavailable")
        notes.append(f"ningun caso con last_cause timeout o explainer_unavailable; causas vistas: {causes}")
    if recommendations:
        first = recommendations[0]
        missing.append("rt3_recommendation_con_f22_apagado")
        notes.append(
            f"{len(recommendations)} recommendation en la ventana; la primera: case_id {first.case_id}, model_version_id {first.model_version_id}"
        )
    if missing:
        return SubOutcome(name, FALLA, tuple(missing), "; ".join(notes), mandatory, readings)
    return SubOutcome(name, PASA, mandatory=mandatory, readings=readings)


def judge_deployed(case_id: str, name: str, ready: bool | None, error: str | None) -> SubOutcome:
    """RT3-a o d desplegado por PR sin registrar: `Ready` no debe ser `True` y sigue sin serlo tras el plazo. La causa `ModelPackageIntegrityFailed` hoy no se puede leer (K16: sin `pods/log` ni `inferenceservices` en `vectra-staging`): `causa_no_leida`."""
    label = f"{case_id}-desplegado"
    mandatory = label in MANDATORY
    if error:
        return SubOutcome(
            label, NO_EJECUTADO, (error,), f"no se pudo leer el InferenceService {name}", mandatory
        )
    if ready:
        return SubOutcome(
            label,
            FALLA,
            (f"rt3_{label}_listo",),
            f"el InferenceService {name} esta Ready con un paquete alterado",
            mandatory,
            {"ready": True},
        )
    return SubOutcome(
        label,
        PASA,
        mandatory=mandatory,
        readings={"ready": False, "causa_no_leida": True, "inference_service": name},
    )


def judge_rt3b(
    registration: RegistrationReading,
    state: str | None,
    cases: Sequence[CaseReading],
    recommendations: Sequence[RecommendationReading],
    model_version_id: str,
) -> SubOutcome:
    """RT3-b: 409 al registrar es `no ejecutado` (comparte `model_version_id` con el modelo de referencia); `validacion_fallida` cumple; si llego a servir, `FailClosed` con `explainer_error` o `feature_dictionary_incomplete` y cero `recommendation` suyas."""
    name, mandatory = "RT3-b", "RT3-b" in MANDATORY
    if registration.status == 409:
        return SubOutcome(
            name,
            NO_EJECUTADO,
            ("rt3b_version_ya_registrada",),
            "el paquete comparte model_version_id con el modelo de referencia ya registrado",
            mandatory,
        )
    if registration.status in (0,) or registration.status >= 500:
        return SubOutcome(
            name, NO_EJECUTADO, ("rt3_dependencia_no_responde",), f"estado {registration.status}", mandatory
        )
    if registration.status != 200:
        return SubOutcome(
            name,
            FALLA,
            ("rt3b_registro_rechazado",),
            f"estado {registration.status} {registration.code}",
            mandatory,
        )
    if state == "validacion_fallida":
        return SubOutcome(name, PASA, mandatory=mandatory, readings={"state": state})
    if state in (None, "registrado", "en_validacion"):
        return SubOutcome(
            name,
            NO_EJECUTADO,
            ("rt3b_validacion_no_termina",),
            f"la validacion no termino (estado {state})",
            mandatory,
        )
    if state in ("lista_para_aprobacion", "aprobado"):
        return SubOutcome(
            name,
            NO_EJECUTADO,
            ("rt3b_promocion_pendiente",),
            f"la version quedo {state}: falta que el operador la promueva",
            mandatory,
        )
    mine = [r for r in recommendations if r.model_version_id == model_version_id]
    if mine:
        return SubOutcome(
            name,
            FALLA,
            ("rt3b_recommendation_de_la_version_alterada",),
            f"la version alterada puntuo el caso {mine[0].case_id}",
            mandatory,
        )
    if not cases or any(c.state not in FAIL_CLOSED_STATES or c.last_cause not in RT3B_CAUSES for c in cases):
        seen = sorted({f"{c.state}/{c.last_cause}" for c in cases})
        return SubOutcome(
            name,
            FALLA,
            ("rt3b_sin_fail_closed_esperado",),
            f"se esperaba fail-closed con explainer_error o feature_dictionary_incomplete: {seen}",
            mandatory,
        )
    return SubOutcome(
        name,
        PASA,
        mandatory=mandatory,
        readings={"state": state, "causes": sorted({c.last_cause or "-" for c in cases})},
    )


# --- lectura -------------------------------------------------------------------------------------------------------------------


class Rt3Run:
    def __init__(self, deps: Rt3Deps, params: Rt3Params) -> None:
        self.d, self.p = deps, params
        self.queries: list[Any] = []

    def register(self, package: Rt3Package) -> RegistrationReading:
        body = registration_body(package.package_dir, package.prefix)
        try:
            self.d.sessions.write(ENGINEER, lambda c: c.register_model(body))
        except ApiError as error:
            return RegistrationReading(error.status, error.code, error.invalid_params)
        return RegistrationReading(200)

    def probe(self, scenario_seed: int) -> tuple[RunReport, datetime]:
        """Envia los casos de sonda (`normal`) con `section = rt3`; devuelve el informe y el inicio de la ventana."""
        started = self.d.clock.now()
        sent = self.d.simulator.run("normal", self.p.probes, scenario_seed, section="rt3")
        return sent.report, started

    def cases(self, ids: Sequence[str], timeout: float) -> list[CaseReading]:
        bff = self.d.sessions.reader(ANALYST)
        seen: dict[str, CaseReading] = {}

        def settled() -> tuple[bool, None]:
            for case_id in ids:
                detail = bff.get_case(case_id)
                seen[case_id] = CaseReading(
                    case_id,
                    detail.state,
                    detail.last_cause,
                    detail.attempts or 0,
                )
            # U8 escribe `attempts` al tomar el trabajo y el caso sigue en `en_evaluacion` mientras la llamada a scoring esta en vuelo: se espera a que salga de `en_evaluacion`
            return all(c.state != "en_evaluacion" for c in seen.values()), None

        poll(self.d.clock, settled, interval=POLL, timeout=timeout)
        return list(seen.values())

    def recommendations(self, since: datetime, until: datetime) -> list[RecommendationReading]:
        items = self.d.registry.metrics(entry_type="recommendation", recorded_from=since, recorded_to=until)
        return [RecommendationReading(str(m.case_id), m.model_version_id) for m in items]

    def deployed_ready(self, name: str) -> tuple[bool | None, str | None]:
        if self.d.k8s is None:
            return None, "rt3_k8s_requerido"
        k8s = self.d.k8s

        def read() -> tuple[bool, bool | None]:
            document = json.loads(k8s.get(f"inferenceservice/{name}", STAGING))
            conditions = {
                c.get("type"): c.get("status") for c in (document.get("status") or {}).get("conditions") or []
            }
            return conditions.get("Ready") == "True", conditions.get("Ready") == "True"

        try:
            waited = poll(self.d.clock, read, interval=POLL * 4, timeout=self.p.deployed_timeout)
        except K8sError as error:
            text = str(error).lower()
            if "forbidden" in text:
                return None, "rt3_k8s_forbidden"
            if "notfound" in text or "not found" in text:
                return None, "rt3_inferenceservice_inexistente"
            return None, "rt3_k8s_no_responde"
        return waited.met, None

    def informative(self) -> dict[str, Any]:
        """Lecturas de `journey-7-3` (U12-T04): el gauge y la alerta `FailClosedPersistente`; no cambian el resultado de RT-3."""
        if self.d.prom is None:
            return {"prometheus": "no disponible"}
        out: dict[str, Any] = {}
        try:
            now = self.d.clock.now()
            gauge, alert = self.d.prom.query(GAUGE, now), self.d.prom.query(ALERT, now)
            self.queries += [gauge, alert]
            out["failclosed_persistent_max"] = float(gauge.result[0]["value"][1]) if gauge.result else None
            out["failclosed_persistent_alert_firing"] = bool(alert.result)
        except ObsError as error:
            out["prometheus"] = str(error)
        return out


def _guarded_registry(run: Rt3Run, case_id: str, package: Rt3Package) -> SubOutcome:
    return judge_registration(case_id, run.register(package))


def _rt3b(run: Rt3Run, package: Rt3Package) -> SubOutcome:
    """RT3-b completo: registra; si pasa, valida; si la validacion pasa, lo aprueba `cro-1` y se espera al operador."""
    reading = run.register(package)
    if reading.status != 200:
        return judge_rt3b(reading, None, [], [], package.case_id)
    model_id = _package_version(package)
    bff = run.d.sessions.reader(ENGINEER)
    try:
        run.d.sessions.write(ENGINEER, lambda c: c.start_validation(model_id))
        waited = poll(
            run.d.clock,
            lambda: (bff.get_model(model_id).state not in ("registrado", "en_validacion"), None),
            interval=POLL * 2,
            timeout=VALIDATION_TIMEOUT,
        )
        state = bff.get_model(model_id).state if waited.met else None
        if state == "lista_para_aprobacion":
            run.d.sessions.write(
                APPROVER,
                lambda c: c.approve_model(
                    model_id,
                    ModelApprovalIn(
                        decision="aprobado",
                        justification="RT-3b: version alterada, se aprueba para probar el fail-closed",
                    ),
                ),
            )
            active = poll(
                run.d.clock,
                lambda: (bff.get_model(model_id).state == "activo", None),
                interval=POLL * 2,
                timeout=run.p.operator_timeout,
            )
            state = "activo" if active.met else "aprobado"
    except ApiError as error:
        result, code = _api_failure(error, "rt3b")
        return SubOutcome("RT3-b", result, (code,), str(error), "RT3-b" in MANDATORY)
    if state != "activo":
        return judge_rt3b(reading, state, [], [], model_id)
    report, since = run.probe(run.p.seed + 2)
    cases = run.cases(report.case_ids, run.p.attempts_timeout)
    return judge_rt3b(reading, state, cases, run.recommendations(since, run.d.clock.now()), model_id)


def _package_version(package: Rt3Package) -> str:
    return str(
        json.loads((package.package_dir / "manifest.json").read_text(encoding="utf-8"))["model_version_id"]
    )


def rt3(deps: Rt3Deps, params: Rt3Params) -> Outcome:
    """La seccion `rt3`. `guard.check_section` antes de la primera solicitud; el registro por `ingeniero-1`; los casos de sonda con `analista-1`. No llama a `resolve_frozen`."""
    guard.check_section(deps.environment, "rt3")
    missing_packages = [c for c in REGISTRY_CASES if c not in params.packages]
    if missing_packages:
        raise ScenarioError("rt3_paquetes_faltan", ",".join(missing_packages))
    run = Rt3Run(deps, params)
    subs: list[SubOutcome] = []
    readings: dict[str, Any] = {}
    try:
        _rt3_steps(deps, params, run, subs, readings)
    except INFRA_ERRORS as error:  # F-05 (ronda 2): un `port-forward` caido o un login que falla no es un incumplimiento; se conservan los sub-resultados ya calculados
        code, detail = infra_failure(error, "rt3")
        readings["interrumpida_tras"] = [s.name for s in subs]
        subs.append(SubOutcome("infraestructura", NO_EJECUTADO, (code,), detail, True))
    return from_subresults(
        "RT-3",
        "RT3-a, c y d rechazados por U4 sin cambios en los modelos, y con F22 apagado ninguna recommendation y casos en fail-closed",
        subs,
        readings=readings,
        queries=run.queries,
    )


def _rt3_steps(
    deps: Rt3Deps, params: Rt3Params, run: Rt3Run, subs: list[SubOutcome], readings: dict[str, Any]
) -> None:
    reader = deps.sessions.reader(ENGINEER)
    try:
        before = snapshot(list_all_models(reader))
        for case_id in REGISTRY_CASES:
            subs.append(_guarded_registry(run, case_id, params.packages[case_id]))
        after = snapshot(list_all_models(reader))
        subs.append(judge_unchanged(before, after, active_model(before), active_model(after)))
    except ApiError as error:
        result, code = _api_failure(error, "rt3")
        subs.append(SubOutcome("registro", result, (code,), str(error), True))
        return
    for case_id in ("RT3-a", "RT3-d"):
        name = params.deployed.get(case_id)
        if name is None:
            subs.append(
                SubOutcome(
                    f"{case_id}-desplegado",
                    NO_EJECUTADO,
                    ("rt3_desplegado_sin_nombre",),
                    "no se dio el InferenceService de staging",
                    f"{case_id}-desplegado" in MANDATORY,
                )
            )
            continue
        ready, failure = run.deployed_ready(name)
        subs.append(judge_deployed(case_id, name, ready, failure))
    if "RT3-b" in params.packages:
        try:
            subs.append(_rt3b(run, params.packages["RT3-b"]))
        except ApiError as error:
            result, code = _api_failure(error, "rt3b")
            subs.append(SubOutcome("RT3-b", result, (code,), str(error), "RT3-b" in MANDATORY))
    else:
        subs.append(
            SubOutcome(
                "RT3-b",
                NO_EJECUTADO,
                ("rt3b_sin_paquete",),
                "no se dio el paquete RT3-b",
                "RT3-b" in MANDATORY,
            )
        )
    try:
        report, since = run.probe(params.seed)
        if report.accepted < report.sent or not report.case_ids:
            subs.append(
                SubOutcome(
                    "F22",
                    FALLA,
                    ("rt3_f22_sonda_rechazada",),
                    f"enviados {report.sent}, aceptados {report.accepted}: {report.rejected_by_code}",
                    True,
                )
            )
        else:
            cases = run.cases(report.case_ids, params.attempts_timeout)
            recommendations = run.recommendations(since, deps.clock.now())
            subs.append(judge_f22(cases, recommendations))
            if params.wait_for_escalation:
                escalated = poll(
                    deps.clock,
                    lambda: (_all_unavailable(run, report.case_ids), None),
                    interval=POLL * 4,
                    timeout=params.escalation_timeout,
                )
                readings["escalated_to_no_disponible"] = escalated.met
                readings.update(run.informative())
    except ApiError as error:
        result, code = _api_failure(error, "rt3")
        subs.append(SubOutcome("F22", result, (code,), str(error), True))


def _all_unavailable(run: Rt3Run, ids: Sequence[str]) -> bool:
    bff = run.d.sessions.reader(ANALYST)
    return all(bff.get_case(i).state == "no_disponible" for i in ids)


def rt3_closing(deps: Rt3Deps, params: Rt3Params, *, timeout: float = ATTEMPTS_TIMEOUT) -> SubOutcome:
    """El cierre de D1 (BR-U12-10), tras revertir el PR de F22: un caso de sonda nuevo llega a `listo`. Un campo propio: no cambia el resultado de RT-3 (P-9 (a))."""
    guard.check_section(deps.environment, "rt3")
    run = Rt3Run(deps, Rt3Params(params.packages, params.seed, probes=1))
    try:
        report, _ = run.probe(params.seed + 3)
        if not report.case_ids:
            return SubOutcome("cierre", FALLA, ("rt3_cierre_sonda_rechazada",), f"{report.rejected_by_code}")
        bff = deps.sessions.reader(ANALYST)
        waited = poll(
            deps.clock,
            lambda: (bff.get_case(report.case_ids[0]).state == "listo", None),
            interval=POLL,
            timeout=timeout,
        )
    except ApiError as error:
        result: Result
        result, code = _api_failure(error, "rt3_cierre")
        return SubOutcome("cierre", result, (code,), str(error))
    if waited.met:
        return SubOutcome("cierre", PASA)
    return SubOutcome(
        "cierre",
        NO_EJECUTADO,
        ("rt3_cierre_f22_sigue_apagado",),
        "el caso de sonda no llego a listo: falta revertir el PR de F22",
    )
