"""Paso 2: `params.py` carga `values-product-metrics-policy.yaml` y falla con un valor fuera de rango (BR-U11-09)."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from vectra_product import params
from vectra_product.params import Params, ParamsError

CHART = Path(__file__).resolve().parents[2] / "chart" / "values-product-metrics-policy.yaml"

VALID: dict[str, Any] = {
    "noise_floor": 0.6,
    "noise_sustain_days": 3,
    "noise_min_decisions": 50,
    "target_complete_response": 1.0,
    "target_origination_hours": 1,
    "target_origination_ratio": 0.8,
    "target_sustained_ratio_month6": 0.7,
    "target_north_star": None,
}


def write(tmp_path: Path, **changes: Any) -> Path:
    path = tmp_path / "values-product-metrics-policy.yaml"
    path.write_text(yaml.safe_dump(VALID | changes), encoding="utf-8")
    return path


def test_the_real_chart_file_loads_the_table_of_domain_entities() -> None:
    assert params.load(CHART) == Params(
        noise_floor=0.6,
        noise_sustain_days=3,
        noise_min_decisions=50,
        target_complete_response=1.0,
        target_origination_hours=1.0,
        target_origination_ratio=0.8,
        target_sustained_ratio_month6=0.7,
        target_north_star=None,
    )


def test_noise_min_decisions_20_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ParamsError, match="noise_min_decisions"):
        params.load(write(tmp_path, noise_min_decisions=20))


# (clave, valores en el limite que deben cargar, valores fuera de rango que deben fallar): cada rango de BR-U11-09
RANGES: list[tuple[str, list[Any], list[Any]]] = [
    ("noise_floor", [0.01, 0.99], [0, 0.0, 1, 1.0, -0.1, 1.5]),
    ("noise_sustain_days", [1, 14], [0, -1, 15]),
    ("noise_min_decisions", [30, 31], [29, 0, -5]),
    ("target_complete_response", [0.0, 1.0], [-0.01, 1.01]),
    ("target_origination_ratio", [0, 1], [-0.01, 1.01]),
    ("target_sustained_ratio_month6", [0.0, 1.0], [-0.5, 2]),
    ("target_origination_hours", [0.25, 8], [0, -1, 0.0]),
    ("target_north_star", [None, 0.0, 1.0], [-0.1, 1.1]),
]


@pytest.mark.parametrize(("key", "inside", "outside"), RANGES)
def test_each_range_in_and_out(tmp_path: Path, key: str, inside: list[Any], outside: list[Any]) -> None:
    for value in inside:
        assert getattr(params.load(write(tmp_path, **{key: value})), key) == value
    for value in outside:
        with pytest.raises(ParamsError, match=key):
            params.load(write(tmp_path, **{key: value}))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("noise_floor", "0.6"),
        ("noise_floor", True),
        ("noise_floor", float("nan")),
        ("noise_floor", float("inf")),
        ("noise_sustain_days", 3.0),
        ("noise_sustain_days", True),
        ("noise_min_decisions", "50"),
        ("target_complete_response", None),
        ("target_origination_hours", "1h"),
        ("target_north_star", "sin target"),
    ],
)
def test_wrong_types_fail(tmp_path: Path, key: str, value: Any) -> None:
    with pytest.raises(ParamsError, match=key):
        params.load(write(tmp_path, **{key: value}))


def test_missing_and_extra_keys_fail(tmp_path: Path) -> None:
    missing = dict(VALID)
    del missing["noise_floor"]
    path = tmp_path / "missing.yaml"
    path.write_text(yaml.safe_dump(missing), encoding="utf-8")
    with pytest.raises(ParamsError, match="keys_mismatch"):
        params.load(path)
    with pytest.raises(ParamsError, match="keys_mismatch"):
        params.load(write(tmp_path, extra=1))


@pytest.mark.parametrize("content", ["", "- 1\n- 2\n", "not: [valid", "\x00"])
def test_unreadable_or_non_mapping_fails(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ParamsError):
        params.load(path)


def test_missing_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ParamsError, match="unreadable"):
        params.load(tmp_path / "no-existe.yaml")


def test_environment_does_not_change_the_loaded_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in VALID:
        monkeypatch.setenv(key.upper(), "999")
        monkeypatch.setenv(key, "999")
    assert params.load(CHART).noise_min_decisions == 50
