"""Prediccion y `confidence` (NFR-U6-04, 05): vector en el orden de `feature_spec.json`, XGBoost y `envelope.confidence` de U5."""

from dataclasses import dataclass
from typing import Any

from vectra_contracts.models.features import FeatureVector
from vectra_reference.envelope.confidence import confidence as envelope_confidence
from vectra_serving_common.model import Model
from vectra_serving_common.package_loader import LoadedPackage


@dataclass(frozen=True)
class Prediction:
    score: float
    margin: float
    confidence: str
    model_version_id: str


class Predictor:
    def __init__(self, package: LoadedPackage) -> None:
        self.model = Model(package)
        self.envelope: dict[str, Any] = package.json("domain_envelope.json")

    @property
    def model_version_id(self) -> str:
        return self.model.model_version_id

    def predict(self, vector: FeatureVector) -> Prediction:
        encoded = self.model.encode(vector)
        score, margin = self.model.score_and_margin(encoded.row)
        return Prediction(
            score=score,
            margin=margin,
            confidence=envelope_confidence(self.envelope, encoded.values),
            model_version_id=self.model.model_version_id,
        )
