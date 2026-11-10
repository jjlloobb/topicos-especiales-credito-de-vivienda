"""`compare_source` (BR-U9-17; US-306; F25): `PrePostReport` de dos juegos de tablas de conteo. No guarda nada.

U0 ya exige los cuatro atributos sin repetir y conteos >= 0 (`CompareSourceRequest`). Aqui se valida ademas el catalogo de U0 §2.2:
un grupo o una banda fuera del catalogo (o una celda repetida) es `422 validation_error` y no se calcula nada. Los 22 grupos salen
de los `Literal` de U0, no de una lista escrita a mano. El informe canonico no supera 48 KiB (BR-U9-17): si no cabe, quita las celdas
de `pre` y despues las de `post` y marca `truncated`; las agregadas, las bandas y `delta` quedan siempre.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final, get_args

from vectra_common.errors import ValidationFailed
from vectra_contracts.canonical import canonicalize
from vectra_contracts.models.api import InvalidParam
from vectra_contracts.models.application import Sex, Stratum
from vectra_contracts.models.features import Band, RangoEdad, Region
from vectra_contracts.models.monitoring import (
    AttributeDelta,
    CompareSourceRequest,
    DisparityResult,
    PrePostDelta,
    PrePostReport,
)
from vectra_contracts.models.monitoring import (
    CountTable as ContractTable,
)
from vectra_disparity import ATTRIBUTES, CountCell, CountTable, quantize4

from vectra_bias import config
from vectra_bias.context import MAX_PACKAGE_BYTES, measure
from vectra_bias.dashboard import DISCLAIMER, MODEL

CATALOG: Final[dict[str, frozenset[str]]] = {
    "sexo": frozenset(get_args(Sex)),
    "rango_edad": frozenset(get_args(RangoEdad)),
    "region": frozenset(get_args(Region)),
    "estrato": frozenset(get_args(Stratum)),
}
BANDS: Final = frozenset(get_args(Band))
#: Una fuente no tiene ventana ni version de modelo: el informe lleva estas etiquetas en los campos que `DisparityResult` exige.
EPOCH: Final = date(1970, 1, 1)


def validate_catalog(request: CompareSourceRequest) -> None:
    """422 `validation_error` con el nombre del campo y un codigo estable, nunca el valor recibido."""
    problems: list[InvalidParam] = []
    for side in ("pre", "post"):
        for t, table in enumerate(getattr(request, side)):
            seen: set[tuple[str, str]] = set()
            for c, cell in enumerate(table.cells):
                where = f"{side}.{t}.cells.{c}"
                if cell.group not in CATALOG[table.attribute]:
                    problems.append(InvalidParam(name=f"{where}.group", reason_code="group_not_in_catalog"))
                if cell.band not in BANDS:
                    problems.append(InvalidParam(name=f"{where}.band", reason_code="band_not_in_catalog"))
                if (cell.group, cell.band) in seen:
                    problems.append(InvalidParam(name=where, reason_code="duplicate_cell"))
                seen.add((cell.group, cell.band))
    if problems:
        raise ValidationFailed(invalid_params=problems)


def _counts(tables: list[ContractTable]) -> dict[str, CountTable]:
    return {
        t.attribute: CountTable(
            t.attribute, tuple(CountCell(c.group, c.band, c.favorable, c.total) for c in t.cells)
        )
        for t in tables
    }


def _difference(post: str | None, pre: str | None) -> str | None:
    if post is None or pre is None:
        return None
    return str(quantize4(Decimal(post) - Decimal(pre)))


def delta_of(pre: DisparityResult, post: DisparityResult) -> PrePostDelta:
    """`post - pre` de cada agregada (en el orden del catalogo) y de `model_aggregate`; `None` si falta una de las dos."""
    before = {a.attribute: a.aggregate for a in pre.attributes}
    after = {a.attribute: a.aggregate for a in post.attributes}
    return PrePostDelta(
        attributes=[
            AttributeDelta(attribute=a, delta=_difference(after.get(a), before.get(a)))  # type: ignore[arg-type]
            for a in ATTRIBUTES
        ],
        model_aggregate=_difference(post.model_aggregate, pre.model_aggregate),
    )


def _without_cells(result: DisparityResult) -> DisparityResult:
    return result.model_copy(
        update={"attributes": [a.model_copy(update={"cells": []}) for a in result.attributes]}
    )


def size_bytes(report: PrePostReport) -> int:
    return len(canonicalize(report.model_dump(mode="json")))


def compare_source(
    request: CompareSourceRequest, policy: config.MonitoringPolicy, max_bytes: int = MAX_PACKAGE_BYTES
) -> PrePostReport:
    validate_catalog(request)
    pre = measure(_counts(request.pre), policy.n_min, MODEL, "pre", EPOCH, EPOCH)
    post = measure(_counts(request.post), policy.n_min, MODEL, "post", EPOCH, EPOCH)
    report = PrePostReport(
        source_id=request.source_id,
        pre=pre,
        post=post,
        delta=delta_of(pre, post),
        threshold_pp=str(quantize4(policy.threshold_pp)),
        n_min=policy.n_min,
        truncated=False,
        disclaimer=DISCLAIMER,
    )
    for side in ("pre", "post"):
        if size_bytes(report) <= max_bytes:
            break
        report = report.model_copy(update={side: _without_cells(getattr(report, side)), "truncated": True})
    return report
