"""AUC-ROC (BR-U4-07): estadistico de Mann-Whitney con rangos promedio; sin scikit-learn (la imagen no lo lleva)."""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
from numpy.typing import NDArray

from vectra_validation.errors import ValidationJobError


def auc_roc(labels: Sequence[int], scores: Sequence[float] | NDArray[np.float64]) -> float:
    """Probabilidad de que un positivo (`default = 1`) puntue mas que un negativo; los empates cuentan 1/2."""
    y = np.asarray(labels, dtype=np.int64)
    s = np.asarray(scores, dtype=np.float64)
    if y.shape != s.shape:
        raise ValidationJobError("labels_scores_length_differs")
    positives = int(y.sum())
    negatives = int(y.size) - positives
    if positives == 0 or negatives == 0:
        raise ValidationJobError("auc_undefined_single_class")
    _, inverse, counts = np.unique(s, return_inverse=True, return_counts=True)
    last = np.cumsum(counts)
    average_rank = (last - counts + 1 + last) / 2
    ranks = average_rank[inverse]
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def decimal4(value: float) -> str:
    """`Decimal4` de U0: 4 decimales, mitad hacia arriba."""
    return str(Decimal(repr(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
