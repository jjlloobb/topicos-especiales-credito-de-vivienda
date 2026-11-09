"""Libreria `vectra_disparity` (U9): disparidad por grupo y banda, solo con la biblioteca estandar (P-U9-05)."""

from vectra_disparity.counts import (
    ATTRIBUTES,
    BANDS,
    UNINFORMED,
    CountCell,
    CountTable,
    counts_from_marginals,
    counts_from_records,
)
from vectra_disparity.disparity import (
    AttributeResult,
    BandResult,
    CellResult,
    disparity_by_band,
    model_aggregate,
    to_dict,
)
from vectra_disparity.stats import newcombe_difference, quantize4, wilson_interval

__version__ = "1.0.0"

__all__ = [
    "ATTRIBUTES",
    "BANDS",
    "UNINFORMED",
    "AttributeResult",
    "BandResult",
    "CellResult",
    "CountCell",
    "CountTable",
    "__version__",
    "counts_from_marginals",
    "counts_from_records",
    "disparity_by_band",
    "model_aggregate",
    "newcombe_difference",
    "quantize4",
    "to_dict",
    "wilson_interval",
]
