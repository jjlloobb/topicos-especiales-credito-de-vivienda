"""Maquina de estados de la version de modelo (BR-U4-01). Pura, sin E/S (Bloque C, Paso 3).

`transition(state, action, actor, context)` implementa la tabla de BR-U4-01 completa, con las condiciones de BR-U4-02
(una sola version servible), BR-U4-04 (bias solo congela), BR-U4-10 (cuatro ojos) y las filas de US-306 (la fuente de
una version candidata debe estar `aprobada`).

Decisiones que el diseno no fija:

- **Errores propios** (A-1 de U04-T02): `Forbidden` y `ConflictState` se definen aqui y no vienen de `vectra_common`,
  que el contrato `pure-no-io` prohibe en este modulo. El Paso 10 los traduce a `vectra_common.errors.Forbidden` y
  `ConflictState` (403 y 409). `transition` los **lanza** (un resultado ignorado no puede pasar por exito).
- **Actor** (A-2): tipo propio, `Actor(kind, id, role, acr)`, con los nombres de U0 (`Role`, y `kind`/`id`/`acr` de
  `models.registry.Actor`). Sin `auth_time`: la frescura del step-up (15 min) es del endpoint (Paso 10). El MFA es
  `acr == "mfa"` (BR-U4-03).
- **Orden de las comprobaciones** cuando varias fallan a la vez: 1) el actor, a nivel de accion (rol, identidad de
  servicio o sistema, y MFA): `Forbidden`; 2) el estado de origen: `ConflictState`; 3) las condiciones del contexto, en
  este orden: BR-U4-10 (cuatro ojos), fuente de la candidata (US-306), BR-U4-02 (otra version `congelado`):
  `ConflictState`. Asi un actor sin permiso nunca aprende en que estado esta la version.
- BR-U4-10 se resuelve como `ConflictState` (409), igual que en la politica; sin `registered_by` en el contexto falla
  cerrado. La justificacion de `reject`, `reactivar`, `descartar` e `investigar` la valida el endpoint (tipos de U0).
- `activo -> inactivo` (`deactivate`) solo lo hace el sistema dentro del `mark_active` de otra version, y
  `congelado -> inactivo` no existe (candidata F-03 de U04-T01): la funcion la rechaza.
"""

from dataclasses import dataclass
from typing import Final, Literal, NamedTuple

from vectra_contracts.catalog import Role
from vectra_contracts.models.governance import ModelState

Action = Literal[
    "register",
    "start_validation",
    "validation_passed",
    "validation_failed",
    "retry_validation",
    "approve",
    "reject",
    "mark_active",
    "deactivate",
    "freeze",
    "reactivar",
    "descartar",
    "investigar",
    "retire",
]
ACTIONS: Final[tuple[Action, ...]] = (
    "register",
    "start_validation",
    "validation_passed",
    "validation_failed",
    "retry_validation",
    "approve",
    "reject",
    "mark_active",
    "deactivate",
    "freeze",
    "reactivar",
    "descartar",
    "investigar",
    "retire",
)

BIAS_JOB: Final = "bias-monitoring-job"
VALIDATION_JOB: Final = "model-validation-job"
MFA: Final = "mfa"


class Forbidden(Exception):
    """403: el actor no puede hacer esta accion."""

    def __init__(self, reason: str = "actor_not_allowed") -> None:
        super().__init__(reason)
        self.reason = reason


class ConflictState(Exception):
    """409: el estado de la version (o su contexto) no admite la accion."""

    def __init__(self, reason: str = "state_not_allowed") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Actor:
    """Quien actua. `kind = user` lleva `role` y `acr`; un servicio lleva su identidad en `id`; `system` es el sistema."""

    kind: Literal["user", "service", "system"]
    id: str
    role: Role | None = None
    acr: str | None = None

    @property
    def mfa(self) -> bool:
        return self.kind == "user" and self.acr == MFA


@dataclass(frozen=True)
class ModelContext:
    """Lo que la funcion necesita saber, ademas del estado, para las condiciones de BR-U4-01, 02 y 10."""

    registered_by: str | None = None
    #: La version declara `source_candidate_for` y la fuente esta en este estado (`None` si no hay fuente).
    source_candidate_for: str | None = None
    source_state: str | None = None
    #: Otra version servible (BR-U4-02): `activo` pasa a `inactivo` en el mismo `mark_active`; `congelado` lo impide.
    other_servable: Literal["activo", "congelado"] | None = None


