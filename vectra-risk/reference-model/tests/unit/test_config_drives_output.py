"""BR-U5-01: los parametros del generador salen de `generator.yaml`; cambiarlos cambia la salida (U05-T01, F-03)."""

from collections.abc import Callable
from typing import Any

import pytest
from vectra_reference import generate as gen

BASE = gen.with_overrides(gen.load_config(), n_rows=400)


def _rows(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return gen.build_rows(cfg)


def _col(rows: list[dict[str, Any]], name: str) -> list[Any]:
    return [r[name] for r in rows]


def _set(path: tuple[str, ...], value: Any) -> Callable[[dict[str, Any]], None]:
    def apply(cfg: dict[str, Any]) -> None:
        node = cfg
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return apply


CASES = [
    (("marginals", "employment_tenure", "mean_months"), 600.0, "employment_months"),
    (("marginals", "employment_tenure", "max_months"), 12, "employment_months"),
    (("marginals", "employment_tenure", "adult_age"), 40, "employment_months"),
    (("marginals", "property", "vis_margin"), 0.30, "property_value"),
    (("marginals", "income", "undeclared_stratum"), 6, "monthly_income"),
    (("marginals", "address", "streets"), 3, "address"),
    (("marginals", "address", "max_number"), 3, "address"),
    (("marginals", "brokers"), 2, "broker_id"),
]


@pytest.mark.parametrize(("path", "value", "column"), CASES)
def test_changing_a_parameter_changes_the_output(path: tuple[str, ...], value: Any, column: str) -> None:
    base = _rows(BASE)
    cfg = gen.with_overrides(BASE)
    _set(path, value)(cfg)
    assert _col(_rows(cfg), column) != _col(base, column), path


def test_the_same_configuration_gives_the_same_rows() -> None:
    assert _rows(BASE) == _rows(gen.with_overrides(BASE))
