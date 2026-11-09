"""Paso 4 (NFR-U6-01, 04): suma de contribuciones + `base_value` = margen del predictor (tolerancia 1e-4) y misma version."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st
from vectra_explainer.app import create_app as explainer_app
from vectra_explainer.core import Explainer
from vectra_predictor.app import create_app as predictor_app
from vectra_predictor.core import Predictor
from vectra_reference.release import Release

from serving_helpers import (
    feature_vector,
    feature_vector_json,
    load_explainer_package,
    load_predictor_package,
    values_strategy,
)

TOLERANCE = 1e-4  # NFR-U6-01: las salidas son float32 (enmienda del 2026-11-08)


@pytest.fixture(scope="module")
def predictor(package_dir: Path) -> Predictor:
    return Predictor(load_predictor_package(package_dir))


@pytest.fixture(scope="module")
def explainer(package_dir: Path) -> Explainer:
    return Explainer(load_explainer_package(package_dir))


@given(data=st.data())
def test_the_sum_of_contributions_plus_base_value_reproduces_the_predictor_margin(
    predictor: Predictor, explainer: Explainer, data: st.DataObject
) -> None:
    values = data.draw(values_strategy(predictor.envelope, list(predictor.model.feature_order)))
    vector = feature_vector(values)
    explanation = explainer.explain(vector)
    margin = predictor.predict(vector).margin
    assert explanation.feature_ids == predictor.model.feature_order  # orden del feature_spec
    assert sum(explanation.contributions) + explanation.base_value == pytest.approx(margin, abs=TOLERANCE)
    assert explanation.model_version_id == predictor.predict(vector).model_version_id


def test_explain_and_predict_answer_with_the_same_model_version_id(
    predictor: Predictor, explainer: Explainer, reference_release: Release
) -> None:
    row = dict(reference_release.splits["test"].values[3])
    body = {"instances": [feature_vector_json(row)]}
    predicted = TestClient(predictor_app(predictor)).post("/v1/models/m:predict", json=body).json()
    explained = TestClient(explainer_app(explainer)).post("/v1/models/m:explain", json=body)
    assert explained.status_code == 200
    (explanation,) = explained.json()["explanations"]
    assert explanation["model_version_id"] == predicted["predictions"][0]["model_version_id"]
    assert [c["feature_id"] for c in explanation["contributions"]] == list(predictor.model.feature_order)
    total = sum(c["contribution"] for c in explanation["contributions"]) + explanation["base_value"]
    assert total == pytest.approx(predictor.predict(feature_vector(row)).margin, abs=TOLERANCE)


def test_explain_missing_feature_is_422_and_without_package_is_503(explainer: Explainer) -> None:
    client = TestClient(explainer_app(explainer))
    assert client.post("/v1/models/m:explain", json={"instances": [{"features": {}}]}).status_code == 422
    assert (
        TestClient(explainer_app(None))
        .post("/v1/models/m:explain", json={"instances": [{"features": {}}]})
        .status_code
        == 503
    )
