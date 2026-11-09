"""El modelo cargado de un paquete verificado: orden de las features, codificacion y XGBoost (P-U6-01, NFR-U6-05).

El vector se arma en el orden de `feature_spec.json`. Una categorica se codifica por su posicion en
`explainer.json:categorical_encoding` (la misma codificacion con la que U5 entreno; fuera de la lista = -1) y el resto
va como `float`. `predict` y `explain` usan la misma instancia de esta clase, asi que comparten orden y version.
"""

import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import xgboost as xgb
from vectra_contracts.models.features import FeatureValue, FeatureVector

from vectra_serving_common.package_loader import LoadedPackage


class FeatureMissing(ValueError):
    """El `FeatureVector` no trae una feature del `feature_spec`."""


@dataclass(frozen=True)
class Encoded:
    """Un vector listo para XGBoost y los mismos valores en la forma que lee `envelope.confidence`."""

    row: np.ndarray
    values: Mapping[str, float | str]


def _raw(value: FeatureValue) -> str | int:
    return value.value


class Model:
    def __init__(self, package: LoadedPackage) -> None:
        spec = package.json("feature_spec.json")
        self.model_version_id = package.model_version_id
        self.feature_order: tuple[str, ...] = tuple(item["feature_id"] for item in spec["features"])
        encoding: Mapping[str, list[str]] = package.json("explainer.json")["categorical_encoding"]
        self._codes = {name: {v: i for i, v in enumerate(levels)} for name, levels in encoding.items()}
        self._booster = xgb.Booster()
        self._booster.load_model(bytearray(package.files["predictor.json"]))
        self._booster.set_param({"nthread": 1})
        # `Booster.predict` no se declara seguro entre hilos: se serializa. El limite de concurrencia es de admision.
        self._lock = threading.Lock()

    def encode(self, vector: FeatureVector) -> Encoded:
        row = np.empty((1, len(self.feature_order)), dtype=np.float64)
        values: dict[str, float | str] = {}
        for j, name in enumerate(self.feature_order):
            feature = vector.features.get(name)
            if feature is None:
                raise FeatureMissing(name)
            raw = _raw(feature)
            if name in self._codes:
                values[name] = str(raw)
                row[0, j] = self._codes[name].get(str(raw), -1)
            else:
                values[name] = float(
                    raw
                )  # DecimalStr o int; un Decimal4 llega como cadena `"0.1250"` (candidata de U5)
                row[0, j] = values[name]
        return Encoded(row, values)

    def _matrix(self, row: np.ndarray) -> xgb.DMatrix:
        return xgb.DMatrix(row, feature_names=list(self.feature_order))

    def score_and_margin(self, row: np.ndarray) -> tuple[float, float]:
        with self._lock:
            matrix = self._matrix(row)
            score = float(self._booster.predict(matrix)[0])
            margin = float(self._booster.predict(matrix, output_margin=True)[0])
        return score, margin

    def contributions(self, row: np.ndarray) -> tuple[list[float], float]:
        """`pred_contribs=True`: una contribucion por feature, en el orden del `feature_spec`, y el sesgo (`base_value`)."""
        with self._lock:
            contribs: Any = self._booster.predict(self._matrix(row), pred_contribs=True)
        values = np.asarray(contribs, dtype=np.float64)[0]
        return [float(v) for v in values[:-1]], float(values[-1])
