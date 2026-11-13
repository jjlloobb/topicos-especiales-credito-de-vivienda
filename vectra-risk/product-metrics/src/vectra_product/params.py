"""Parametros de cumplimiento de `values-product-metrics-policy.yaml` (BR-U11-09; domain-entities §4).

El chart los monta como `ConfigMap`; `load` falla al arrancar con un valor fuera de rango, una clave faltante o una clave de mas.
El archivo se parsea con `yaml.safe_load`; nada sale de variables de entorno.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Final

import yaml

from vectra_product import config
from vectra_product.model import Params

#: Donde el chart monta el archivo (como U9: sin `subPath`).
POLICY_PATH: Final = Path("/etc/vectra/product-metrics-policy/values-product-metrics-policy.yaml")


class ParamsError(Exception):
    """Archivo ilegible, clave faltante o de mas, o valor fuera de rango: el proceso no arranca."""


__all__ = ["POLICY_PATH", "Params", "ParamsError", "load", "parse"]

_KEYS: Final = frozenset(Params.__slots__)


def _number(raw: dict[str, Any], key: str) -> float:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ParamsError(f"{key}: no es un numero")
    return float(value)


def _integer(raw: dict[str, Any], key: str) -> int:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParamsError(f"{key}: no es un entero")
    return value


def _unit_closed(raw: dict[str, Any], key: str) -> float:
    value = _number(raw, key)
    if not config.TARGET_RATIO_MIN <= value <= config.TARGET_RATIO_MAX:
        raise ParamsError(f"{key}: fuera de {config.TARGET_RATIO_MIN:g}..{config.TARGET_RATIO_MAX:g}")
    return value


def parse(raw: Any) -> Params:
    """Valida el contenido ya leido contra los rangos de BR-U11-09."""
    if not isinstance(raw, dict) or set(raw) != _KEYS:
        raise ParamsError("params_keys_mismatch")
    floor = _number(raw, "noise_floor")
    if not config.NOISE_FLOOR_MIN_EXCLUSIVE < floor < config.NOISE_FLOOR_MAX_EXCLUSIVE:
        raise ParamsError(
            f"noise_floor: fuera de {config.NOISE_FLOOR_MIN_EXCLUSIVE:g} < F < {config.NOISE_FLOOR_MAX_EXCLUSIVE:g}"
        )
    sustain = _integer(raw, "noise_sustain_days")
    if not config.NOISE_SUSTAIN_DAYS_MIN <= sustain <= config.NOISE_SUSTAIN_DAYS_MAX:
        raise ParamsError(
            f"noise_sustain_days: fuera de {config.NOISE_SUSTAIN_DAYS_MIN}..{config.NOISE_SUSTAIN_DAYS_MAX}"
        )
    minimum = _integer(raw, "noise_min_decisions")
    if minimum < config.NOISE_MIN_DECISIONS_MIN:
        raise ParamsError(f"noise_min_decisions: menor que {config.NOISE_MIN_DECISIONS_MIN}")
    hours = _number(raw, "target_origination_hours")
    if hours <= config.TARGET_ORIGINATION_HOURS_MIN_EXCLUSIVE:
        raise ParamsError(
            f"target_origination_hours: no es mayor que {config.TARGET_ORIGINATION_HOURS_MIN_EXCLUSIVE:g}"
        )
    north_star = None if raw["target_north_star"] is None else _unit_closed(raw, "target_north_star")
    return Params(
        noise_floor=floor,
        noise_sustain_days=sustain,
        noise_min_decisions=minimum,
        target_complete_response=_unit_closed(raw, "target_complete_response"),
        target_origination_hours=hours,
        target_origination_ratio=_unit_closed(raw, "target_origination_ratio"),
        target_sustained_ratio_month6=_unit_closed(raw, "target_sustained_ratio_month6"),
        target_north_star=north_star,
    )


def load(path: Path = POLICY_PATH) -> Params:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ParamsError(f"params_unreadable:{type(error).__name__}") from error
    return parse(raw)
