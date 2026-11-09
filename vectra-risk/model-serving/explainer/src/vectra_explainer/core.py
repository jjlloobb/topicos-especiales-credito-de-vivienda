"""Contribuciones por feature y `base_value` (NFR-U6-01, 04): suma de contribuciones + `base_value` = margen del predictor."""

from dataclasses import dataclass

from vectra_contracts.models.features import FeatureVector
from vectra_serving_common.model import Model
from vectra_serving_common.package_loader import LoadedPackage


@dataclass(frozen=True)
class Explanation:
    feature_ids: tuple[str, ...]
    contributions: tuple[float, ...]
    base_value: float
    model_version_id: str


class Explainer:
    def __init__(self, package: LoadedPackage) -> None:
        self.model = Model(package)

    @property
    def model_version_id(self) -> str:
        return self.model.model_version_id

    def explain(self, vector: FeatureVector) -> Explanation:
        encoded = self.model.encode(vector)
        contributions, base_value = self.model.contributions(encoded.row)
        return Explanation(
            feature_ids=self.model.feature_order,
            contributions=tuple(contributions),
            base_value=base_value,
            model_version_id=self.model.model_version_id,
        )
