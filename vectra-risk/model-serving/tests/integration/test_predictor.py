"""Paso 3 (P-U6-01, NFR-U6-04, 05): contrato de `:predict`, `model_version_id` del manifiesto y 503 sin paquete verificado."""

import re
from pathlib import Path

import numpy as np
import pytest
import xgboost as xgb
from fastapi.testclient import TestClient
from vectra_common.metrics import REGISTRY
from vectra_predictor.app import create_app
from vectra_predictor.core import Predictor
from vectra_reference.release import Release
from vectra_reference.train import encode

from serving_helpers import feature_vector_json, load_predictor_package, rounded, version_of

URL = "/v1/models/isvc-51241dc4:predict"


@pytest.fixture(scope="module")
def predictor(package_dir: Path) -> Predictor:
    return Predictor(load_predictor_package(package_dir))


@pytest.fixture(scope="module")
def client(predictor: Predictor) -> TestClient:
    return TestClient(create_app(predictor))


def _row(release: Release, i: int) -> dict[str, float | str]:
    return dict(release.splits["test"].values[i])


def test_the_response_has_score_confidence_and_the_manifest_version(
    client: TestClient, reference_release: Release, package_dir: Path
) -> None:
    response = client.post(URL, json={"instances": [feature_vector_json(_row(reference_release, 0))]})
    assert response.status_code == 200
    (prediction,) = response.json()["predictions"]
    assert set(prediction) == {"score", "confidence", "model_version_id"}
    assert isinstance(prediction["score"], float) and 0.0 < prediction["score"] < 1.0
    assert re.fullmatch(r"[01]\.\d{4}", prediction["confidence"])
    assert prediction["model_version_id"] == version_of(package_dir)  # el del manifiesto, no uno fijo


def test_the_score_is_the_xgboost_probability_of_the_u5_model(
    client: TestClient, reference_release: Release
) -> None:
    model = reference_release.model
    rows = [_row(reference_release, i) for i in range(40)]
    expected = model.booster.predict(
        xgb.DMatrix(
            encode([rounded(r) for r in rows], model.feature_order, model.vocabulary),
            feature_names=list(model.feature_order),
        )
    )
    for row, want in zip(rows, expected, strict=True):
        got = client.post(URL, json={"instances": [feature_vector_json(row)]}).json()["predictions"][0][
            "score"
        ]
        assert got == pytest.approx(float(want), abs=1e-5)
    assert np.isfinite(expected).all()


def test_a_missing_feature_is_422(client: TestClient, reference_release: Release) -> None:
    row = _row(reference_release, 1)
    del row["monthly_income"]
    response = client.post(URL, json={"instances": [feature_vector_json(row)]})
    assert response.status_code == 422
    assert response.json() == {"error": "feature_missing", "feature_id": "monthly_income"}


@pytest.mark.parametrize("instances", [[], "x"])
def test_a_body_without_exactly_one_instance_is_422(client: TestClient, instances: object) -> None:
    assert client.post(URL, json={"instances": instances}).status_code == 422


def test_without_a_verified_package_the_component_is_not_ready() -> None:
    response = TestClient(create_app(None)).post(URL, json={"instances": [{"features": {}}]})
    assert response.status_code == 503
    assert response.json() == {"error": "not_ready"}


def test_the_duration_histogram_counts_the_request(client: TestClient, reference_release: Release) -> None:
    def count() -> float:
        return (
            REGISTRY.get_sample_value(
                "vectra_serving_request_duration_seconds_count", {"component": "predictor"}
            )
            or 0.0
        )

    before = count()
    client.post(URL, json={"instances": [feature_vector_json(_row(reference_release, 2))]})
    assert count() == before + 1
