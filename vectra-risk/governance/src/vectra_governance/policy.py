"""Politicas y parametros normativos (BR-U4-10, 11). Pura, sin E/S (Bloque C, Paso 4).

- **Lista normativa** (BR-U0-33): `validate_normative` reutiliza la validacion de U0 (`PolicyDraft`); no duplica la regla
  de solapes.
- **Vigencia** (domain-entities §3.2): `normative_at(policy, dia)`. Las fechas son las de `America/Bogota` (P-U4-05):
  `bogota_date(instante)` convierte un instante UTC a la fecha de Bogota, y `normative_current(policy, ahora)` los une.
  El reloj entra siempre como parametro (`ahora`); este modulo nunca lo lee. El temporizador de las 00:00 de Bogota
  es del Paso 9.
- **Cuatro ojos** (BR-U4-10, PBT-U4-04): aprobar <=> el aprobador es `cro` con MFA y distinto de quien propuso (por
  `sub`). Rol o MFA equivocado: `Forbidden`; el mismo usuario: `ConflictState` (409, BR-U4-10).
- **Activacion** (BR-U4-11): `approve_policy` devuelve los dos cambios de estado (`propuesta -> activa` y
  `activa -> historica`) como una sola unidad; la persistencia y la evidencia son del Paso 8.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from vectra_contracts.catalog import Role
from vectra_contracts.models.governance import NormativeParams, PolicyDraft, PolicyVersion

from vectra_governance.model_fsm import Actor, ConflictState, Forbidden

BOGOTA = ZoneInfo("America/Bogota")


class PolicyInvalid(ValueError):
    """La lista normativa no cumple BR-U0-33 (el motivo es el de U0, p. ej. `normative_overlap`)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_normative(normative: Sequence[NormativeParams]) -> None:
    """BR-U0-33 con la validacion de U0: `PolicyDraft` rechaza solapes y vigencias que terminan antes de empezar."""
    try:
        PolicyDraft(
            cutoff="0.5000", low_confidence_threshold="0.5000", channel_rules=[], normative=list(normative)
        )
    except ValidationError as error:
        raise PolicyInvalid(str(error.errors()[0]["ctx"]["error"])) from error


def bogota_date(instant: datetime) -> date:
    """La fecha de `America/Bogota` de un instante (con zona). Un instante sin zona no es un instante: `ValueError`."""
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("instant_without_timezone")
    return instant.astimezone(BOGOTA).date()


def normative_at(policy: PolicyDraft, day: date) -> NormativeParams | None:
    """El unico `NormativeParams` con `effective_from <= day` y (`effective_to` nulo o `day < effective_to`), o nulo."""
    for item in policy.normative:
        if item.effective_from <= day and (item.effective_to is None or day < item.effective_to):
            return item
    return None


def normative_current(policy: PolicyDraft, now: datetime) -> NormativeParams | None:
    """`normative_at(policy, hoy)`, con `hoy` = la fecha de Bogota de `now` (BR-U4-11)."""
    return normative_at(policy, bogota_date(now))


def check_four_eyes(proposed_by: str, approver: Actor) -> None:
    """BR-U4-10: `cro` con MFA (si no, `Forbidden`) y distinto de quien propuso (si no, `ConflictState`)."""
    if approver.kind != "user" or approver.role != Role.CRO or not approver.mfa:
        raise Forbidden("actor_not_allowed")
    if approver.id == proposed_by:
        raise ConflictState("approver_is_proposer")


@dataclass(frozen=True)
class StateChange:
    policy_version_id: str
    from_state: str
    to_state: str


@dataclass(frozen=True)
class Activation:
    """Los cambios de la activacion: una sola unidad de evidencia (BR-U4-17)."""

    activated: StateChange
    superseded: StateChange | None

    @property
    def changes(self) -> tuple[StateChange, ...]:
        return (self.activated,) if self.superseded is None else (self.activated, self.superseded)


def approve_policy(proposed: PolicyVersion, approver: Actor, active: PolicyVersion | None) -> Activation:
    """Aprobar una `propuesta` la deja `activa` y la `activa` anterior pasa a `historica` (BR-U4-11)."""
    check_four_eyes(proposed.proposed_by, approver)
    if proposed.state != "propuesta":
        raise ConflictState("policy_not_proposed")
    superseded: StateChange | None = None
    if active is not None:
        if active.state != "activa" or active.policy_version_id == proposed.policy_version_id:
            raise ConflictState("active_policy_inconsistent")
        superseded = StateChange(active.policy_version_id, "activa", "historica")
    return Activation(StateChange(proposed.policy_version_id, "propuesta", "activa"), superseded)
