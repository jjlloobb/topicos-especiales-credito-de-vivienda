"""Validacion del explicador contra `shap` (NFR-U5-30). Unico modulo de U5 que importa `shap`.

En runtime U6 calcula TreeSHAP con XGBoost (`pred_contribs=True`), sin `shap`. Aqui se comprueba, sobre filas de
`test`, que esos valores coinciden con `shap.TreeExplainer(feature_perturbation="tree_path_dependent")` y que la
suma de cada vector mas `base_value` reproduce el margen del modelo (precisado por U6 NFR Q1).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import shap
import xgboost as xgb

FEATURE_PERTURBATION = "tree_path_dependent"


class ExplainerParityError(Exception):
    """El explicador no coincide con `shap` o no reproduce el margen del modelo."""


@dataclass(frozen=True)
class ExplainerCheck:
    rows: int
    max_abs_diff_vs_shap: float
    max_abs_margin_error: float
    base_value: float


def xgboost_contributions(booster: xgb.Booster, matrix: np.ndarray, feature_order: list[str]) -> np.ndarray:
    """Lo que calcula el explicador en runtime: `pred_contribs=True` -> (n, k + 1), la ultima columna es el sesgo."""
    dmatrix = xgb.DMatrix(matrix, feature_names=feature_order)
    return np.asarray(booster.predict(dmatrix, pred_contribs=True), dtype=np.float64)


def validate_explainer(
    booster: xgb.Booster,
    matrix: np.ndarray,
    feature_order: list[str],
    tolerance: float,
    margin_tolerance: float,
) -> ExplainerCheck:
    """Paridad con `shap` (<= `tolerance`) y suma de contribuciones + `base_value` = margen.

    La suma se compara con `margin_tolerance`: XGBoost devuelve contribuciones y margen en float32 y acumula
    ~300 arboles, asi que la suma difiere del margen en ~1e-5 (medido 8,5e-6) aunque ambos sean exactos.
    """
    contribs = xgboost_contributions(booster, matrix, feature_order)
    explainer = shap.TreeExplainer(booster, feature_perturbation=FEATURE_PERTURBATION)
    reference = np.asarray(explainer.shap_values(matrix), dtype=np.float64)
    base_value = float(np.ravel(explainer.expected_value)[0])
    diff = float(np.max(np.abs(contribs[:, :-1] - reference)))
    margin = np.asarray(
        booster.predict(xgb.DMatrix(matrix, feature_names=feature_order), output_margin=True),
        dtype=np.float64,
    )
    margin_error = float(np.max(np.abs(contribs[:, :-1].sum(axis=1) + base_value - margin)))
    if diff > tolerance:
        raise ExplainerParityError(f"shap_parity: max |xgboost - shap| = {diff:.3e} > {tolerance:.0e}")
    if margin_error > margin_tolerance:
        raise ExplainerParityError(f"margin_sum: max error = {margin_error:.3e} > {margin_tolerance:.0e}")
    return ExplainerCheck(len(matrix), diff, margin_error, base_value)
