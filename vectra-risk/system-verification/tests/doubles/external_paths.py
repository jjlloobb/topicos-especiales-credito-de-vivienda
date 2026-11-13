"""Rutas de los dobles de otras unidades (solo pruebas; `src/` nunca las importa): las de U10 (BFF) y U8 (`case-service`) y los generadores de U0 que usan. Los nombres `bff_*`, `case_*`, `u8_support`
y `strategies` no chocan con los de U12."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def use_u10_doubles() -> None:
    for path in (
        ROOT / "console" / "bff" / "tests" / "doubles",
        ROOT / "contracts" / "tests",
        ROOT / "console" / "bff" / "src",
    ):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def use_u8_doubles() -> None:
    for path in (
        ROOT / "case-management" / "tests" / "doubles",
        ROOT / "case-management" / "tests" / "migrations",
        ROOT / "contracts" / "tests",
    ):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
