"""Paso 3 (BR-U5-07, BR-U5-08; NFR-U5-10): entrenamiento, AUC minimo, features excluidas y determinismo."""

import hashlib
from typing import Any

import pytest
from vectra_contracts.models.features import FeatureSpec, FeatureSpecItem
from vectra_reference import generate as gen
from vectra_reference.features import BASE_FEATURES, FeatureSpecError, base_feature_spec
from vectra_reference.release import Release
from vectra_reference.train import TrainingError, predictor_bytes, train_model, xgb_params

CONFIG = gen.load_config()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_auc_of_validation_reaches_the_minimum_with_the_reference_seed(reference_release: Release) -> None:
    """BR-U5-08. Tambien BR-U5-05: el AUC de ~0,88 es el efecto de la funcion de riesgo latente del generador."""
    assert reference_release.model.auc_validation >= 0.85
    assert reference_release.model.auc_validation >= CONFIG["model"]["min_auc"]
    assert reference_release.manifest["auc_validation"] >= 0.85


def test_the_model_uses_exactly_the_allowed_features(reference_release: Release) -> None:
    assert reference_release.model.feature_order == BASE_FEATURES
    assert set(reference_release.model.booster.feature_names or []) == set(BASE_FEATURES)


@pytest.mark.parametrize(
    "item",
    [
        FeatureSpecItem(feature_id="sex", origin="field", source_fields=["sex"]),
        FeatureSpecItem(
            feature_id="socioeconomic_stratum", origin="field", source_fields=["socioeconomic_stratum"]
        ),
        FeatureSpecItem(feature_id="age_years", origin="derived"),
        FeatureSpecItem(feature_id="broker_id", origin="field", source_fields=["broker_id"]),
        FeatureSpecItem(feature_id="free_text", origin="field", source_fields=["free_text"]),
        FeatureSpecItem(feature_id="municipality_code", origin="field", source_fields=["municipality_code"]),
        FeatureSpecItem(
            feature_id="zona", origin="lookup", source_fields=["municipality_code"], table={"1": "a"}
        ),
        FeatureSpecItem(feature_id="extra_ajena", origin="field", source_fields=["monthly_income"]),
    ],
    ids=lambda item: item.feature_id,
)
def test_an_excluded_or_foreign_feature_in_the_spec_is_an_error(small_release: Release, item: Any) -> None:
    spec = FeatureSpec(model_version_id="mv-x", features=[*base_feature_spec().features, item])
    with pytest.raises(FeatureSpecError):
        train_model(small_release.splits["train"], small_release.splits["validation"], spec, CONFIG)


def test_training_fails_when_the_auc_is_below_the_minimum(small_release: Release) -> None:
    config = {**CONFIG, "model": {**CONFIG["model"], "min_auc": 0.99}}
    with pytest.raises(TrainingError, match="auc_below_minimum"):
        train_model(
            small_release.splits["train"], small_release.splits["validation"], base_feature_spec(), config
        )


def test_two_trainings_with_the_same_seed_give_the_same_predictor_sha256(reference_release: Release) -> None:
    train, validation = reference_release.splits["train"], reference_release.splits["validation"]
    first = train_model(train, validation, base_feature_spec(), CONFIG)
    second = train_model(train, validation, base_feature_spec(), CONFIG)
    assert _sha(predictor_bytes(first.booster)) == _sha(predictor_bytes(second.booster))
    packaged = (reference_release.package_dir / "predictor.json").read_bytes()
    assert _sha(predictor_bytes(first.booster)) == _sha(packaged)


def test_training_parameters_are_fixed() -> None:
    params = xgb_params(CONFIG)
    assert params["tree_method"] == "hist"
    assert isinstance(params["nthread"], int) and params["nthread"] >= 1
    assert isinstance(params["seed"], int)


def _small_sha(release: Release, config: dict[str, Any]) -> str:
    model = train_model(
        release.splits["train"],
        release.splits["validation"],
        base_feature_spec(),
        config,
        enforce_min_auc=False,
    )
    return _sha(predictor_bytes(model.booster))


def test_two_trainings_with_the_same_seed_are_identical_on_a_small_set(small_release: Release) -> None:
    assert _small_sha(small_release, CONFIG) == _small_sha(small_release, CONFIG)


def test_a_different_seed_changes_the_predictor(small_release: Release) -> None:
    """La semilla importa: con otra el SHA-256 cambia, asi que la prueba de determinismo no es vacia."""
    other = {**CONFIG, "model": {**CONFIG["model"], "seed": CONFIG["model"]["seed"] + 1}}
    assert _small_sha(small_release, CONFIG) != _small_sha(small_release, other)
