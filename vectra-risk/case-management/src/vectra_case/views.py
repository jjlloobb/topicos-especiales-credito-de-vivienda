"""Vistas hacia el BFF (puro; Paso 7; BR-U8-13, 13b, 21; US-107).

`views` recibe la fila del caso con sus datos asociados ya leidos (`CaseRow`); no lee la base (eso es de `api.py`).
Elecciones registradas (la tarea las dejaba abiertas):
- `last_cause` solo va en `en_sincronizacion` y `no_disponible` (BR-U8-13); en los demas estados es `None`. `attempts` siempre va.
- `decision` solo va en `decidido`; `credit_status` solo en `decidido` (BR-U8-21), `None` en el resto aunque la fila lo traiga.
- `applicant_display` es `full_name` + ultimos 4 digitos del documento; vacio si el caso esta anonimizado o no hay identificadores.
- `PersistentFailure` exige `no_disponible` y la fecha de entrada (`ValueError` si no).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from vectra_contracts.catalog import CaseState, CreditStatus
from vectra_contracts.models.api import CaseDetail, DecisionView
from vectra_contracts.models.application import (
    ApplicationView,
    CaseIdentifierGroup,
    CaseSummary,
    PersistentFailure,
)
from vectra_contracts.models.base import validate_nested
from vectra_contracts.outcome import Recommendation
from vectra_contracts.outcome._internal import CONSTRUCTION_TOKEN

SHOWS_RESULT: Final = frozenset({CaseState.LISTO, CaseState.DECIDIDO})
SHOWS_FAILURE: Final = frozenset({CaseState.EN_SINCRONIZACION, CaseState.NO_DISPONIBLE})
# `cases.application` guarda estos dos campos para el monitoreo (FR-ING-05); `ApplicationView` no los tiene.
MONITORING_ONLY: Final = ("sex", "socioeconomic_stratum")
DOC_SUFFIX: Final = 4
# HALLAZGO sobre U0 (no se corrige aqui): `CaseDetail.recommendation` es una `Recommendation`, cuyo validador exige el token privado
# del paquete `outcome` aun cuando el valor ya es una instancia valida; sin el contexto no hay forma publica de construir un `CaseDetail`
# con recomendacion. Se pasa el token solo a la validacion de `CaseDetail`; el cierre es una tarea de U0 (ver bitacora).
_CONTEXT: Final = {"token": CONSTRUCTION_TOKEN}


@dataclass(frozen=True)
class CaseRow:
    """La fila de `cases` y lo que `api.py` leyo de las tablas asociadas."""

    case_id: UUID
    state: CaseState
    channel: str
    created_at: datetime
    application: Mapping[str, Any]
    attempts: int
    last_cause: str | None
    model_frozen_after_recommendation: bool
    anonymized: bool
    identifiers: CaseIdentifierGroup | None = None
    recommendation: Recommendation | None = None
    recommendation_entry_id: str | None = None
    decision: DecisionView | None = None
    credit_status: CreditStatus | None = None
    no_disponible_since: datetime | None = None


def applicant_display(row: CaseRow) -> str:
    if row.anonymized or row.identifiers is None:
        return ""
    return f"{row.identifiers.full_name} {row.identifiers.document_number[-DOC_SUFFIX:]}"


def _result(row: CaseRow) -> Recommendation | None:
    return row.recommendation if row.state in SHOWS_RESULT else None


def case_summary(row: CaseRow) -> CaseSummary:
    rec = _result(row)
    return CaseSummary(
        case_id=row.case_id,
        state=row.state,
        channel=row.channel,
        created_at=row.created_at,
        outcome=None if rec is None else rec.outcome,
        score=None if rec is None else rec.score,
        applicant_display=applicant_display(row),
    )


def application_view(application: Mapping[str, Any]) -> ApplicationView:
    """Quita explicitamente `sex` y `socioeconomic_stratum`: el rechazo de campos extra de `StrictModel` no es la defensa."""
    data = {k: v for k, v in application.items() if k not in MONITORING_ONLY}
    return validate_nested(ApplicationView, data)


def case_detail(row: CaseRow) -> CaseDetail:
    rec = _result(row)
    summary = case_summary(row)
    decided = row.state is CaseState.DECIDIDO
    fields: dict[str, Any] = {
        **summary.model_dump(),
        "application": application_view(row.application),
        "identifiers": None if row.anonymized else row.identifiers,
        "recommendation": rec,
        "recommendation_entry_id": None if rec is None else row.recommendation_entry_id,
        "credit_status": row.credit_status if decided else None,
        "decision": row.decision if decided else None,
        "model_frozen_after_recommendation": row.model_frozen_after_recommendation,
        "anonymized": row.anonymized,
        "attempts": row.attempts,
        "last_cause": row.last_cause if row.state in SHOWS_FAILURE else None,
    }
    return CaseDetail.model_validate(fields, context=_CONTEXT)


def persistent_failure(row: CaseRow) -> PersistentFailure:
    if row.state is not CaseState.NO_DISPONIBLE or row.no_disponible_since is None:
        raise ValueError("persistent_failure_requires_no_disponible_with_since")
    return PersistentFailure(
        case_id=row.case_id,
        channel=row.channel,
        created_at=row.created_at,
        attempts=row.attempts,
        last_cause=row.last_cause or "",
        since=row.no_disponible_since,
    )
