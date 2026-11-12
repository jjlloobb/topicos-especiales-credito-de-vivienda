"""Traduccion de un error de un destino al `Problem` de U0 (BR-U10-04, P-U10-03; US-611). Pura, sin E/S.

La salida siempre valida como `Problem`: sin `detail`, sin trazas y sin campos extra. El `code` del destino se
conserva si pertenece a `ProblemCode`; si no, o si el cuerpo es vacio, no es JSON o no es un objeto, sale
`internal_error` (500). Un 403 o un 404 del destino se propaga con su estado, tambien con un cuerpo malformado.
"""

import json
from typing import Any, Final

from pydantic import ValidationError
from vectra_common import errors as ue
from vectra_common.errors import VectraError, to_problem
from vectra_contracts.catalog import PROBLEM_STATUS, REASON_ALLOWED_CODE, ProblemCode, ProblemReason
from vectra_contracts.models.api import InvalidParam, Problem

# Una clase de error de U0 por codigo del catalogo; `to_problem` pone el titulo y el estado de cada una.
_CLASS_BY_CODE: Final[dict[ProblemCode, type[VectraError]]] = {
    ProblemCode.MALFORMED_REQUEST: ue.MalformedRequest,
    ProblemCode.UNSUPPORTED_MEDIA_TYPE: ue.UnsupportedMediaType,
    ProblemCode.VALIDATION_ERROR: ue.ValidationFailed,
    ProblemCode.UNAUTHENTICATED: ue.Unauthenticated,
    ProblemCode.FORBIDDEN: ue.Forbidden,
    ProblemCode.MFA_REQUIRED: ue.MfaRequired,
    ProblemCode.NOT_FOUND: ue.NotFound,
    ProblemCode.CONFLICT_STATE: ue.ConflictState,
    ProblemCode.PAYLOAD_TOO_LARGE: ue.PayloadTooLarge,
    ProblemCode.RATE_LIMITED: ue.RateLimited,
    ProblemCode.DEPENDENCY_UNAVAILABLE: ue.DependencyUnavailable,
    ProblemCode.INTERNAL_ERROR: VectraError,
    ProblemCode.UNPROCESSABLE_EXPLANATION: ue.UnprocessableExplanation,
    ProblemCode.DEADLINE_EXCEEDED: ue.DeadlineExceeded,
}

# Estados que se propagan tal cual: una falla de autorizacion o de datos, no una caida (BR-U10-03).
_PROPAGATED: Final = {403: ProblemCode.FORBIDDEN, 404: ProblemCode.NOT_FOUND}


def _parse(body: bytes | str) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except (ValueError, RecursionError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _code_of(parsed: dict[str, Any]) -> ProblemCode | None:
    raw = parsed.get("code")
    if not isinstance(raw, str):
        return None
    try:
        return ProblemCode(raw)
    except ValueError:
        return None


def _reason_of(parsed: dict[str, Any], code: ProblemCode) -> ProblemReason | None:
    raw = parsed.get("reason")
    if not isinstance(raw, str):
        return None
    try:
        reason = ProblemReason(raw)
    except ValueError:
        return None
    return reason if REASON_ALLOWED_CODE[reason] is code else None


def _invalid_params_of(parsed: dict[str, Any], code: ProblemCode) -> list[InvalidParam] | None:
    raw = parsed.get("invalid_params")
    if code is not ProblemCode.VALIDATION_ERROR or not isinstance(raw, list):
        return None
    try:
        return [InvalidParam.model_validate(item) for item in raw]
    except ValidationError:
        return None


def translate_error(status: int, body: bytes | str, correlation_id: str) -> Problem:
    """`status` y `body` son los de la respuesta de error del destino; `correlation_id` es el del BFF."""
    parsed = _parse(body)
    code = _code_of(parsed)
    propagated = _PROPAGATED.get(status)
    if propagated is not None and (code is None or PROBLEM_STATUS[code] != status):
        code = propagated
    if code is None or status < 400:
        code = ProblemCode.INTERNAL_ERROR
    error = _CLASS_BY_CODE[code](_reason_of(parsed, code), _invalid_params_of(parsed, code))
    return to_problem(error, correlation_id)
