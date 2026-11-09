"""Orquestador de la entrega de U5 (`make release`): genera, entrena, ajusta la envolvente, calibra y empaqueta.

Falla (excepcion y codigo de salida distinto de 0) si una regla de calidad no se cumple: AUC de validacion
(BR-U5-08), calibracion contra RT-4 (BR-U5-13), paridad del explicador (NFR-U5-30) o un paquete invalido
(BR-U5-09, BR-U5-10). La disparidad (BR-U5-06) y la variante proxy (BR-U5-14) llegan con el Bloque D.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from vectra_contracts.models.governance import PolicyDraft

from vectra_reference import generate as gen
from vectra_reference.adversarial import rt4_cases
from vectra_reference.envelope.calibrate import Calibration, build_policy, calibrate_threshold
from vectra_reference.envelope.confidence import confidence
from vectra_reference.envelope.fit import fit_envelope
from vectra_reference.explainer_validation import ExplainerCheck, validate_explainer
from vectra_reference.features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    Value,
    base_feature_spec,
    row_values,
)
from vectra_reference.package import build_package, dump_json
from vectra_reference.train import Split, TrainedModel, encode, load_split, train_model

POLICY_FILE = "reference-policy.json"


@dataclass(frozen=True)
class Release:
    manifest: dict[str, Any]
    model: TrainedModel
    envelope: dict[str, Any]
    calibration: Calibration
    policy: PolicyDraft
    rt4: list[dict[str, Any]]
    rt4_confidence: list[str]
    test_confidence: list[str]
    splits: dict[str, Split]
    explainer: ExplainerCheck
    package_dir: Path
    policy_path: Path


def _confidences(envelope: Mapping[str, Any], values: list[dict[str, Value]]) -> list[str]:
    return [confidence(envelope, v) for v in values]


def run_release(
    out: Path,
    config: dict[str, Any] | None = None,
    *,
    datasets: Mapping[str, Path] | None = None,
    enforce_min_auc: bool = True,
) -> Release:
    config = config or gen.load_config()
    paths = datasets or gen.generate(out / "datasets", config)
    splits = {name: load_split(paths[name]) for name in gen.PARTITIONS}
    model = train_model(
        splits["train"], splits["validation"], base_feature_spec(), config, enforce_min_auc=enforce_min_auc
    )

    train_x = encode(splits["train"].values, model.feature_order, model.vocabulary)
    numeric_columns = [model.feature_order.index(name) for name in NUMERIC_FEATURES]
    env = config["envelope"]
    envelope = fit_envelope(
        train_x[:, numeric_columns],
        NUMERIC_FEATURES,
        {name: [v[name] for v in splits["train"].values] for name in CATEGORICAL_FEATURES},
        support_fraction=float(env["mcd_support_fraction"]),
        random_state=int(env["mcd_random_state"]),
        grid_size=int(env["distance_grid_size"]),
        max_rows=int(env["mcd_max_rows"]),
        model_version_id="mv-pending",
    )

    rt4 = rt4_cases(envelope, row_values)
    rt4_confidence = _confidences(envelope, [row_values(c["input"]) for c in rt4])
    test_confidence = _confidences(envelope, splits["test"].values)
    ref = config["reference_policy"]
    calibration = calibrate_threshold(
        _confidences(envelope, splits["train"].values),
        test_confidence,
        rt4_confidence,
        quantile=float(ref["calibration_train_quantile"]),
        min_test_above=float(ref["min_test_above"]),
    )
    policy = build_policy(config, calibration.threshold)

    pkg = config["package"]
    n_check = int(pkg["explainer_validation_rows"])
    explainer = validate_explainer(
        model.booster,
        encode(splits["test"].values[:n_check], model.feature_order, model.vocabulary),
        list(model.feature_order),
        float(pkg["explainer_tolerance"]),
        float(pkg["explainer_margin_tolerance"]),
    )

    chosen = np.sort(
        np.random.default_rng([int(config["seed"]), 2]).choice(
            len(splits["train"].values),
            size=min(int(pkg["background_rows"]), len(splits["train"].values)),
            replace=False,
        )
    )
    background = [splits["train"].values[int(i)] for i in chosen]
    stats = {
        "sizes": {name: len(splits[name].values) for name in gen.PARTITIONS},
        "default_rates": {name: round(float(splits[name].y.mean()), 6) for name in gen.PARTITIONS},
        "auc_validation": round(model.auc_validation, 6),
        "disparity_pp": None,  # la mide el Bloque D con la libreria de U9
        "low_confidence_threshold": calibration.threshold,
        "test_above_threshold": round(calibration.test_above, 6),
    }
    package_dir = out / "package"
    manifest = build_package(package_dir, model, envelope, background, explainer.base_value, config, stats)
    policy_path = out / POLICY_FILE
    policy_path.write_bytes(dump_json(policy.model_dump(mode="json")))
    return Release(
        manifest, model, envelope, calibration, policy, rt4, rt4_confidence, test_confidence, splits,
        explainer, package_dir, policy_path,
    )  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Entrega de U5: datos, modelo, envolvente y paquete")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    release = run_release(args.out, gen.load_config(args.config))
    print(  # noqa: T201
        f"{release.manifest['model_version_id']} auc={release.model.auc_validation:.4f} "
        f"umbral={release.calibration.threshold} paquete={release.package_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
