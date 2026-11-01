"""Tipos base del contrato (BR-U0-15; NFR-U0-14)."""

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints
from pydantic_core import to_json

DECIMAL4_PATTERN = r"^-?\d+\.\d{4}$"
DECIMAL_PATTERN = r"^-?\d+(\.\d+)?$"
ISVC_PATTERN = r"^isvc-[0-9a-f]{8}$"


class StrictModel(BaseModel):
    """`strict` y `extra="forbid"`: la entrada se valida con `model_validate_json`."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


def validate_nested[M: BaseModel](model: type[M], value: object) -> M:
    """Valida un valor anidado con las reglas de JSON, para cadenas de fecha o enumerados."""
    return model.model_validate_json(to_json(value))


def _unit_interval(value: str) -> str:
    if not Decimal(0) <= Decimal(value) <= Decimal(1):
        raise ValueError("out_of_unit_interval")
    return value


def _is_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp_not_utc")
    return value.astimezone(UTC)


Decimal4 = Annotated[str, StringConstraints(pattern=DECIMAL4_PATTERN)]
UnitDecimal4 = Annotated[str, StringConstraints(pattern=DECIMAL4_PATTERN), AfterValidator(_unit_interval)]
DecimalStr = Annotated[str, StringConstraints(pattern=DECIMAL_PATTERN)]
COP = Annotated[int, Field(ge=0, le=10**12)]
Timestamp = Annotated[AwareDatetime, AfterValidator(_is_utc)]
InferenceServiceName = Annotated[str, StringConstraints(pattern=ISVC_PATTERN)]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_NON_EMPTY = re.compile(r"\S")
NonEmpty = Annotated[str, StringConstraints(min_length=1, pattern=_NON_EMPTY.pattern)]