class _Who(NamedTuple):
    """Quien puede: un rol de usuario (con MFA), una identidad de servicio o el sistema."""

    kind: Literal["user", "service", "system"]
    name: str | None  # rol o id del servicio
    mfa: bool = False

    def matches(self, actor: Actor) -> bool:
        if actor.kind != self.kind:
            return False
        if self.kind == "user":
            return actor.role is not None and actor.role.value == self.name and (actor.mfa or not self.mfa)
        if self.kind == "service":
            return actor.id == self.name
        return True


_ING = _Who("user", Role.INGENIERO_RIESGO.value, mfa=True)
_CRO = _Who("user", Role.CRO.value, mfa=True)
_CUM = _Who("user", Role.CUMPLIMIENTO.value, mfa=True)
_VALIDATION = _Who("service", VALIDATION_JOB)
_BIAS = _Who("service", BIAS_JOB)
_SYSTEM = _Who("system", None)

#: Quien puede cada accion (BR-U4-01, columna Actor). No depende del estado.
ACTORS: Final[dict[Action, tuple[_Who, ...]]] = {
    "register": (_ING,),
    "start_validation": (_ING,),
    "validation_passed": (_VALIDATION,),
    "validation_failed": (_VALIDATION, _SYSTEM),
    "retry_validation": (_ING,),
    "approve": (_CRO,),
    "reject": (_CRO,),
    "mark_active": (_ING,),
    "deactivate": (_SYSTEM,),
    "freeze": (_BIAS,),
    "reactivar": (_CUM,),
    "descartar": (_CUM,),
    "investigar": (_CUM,),
    "retire": (_CRO,),
}

#: (estado de origen, accion) -> estado de destino (BR-U4-01, columnas Desde y Hacia). `None` = no hay version todavia.
TRANSITIONS: Final[dict[tuple[ModelState | None, Action], ModelState]] = {
    (None, "register"): "registrado",
    ("registrado", "start_validation"): "en_validacion",
    ("en_validacion", "validation_passed"): "lista_para_aprobacion",
    ("en_validacion", "validation_failed"): "validacion_fallida",
    ("validacion_fallida", "retry_validation"): "en_validacion",
    ("lista_para_aprobacion", "approve"): "aprobado",
    ("lista_para_aprobacion", "reject"): "rechazado",
    ("aprobado", "mark_active"): "activo",
    ("inactivo", "mark_active"): "activo",
    ("activo", "deactivate"): "inactivo",
    ("activo", "freeze"): "congelado",
    ("congelado", "reactivar"): "activo",
    ("congelado", "descartar"): "retirado",
    ("congelado", "investigar"): "congelado",  # con `investigation = true`
    ("inactivo", "retire"): "retirado",
    ("rechazado", "retire"): "retirado",
    ("validacion_fallida", "retire"): "retirado",
}


def transition(
    state: ModelState | None, action: Action, actor: Actor, context: ModelContext | None = None
) -> ModelState:
    """Estado nuevo de la version, o `Forbidden` (403) / `ConflictState` (409). Orden de comprobacion: ver el modulo."""
    context = context or ModelContext()
    if not any(who.matches(actor) for who in ACTORS.get(action, ())):
        raise Forbidden("actor_not_allowed")
    target = TRANSITIONS.get((state, action))
    if target is None:
        raise ConflictState("state_not_allowed")
    if action == "approve":
        if context.registered_by is None or actor.id == context.registered_by:  # BR-U4-10
            raise ConflictState("approver_is_registrant")
        _require_approved_source(context)
    if action == "mark_active":
        if state == "aprobado":
            _require_approved_source(context)
        if context.other_servable == "congelado":  # BR-U4-02
            raise ConflictState("active_version_frozen")
    return target


def _require_approved_source(context: ModelContext) -> None:
    """US-306 (BR-U4-01, 13): la candidata de una fuente no se aprueba ni se activa mientras la fuente no este aprobada."""
    if context.source_candidate_for is not None and context.source_state != "aprobada":
        raise ConflictState("source_not_approved")
