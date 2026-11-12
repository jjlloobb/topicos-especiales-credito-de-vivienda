"""Reglas de objeto de C03 (BR-U10-01, P-U10-01): funciones puras, sin E/S.

Cada funcion recibe el **estado** que devolvio el destino, tipado con los tipos de U0, y responde aceptar,
403 o 409. Los tres controles se aplican en orden: rol y MFA son del middleware de U0; esta es la tercera.
Una discrepancia de estado es 409 (`conflict_state`): el objeto existe pero no admite la accion. El 403 de
objeto existe en el tipo de respuesta por P-U10-01, pero ninguna regla de estado de C03 lo produce.

Las filas de C03 con «—» o «el caso existe» no llevan funcion: ese 404 lo da el destino.
`OBJECT_RULES` ata cada `operation_id` de las rutas del BFF a su regla o a `None` declarado (deny by default,
P-U10-01); exigir que toda ruta este en el mapa es del Paso 5.
"""

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Final, Literal

from vectra_contracts.catalog import CaseState, FinalOutcome
from vectra_contracts.models.governance import ModelState

DataSourceState = Literal["propuesta", "en_evaluacion", "aprobada", "rechazada"]
PolicyState = Literal["propuesta", "activa", "rechazada", "historica"]
PolicyDecision = Literal["aprobada", "rechazada"]


class ObjectVerdict(StrEnum):
    ACCEPT = "accept"
    FORBIDDEN = "forbidden"
    CONFLICT = "conflict"

    @property
    def status(self) -> int:
        return _STATUS[self]


_STATUS: Final = {
    ObjectVerdict.ACCEPT: 200,
    ObjectVerdict.FORBIDDEN: 403,
    ObjectVerdict.CONFLICT: 409,
}


def _accept_if(condition: bool) -> ObjectVerdict:
    return ObjectVerdict.ACCEPT if condition else ObjectVerdict.CONFLICT


def record_explanation_view(case_state: CaseState) -> ObjectVerdict:
    """C03 «Casos», `record_explanation_view`: el caso esta `listo` o `decidido`."""
    return _accept_if(case_state in (CaseState.LISTO, CaseState.DECIDIDO))


def record_decision(case_state: CaseState) -> ObjectVerdict:
    """C03 «Casos», `record_decision`: el caso esta `listo` (si no, 409)."""
    return _accept_if(case_state is CaseState.LISTO)


def create_applicant_summary(case_state: CaseState, final_outcome: FinalOutcome | None) -> ObjectVerdict:
    """C03 «Casos», `create_applicant_summary`: caso `decidido` con decision final `desfavorable` (BR-U7-13)."""
    return _accept_if(case_state is CaseState.DECIDIDO and final_outcome is FinalOutcome.DESFAVORABLE)


def retry_case(case_state: CaseState, anonymized: bool) -> ObjectVerdict:
    """C03 «Casos», `retry_case`: el caso esta `no_disponible` y no anonimizado (si no, 409)."""
    return _accept_if(case_state is CaseState.NO_DISPONIBLE and not anonymized)


def start_validation(model_state: ModelState) -> ObjectVerdict:
    """C03 «Modelos», `start_validation`: `registrado` o `validacion_fallida` (reintento, BR-U4-01)."""
    return _accept_if(model_state in ("registrado", "validacion_fallida"))


def start_source_comparison(
    source_state: DataSourceState,
    ds_id: str,
    candidate_source_candidate_for: str | None,
    active_version_exists: bool,
) -> ObjectVerdict:
    """C03 «Modelos», `start_source_comparison`: fuente `en_evaluacion`, candidata con `source_candidate_for`
    igual a la fuente y una version `activo` (U4 BR-U4-13)."""
    return _accept_if(
        source_state == "en_evaluacion" and candidate_source_candidate_for == ds_id and active_version_exists
    )


def approve_model(model_state: ModelState) -> ObjectVerdict:
    """C03 «Modelos», `approve_model`: estado `lista_para_aprobacion`."""
    return _accept_if(model_state == "lista_para_aprobacion")


def resolve_frozen(model_state: ModelState) -> ObjectVerdict:
    """C03 «Modelos», `resolve_frozen`: estado `congelado`."""
    return _accept_if(model_state == "congelado")


def retire_model(model_state: ModelState) -> ObjectVerdict:
    """C03 «Modelos», `retire_model`: `inactivo`, `rechazado` o `validacion_fallida` (BR-U4-01)."""
    return _accept_if(model_state in ("inactivo", "rechazado", "validacion_fallida"))


def approve_policy(
    policy_state: PolicyState, decision: PolicyDecision, justification: str | None
) -> ObjectVerdict:
    """C03 «Politicas», `approve_policy`: estado `propuesta`; `rechazada` exige `justification` (2026-11-01).

    La falta de justificacion no es un 403 y el contrato admite solo 403 o 409, asi que sale 409. En la practica
    `PolicyDecisionIn` ya la rechaza con 422 antes de llegar aqui: esta rama es defensa en profundidad.
    """
    justified = decision != "rechazada" or bool(justification and justification.strip())
    return _accept_if(policy_state == "propuesta" and justified)


def decide_data_source(source_state: DataSourceState, has_report: bool) -> ObjectVerdict:
    """C03 «Fuentes de datos», `decide_data_source`: `en_evaluacion` con informe antes/despues."""
    return _accept_if(source_state == "en_evaluacion" and has_report)


# `operation_id` de `RouteContract` (U0) -> regla de objeto. `None` declarado: sin regla de estado en C03.
OBJECT_RULES: Final[Mapping[str, Callable[..., ObjectVerdict] | None]] = {
    "get_api_console_me": None,
    "post_api_console_client-errors": None,
    "get_api_console_cases": None,
    "get_api_console_cases_failures": None,
    "get_api_console_cases_id": None,
    "post_api_console_cases": None,
    "post_api_console_cases_id_explanation-views": record_explanation_view,
    "post_api_console_cases_id_decision": record_decision,
    "post_api_console_cases_id_applicant-summary": create_applicant_summary,
    "post_api_console_cases_id_retry": retry_case,
    "get_api_console_cases_id_dossier": None,
    "post_api_console_integrity-checks": None,
    "get_api_console_integrity-checks_id": None,
    "get_api_console_models": None,
    "get_api_console_models_id": None,
    "post_api_console_models": None,
    "post_api_console_models_id_validations": start_validation,
    "post_api_console_data-sources_id_comparisons": start_source_comparison,
    "post_api_console_models_id_approval": approve_model,
    "post_api_console_models_id_frozen-resolution": resolve_frozen,
    "post_api_console_models_id_retirement": retire_model,
    "get_api_console_policies": None,
    "post_api_console_policies": None,
    "post_api_console_policies_id_approval": approve_policy,
    "get_api_console_data-sources": None,
    "post_api_console_data-sources": None,
    "post_api_console_data-sources_id_decision": decide_data_source,
    "get_api_console_disparity": None,
    "get_api_console_freezes": None,
    "get_api_console_freezes_id": None,
}
