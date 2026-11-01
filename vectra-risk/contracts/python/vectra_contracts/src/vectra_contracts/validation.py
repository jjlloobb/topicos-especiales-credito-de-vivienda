"""Validaciones cruzadas puras (BR-U0-22..28, 32..38, 95). Sin reloj implicito (NFR-U0-22)."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import cast

from vectra_contracts.catalog import (
    FORBIDDEN_REGISTRY_KEYS,
    Decision,
    FailClosedCause,
    FinalOutcome,
    LocalCause,
    Outcome,
)
from vectra_contracts.dane import DEPARTMENTS, MUNICIPALITY_DEPARTMENT

_EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
_PHONE = re.compile(r"^(\+[1-9]\d{7,14}|\d{10})$")
_CC = re.compile(r"^\d{5,10}$")
_OTHER_DOC = re.compile(r"^[A-Za-z0-9]{5,15}$")
MIN_AGE = 18
MAX_AGE = 120
BUSINESS_TIME_FIELDS = ("evaluated_at", "decided_at", "viewed_at", "frozen_at", "escalated_at")
MAX_LATENESS = timedelta(days=7)


def check_document(document_type: str, document_number: str) -> None:
    pattern = _CC if document_type == "CC" else _OTHER_DOC
    if not pattern.fullmatch(document_number):
        raise ValueError("document_number_invalid")


def check_contact(email: str, phone: str) -> None:
    if not _EMAIL.fullmatch(email):
        raise ValueError("email_invalid")
    if not _PHONE.fullmatch(phone):
        raise ValueError("phone_invalid")


def check_location(department_code: str, municipality_code: str) -> None:
    if department_code not in DEPARTMENTS:
        raise ValueError("department_unknown")
    if MUNICIPALITY_DEPARTMENT.get(municipality_code) != department_code:
        raise ValueError("municipality_not_in_department")


def check_amounts(requested_amount: int, property_value: int) -> None:
    if requested_amount <= 0:
        raise ValueError("requested_amount_not_positive")
    if property_value <= 0:
        raise ValueError("property_value_not_positive")
    if requested_amount > property_value:
        raise ValueError("requested_amount_exceeds_property_value")


def check_rate(rate: str) -> None:
    if not Decimal(0) < Decimal(rate) < Decimal(1):
        raise ValueError("rate_out_of_range")


def age_at(birth_date: date, at: date) -> int:
    return at.year - birth_date.year - ((at.month, at.day) < (birth_date.month, birth_date.day))


def check_age(birth_date: date, evaluated_on: date) -> None:
    """BR-U0-24: depende de la fecha de evaluacion, por eso es una funcion aparte."""
    if not MIN_AGE <= age_at(birth_date, evaluated_on) <= MAX_AGE:
        raise ValueError("age_out_of_range")


def check_free_text(free_text: str) -> None:
    """BR-U0-29: cualquier Unicode imprimible; saltos de linea y tabuladores se admiten."""
    if not all(ch.isprintable() or ch in "\n\r\t" for ch in free_text):
        raise ValueError("free_text_not_printable")


def check_used_factors(used_factors: Sequence[str]) -> None:
    if list(used_factors) == ["ninguno"]:
        return
    if "ninguno" in used_factors:
        raise ValueError("ninguno_combined")
    if not 1 <= len(used_factors) <= 20:
        raise ValueError("used_factors_size")
    if len(set(used_factors)) != len(used_factors):
        raise ValueError("used_factors_repeated")


def check_justification(decision: Decision, justification: str) -> None:
    """BR-U0-36: obligatoria en `se_aparta` y `resuelve_revision`, tras quitar espacios."""
    stripped = len(justification.strip())
    if decision is not Decision.SIGUE and not 20 <= stripped <= 2000:
        raise ValueError("justification_length")


def decision_is_coherent(decision: Decision, final_outcome: FinalOutcome, outcome: Outcome) -> bool:
    """BR-U0-35. U0 fija la regla; U8 la comprueba contra el caso y responde `conflict_state`."""
    if outcome is Outcome.REVISION_REQUERIDA:
        return decision is Decision.RESUELVE_REVISION
    if decision is Decision.SIGUE:
        return final_outcome.value == outcome.value
    if decision is Decision.SE_APARTA:
        return final_outcome.value != outcome.value
    return False


def check_no_forbidden_keys(value: object) -> None:
    """BR-U0-34, BR-U0-95: en cualquier nivel."""
    if isinstance(value, Mapping):
        for key, item in cast(Mapping[object, object], value).items():
            if key in FORBIDDEN_REGISTRY_KEYS:
                raise ValueError("forbidden_key")
            check_no_forbidden_keys(item)
    elif isinstance(value, list | tuple):
        for item in cast(Sequence[object], value):
            check_no_forbidden_keys(item)


def check_fail_closed_payload(
    cause: FailClosedCause | None,
    local_cause: LocalCause | None,
    retryable: bool,
    has_escalated_at: bool,
) -> None:
    """BR-U0-38."""
    if (cause is None) == (local_cause is None):
        raise ValueError("exactly_one_cause")
    if local_cause is not None and not has_escalated_at:
        raise ValueError("local_cause_without_escalated_at")
    expected = (
        cause is not FailClosedCause.MODEL_FROZEN
        if cause is not None
        else (local_cause is not LocalCause.SCORING_REJECTED)
    )
    if retryable != expected:
        raise ValueError("retryable_incoherent")


@dataclass(frozen=True)
class BusinessTimeError:
    field: str
    reason_code: str


def check_business_time(payload: Mapping[str, object], occurred_at: datetime) -> BusinessTimeError | None:
    """BR-U0-37. No corre en el pipeline de validacion: la llama U3 tras la idempotencia.

    `received_at` no es momento de negocio de la entrada y queda fuera de esta cota.
    """
    for name in BUSINESS_TIME_FIELDS:
        moment = payload.get(name)
        if moment is None:
            continue
        if not isinstance(moment, datetime):
            return BusinessTimeError(name, "not_a_timestamp")
        if moment > occurred_at:
            return BusinessTimeError(name, "after_occurred_at")
        if occurred_at - moment > MAX_LATENESS:
            return BusinessTimeError(name, "older_than_7_days")
    return None
