"""Maquina de estados del caso (puro; Paso 4; BR-U8-12; US-107, US-112).

La tabla es la de BR-U8-12 sin el rol: `evaluation`, `sweeps` y `evidence` la usan, y la base la repite en `case_transitions`
(`guard_transition`, migracion 0003). Una prueba compara las dos. `Rechazo` es un valor de retorno, no una excepcion.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from vectra_contracts.catalog import CaseState


class CaseEvent(StrEnum):
    """Los diez eventos de BR-U8-12, uno por fila de la tabla."""

    ALTA = "alta"  # ingesta o alta manual valida (no hay estado previo)
    RECOMMENDATION = "recommendation"
    RETRYABLE_FAILURE = (
        "retryable_failure"  # fail-closed reintentable o scoring sin respuesta, con intentos restantes
    )
    ATTEMPT_6_FAILED = "attempt_6_failed"
    SCORING_REJECTED = "scoring_rejected"  # 4xx no reintentable (BR-U8-08)
    MODEL_FROZEN = "model_frozen"  # FailClosed(model_frozen)
    SWEEP_ACTIVE = "sweep_active"  # barrido con `serving-config` activo
    RETRY = "retry"  # `retry` del CRO
    DECISION_CONFIRMED = "decision_confirmed"
    RETENTION_EXPIRED = "retention_expired"  # retencion vencida sin decision (BR-U8-20)


@dataclass(frozen=True)
class Rechazo:
    """Transicion fuera de la tabla: el estado de partida (`None` = el caso no existe) y el evento."""

    state: CaseState | None
    event: CaseEvent


_S = CaseState
_E = CaseEvent
_IN_FLIGHT: Final = (_S.EN_EVALUACION, _S.EN_SINCRONIZACION)

# (estado de partida, evento) -> estado de llegada. `None` como partida es la fila de creacion.
TRANSITIONS: Final[dict[tuple[CaseState | None, CaseEvent], CaseState]] = {
    (None, _E.ALTA): _S.EN_EVALUACION,
    **{(s, _E.RECOMMENDATION): _S.LISTO for s in _IN_FLIGHT},
    **{(s, _E.RETRYABLE_FAILURE): _S.EN_SINCRONIZACION for s in _IN_FLIGHT},
    (_S.EN_SINCRONIZACION, _E.ATTEMPT_6_FAILED): _S.NO_DISPONIBLE,
    **{(s, _E.SCORING_REJECTED): _S.NO_DISPONIBLE for s in _IN_FLIGHT},
    **{(s, _E.MODEL_FROZEN): _S.MODELO_CONGELADO for s in _IN_FLIGHT},
    (_S.MODELO_CONGELADO, _E.SWEEP_ACTIVE): _S.EN_EVALUACION,
    (_S.NO_DISPONIBLE, _E.RETRY): _S.EN_EVALUACION,
    (_S.LISTO, _E.DECISION_CONFIRMED): _S.DECIDIDO,
    **{
        (s, _E.RETENTION_EXPIRED): _S.VENCIDO
        for s in (_S.EN_EVALUACION, _S.LISTO, _S.EN_SINCRONIZACION, _S.NO_DISPONIBLE, _S.MODELO_CONGELADO)
    },
}

TERMINAL: Final = frozenset({_S.DECIDIDO, _S.VENCIDO})


def transition(state: CaseState | None, event: CaseEvent) -> CaseState | Rechazo:
    """Estado de llegada, o `Rechazo` si el par no esta en la tabla. `state=None` es el alta."""
    target = TRANSITIONS.get((state, event))
    if target is None:
        return Rechazo(state, event)
    return target
