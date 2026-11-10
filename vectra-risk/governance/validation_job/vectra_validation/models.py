"""Predictor y explicador del paquete (BR-U4-07). Solo este modulo importa las librerias de inferencia (NFR-U4-24).

El formato sale de la extension del `artifact_uri` (`ArtifactFormat` de U0). Las probabilidades son de `default`; el margen es
el log-odds, la escala en la que las contribuciones del explicador suman (NFR-U6-01).
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol

import lightgbm as lgb
import numpy as np
import onnxruntime as ort
import xgboost as xgb
from numpy.typing import NDArray

from vectra_validation.errors import ValidationJobError

Matrix = NDArray[np.float64]
FORMATS = {".onnx": "onnx", ".json": "xgboost_json", ".ubj": "xgboost_ubj", ".txt": "lightgbm_txt"}
_EPS = 1e-12


class Predictor(Protocol):
    def probability(self, matrix: Matrix) -> Matrix: ...

    def margin(self, matrix: Matrix) -> Matrix: ...


class Explainer(Protocol):
    def contributions(self, matrix: Matrix) -> Matrix | None:
        """(n, k + 1) con el sesgo en la ultima columna, o `None` si este explicador no produce vectores."""
        ...


def artifact_format(uri: str) -> str:
    for suffix, name in FORMATS.items():
        if uri.lower().endswith(suffix):
            return name
    raise ValidationJobError("artifact_format_unknown")


@dataclass(frozen=True)
class XgboostModel:
    booster: xgb.Booster
    feature_order: tuple[str, ...]

    def _matrix(self, matrix: Matrix) -> xgb.DMatrix:
        return xgb.DMatrix(matrix, feature_names=list(self.feature_order))

    def probability(self, matrix: Matrix) -> Matrix:
        return np.asarray(self.booster.predict(self._matrix(matrix)), dtype=np.float64)

    def margin(self, matrix: Matrix) -> Matrix:
        return np.asarray(self.booster.predict(self._matrix(matrix), output_margin=True), dtype=np.float64)

    def contributions(self, matrix: Matrix) -> Matrix | None:
        return np.asarray(self.booster.predict(self._matrix(matrix), pred_contribs=True), dtype=np.float64)


@dataclass(frozen=True)
class LightgbmModel:
    booster: lgb.Booster

    def probability(self, matrix: Matrix) -> Matrix:
        return np.asarray(self.booster.predict(matrix), dtype=np.float64)

    def margin(self, matrix: Matrix) -> Matrix:
        return np.asarray(self.booster.predict(matrix, raw_score=True), dtype=np.float64)

    def contributions(self, matrix: Matrix) -> Matrix | None:
        return np.asarray(self.booster.predict(matrix, pred_contrib=True), dtype=np.float64)


class OnnxModel:
    """Predictor ONNX: solo puntua. El formato no trae contribuciones, asi que su explicador no produce vectores."""

    def __init__(self, data: bytes) -> None:
        self._session = ort.InferenceSession(data, providers=["CPUExecutionProvider"])
        self._input = self._session.get_inputs()[0].name

    def probability(self, matrix: Matrix) -> Matrix:
        out: Any = self._session.run(None, {self._input: matrix.astype(np.float32)})[0]
        values = np.asarray(out, dtype=np.float64)
        if values.ndim == 2 and values.shape[1] == 2:
            return values[:, 1]
        return values.reshape(-1)

    def margin(self, matrix: Matrix) -> Matrix:
        p = np.clip(self.probability(matrix), _EPS, 1 - _EPS)
        return np.log(p / (1 - p))

    def contributions(self, matrix: Matrix) -> Matrix | None:
        return None


Model = XgboostModel | LightgbmModel | OnnxModel


def load_model(fmt: str, data: bytes, feature_order: tuple[str, ...]) -> Model:
    """Carga el predictor desde bytes. Nunca pickle: los formatos son los de `ArtifactFormat`."""
    if fmt == "onnx":
        return OnnxModel(data)
    if fmt in ("xgboost_json", "xgboost_ubj"):
        booster = xgb.Booster()
        booster.load_model(bytearray(data))
        return XgboostModel(booster, feature_order)
    if fmt == "lightgbm_txt":
        return LightgbmModel(lgb.Booster(model_str=data.decode("utf-8")))
    raise ValidationJobError("artifact_format_unknown")


@dataclass(frozen=True)
class ExplainerSpec:
    """`explainer.json` del paquete: version, orden de features y codificacion de las categoricas."""

    model_version_id: str
    feature_order: tuple[str, ...]
    categorical_encoding: dict[str, list[str]]


def parse_explainer(data: bytes) -> ExplainerSpec:
    try:
        raw = json.loads(data)
        return ExplainerSpec(
            model_version_id=str(raw["model_version_id"]),
            feature_order=tuple(raw["feature_order"]),
            categorical_encoding={k: list(v) for k, v in raw["categorical_encoding"].items()},
        )
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ValidationJobError("explainer_unreadable") from error
