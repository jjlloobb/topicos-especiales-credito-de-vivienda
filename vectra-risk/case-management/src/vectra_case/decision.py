"""Validacion de la decision contra la recomendacion del caso (puro; Paso 6; BR-U8-16; US-108, US-502).

Reparto con U0, que no se reimplementa aqui:
- BR-U0-36 (justificacion) y la forma de `used_factors` (`ninguno` solo, 1 a 20, sin repetidos) los aplica el validador de
  `DecisionIn` (`check_justification`, `check_used_factors`): una violacion es un 422 antes de llegar aqui.
- BR-U0-35 es `decision_is_coherent`; U0 dice que U8 la comprueba contra el caso y responde `conflict_state` (409).
- Lo propio de U8 (BR-U8-16): `used_factors` es subconjunto de los `feature_id` del `shap_vector`, o exactamente `["ninguno"]`
  (esa excepcion ya la acepta `DecisionIn`). Una violacion es `validation_error` (422).
Si hay ambas violaciones gana la 422: los datos de la peticion se rechazan antes que el estado del caso.
"""

from dataclasses import dataclass

from vectra_contracts.catalog import ProblemCode
from vectra_contracts.models.api import DecisionIn
from vectra_contracts.outcome import Recommendation
from vectra_contracts.validation import decision_is_coherent

NO_FACTORS = ["ninguno"]


@dataclass(frozen=True)
class Rechazo:
    """Decision rechazada: el codigo del catalogo de U0 (el estado HTTP sale de `PROBLEM_STATUS`) y la razon."""

    code: ProblemCode
    reason: str


def validate_decision(decision: DecisionIn, recommendation: Recommendation) -> Rechazo | None:
    """`None` si la decision se acepta; si no, el `Rechazo` con el `ProblemCode`."""
    if decision.used_factors != NO_FACTORS:
        known = {c.feature_id for c in recommendation.explanation.shap_vector}
        if not set(decision.used_factors) <= known:
            return Rechazo(ProblemCode.VALIDATION_ERROR, "used_factors_not_in_shap_vector")
    if not decision_is_coherent(decision.decision, decision.final_outcome, recommendation.outcome):
        return Rechazo(ProblemCode.CONFLICT_STATE, "decision_incoherent_with_outcome")
    return None
