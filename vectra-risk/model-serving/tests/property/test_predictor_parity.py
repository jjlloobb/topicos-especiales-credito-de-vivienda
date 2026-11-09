"""PBT-U5-04 contra el predictor (NFR-U6-05): `confidence` de `:predict` coincide con `envelope.confidence` de U5."""

from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from vectra_predictor.core import Predictor
from vectra_reference.envelope.confidence import confidence

from serving_helpers import feature_vector, load_predictor_package, rounded, values_strategy


@pytest.fixture(scope="module")
def predictor(package_dir: Path) -> Predictor:
    return Predictor(load_predictor_package(package_dir))


@given(data=st.data())
def test_pbt_u5_04_predictor_confidence_matches_the_shared_function(
    predictor: Predictor, data: st.DataObject
) -> None:
    """Para todo `FeatureVector` valido (dentro y fuera de la envolvente, con categorias no vistas), mismo valor."""
    envelope: dict[str, Any] = predictor.envelope
    values = data.draw(values_strategy(envelope, list(predictor.model.feature_order)))
    got = predictor.predict(feature_vector(values))
    assert got.confidence == confidence(envelope, rounded(values))
    assert 0.0 <= float(got.confidence) <= 1.0


@given(data=st.data())
def test_pbt_u5_04_an_unseen_category_gives_zero_confidence(
    predictor: Predictor, data: st.DataObject
) -> None:
    values = data.draw(values_strategy(predictor.envelope, list(predictor.model.feature_order)))
    name = data.draw(st.sampled_from(sorted(predictor.envelope["categories"])))
    values[name] = "no_vista"
    assert predictor.predict(feature_vector(values)).confidence == "0.0000"
