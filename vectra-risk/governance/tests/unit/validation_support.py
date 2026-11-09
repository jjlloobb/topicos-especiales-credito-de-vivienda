"""Soporte de las pruebas del `model-validation-job`: dataset de U5 (Parquet real), modelos de fixture y un store en memoria."""

import io
import json
from datetime import date
from typing import Any

import numpy as np
import onnx
import pyarrow as pa
import pyarrow.parquet as pq
import xgboost as xgb
from onnx import TensorProto, helper
from vectra_contracts.models.governance import ValidationReport
from vectra_reference.features import BASE_FEATURES, base_feature_spec, categorical_vocabulary
from vectra_reference.generate import build_rows, load_config, with_overrides
from vectra_validation.config import JobConfig
from vectra_validation.features import Dataset, build_dataset

VERSION = "mv-2026-11-09-0badc0de"
OTHER_VERSION = "mv-2026-11-09-deadbeef"
EVALUATED_ON = date(2026, 11, 9)
MANIFEST = "s3://model-store/mv/manifest.json"
DATASET = "s3://validation-datasets/mv/validation.parquet"
CONFIG = load_config()


def rows(n: int = 600) -> list[dict[str, Any]]:
    return build_rows(with_overrides(CONFIG, n_rows=n))


def parquet(data: list[dict[str, Any]]) -> bytes:
    sink = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(data), sink)
    return sink.getvalue()


def spec_bytes(version: str = VERSION) -> bytes:
    return base_feature_spec(version).model_dump_json().encode()


def dataset(data: list[dict[str, Any]]) -> Dataset:
    return build_dataset(data, base_feature_spec(VERSION), BASE_FEATURES, categorical_vocabulary(CONFIG), EVALUATED_ON)


def xgboost_bytes(data: list[dict[str, Any]]) -> bytes:
    """Un XGBoost real entrenado sobre el dataset de fixture (JSON, como `predictor.json` de U5)."""
    d = dataset(data)
    booster = xgb.train(
        {"objective": "binary:logistic", "max_depth": 3, "eta": 0.3, "seed": 7},
        xgb.DMatrix(d.matrix, label=np.array(d.defaults), feature_names=list(BASE_FEATURES)),
        num_boost_round=20,
    )
    return bytes(booster.save_raw(raw_format="json"))


def onnx_bytes(n_features: int = len(BASE_FEATURES)) -> bytes:
    """Regresion logistica ONNX de fixture: `sigmoid(x @ w + b)`; el peso lleva el signo de la relacion cuota-ingreso."""
    weights = np.zeros((n_features, 1), dtype=np.float32)
    weights[BASE_FEATURES.index("installment_to_income"), 0] = 4.0
    graph = helper.make_graph(
        [
            helper.make_node("MatMul", ["x", "w"], ["z"]),
            helper.make_node("Add", ["z", "b"], ["s"]),
            helper.make_node("Sigmoid", ["s"], ["probabilities"]),
        ],
        "logistic",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [None, n_features])],
        [helper.make_tensor_value_info("probabilities", TensorProto.FLOAT, [None, 1])],
        [onnx.numpy_helper.from_array(weights, "w"), onnx.numpy_helper.from_array(np.array([-2.0], dtype=np.float32), "b")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)], ir_version=8)
    return model.SerializeToString()


def explainer_bytes(version: str = VERSION) -> bytes:
    return json.dumps(
        {
            "model_version_id": version,
            "mode": "tree_path_dependent",
            "runtime": "xgboost pred_contribs=True",
            "feature_order": list(BASE_FEATURES),
            "categorical_encoding": categorical_vocabulary(CONFIG),
            "base_value": 0.0,
        }
    ).encode()


def manifest_bytes(predictor_name: str, version: str = VERSION, predictor_version: str | None = None) -> bytes:
    files = [
        {"name": predictor_name, "model_version_id": predictor_version or version},
        {"name": "explainer.json", "model_version_id": version},
        {"name": "feature_spec.json", "model_version_id": version},
    ]
    return json.dumps({"model_version_id": version, "files": files}).encode()


class MemoryStore:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.reads: list[str] = []

    def read(self, uri: str) -> bytes:
        self.reads.append(uri)
        return self.objects[uri]


class CapturingSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, ValidationReport]] = []

    def send(self, model_version_id: str, report: ValidationReport) -> None:
        self.sent.append((model_version_id, report))


def job_config(artifact_uri: str, **over: Any) -> JobConfig:
    base: dict[str, Any] = {
        "mode": "validacion",
        "run_id": "run-1",
        "model_version_id": VERSION,
        "manifest_uri": MANIFEST,
        "artifact_uri": artifact_uri,
        "explainer_uri": "s3://model-store/mv/explainer.json",
        "dataset_ref": DATASET,
        "governance_url": "http://governance-service.vectra-app.svc:8080",
        "s3_endpoint": "http://minio:9000",
        "s3_access_key": "validation-readonly",
        "s3_secret_key": "s3cret",
        "token_url": "https://keycloak/token",
        "client_id": "model-validation-job",
        "key_path": "/var/run/vectra/client/private-key",
        "key_id": None,
        "audience": "governance-service",
        "evaluated_on": EVALUATED_ON.isoformat(),
    }
    return JobConfig(**{**base, **over})


def package(artifact_name: str, artifact: bytes, data: list[dict[str, Any]], *, predictor_version: str | None = None) -> tuple[str, MemoryStore]:
    prefix = "s3://model-store/mv/"
    store = MemoryStore(
        {
            MANIFEST: manifest_bytes(artifact_name, predictor_version=predictor_version),
            prefix + artifact_name: artifact,
            prefix + "explainer.json": explainer_bytes(),
            prefix + "feature_spec.json": spec_bytes(),
            DATASET: parquet(data),
        }
    )
    return prefix + artifact_name, store
