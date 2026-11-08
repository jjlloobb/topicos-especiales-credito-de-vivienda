"""NFR-U5-30 (precisado por U6 NFR Q1): `pred_contribs` de XGBoost contra `shap.TreeExplainer(tree_path_dependent)`."""

import json

import numpy as np
import pytest
import shap
import vectra_reference.explainer_validation as ev
from vectra_reference.explainer_validation import (
    ExplainerParityError,
    validate_explainer,
    xgboost_contributions,
)
from vectra_reference.generate import load_config
from vectra_reference.release import Release
from vectra_reference.train import encode

PKG = load_config()["package"]


def _matrix(release: Release, rows: int) -> np.ndarray:
    return encode(release.splits["test"].values[:rows], release.model.feature_order, release.model.vocabulary)


def test_xgboost_contributions_match_shap_tree_path_dependent_on_1000_rows(
    reference_release: Release,
) -> None:
    matrix = _matrix(reference_release, 1000)
    assert matrix.shape[0] == 1000
    contribs = xgboost_contributions(
        reference_release.model.booster, matrix, list(reference_release.model.feature_order)
    )
    explainer = shap.TreeExplainer(
        reference_release.model.booster, feature_perturbation="tree_path_dependent"
    )
    reference = np.asarray(explainer.shap_values(matrix), dtype=np.float64)
    assert float(np.max(np.abs(contribs[:, :-1] - reference))) <= 1e-6


def test_contributions_plus_base_value_reproduce_the_model_margin(reference_release: Release) -> None:
    check = reference_release.explainer
    assert check.rows == PKG["explainer_validation_rows"] == 1000
    assert check.max_abs_diff_vs_shap <= PKG["explainer_tolerance"]
    assert check.max_abs_margin_error <= PKG["explainer_margin_tolerance"]
    explainer = json.loads((reference_release.package_dir / "explainer.json").read_text())
    assert explainer["mode"] == "tree_path_dependent"
    assert explainer["feature_order"] == list(reference_release.model.feature_order)
    assert explainer["base_value"] == pytest.approx(check.base_value)


def test_validate_explainer_fails_when_the_tolerance_is_not_met(small_release: Release) -> None:
    matrix = _matrix(small_release, 50)
    order = list(small_release.model.feature_order)
    with pytest.raises(ExplainerParityError, match="margin_sum"):
        validate_explainer(small_release.model.booster, matrix, order, 1e-6, 0.0)


def test_validate_explainer_fails_when_the_shap_values_differ(
    small_release: Release, monkeypatch: pytest.MonkeyPatch
) -> None:
    matrix = _matrix(small_release, 50)
    order = list(small_release.model.feature_order)

    class Shifted:
        def __init__(self, *_a: object, **_k: object) -> None:
            self.expected_value = 0.0

        def shap_values(self, x: np.ndarray) -> np.ndarray:
            return np.zeros((len(x), x.shape[1])) + 0.01

    monkeypatch.setattr(ev.shap, "TreeExplainer", Shifted)
    with pytest.raises(ExplainerParityError, match="shap_parity"):
        validate_explainer(small_release.model.booster, matrix, order, 1e-6, 1.0)


def test_the_validation_uses_tree_path_dependent() -> None:
    assert ev.FEATURE_PERTURBATION == "tree_path_dependent"
