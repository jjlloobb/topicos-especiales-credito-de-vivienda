"""Cobertura del diccionario de features (BR-U0-80..81)."""

from collections.abc import Iterable

from vectra_contracts.models.features import FeatureContribution, FeatureDictionary


def covers(dictionary: FeatureDictionary, shap_vector: Iterable[FeatureContribution]) -> bool:
    known = {entry.feature_id for entry in dictionary.entries}
    return all(item.feature_id in known for item in shap_vector)
