"""Ajuste de la envolvente (BR-U5-11). Unico modulo de U5 que puede importar sklearn (NFR-U5-31)."""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from sklearn.covariance import MinCovDet

from vectra_reference.envelope.confidence import distances


def fit_envelope(
    numeric: np.ndarray,
    numeric_names: Sequence[str],
    categorical: Mapping[str, Sequence[str]],
    *,
    support_fraction: float,
    random_state: int,
    grid_size: int,
    max_rows: int | None = None,
    model_version_id: str,
) -> dict[str, Any]:
    """Envolvente calculada sobre `train`: p1/p99, categorias vistas, media y covarianza robusta (MCD, ajustada sobre `max_rows` filas de
    `train` elegidas con la semilla) y la distribucion empirica de las distancias de Mahalanobis del entrenamiento (cuantiles en una malla fija).

    `numeric` es la matriz (n, k) de las features numericas en el orden de `numeric_names`; `categorical` lleva
    los valores de cada categorica por fila. Determinista para una semilla (`random_state`).
    """
    sample = numeric
    if (
        max_rows is not None and len(numeric) > max_rows
    ):  # el MCD cuesta O(n); la media y la covarianza usan una muestra fija
        chosen = np.sort(
            np.random.default_rng(random_state).choice(len(numeric), size=max_rows, replace=False)
        )
        sample = numeric[chosen]
    with warnings.catch_warnings():
        # FastMCD avisa de pequenos aumentos del determinante (~1e-3 relativo) entre iteraciones C-step: no cambia el
        # resultado ni su determinismo y llena la salida de la entrega.
        warnings.filterwarnings("ignore", message="Determinant has increased", category=RuntimeWarning)
        mcd = MinCovDet(support_fraction=support_fraction, random_state=random_state).fit(sample)
    mean = [float(v) for v in mcd.location_]
    covariance = [[float(v) for v in row] for row in mcd.covariance_]
    train_distances = distances(mean, covariance, numeric)
    probabilities = np.linspace(0.0, 1.0, grid_size)
    return {
        "model_version_id": model_version_id,
        "numeric": [
            {
                "name": name,
                "p1": float(np.percentile(numeric[:, j], 1)),
                "p99": float(np.percentile(numeric[:, j], 99)),
            }
            for j, name in enumerate(numeric_names)
        ],
        "categories": {name: sorted({str(v) for v in values}) for name, values in categorical.items()},
        "mean": mean,
        "covariance": covariance,
        "distance_quantiles": [float(v) for v in np.quantile(train_distances, probabilities)],
        "support_fraction": support_fraction,
        "n_train": int(numeric.shape[0]),
    }
