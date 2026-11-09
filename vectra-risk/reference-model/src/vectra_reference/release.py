"""Orquestador de la entrega de U5 (`make release`): genera, entrena, ajusta la envolvente, calibra y empaqueta.

Falla (excepcion y codigo de salida distinto de 0) si una regla de calidad no se cumple: AUC de validacion
(BR-U5-08), calibracion contra RT-4 (BR-U5-13), paridad del explicador (NFR-U5-30) o un paquete invalido
(BR-U5-09, BR-U5-10), la disparidad del modelo base (BR-U5-06, menor de 5 pp), la disparidad de la variante proxy
(BR-U5-14, al menos 10 pp) y el conjunto adversarial (BR-U5-16..18).

`run_release` hace los Pasos 2 a 5 (modelo base); `run_proxy_release` el Paso 6 (5 paquetes de la variante RT-2) y
`run_adversarial` el Paso 7. `main` corre los tres; `--only base` corre solo el primero.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb
from vectra_contracts.models.governance import PolicyDraft

from vectra_reference import generate as gen
from vectra_reference import proxy as px
from vectra_reference.adversarial import rt4_cases, write_adversarial
from vectra_reference.envelope.calibrate import Calibration, build_policy, calibrate_threshold
from vectra_reference.envelope.confidence import confidence
from vectra_reference.envelope.fit import fit_envelope
from vectra_reference.explainer_validation import ExplainerCheck, validate_explainer
from vectra_reference.features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    PLACEHOLDER_ID,
    Value,
    base_feature_spec,
    read_rows,
    row_values,
)
from vectra_reference.package import PURPOSE_RT2, build_package, dump_json
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
    out: Path
    datasets: Mapping[str, Path]


def _probabilities(
    booster: xgb.Booster,
    feature_order: tuple[str, ...],
    vocabulary: Mapping[str, Any],
    values: list[dict[str, Value]],
) -> np.ndarray:
    matrix = xgb.DMatrix(encode(values, feature_order, vocabulary), feature_names=list(feature_order))
    return np.asarray(booster.predict(matrix), dtype=np.float64)


def _background(config: Mapping[str, Any], train: Split) -> list[dict[str, Value]]:
    """Filas de fondo del explicador: una muestra fija de `train` (semilla `[seed, 2]`)."""
    chosen = np.sort(
        np.random.default_rng([int(config["seed"]), 2]).choice(
            len(train.values),
            size=min(int(config["package"]["background_rows"]), len(train.values)),
            replace=False,
        )
    )
    return [train.values[int(i)] for i in chosen]


def _confidences(envelope: Mapping[str, Any], values: list[dict[str, Value]]) -> list[str]:
    return [confidence(envelope, v) for v in values]


def run_release(
    out: Path,
    config: dict[str, Any] | None = None,
    *,
    datasets: Mapping[str, Path] | None = None,
    enforce_min_auc: bool = True,
    enforce_disparity: bool | None = None,
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

    background = _background(config, splits["train"])
    # BR-U5-06: la disparidad del modelo base sobre `validation`, con el doble de la libreria de U9 y el `outcome` completo
    # de BR-U7-04/05 (baja confianza, usura y corte), debe ser < 5 pp.
    reference_date = date.fromisoformat(str(config["reference_date"]))
    validation_rows = read_rows(paths["validation"])
    validation_probabilities = _probabilities(
        model.booster, model.feature_order, model.vocabulary, splits["validation"].values
    )
    outcomes = px.outcomes_of(
        validation_rows,
        validation_probabilities,
        _confidences(envelope, splits["validation"].values),
        policy,
        reference_date,
    )
    trigger, disparity = px.disparity_pp(validation_rows, outcomes, reference_date)
    if enforce_min_auc if enforce_disparity is None else enforce_disparity:
        px.check_base_disparity(disparity, config)
    stats = {
        "sizes": {name: len(splits[name].values) for name in gen.PARTITIONS},
        "default_rates": {name: round(float(splits[name].y.mean()), 6) for name in gen.PARTITIONS},
        "auc_validation": round(model.auc_validation, 6),
        "disparity_pp": disparity,
        "disparity_trigger_attribute": trigger,
        "validation_review_rate": round(outcomes.count(px.REVIEW) / len(outcomes), 6),
        "low_confidence_threshold": calibration.threshold,
        "test_above_threshold": round(calibration.test_above, 6),
    }
    package_dir = out / "package"
    manifest = build_package(package_dir, model, envelope, background, explainer.base_value, config, stats)
    policy_path = out / POLICY_FILE
    policy_path.write_bytes(dump_json(policy.model_dump(mode="json")))
    return Release(
        manifest, model, envelope, calibration, policy, rt4, rt4_confidence, test_confidence, splits,
        explainer, package_dir, policy_path, out, paths,
    )  # fmt: skip


@dataclass(frozen=True)
class ProxyRelease:
    manifests: list[dict[str, Any]]
    package_dirs: list[Path]
    model: TrainedModel
    envelope: dict[str, Any]
    explainer: ExplainerCheck
    disparity_pp: float
    trigger_attribute: str


def run_proxy_release(
    base: Release, config: dict[str, Any] | None = None, *, enforce_disparity: bool = True
) -> ProxyRelease:
    """Paso 6 (BR-U5-14, BR-U5-15): entrena la variante proxy y escribe `proxy/run-1` a `proxy/run-N`.

    Los N paquetes (N = `proxy.rt2_runs`, 5) comparten predictor, explicador y envolvente y difieren en `rt2_run` y, por
    eso, en `model_version_id`. Falla si la disparidad agregada de `validation` queda bajo `proxy.min_disparity_pp`.
    """
    config = config or gen.load_config()
    out, paths = base.out, base.datasets
    catalog = px.load_proxy_catalog()
    spec = px.proxy_feature_spec(catalog, config, PLACEHOLDER_ID)
    vocabulary = px.proxy_vocabulary(catalog, config)
    rows = {name: read_rows(paths[name]) for name in gen.PARTITIONS}
    splits = {
        name: Split(
            [px.with_lookups(v, r, spec) for v, r in zip(base.splits[name].values, rows[name], strict=True)],
            px.proxy_labels(rows[name], base.splits[name].y, spec, config, k),
        )
        for k, name in enumerate(gen.PARTITIONS)
    }
    model = train_model(
        splits["train"], splits["validation"], spec, config,
        enforce_min_auc=False, extra_allowed=px.PROXY_FEATURES, extra_vocabulary=vocabulary,
    )  # fmt: skip
    train_x = encode(splits["train"].values, model.feature_order, model.vocabulary)
    numeric_columns = [model.feature_order.index(name) for name in NUMERIC_FEATURES]
    categorical = (*CATEGORICAL_FEATURES, *px.PROXY_FEATURES)
    env = config["envelope"]
    envelope = fit_envelope(
        train_x[:, numeric_columns],
        NUMERIC_FEATURES,
        {name: [v[name] for v in splits["train"].values] for name in categorical},
        support_fraction=float(env["mcd_support_fraction"]),
        random_state=int(env["mcd_random_state"]),
        grid_size=int(env["distance_grid_size"]),
        max_rows=int(env["mcd_max_rows"]),
        model_version_id=PLACEHOLDER_ID,
    )
    reference_date = date.fromisoformat(str(config["reference_date"]))
    probabilities = _probabilities(
        model.booster, model.feature_order, model.vocabulary, splits["validation"].values
    )
    # La variante se sirve con la politica de referencia del modelo base (la demo no calibra otra).
    outcomes = px.outcomes_of(
        rows["validation"],
        probabilities,
        _confidences(envelope, splits["validation"].values),
        base.policy,
        reference_date,
    )
    trigger, disparity = px.disparity_pp(rows["validation"], outcomes, reference_date)
    if enforce_disparity:
        px.check_proxy_disparity(disparity, config)

    pkg = config["package"]
    n_check = int(pkg["explainer_validation_rows"])
    explainer = validate_explainer(
        model.booster,
        encode(splits["test"].values[:n_check], model.feature_order, model.vocabulary),
        list(model.feature_order),
        float(pkg["explainer_tolerance"]),
        float(pkg["explainer_margin_tolerance"]),
    )
    background = _background(config, splits["train"])
    stats = {
        "sizes": {name: len(splits[name].values) for name in gen.PARTITIONS},
        "default_rates": {name: round(float(splits[name].y.mean()), 6) for name in gen.PARTITIONS},
        "auc_validation": round(model.auc_validation, 6),
        "disparity_pp": disparity,
        "disparity_trigger_attribute": trigger,
        "validation_review_rate": round(outcomes.count(px.REVIEW) / len(outcomes), 6),
        "base_disparity_pp": base.manifest["disparity_pp"],
    }
    manifests, directories = [], []
    for run in range(1, int(config["proxy"]["rt2_runs"]) + 1):
        directory = out / "proxy" / f"run-{run}"
        manifests.append(
            build_package(
                directory, model, envelope, background, explainer.base_value, config, stats,
                spec_for=lambda version: px.proxy_feature_spec(catalog, config, version),
                purpose=PURPOSE_RT2, not_applicant_safe=px.PROXY_FEATURES, extra_meta={"rt2_run": run},
            )
        )  # fmt: skip
        directories.append(directory)
    ids = [m["model_version_id"] for m in manifests]
    if len(set(ids)) != len(ids):
        raise px.ProxyError("model_version_id_repeated")
    return ProxyRelease(manifests, directories, model, envelope, explainer, disparity, trigger)


def run_adversarial(base: Release, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Paso 7 (BR-U5-16..18): escribe `adversarial/manifest.json` y los cuatro paquetes RT-3 a partir del paquete base."""
    config = config or gen.load_config()
    return write_adversarial(
        base.out / "adversarial", base.package_dir, base.envelope, row_values, config, base.rt4
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Entrega de U5: datos, modelo, envolvente, paquete, variante proxy y adversarial"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--only",
        choices=("all", "base"),
        default="all",
        help="`base`: solo los Pasos 2 a 5 (sin variante proxy ni adversarial)",
    )
    args = parser.parse_args(argv)
    config = gen.load_config(args.config)
    release = run_release(args.out, config)
    print(  # noqa: T201
        f"{release.manifest['model_version_id']} auc={release.model.auc_validation:.4f} "
        f"disparidad={release.manifest['disparity_pp']}pp umbral={release.calibration.threshold} "
        f"paquete={release.package_dir}"
    )
    if args.only == "base":
        return 0
    proxy_release = run_proxy_release(release, config)
    print(  # noqa: T201
        f"proxy: {len(proxy_release.manifests)} paquetes disparidad={proxy_release.disparity_pp}pp "
        f"({proxy_release.trigger_attribute}) ids={[m['model_version_id'] for m in proxy_release.manifests]}"
    )
    adversarial = run_adversarial(release, config)
    print(f"adversarial: {len(adversarial['cases'])} casos en {args.out / 'adversarial'}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
