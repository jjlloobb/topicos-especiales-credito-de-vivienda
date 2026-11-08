"""PBT-U5-03 y PBT-U5-04 (envolvente y `confidence`) y la calibracion contra RT-4 (BR-U5-11..13; NFR-U5-33)."""

import json
import math
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from vectra_contracts.models.governance import PolicyDraft
from vectra_reference.adversarial import N_RT4, AdversarialError, outside_envelope, rt4_cases
from vectra_reference.envelope.calibrate import CalibrationError, build_policy, calibrate_threshold
from vectra_reference.envelope.confidence import confidence, confidence_raw, distances
from vectra_reference.envelope.fit import fit_envelope
from vectra_reference.features import (
    BASE_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    categorical_vocabulary,
    row_values,
)
from vectra_reference.generate import generate, load_config, with_overrides
from vectra_reference.release import Release
from vectra_reference.train import encode, load_split

CONFIG = load_config()


@pytest.fixture(scope="module")
def envelope(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Envolvente ajustada con un conjunto chico (6 000 filas): las propiedades no necesitan la entrega completa."""
    config = with_overrides(CONFIG, n_rows=6000)
    train = load_split(generate(tmp_path_factory.mktemp("envelope"), config)["train"])
    matrix = encode(train.values, BASE_FEATURES, categorical_vocabulary(config))
    return fit_envelope(
        matrix[:, [BASE_FEATURES.index(n) for n in NUMERIC_FEATURES]],
        NUMERIC_FEATURES,
        {name: [v[name] for v in train.values] for name in CATEGORICAL_FEATURES},
        support_fraction=config["envelope"]["mcd_support_fraction"],
        random_state=config["envelope"]["mcd_random_state"],
        grid_size=config["envelope"]["distance_grid_size"],
        model_version_id="mv-test",
    )


def _in_range_values(envelope: dict[str, Any], draw: st.DataObject) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for item in envelope["numeric"]:
        values[item["name"]] = draw.draw(st.floats(item["p1"], item["p99"], allow_nan=False))
    for name, seen in envelope["categories"].items():
        values[name] = draw.draw(st.sampled_from(seen))
    return values


@st.composite
def any_values(draw: st.DrawFn, envelope: dict[str, Any]) -> dict[str, Any]:
    """Entradas dentro y fuera de la envolvente, y con categorias vistas y no vistas."""
    values: dict[str, Any] = {}
    for item in envelope["numeric"]:
        span = max(item["p99"] - item["p1"], 1.0)
        values[item["name"]] = draw(
            st.one_of(
                st.floats(item["p1"], item["p99"], allow_nan=False),
                st.floats(item["p1"] - 10 * span, item["p99"] + 10 * span, allow_nan=False),
            )
        )
    for name, seen in envelope["categories"].items():
        values[name] = draw(st.one_of(st.sampled_from(seen), st.text(min_size=1, max_size=12)))
    return values


# PBT-U5-03 ------------------------------------------------------------------------------------------------------


@given(data=st.data())
def test_pbt_u5_03_confidence_is_in_the_unit_interval(envelope: dict[str, Any], data: st.DataObject) -> None:
    values = data.draw(any_values(envelope))
    raw = confidence_raw(envelope, values)
    assert 0.0 <= raw <= 1.0
    quantized = confidence(envelope, values)
    assert Decimal(0) <= Decimal(quantized) <= Decimal(1)
    assert len(quantized.split(".")[1]) == 4  # Decimal4 (BR-U0-07)


@given(data=st.data())
def test_pbt_u5_03_an_unseen_category_gives_zero(envelope: dict[str, Any], data: st.DataObject) -> None:
    values = _in_range_values(envelope, data)
    name = data.draw(st.sampled_from(sorted(envelope["categories"])))
    values[name] = data.draw(
        st.text(min_size=1, max_size=12).filter(lambda t: t not in envelope["categories"][name])
    )
    assert confidence_raw(envelope, values) == 0.0
    assert confidence(envelope, values) == "0.0000"


@given(data=st.data())
def test_pbt_u5_03_confidence_does_not_increase_as_a_feature_moves_away_from_the_range(
    envelope: dict[str, Any], data: st.DataObject
) -> None:
    """Parte del borde de [p1, p99] y se aleja mas, con las demas features dentro del rango y fijas."""
    values = _in_range_values(envelope, data)
    item = data.draw(st.sampled_from(envelope["numeric"]))
    span = max(item["p99"] - item["p1"], 1.0)
    upward = data.draw(st.booleans())
    near, far = sorted(data.draw(st.floats(0.0, 20.0)) for _ in range(2))

    def moved(shift: float) -> dict[str, Any]:
        value = item["p99"] + shift * span if upward else item["p1"] - shift * span
        return {**values, item["name"]: value}

    assert confidence_raw(envelope, moved(far)) <= confidence_raw(envelope, moved(near))


# PBT-U5-04 ------------------------------------------------------------------------------------------------------


def _oracle(envelope: dict[str, Any], values: dict[str, Any]) -> float:
    """BR-U5-12 escrito aparte, en Python puro (sin numpy): eliminacion gaussiana y busqueda lineal en F."""
    if any(str(values[name]) not in seen for name, seen in envelope["categories"].items()):
        return 0.0
    numeric = envelope["numeric"]
    x = [float(values[item["name"]]) for item in numeric]
    outside = sum(not (item["p1"] <= v <= item["p99"]) for item, v in zip(numeric, x, strict=True))
    c_range = 1.0 - outside / len(numeric)
    k = len(x)
    delta = [v - m for v, m in zip(x, envelope["mean"], strict=True)]
    a = [[*row, delta[i]] for i, row in enumerate(envelope["covariance"])]
    for col in range(k):  # Gauss-Jordan con pivote parcial: resuelve Sigma y = delta
        pivot = max(range(col, k), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        a[col] = [v / a[col][col] for v in a[col]]
        for r in range(k):
            if r != col:
                f = a[r][col]
                a[r] = [v - f * w for v, w in zip(a[r], a[col], strict=True)]
    d = math.sqrt(max(sum(delta[i] * a[i][k] for i in range(k)), 0.0))
    grid = envelope["distance_quantiles"]
    n = len(grid)
    if d <= grid[0]:
        f_d = 0.0
    elif d >= grid[-1]:
        f_d = 1.0
    else:
        i = max(j for j in range(n) if grid[j] <= d)
        f_d = (i + (d - grid[i]) / (grid[i + 1] - grid[i])) / (n - 1)
    return min(c_range, 1.0 - f_d)


@given(data=st.data())
def test_pbt_u5_04_the_shared_implementation_matches_an_independent_one(
    envelope: dict[str, Any], data: st.DataObject
) -> None:
    """U6 importa esta misma funcion con `domain_envelope.json`: se fija contra un oraculo y contra la ruta JSON."""
    values = data.draw(any_values(envelope))
    expected = _oracle(envelope, values)
    assert confidence_raw(envelope, values) == pytest.approx(expected, abs=1e-9)
    shipped = json.loads(json.dumps(envelope))  # lo que lee U6 de domain_envelope.json
    assert confidence(shipped, values) == confidence(envelope, values)
    assert abs(Decimal(confidence(envelope, values)) - Decimal(repr(expected))) <= Decimal("0.0001")


# Ramas de confidence y funciones de apoyo -----------------------------------------------------------------------


def test_confidence_rejects_a_missing_feature(envelope: dict[str, Any]) -> None:
    values = {
        **dict.fromkeys(NUMERIC_FEATURES, 1.0),
        **{c: envelope["categories"][c][0] for c in CATEGORICAL_FEATURES},
    }
    for name in (*NUMERIC_FEATURES[:1], *CATEGORICAL_FEATURES[:1]):
        broken = {k: v for k, v in values.items() if k != name}
        with pytest.raises(ValueError, match=f"feature_missing:{name}"):
            confidence_raw(envelope, broken)


def test_confidence_is_zero_for_a_non_finite_distance(envelope: dict[str, Any]) -> None:
    values = _central_values(envelope)
    values["monthly_income"] = float("nan")
    assert confidence_raw(envelope, values) == 0.0
    values["monthly_income"] = float("inf")
    assert confidence_raw(envelope, values) == 0.0


def _central_values(envelope: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {item["name"]: (item["p1"] + item["p99"]) / 2 for item in envelope["numeric"]}
    values.update({name: seen[0] for name, seen in envelope["categories"].items()})
    return values


def test_the_median_input_has_a_high_confidence_and_far_inputs_have_none(envelope: dict[str, Any]) -> None:
    near = dict(zip(NUMERIC_FEATURES, envelope["mean"], strict=True))
    near.update({name: seen[0] for name, seen in envelope["categories"].items()})
    assert Decimal(confidence(envelope, near)) > Decimal("0.5")
    far = {**near, "monthly_income": 10**12}
    assert confidence(envelope, far) == "0.0000"


def test_distances_of_the_centre_are_zero() -> None:
    assert distances([1.0, 2.0], [[2.0, 0.0], [0.0, 3.0]], np.array([[1.0, 2.0]]))[0] == 0.0


# Envolvente (BR-U5-11) -------------------------------------------------------------------------------------------


def test_the_envelope_has_the_parts_of_br_u5_11(envelope: dict[str, Any]) -> None:
    assert [item["name"] for item in envelope["numeric"]] == list(NUMERIC_FEATURES)
    assert all(item["p1"] <= item["p99"] for item in envelope["numeric"])
    assert set(envelope["categories"]) == set(CATEGORICAL_FEATURES)
    k = len(NUMERIC_FEATURES)
    assert len(envelope["mean"]) == k and len(envelope["covariance"]) == k
    grid = envelope["distance_quantiles"]
    assert len(grid) == CONFIG["envelope"]["distance_grid_size"]
    assert all(a <= b for a, b in zip(grid, grid[1:], strict=False))


def test_fit_envelope_is_deterministic_and_subsamples_when_asked() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(600, 3))
    kwargs: dict[str, Any] = {
        "support_fraction": 0.9,
        "random_state": 1,
        "grid_size": 11,
        "model_version_id": "mv-x",
    }
    categories = {"c": ["a"] * 600}
    one = fit_envelope(x, ["a", "b", "c"], categories, max_rows=200, **kwargs)
    two = fit_envelope(x, ["a", "b", "c"], categories, max_rows=200, **kwargs)
    full = fit_envelope(x, ["a", "b", "c"], categories, **kwargs)
    assert one == two
    assert one["mean"] != full["mean"]
    assert full["n_train"] == 600


# Calibracion contra RT-4 (BR-U5-13) y politica de referencia --------------------------------------------------


def test_the_18_rt4_cases_fall_below_the_threshold_and_95_percent_of_test_above(
    reference_release: Release,
) -> None:
    threshold = Decimal(reference_release.calibration.threshold)
    assert len(reference_release.rt4) == N_RT4 == 18
    assert all(Decimal(c) < threshold for c in reference_release.rt4_confidence), (
        reference_release.rt4_confidence
    )
    above = sum(Decimal(c) >= threshold for c in reference_release.test_confidence) / len(
        reference_release.test_confidence
    )
    assert above >= 0.95
    assert above == pytest.approx(reference_release.calibration.test_above)


def test_the_rt4_cases_are_valid_applications_outside_the_envelope(reference_release: Release) -> None:
    for case in reference_release.rt4:
        assert case["scenario"] == "RT-4"
        assert outside_envelope(reference_release.envelope, row_values(case["input"])), case["case_id"]


def test_reference_policy_json_is_valid_according_to_policy_draft(reference_release: Release) -> None:
    raw = reference_release.policy_path.read_bytes()
    policy = PolicyDraft.model_validate_json(raw)
    assert policy.low_confidence_threshold == reference_release.calibration.threshold
    assert policy == reference_release.policy
    assert Decimal(policy.low_confidence_threshold) > 0


def test_calibration_fails_when_an_rt4_case_is_not_below_the_threshold() -> None:
    train = ["0.5000"] * 99 + ["0.0100"]
    with pytest.raises(CalibrationError, match="rt4_not_below_threshold"):
        calibrate_threshold(train, ["0.5000"] * 10, ["0.5000"], quantile=0.5, min_test_above=0.95)


def test_calibration_fails_when_test_is_not_95_percent_above() -> None:
    with pytest.raises(CalibrationError, match="test_below_minimum"):
        calibrate_threshold(["0.5000"] * 10, ["0.4000"] * 10, ["0.0000"], quantile=0.5, min_test_above=0.95)


def test_calibration_returns_a_floored_decimal4_threshold() -> None:
    result = calibrate_threshold(
        [f"{i / 1000:.4f}" for i in range(1000)],
        ["0.9000"] * 20,
        ["0.0000"],
        quantile=0.0305,
        min_test_above=0.95,
    )
    assert result.threshold == "0.0304"  # 0,03047 baja a 0,0304 (redondear daria 0,0305)


def test_the_policy_builder_validates_with_the_u0_contract() -> None:
    policy = build_policy(CONFIG, "0.0300")
    assert policy.low_confidence_threshold == "0.0300" and policy.channel_rules == []


def test_rt4_generation_rejects_an_in_envelope_or_invalid_case(envelope: dict[str, Any]) -> None:
    with pytest.raises(AdversarialError, match="fuera de la envolvente"):
        rt4_cases(envelope, lambda _app: _central_values(envelope))
    long_name = "x" * 201  # `full_name` admite 200 caracteres
    with pytest.raises(AdversarialError, match="valida"):
        rt4_cases(envelope, row_values, {"given_names": [long_name] * 40, "surnames": ["y"] * 40})
