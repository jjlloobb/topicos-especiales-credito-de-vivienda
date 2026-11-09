"""Apoyo de las pruebas de U6: cargar un paquete y armar `FeatureVector` validos."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hypothesis import strategies as st
from vectra_contracts.models.features import FeatureVector
from vectra_serving_common.package_loader import EXPLAINER_FILES, PREDICTOR_FILES, LoadedPackage, load_package

NUMERIC_DECIMALS = 4


def version_of(directory: Path) -> str:
    return str(json.loads((directory / "manifest.json").read_bytes())["model_version_id"])


def load_predictor_package(directory: Path) -> LoadedPackage:
    return load_package(directory, version_of(directory), PREDICTOR_FILES, "predictor")


def load_explainer_package(directory: Path) -> LoadedPackage:
    return load_package(directory, version_of(directory), EXPLAINER_FILES, "explainer")


def feature_vector_json(values: Mapping[str, float | str]) -> dict[str, Any]:
    """`FeatureVector` como lo recibe `:predict`: numericas `decimal`, categoricas `category`."""
    features: dict[str, Any] = {}
    for name, value in values.items():
        if isinstance(value, str):
            features[name] = {"type": "category", "value": value}
        else:
            features[name] = {"type": "decimal", "value": f"{value:.{NUMERIC_DECIMALS}f}"}
    return {"features": features}


def feature_vector(values: Mapping[str, float | str]) -> FeatureVector:
    return FeatureVector.model_validate_json(json.dumps(feature_vector_json(values)))


def rounded(values: Mapping[str, float | str]) -> dict[str, float | str]:
    """Los valores tal como los lee U6 tras pasar por la cadena Decimal del contrato."""
    return {k: v if isinstance(v, str) else float(f"{v:.{NUMERIC_DECIMALS}f}") for k, v in values.items()}


def values_strategy(
    envelope: Mapping[str, Any], feature_order: list[str]
) -> st.SearchStrategy[dict[str, float | str]]:
    """Valores dentro y fuera de la envolvente, y categorias vistas y no vistas (todas las features del `feature_spec`)."""
    parts: dict[str, st.SearchStrategy[float | str]] = {}
    numeric = {item["name"]: item for item in envelope["numeric"]}
    for name in feature_order:
        if name in numeric:
            low, high = numeric[name]["p1"], numeric[name]["p99"]
            width = max(high - low, 1.0)
            parts[name] = st.floats(low - 2 * width, high + 2 * width, allow_nan=False, allow_infinity=False)
        else:
            seen = list(envelope["categories"][name])
            parts[name] = st.sampled_from([*seen, "no_vista"])
    return st.fixed_dictionaries(parts)
