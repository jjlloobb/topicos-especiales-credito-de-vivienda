"""Las evidencias de las cuatro demos (U12-T04, P-4; `report.ELEMENT_IDS`: `journey-7-3`, `journey-7-4`, `rt-5`, `dashboard`). Logica pura: cada una se **deriva** del resultado de su seccion, sin leer nada mas.

`rt3` -> `journey-7-3` (F22 mas la escalada a `no_disponible` y `FailClosedPersistente`); `rt2` -> `journey-7-4` (el paquete y la resolucion con MFA, y que modo de reactivacion se uso); `rt5` -> `rt-5` (la alerta
`CoreWriteAttempt` y el rastro de la corrida). `dashboard` es de `scenarios.u11`. Un `no ejecutado` no da evidencia (BR-U12-11).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any, Final

from vectra_verification.report import FALLA, NO_EJECUTADO, PASA
from vectra_verification.scenarios.outcome import Outcome, SubOutcome

REACTIVATION_MODES: Final = ("tool", "presenter")
MODE_TEXT: Final = {
    "tool": "la herramienta reactivo con el step-up de cumplimiento-1 (el BFF exige MFA)",
    "presenter": "el presentador reactivo en la consola con cumplimiento-2; el step-up (MFA) lo impuso el BFF, no la herramienta",
}


def _find(subs: Sequence[SubOutcome], suffix: str) -> list[SubOutcome]:
    return [s for s in subs if s.name == suffix or s.name.endswith(f":{suffix}")]


def journey_7_3(rt3: Outcome) -> Outcome:
    expected = "D1: con F22 apagado los casos de sonda terminan en fail-closed, escalan a no_disponible y FailClosedPersistente se ve en firing"
    f22 = _find(rt3.subresults, "F22")
    readings = {
        k: v
        for k, v in rt3.readings.items()
        if k
        in (
            "escalated_to_no_disponible",
            "failclosed_persistent_max",
            "failclosed_persistent_alert_firing",
            "prometheus",
        )
    }
    if not f22 or f22[0].result == NO_EJECUTADO:
        return Outcome(
            "journey-7-3",
            NO_EJECUTADO,
            expected,
            "F22 no se ejecuto",
            ("journey_7_3_sin_f22",),
            readings=readings,
        )
    if f22[0].result == FALLA:
        return Outcome(
            "journey-7-3", FALLA, expected, f"F22 fallo: {f22[0].detail}", f22[0].missing, readings=readings
        )
    escalated = rt3.readings.get("escalated_to_no_disponible")
    if escalated is None:
        return Outcome(
            "journey-7-3",
            NO_EJECUTADO,
            expected,
            "no se espero la escalada a no_disponible",
            ("journey_7_3_escalada_no_esperada",),
            readings=readings,
        )
    if escalated is False:
        return Outcome(
            "journey-7-3",
            FALLA,
            expected,
            "los casos de sonda no llegaron a no_disponible dentro del plazo",
            ("journey_7_3_sin_escalada",),
            readings=readings,
        )
    if rt3.readings.get("failclosed_persistent_alert_firing") is not True:
        return Outcome(
            "journey-7-3",
            NO_EJECUTADO,
            expected,
            "la escalada se vio, pero FailClosedPersistente no estaba en firing al leerla (o Prometheus no respondio)",
            ("journey_7_3_alerta_no_vista",),
            readings=readings,
        )
    return Outcome("journey-7-3", PASA, expected, expected, (), readings=readings)


def journey_7_4(subs: Sequence[SubOutcome], mode: str) -> Outcome:
    expected = "D2: el paquete de congelamiento esta completo y la reactivacion quedo registrada como frozen_resolution con MFA"
    readings: dict[str, Any] = {"reactivation_mode": mode, "reactivation": MODE_TEXT[mode]}
    mine = _find(subs, "paquete") + _find(subs, "reactivacion")
    failed = [s for s in mine if s.result == FALLA]
    if failed:
        return Outcome(
            "journey-7-4",
            FALLA,
            expected,
            "; ".join(f"{s.name}: {s.detail}" for s in failed),
            tuple(c for s in failed for c in s.missing),
            readings=readings,
        )
    needed = _find(subs, "paquete") and _find(subs, "reactivacion")
    if not needed or any(s.result != PASA for s in mine):
        return Outcome(
            "journey-7-4",
            NO_EJECUTADO,
            expected,
            "faltan el paquete o la reactivacion",
            ("journey_7_4_incompleta",),
            readings=readings,
        )
    return Outcome("journey-7-4", PASA, expected, expected, (), readings=readings)


def rt_5_demo(rt5: Outcome) -> Outcome:
    expected = "D3: la alerta CoreWriteAttempt se ve en firing tras el Job de RT-5 y la evidencia de la corrida (query_range) la respalda"
    if rt5.result == NO_EJECUTADO:
        return replace(rt5, id="rt-5", expected=expected)
    return replace(
        rt5, id="rt-5", expected=expected, obtained=expected if rt5.result == PASA else rt5.obtained
    )
