"""Monitoreo de sesgo (domain-entities §9.4)."""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from vectra_contracts.catalog import Decision
from vectra_contracts.models.base import Decimal4, StrictModel, Timestamp
from vectra_contracts.models.features import Attribute, Band

Population = Literal["modelo", "humana"]
ALL_ATTRIBUTES = frozenset({"sexo", "rango_edad", "region", "estrato"})


class MonitoringMarginalCount(StrictModel):
    population: Population
    model_version_id: str
    range_id: str
    attribute: Attribute
    group: str
    band: Band
    result: str
    decision: Decision | None = None
    count: Annotated[int, Field(ge=0)]


class MonitoringRangeRequest(StrictModel):
    range_id: str
    model_version_id: str | None = None
    population: Population
    from_day: date
    to_day: date

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.from_day > self.to_day:
            raise ValueError("range_inverted")
        return self


class DayRange(StrictModel):
    from_day: date
    to_day: date

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.from_day > self.to_day:
            raise ValueError("range_inverted")
        return self


class MonitoringQuery(StrictModel):
    ranges: Annotated[list[MonitoringRangeRequest], Field(min_length=1, max_length=12)]
    include_versions: bool
    unattributable_range: DayRange | None = None


class VersionWindow(StrictModel):
    model_version_id: str
    population: Population
    first_day: date
    last_day: date


class RangeTotals(StrictModel):
    range_id: str
    total_entries: Annotated[int, Field(ge=0)]
    invalid_entries: Annotated[int, Field(ge=0)]


class MonitoringWindow(StrictModel):
    versions: list[VersionWindow]
    counts: list[MonitoringMarginalCount]
    totals: list[RangeTotals]
    unattributable_invalid: Annotated[int, Field(ge=0)]
    invalid_seqs: Annotated[list[int], Field(max_length=100)]
    watermark_seq: int
    lag_seconds: int


class CountCell(StrictModel):
    group: str
    band: Band
    favorable: Annotated[int, Field(ge=0)]
    total: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def _bounded(self) -> Self:
        if self.favorable > self.total:
            raise ValueError("favorable_exceeds_total")
        return self


class CountTable(StrictModel):
    attribute: Attribute
    cells: list[CountCell]


class CellResult(StrictModel):
    group: str
    band: Band
    n: Annotated[int, Field(ge=0)]
    rate: Decimal4 | None = None
    status: Literal["suficiente", "muestra_insuficiente"]

    @model_validator(mode="after")
    def _insufficient_without_rate(self) -> Self:
        if self.status == "muestra_insuficiente" and self.rate is not None:
            raise ValueError("insufficient_cell_with_rate")
        return self


class BandResult(StrictModel):
    band: Band
    difference: Decimal4 | None = None
    extreme_pair: list[str] | None = None
    ci_95: list[Decimal4] | None = None
    n_band: Annotated[int, Field(ge=0)]


class AttributeResult(StrictModel):
    attribute: Attribute
    cells: list[CellResult]
    bands: list[BandResult]
    aggregate: Decimal4 | None = None
    aggregate_ci_95: list[Decimal4] | None = None
    population_difference: Decimal4 | None = None
    population_difference_partial: bool


class DepartureRate(StrictModel):
    group: str
    band: Band
    rate: Decimal4


class DisparityResult(StrictModel):
    population: Population
    model_version_id: str
    window_from: date
    window_to: date
    attributes: list[AttributeResult]
    model_aggregate: Decimal4 | None = None
    trigger_attribute: Attribute | None = None
    departure_rates: list[DepartureRate] | None = None


class FreezeContext(StrictModel):
    model_version_id: str
    computed_at: Timestamp
    threshold_pp: Decimal4
    n_min: int
    window_days: int
    schedule: str
    stale_after_s: int
    library_version: str
    window_start: date
    before: DisparityResult | Literal["sin_datos"]
    after: DisparityResult
    last_7_days: DisparityResult | Literal["sin_datos"]
    trigger_attribute: Attribute
    implicated: list[JsonValue]
    affected_volume: int
    truncated: bool


class InitialDisparity(StrictModel):
    attributes: list[AttributeResult]
    model_aggregate: Decimal4 | None = None
    trigger_attribute: Attribute | None = None
    n_min: int | None = None
    threshold_pp: Decimal4 | None = None
    rule_met: bool | None = None


class Resolution(StrictModel):
    action: Literal["reactivar", "descartar", "investigar"]
    recorded_at: Timestamp


class FreezeContextPackage(FreezeContext):
    """`FreezeContext` mas lo que agrega governance (BR-U9-16)."""

    data_sources: list[JsonValue]
    initial_disparity: InitialDisparity


class FreezeRecord(StrictModel):
    freeze_id: str
    model_version_id: str
    frozen_at: Timestamp
    context_package: FreezeContextPackage
    resolutions: list[Resolution]

    @field_validator("resolutions")
    @classmethod
    def _ordered(cls, value: list[Resolution]) -> list[Resolution]:
        if [r.recorded_at for r in value] != sorted(r.recorded_at for r in value):
            raise ValueError("resolutions_not_ordered")
        return value


class CompareSourceRequest(StrictModel):
    source_id: str
    pre: list[CountTable]
    post: list[CountTable]

    @model_validator(mode="after")
    def _four_attributes(self) -> Self:
        for tables in (self.pre, self.post):
            attributes = [table.attribute for table in tables]
            if len(attributes) != 4 or set(attributes) != ALL_ATTRIBUTES:
                raise ValueError("attributes_must_be_the_four_without_repeat")
        return self


class SourceCountsIn(StrictModel):
    pre: list[CountTable]
    post: list[CountTable]


class PrePostReport(StrictModel):
    source_id: str
    pre: DisparityResult
    post: DisparityResult
    delta: Decimal4 | None = None
    threshold_pp: Decimal4
    n_min: int
    truncated: bool
    disclaimer: str


class DisparityView(StrictModel):
    model_version_id: str
    window: DayRange
    computed_at: Timestamp
    model: DisparityResult
    human: DisparityResult
    threshold_pp: Decimal4
    n_min: int
    window_days: int
    schedule: str
    stale_after_s: int
    invalid_entries: int
    disclaimer: str


class FreezeSummary(StrictModel):
    freeze_id: str
    model_version_id: str
    frozen_at: Timestamp
    trigger_attribute: Attribute
    model_aggregate: Decimal4 | None = None
    resolution: Resolution | None = None
