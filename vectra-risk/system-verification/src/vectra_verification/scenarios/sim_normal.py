"""`SIM-NORMAL` (U12-T03, Paso 10; BR-U12-02, 06; domain-entities §4.1): el flujo base de D4. `accepted = sent`, un caso por solicitud aceptada y cada caso en `listo` o en un fail-closed documentado.

Entradas: el `RunReport` de la corrida `normal` (los 2 000 de `decisions`) y una sesion de `analista-1`. Cada caso se lee por el BFF (`GET /api/console/cases/{id}`), espaciado por debajo de 20/s por usuario (el limite
`console` del gateway; el reloj inyectado hace la espera). Un caso `decidido` cuenta como llegado a `listo` (P-7 (a): el conductor ya lo decidio); `en_evaluacion` espera hasta un plazo y despues es `falla` con el conteo.
No usa `created_from` ni `created_to`: el filtro de fecha de la bandeja da 422 contra el BFF real (`DECISIONES-LOOP.md` §10, U10-T04). El resultado trae el conteo por estado y por causa y nunca datos del solicitante.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from vectra_verification import guard
from vectra_verification.clients._api import ApiError
from vectra_verification.clients.bff import BffClient
from vectra_verification.clock import Clock
from vectra_verification.guard import Environment
from vectra_verification.report import FALLA, NO_EJECUTADO, PASA
from vectra_verification.scenarios.outcome import Outcome
from vectra_verification.scenarios.rt3 import CATALOG_CAUSES
from vectra_verification.scenarios.waits import poll
from vectra_verification.simulator import RunReport

READ_RATE: Final = 15.0  # lecturas por segundo y usuario: por debajo del limite de 20/s
EVALUATION_TIMEOUT: Final = 600.0
EVALUATION_POLL: Final = 15.0
OK_STATES: Final = ("listo", "decidido", "modelo_congelado")
FAIL_CLOSED_STATES: Final = ("en_sincronizacion", "no_disponible")
EXPECTED: Final = (
    "accepted = sent, un caso por solicitud aceptada y cada caso en listo o en un fail-closed documentado"
)


@dataclass(frozen=True)
class CaseRead:
    state: str | None  # `None`: el BFF no conoce el caso (404)
    cause: str | None = None


def judge(
    sent: int,
    accepted: int,
    rejected_by_code: Mapping[str, int],
    case_ids: Sequence[str],
    reads: Mapping[str, CaseRead],
) -> Outcome:
    """Puro: el resultado con lo leido (`reads`: un `CaseRead` por `case_id`)."""
    missing: list[str] = []
    notes: list[str] = []
    if accepted != sent:
        missing.append("sim_normal_aceptadas_menor_que_enviadas")
        notes.append(f"aceptadas {accepted} de {sent}; rechazos por codigo: {dict(rejected_by_code)}")
    if len(set(case_ids)) != len(case_ids):
        missing.append("sim_normal_case_id_repetido")
        notes.append(f"{len(case_ids) - len(set(case_ids))} case_id repetidos")
    if len(case_ids) != accepted:
        missing.append("sim_normal_casos_distintos_de_aceptadas")
        notes.append(f"{len(case_ids)} case_id para {accepted} aceptadas")
    states: Counter[str] = Counter()
    causes: Counter[str] = Counter()
    bad: Counter[str] = Counter()
    for case_id in case_ids:
        read = reads.get(case_id)
        if read is None or read.state is None:
            bad["sim_normal_caso_desconocido"] += 1
            continue
        states[read.state] += 1
        if read.cause:
            causes[read.cause] += 1
        if read.state in OK_STATES:
            continue
        if read.state in FAIL_CLOSED_STATES:
            if read.cause is None:
                bad["sim_normal_fail_closed_sin_causa"] += 1
            elif read.cause not in CATALOG_CAUSES:
                bad["sim_normal_causa_fuera_del_catalogo"] += 1
        elif read.state == "en_evaluacion":
            bad["sim_normal_casos_en_evaluacion_tras_el_plazo"] += 1
        else:
            bad[f"sim_normal_estado_{read.state}"] += 1
    for code, count in bad.items():
        missing.append(code)
        notes.append(f"{code}: {count} caso(s)")
    readings = {
        "sent": sent,
        "accepted": accepted,
        "states": dict(states),
        "causes": dict(causes),
        "rejected_by_code": dict(rejected_by_code),
    }
    if missing:
        return Outcome("SIM-NORMAL", FALLA, EXPECTED, "; ".join(notes), tuple(missing), readings=readings)
    return Outcome("SIM-NORMAL", PASA, EXPECTED, EXPECTED, (), readings=readings)


def read_cases(
    bff: BffClient, clock: Clock, case_ids: Sequence[str], timeout: float = EVALUATION_TIMEOUT
) -> dict[str, CaseRead]:
    """Lee cada caso (a menos de 20/s) y vuelve a leer los `en_evaluacion` cada 15 s hasta el plazo."""
    reads: dict[str, CaseRead] = {}
    pending: list[str] = list(case_ids)

    def sweep() -> tuple[bool, None]:
        still: list[str] = []
        for number, case_id in enumerate(pending):
            if number:
                clock.sleep(1.0 / READ_RATE)
            try:
                detail = bff.get_case(case_id)
            except ApiError as error:
                if error.status != 404:
                    raise
                reads[case_id] = CaseRead(None)
                continue
            reads[case_id] = CaseRead(str(detail.state), detail.last_cause)
            if str(detail.state) == "en_evaluacion":
                still.append(case_id)
        pending[:] = still
        return not still, None

    poll(clock, sweep, interval=EVALUATION_POLL, timeout=timeout)
    return reads


def sim_normal(
    environment: Environment,
    bff: BffClient,
    clock: Clock,
    report: RunReport,
    *,
    timeout: float = EVALUATION_TIMEOUT,
) -> Outcome:
    """La medicion `SIM-NORMAL` con el `RunReport` de la corrida `normal`. El BFF que no responde (o responde 5xx) es `no ejecutado`."""
    guard.check_section(environment, "decisions")
    try:
        reads = read_cases(bff, clock, report.case_ids, timeout)
    except ApiError as error:
        if error.status == 0 or error.status >= 500:
            return Outcome(
                "SIM-NORMAL", NO_EJECUTADO, EXPECTED, "el BFF no responde", ("sim_normal_bff_no_responde",)
            )
        return Outcome(
            "SIM-NORMAL",
            FALLA,
            EXPECTED,
            f"el BFF respondio {error.status} {error.code}",
            (f"sim_normal_http_{error.status}_{error.code or 'sin_codigo'}",),
        )
    return judge(report.sent, report.accepted, report.rejected_by_code, report.case_ids, reads)
