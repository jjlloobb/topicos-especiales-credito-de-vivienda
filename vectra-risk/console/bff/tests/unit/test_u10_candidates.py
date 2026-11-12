"""Dos candidatas de `CANDIDATAS.md` que U10-T02 atiende (revisor, U10-T01, ronda 1: F-02 y F-05)."""

import re
from pathlib import Path
from typing import get_args

from vectra_contracts.models import governance as gov

from console_bff import config, object_rules

SPA_CONSTANTS = Path(__file__).resolve().parents[3] / "spa/src/config/constants.ts"


def _literal(model: type, field: str) -> tuple[str, ...]:
    return get_args(model.model_fields[field].annotation)  # type: ignore[attr-defined]


def test_the_literals_copied_in_object_rules_are_those_of_u0() -> None:
    """F-02: `DataSourceState`, `PolicyState` y `PolicyDecision` copian los `Literal` de `models/governance.py` (U0)."""
    assert get_args(object_rules.DataSourceState) == _literal(gov.DataSource, "state")
    assert get_args(object_rules.PolicyState) == _literal(gov.PolicyVersion, "state")
    assert get_args(object_rules.PolicyDecision) == _literal(gov.PolicyDecisionIn, "decision")
    assert get_args(object_rules.PolicyDecision) == _literal(gov.DataSourceDecisionIn, "decision")


def test_the_spa_api_timeout_is_the_one_of_the_bff_constants() -> None:
    """F-05: `SPA_API_TIMEOUT_SECONDS` duplica `API_TIMEOUT_SECONDS` de `constants.ts`: una prueba los ata."""
    found = re.search(
        r"export const API_TIMEOUT_SECONDS = (\d+(?:\.\d+)?);", SPA_CONSTANTS.read_text(encoding="utf-8")
    )
    assert found is not None
    assert float(found.group(1)) == config.SPA_API_TIMEOUT_SECONDS
