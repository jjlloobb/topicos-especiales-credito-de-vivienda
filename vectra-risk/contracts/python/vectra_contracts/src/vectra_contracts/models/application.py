"""Solicitud y vistas de caso (domain-entities §1)."""

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from vectra_contracts.catalog import CaseState, Outcome
from vectra_contracts.models.base import COP, Decimal4, StrictModel, Timestamp, UnitDecimal4
from vectra_contracts.validation import (
    check_amounts,
    check_contact,
    check_document,
    check_free_text,
    check_location,
    check_rate,
)

Str20 = Annotated[str, Field(max_length=20)]
Str40 = Annotated[str, Field(max_length=40)]
DocumentType = Literal["CC", "CE", "PA", "PPT"]
EmploymentType = Literal["asalariado", "independiente", "pensionado"]
Sex = Literal["F", "M", "no_informado"]
Stratum = Literal["1", "2", "3", "4", "5", "6", "no_informado"]


class CaseIdentifierGroup(StrictModel):
    """Grupo de identificacion de §1.1: nunca sale al registro (BR-U0-95)."""

    full_name: Annotated[str, Field(max_length=200)]
    document_type: DocumentType
    document_number: Annotated[str, Field(max_length=15)]
    birth_date: date
    phone: Str20
    email: Annotated[str, Field(max_length=254)]
    address: Annotated[str, Field(max_length=300)]
    municipality_code: Annotated[str, Field(pattern=r"^\d{5}$")]


class ApplicationView(StrictModel):
    """`ApplicationIn` sin identificacion y sin etiquetas de monitoreo (§1.2)."""

    department_code: Annotated[str, Field(pattern=r"^\d{2}$")]
    monthly_income: COP
    other_income: COP
    employment_type: EmploymentType
    employment_months: Annotated[int, Field(ge=0, le=720)]
    monthly_obligations: COP
    max_days_past_due_12m: Annotated[int, Field(ge=0, le=365)]
    property_value: COP
    requested_amount: COP
    term_months: Annotated[int, Field(ge=12, le=360)]
    proposed_rate_ea: Decimal4
    property_condition: Literal["nueva", "usada"]
    channel: Str40
    broker_id: Str40 | None = None
    free_text: Annotated[str, Field(max_length=2000)] | None = None


class ApplicationIn(ApplicationView, CaseIdentifierGroup):
    sex: Sex = "no_informado"
    socioeconomic_stratum: Stratum = "no_informado"

    @model_validator(mode="after")
    def _cross_field(self) -> Self:
        check_document(self.document_type, self.document_number)
        check_contact(self.email, self.phone)
        check_location(self.department_code, self.municipality_code)
        check_amounts(self.requested_amount, self.property_value)
        check_rate(self.proposed_rate_ea)
        if self.free_text is not None:
            check_free_text(self.free_text)
        return self


class CaseRef(StrictModel):
    case_id: UUID
    state: CaseState


class CaseFilter(StrictModel):
    state: list[CaseState] | None = None
    channel: Str40 | None = None
    created_from: Timestamp | None = None
    created_to: Timestamp | None = None
    model_frozen_after_recommendation: bool | None = None
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 20


class PersistentFailure(StrictModel):
    case_id: UUID
    channel: Str40
    created_at: Timestamp
    attempts: int
    last_cause: str
    since: Timestamp


class CaseSummary(StrictModel):
    case_id: UUID
    state: CaseState
    channel: Str40
    created_at: Timestamp
    outcome: Outcome | None = None
    score: UnitDecimal4 | None = None
    applicant_display: str


class CaseIdentifiers(StrictModel):
    case_id: UUID
    identifiers: CaseIdentifierGroup | None = None
    anonymized: bool

    @model_validator(mode="after")
    def _anonymized_without_identifiers(self) -> Self:
        if self.anonymized and self.identifiers is not None:
            raise ValueError("anonymized_with_identifiers")
        return self
