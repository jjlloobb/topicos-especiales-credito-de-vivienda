"""Entrenamiento del modelo base (BR-U5-07, BR-U5-08; NFR-U5-10).

XGBoost con `nthread` fijo, `tree_method = "hist"` y semilla, hiperparametros de `generator.yaml` (seccion
`model`). Solo entran las features de domain-entities §3.1; el `feature_spec` se valida antes de entrenar.
Si el AUC de validacion queda bajo el minimo **[INTERNO]** (0,85), la entrega falla.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb
from vectra_contracts.models.features import FeatureSpec

from vectra_reference.features import (
    Value,
    categorical_vocabulary,
    read_rows,
    row_values,
    validate_feature_spec,
)


class TrainingError(Exception):
    """La entrega falla: el AUC de validacion no alcanza el minimo (BR-U5-08)."""


@dataclass(frozen=True)
class Split:
    """Una particion ya convertida a features (valores por fila) y su etiqueta."""

    values: list[dict[str, Value]]
    y: np.ndarray


@dataclass(frozen=True)
class TrainedModel:
    booster: xgb.Booster
    feature_order: tuple[str, ...]
    vocabulary: dict[str, list[str]]
    auc_validation: float


def load_split(path: Path) -> Split:
    rows = read_rows(path)
    return Split([row_values(r) for r in rows], np.array([r["default"] for r in rows], dtype=np.int64))


def encode(
    values: Sequence[Mapping[str, Value]],
    feature_order: Sequence[str],
    vocabulary: Mapping[str, Sequence[str]],
) -> np.ndarray:
    """Matriz (n, k) en el orden de `feature_order`; una categorica se codifica por su posicion (-1 si no esta)."""
    out = np.empty((len(values), len(feature_order)), dtype=np.float64)
    for j, name in enumerate(feature_order):
        if name in vocabulary:
            index = {v: i for i, v in enumerate(vocabulary[name])}
            out[:, j] = [index.get(str(v[name]), -1) for v in values]
        else:
            out[:, j] = [float(v[name]) for v in values]  # type: ignore[arg-type]
    return out


def xgb_params(config: Mapping[str, Any]) -> dict[str, Any]:
    model = config["model"]
    return {
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "tree_method": "hist",
        "nthread": int(model["nthread"]),
        "seed": int(model["seed"]),
        **model["params"],
    }


def train_model(
    train: Split,
    validation: Split,
    spec: FeatureSpec,
    config: Mapping[str, Any],
    *,
    enforce_min_auc: bool = True,
) -> TrainedModel:
    """Entrena y mide el AUC de validacion. `spec` fuera de §3.1 -> `FeatureSpecError` antes de entrenar."""
    validate_feature_spec(spec)
    feature_order = tuple(item.feature_id for item in spec.features)
    vocabulary = {k: v for k, v in categorical_vocabulary(config).items() if k in feature_order}
    dtrain = xgb.DMatrix(
        encode(train.values, feature_order, vocabulary), label=train.y, feature_names=list(feature_order)
    )
    dval = xgb.DMatrix(
        encode(validation.values, feature_order, vocabulary),
        label=validation.y,
        feature_names=list(feature_order),
    )
    history: dict[str, dict[str, list[float]]] = {}
    booster = xgb.train(
        xgb_params(config),
        dtrain,
        num_boost_round=int(config["model"]["num_boost_round"]),
        evals=[(dval, "validation")],
        evals_result=history,
        verbose_eval=False,
    )
    auc = float(history["validation"]["auc"][-1])
    minimum = float(config["model"]["min_auc"])
    if enforce_min_auc and auc < minimum:
        raise TrainingError(f"auc_below_minimum: {auc:.4f} < {minimum}")
    return TrainedModel(booster, feature_order, vocabulary, auc)


def predictor_bytes(booster: xgb.Booster) -> bytes:
    """`predictor.json` (XGBoost JSON); sin pickle ni joblib (BR-U5-09)."""
    return bytes(booster.save_raw(raw_format="json"))
