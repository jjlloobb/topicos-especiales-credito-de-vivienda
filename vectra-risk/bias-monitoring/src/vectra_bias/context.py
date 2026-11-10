"""Resultado de disparidad del contrato y paquete de contexto de `freeze` (BR-U9-15; PBT-U9-08). Puro: sin E/S.

La supresion de celdas chicas ya la hace la libreria (P-U9-04): este modulo no construye un `CellResult` con tasa propia;
solo traduce lo que la libreria devuelve a los tipos de U0 §9.4 (que ademas rechazan una celda insuficiente con tasa).
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from typing import Any

from vectra_contracts.canonical import canonicalize
from vectra_contracts.models.monitoring import (
    AffectedVolume,
    DepartureRate,
    DisparityResult,
    FreezeContext,
)
from vectra_disparity import (
    ATTRIBUTES,
    BANDS,
    AttributeResult,
    CountTable,
    disparity_by_band,
    model_aggregate,
    quantize4,
    to_dict,
)
from vectra_disparity import __version__ as LIBRARY_VERSION

from vectra_bias.freeze_rule import FreezeDecision

MAX_PACKAGE_BYTES = (
    48 * 1024
)  # BR-U9-15: para que el evento `freeze` quepa en los 64 KiB del registro (BR-U3-07)
NO_DATA = "sin_datos"
UNINFORMED = "no_informado"


def disparity_result(
    population: str,
    model_version_id: str,
    window_from: date,
    window_to: date,
    results: Mapping[str, AttributeResult],
    departure: list[DepartureRate] | None = None,
) -> DisparityResult:
    """`DisparityResult` de U0 con los cuatro atributos (en el orden del catalogo), la mayor agregada y su atributo."""
    ordered = [results[a] for a in ATTRIBUTES]
    best = model_aggregate(ordered)
    payload: dict[str, Any] = {
        "population": population,
        "model_version_id": model_version_id,
        "window_from": window_from.isoformat(),
        "window_to": window_to.isoformat(),
        "attributes": [to_dict(r) for r in ordered],
        "model_aggregate": None if best is None else str(best[1]),
        "trigger_attribute": None if best is None else best[0],
        "departure_rates": None if departure is None else [d.model_dump(mode="json") for d in departure],
    }
    return DisparityResult.model_validate_json(json.dumps(payload))


def measure(
    counts: Mapping[str, CountTable],
    n_min: int,
    population: str,
    model_version_id: str,
    window_from: date,
    window_to: date,
    departure: list[DepartureRate] | None = None,
) -> DisparityResult:
    """Medicion de una poblacion en un rango: `disparity_by_band` de los cuatro atributos a la forma de U0."""
    return disparity_result(
        population,
        model_version_id,
        window_from,
        window_to,
        {a: disparity_by_band(counts, a, n_min) for a in ATTRIBUTES},
        departure,
    )


def departure_rates(marginals: Iterable[Any], n_min: int) -> list[DepartureRate]:
    """Tasa de apartamiento por grupo y banda: `se_aparta / (sigue + se_aparta)` (BR-U9-14); `resuelve_revision` no entra.

    Un grupo y banda con menos de `n_min` decisiones comparables no lleva tasa (misma supresion que las celdas, NFR-U9-31).
    """
    sums: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for m in marginals:
        if m.decision in ("sigue", "se_aparta"):
            acc = sums[(m.group, m.band)]
            acc[0] += m.count if m.decision == "se_aparta" else 0
            acc[1] += m.count
    return [
        DepartureRate(group=g, band=b, rate=str(quantize4(Fraction(a, n))))  # type: ignore[arg-type]
        for (g, b), (a, n) in sorted(sums.items(), key=lambda kv: (kv[0][0], BANDS.index(kv[0][1])))
        if n >= n_min and g != UNINFORMED
    ]


def implicated(
    after: DisparityResult, decision: FreezeDecision, threshold_pp: Decimal
) -> list[dict[str, Any]]:
    """Por atributo que cumplio la regla R4: el atributo, su limite y las bandas cuya diferencia supera el umbral (BR-U9-15)."""
    threshold = Decimal(threshold_pp) / 100
    by_attribute = {a.attribute: a for a in after.attributes}
    out: list[dict[str, Any]] = []
    for met in decision.met:
        bands = [
            {"band": b.band, "difference": b.difference, "extreme_pair": b.extreme_pair}
            for b in by_attribute[met.attribute].bands
            if b.difference is not None and Decimal(b.difference) > threshold
        ]
        out.append({"attribute": met.attribute, "freeze_lower_limit": str(met.limit), "bands": bands})
    return out


def _without_cells(result: DisparityResult | str) -> DisparityResult | str:
    if isinstance(result, str):
        return result
    return result.model_copy(
        update={"attributes": [a.model_copy(update={"cells": []}) for a in result.attributes]}
    )


def size_bytes(context: FreezeContext) -> int:
    return len(canonicalize(context.model_dump(mode="json")))


def build_context_package(
    *,
    model_version_id: str,
    computed_at: datetime,
    threshold_pp: Decimal,
    n_min: int,
    window_days: int,
    schedule: str,
    stale_after_s: int,
    window_start: date,
    before: DisparityResult | None,
    after: DisparityResult,
    last_7_days: DisparityResult | None,
    decision: FreezeDecision,
    affected_volume: AffectedVolume,
    max_bytes: int = MAX_PACKAGE_BYTES,
) -> FreezeContext:
    """Paquete que bias envia a `freeze` (domain-entities §3.1). `None` en `before` o `last_7_days` = `sin_datos`.

    Si el paquete canonico (JCS) supera `max_bytes`, quita en orden las celdas de `before`, las de `last_7_days` y las de
    `after`; conserva siempre las agregadas, las bandas, `trigger_attribute` e `implicated`, y marca `truncated`. El
    congelamiento nunca espera por el tamano: si ni asi cabe, el paquete sale igual (governance lo reduce, BR-U9-16).
    """
    if after.trigger_attribute is None:
        raise ValueError("context_without_trigger_attribute")
    context = FreezeContext(
        model_version_id=model_version_id,
        computed_at=computed_at,
        threshold_pp=str(quantize4(threshold_pp)),
        n_min=n_min,
        window_days=window_days,
        schedule=schedule,
        stale_after_s=stale_after_s,
        library_version=LIBRARY_VERSION,
        window_start=window_start,
        before=NO_DATA if before is None else before,
        after=after,
        last_7_days=NO_DATA if last_7_days is None else last_7_days,
        trigger_attribute=after.trigger_attribute,
        implicated=implicated(after, decision, threshold_pp),  # type: ignore[arg-type]
        affected_volume=affected_volume,
        truncated=False,
    )
    for field in ("before", "last_7_days", "after"):
        if size_bytes(context) <= max_bytes:
            return context
        context = context.model_copy(
            update={field: _without_cells(getattr(context, field)), "truncated": True}
        )
    return context
