"""Soporte de las pruebas del `model-validation-job`: dataset de U5 (Parquet real), modelos de fixture y un store en memoria."""

import io
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import onnx
import pyarrow as pa
import pyarrow.parquet as pq
import xgboost as xgb
from onnx import TensorProto, helper
from vectra_contracts.models.governance import PolicyDraft, ValidationReport
from vectra_reference.features import (
    BASE_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    base_feature_spec,
    categorical_vocabulary,
    row_values,
)
from vectra_reference.generate import build_rows, load_config, with_overrides
from vectra_reference.train import encode
from vectra_validation.confidence import distances
from vectra_validation.config import JobConfig
from vectra_validation.features import Dataset, build_dataset

VERSION = "mv-2026-11-09-0badc0de"
OTHER_VERSION = "mv-2026-11-09-deadbeef"
EVALUATED_ON = date(2026, 11, 9)
MANIFEST = "s3://model-store/mv/manifest.json"
DATASET = "s3://validation-datasets/mv/validation.parquet"
CONFIG = load_config()


def policy(**over: Any) -> PolicyDraft:
    """La politica activa de la demo: corte 0,08, confianza minima 0,03 y una vigencia normativa que cubre `EVALUATED_ON`."""
    base: dict[str, Any] = {
        "cutoff": "0.0800",
        "low_confidence_threshold": "0.0300",
        "channel_rules": [],
        "normative": [
            {
                "vis_max_property_value": 200_000_000,
                "usury_cap_ea": "0.2800",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "source_ref": "sintetico",
            }
        ],
    }
    return PolicyDraft.model_validate_json(json.dumps({**base, **over}))


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
    """Un XGBoost real entrenado sobre el dataset de fixture (JSON, como `predictor.json` de U5).

    La matriz es la de U5 (`vectra_reference.train.encode` sobre `row_values`), no la del propio Job: asi una divergencia de
    codificacion entre el Job y U5 no queda escondida por el fixture.
    """
    matrix = encode([row_values(r) for r in data], BASE_FEATURES, categorical_vocabulary(CONFIG))
    booster = xgb.train(
        {"objective": "binary:logistic", "max_depth": 3, "eta": 0.3, "seed": 7},
        xgb.DMatrix(matrix, label=np.array([int(r["default"]) for r in data]), feature_names=list(BASE_FEATURES)),
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


def envelope_bytes(data: list[dict[str, Any]], version: str = VERSION) -> bytes:
    """`domain_envelope.json` de fixture, calculado sobre el dataset con el formato de U5 (p1/p99, categorias, media, covarianza, deciles)."""
    d = dataset(data)
    numeric = np.array([[float(v[name]) for name in NUMERIC_FEATURES] for v in d.values])
    mean = numeric.mean(axis=0)
    covariance = np.cov(numeric, rowvar=False) + np.eye(numeric.shape[1]) * 1e-6
    grid = np.quantile(distances(mean.tolist(), covariance.tolist(), numeric), np.linspace(0.0, 1.0, 101))
    return json.dumps(
        {
            "model_version_id": version,
            "numeric": [
                {"name": n, "p1": float(np.percentile(numeric[:, j], 1)), "p99": float(np.percentile(numeric[:, j], 99))}
                for j, n in enumerate(NUMERIC_FEATURES)
            ],
            "categories": {n: sorted({str(v[n]) for v in d.values}) for n in CATEGORICAL_FEATURES},
            "mean": mean.tolist(),
            "covariance": covariance.tolist(),
            "distance_quantiles": [float(v) for v in grid],
        }
    ).encode()


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
        {"name": "domain_envelope.json", "model_version_id": version},
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
        "assertion_audience": "https://issuer.example/realms/vectra",
        "client_id": "model-validation-job",
        "key_path": "/var/run/vectra/client/private-key",
        "key_id": None,
        "audience": "governance-service",
        "evaluated_on": EVALUATED_ON.isoformat(),
        "policy": policy(),
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
            prefix + "domain_envelope.json": envelope_bytes(data),
            DATASET: parquet(data),
        }
    )
    return prefix + artifact_name, store


ROOT = Path(__file__).resolve().parents[3]
U5_OUT = ROOT / "reference-model" / ".out"


def u5_base_release() -> Path:
    """`reference-model/.out` con el modelo base real de U5 (`release --only base`); lo genera si falta (unos 80 s, determinista)."""
    if not (U5_OUT / "package" / "manifest.json").is_file():
        subprocess.run(  # noqa: S603
            [sys.executable, "-m", "vectra_reference.release", "--out", str(U5_OUT), "--only", "base"], check=True, cwd=ROOT
        )
    return U5_OUT


def u5_package_store(out: Path) -> tuple[str, MemoryStore, str]:
    """El paquete real de U5 y su `validation.parquet` en un store en memoria; devuelve (artifact_uri, store, model_version_id)."""
    prefix = "s3://model-store/u5/"
    manifest = (out / "package" / "manifest.json").read_bytes()
    version = json.loads(manifest)["files"][0]["model_version_id"]
    objects = {prefix + f.name: f.read_bytes() for f in (out / "package").iterdir()}
    objects[prefix + "manifest.json"] = manifest
    objects[DATASET] = (out / "datasets" / "validation.parquet").read_bytes()
    return prefix + "predictor.json", MemoryStore(objects), str(version)
