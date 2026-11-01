"""Jerarquia cerrada de errores y traduccion a `Problem` (P-U0-05, BR-U0-60, 61)."""

import json
from typing import ClassVar, Final

from pydantic import ValidationError
from vectra_contracts.catalog import PROBLEM_STATUS, ProblemCode, ProblemReason
from vectra_contracts.models.api import InvalidParam, Problem

_TITLES: Final[dict[ProblemCode, str]] = {
    ProblemCode.MALFORMED_REQUEST: "La solicitud no es JSON válido",
    ProblemCode.UNSUPPORTED_MEDIA_TYPE: "Tipo de contenido no admitido",
    ProblemCode.VALIDATION_ERROR: "La solicitud no es válida",
    ProblemCode.UNAUTHENTICATED: "Autenticación requerida",
    ProblemCode.FORBIDDEN: "Acción no permitida",
    ProblemCode.MFA_REQUIRED: "Se requiere verificación adicional",
    ProblemCode.NOT_FOUND: "Recurso no encontrado",
    ProblemCode.CONFLICT_STATE: "El estado actual no permite la acción",
    ProblemCode.PAYLOAD_TOO_LARGE: "La solicitud es demasiado grande",
    ProblemCode.RATE_LIMITED: "Demasiadas solicitudes",
    ProblemCode.DEPENDENCY_UNAVAILABLE: "Servicio no disponible temporalmente",
    ProblemCode.INTERNAL_ERROR: "Error interno",
    ProblemCode.UNPROCESSABLE_EXPLANATION: "No se pudo procesar la explicación",
    ProblemCode.DEADLINE_EXCEEDED: "Se agotó el tiempo de la solicitud",
}


class VectraError(Exception):
    code: ClassVar[ProblemCode] = ProblemCode.INTERNAL_ERROR

    def __init__(
        self, reason: ProblemReason | None = None, invalid_params: list[InvalidParam] | None = None
    ) -> None:
        super().__init__(self.code.value)
        self.reason = reason
        self.invalid_params = invalid_params


class MalformedRequest(VectraError):
    code = ProblemCode.MALFORMED_REQUEST


class UnsupportedMediaType(VectraError):
    code = ProblemCode.UNSUPPORTED_MEDIA_TYPE


class ValidationFailed(VectraError):
    code = ProblemCode.VALIDATION_ERROR


class Unauthenticated(VectraError):
    code = ProblemCode.UNAUTHENTICATED


class Forbidden(VectraError):
    code = ProblemCode.FORBIDDEN


class MfaRequired(VectraError):
    code = ProblemCode.MFA_REQUIRED


class NotFound(VectraError):
    code = ProblemCode.NOT_FOUND


class ConflictState(VectraError):
    code = ProblemCode.CONFLICT_STATE


class PayloadTooLarge(VectraError):
    code = ProblemCode.PAYLOAD_TOO_LARGE


class RateLimited(VectraError):
    code = ProblemCode.RATE_LIMITED


class DependencyUnavailable(VectraError):
    code = ProblemCode.DEPENDENCY_UNAVAILABLE


class DependencyTimeout(DependencyUnavailable):
    """Timeout o presupuesto agotado durante el trabajo: 504 (domain-entities §6; U7 §2)."""

    code = ProblemCode.DEADLINE_EXCEEDED


class UnprocessableExplanation(VectraError):
    code = ProblemCode.UNPROCESSABLE_EXPLANATION


class DeadlineExceeded(VectraError):
    code = ProblemCode.DEADLINE_EXCEEDED


def to_problem(error: VectraError, correlation_id: str) -> Problem:
    return Problem(
        type=f"urn:vectra:problem:{error.code.value}",
        title=_TITLES[error.code],
        status=PROBLEM_STATUS[error.code],
        code=error.code,
        correlation_id=correlation_id,
        reason=error.reason,
        invalid_params=error.invalid_params,
    )


def validation_failed(exc: ValidationError) -> ValidationFailed:
    """BR-U0-30: nombre del campo y `reason_code`, nunca el valor recibido."""
    params = [
        InvalidParam(name=".".join(str(part) for part in err["loc"]) or "body", reason_code=err["type"])
        for err in exc.errors(include_input=False, include_url=False, include_context=False)
    ]
    return ValidationFailed(invalid_params=params)


def problem_body(problem: Problem) -> bytes:
    return json.dumps(problem.model_dump(mode="json", exclude_none=True), ensure_ascii=False).encode("utf-8")
