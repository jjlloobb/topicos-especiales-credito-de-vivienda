"""Las features del modelo base coinciden con `derive` de U0 (BR-U5-07) y el `feature_spec` base es valido."""

from datetime import date

from vectra_contracts.labels import derive
from vectra_contracts.models.application import ApplicationIn
from vectra_reference import generate as gen
from vectra_reference.features import (
    BASE_FEATURES,
    CATEGORICAL_FEATURES,
    EXCLUDED_FEATURES,
    NUMERIC_FEATURES,
    base_feature_spec,
    categorical_vocabulary,
    row_values,
    validate_feature_spec,
)

CONFIG = gen.with_overrides(gen.load_config(), n_rows=300)


def test_row_values_equal_the_feature_vector_that_derive_produces() -> None:
    spec = base_feature_spec()
    for row in gen.build_rows(CONFIG):
        application = ApplicationIn.model_validate(gen.application_fields(row))
        vector = derive(application, date(2026, 1, 1), spec).features
        values = row_values(row)
        assert list(values) == list(BASE_FEATURES)
        for name, value in values.items():
            produced = vector[name].value  # type: ignore[union-attr]
            if name in CATEGORICAL_FEATURES:
                assert produced == value
            else:
                assert float(produced) == value  # `derive` da `proposed_rate_ea` como cadena Decimal4


def test_the_base_spec_is_valid_and_has_no_excluded_feature() -> None:
    spec = base_feature_spec()
    validate_feature_spec(spec)
    assert not EXCLUDED_FEATURES & {item.feature_id for item in spec.features}
    assert set(NUMERIC_FEATURES) | set(CATEGORICAL_FEATURES) == set(BASE_FEATURES)
    assert len(BASE_FEATURES) == 12


def test_the_categorical_vocabulary_comes_from_the_configuration() -> None:
    vocabulary = categorical_vocabulary(CONFIG)
    assert set(vocabulary) == set(CATEGORICAL_FEATURES)
    assert vocabulary["channel"] == list(CONFIG["marginals"]["channel_weights"])
