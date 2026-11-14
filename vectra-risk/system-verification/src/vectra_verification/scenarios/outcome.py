"""Resultado de tres valores de un oraculo (U12-T03, P-4 (a); BR-U12-11; NFR-U12-42). Logica pura: sin E/S.

Todo oraculo devuelve un `Outcome`: `pasa`, `falla` o `no ejecutado`, con `expected` y `obtained` en texto (iguales si y solo si pasa), **que falto** (codigos estables: vacio en
`pasa`, no vacio en los otros dos), los sub-resultados, las consultas a Prometheus usadas (`QueryResult`: texto y ventana, NFR-U12-50) y las lecturas (conteos, estados, mediciones:
nunca datos del solicitante). `no ejecutado` no es una `Evidence`: `to_evidence` devuelve `None` y el informe lo marca `no ejecutado` por falta de evidencia (BR-U12-11).
`falla` es que el sistema respondio y no cumplio; `no ejecutado`, que faltaba un prerrequisito y el oraculo no pudo juzgar.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

from vectra_verification.clients.prom import QueryResult
from vectra_verification.report import FALLA, NO_EJECUTADO, PASA, Evidence, Result

MANDATORY: Final = "obligatorio"
OPTIONAL: Final = "opcional"


@dataclass(frozen=True)
class SubOutcome:
    """El resultado de una parte de un escenario (un paquete de RT-3, una fase de RT-2), con su codigo de «que falto»."""

    name: str
    result: Result
    missing: tuple[str, ...] = ()
    detail: str = ""
    mandatory: bool = True
    readings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check(self.result, self.missing, self.name)


def _check(result: str, missing: Sequence[str], name: str) -> None:
    if result not in (PASA, FALLA, NO_EJECUTADO):
        raise ValueError(f"result_unknown:{name}:{result}")
    if result == PASA and missing:
        raise ValueError(f"pasa_with_missing:{name}")
    if result != PASA and not missing:
        raise ValueError(f"{'falla' if result == FALLA else 'no_ejecutado'}_without_missing:{name}")


@dataclass(frozen=True)
class Outcome:
    id: str
    result: Result
    expected: str
    obtained: str
    missing: tuple[str, ...] = ()
    subresults: tuple[SubOutcome, ...] = ()
    queries: tuple[QueryResult, ...] = ()
    readings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check(self.result, self.missing, self.id)
        if (self.result == PASA) != (self.expected == self.obtained):
            raise ValueError(f"expected_obtained_mismatch:{self.id}")


def combine(subresults: Sequence[SubOutcome]) -> tuple[Result, tuple[str, ...]]:
    """P-2 (a): un `falla` (obligatorio u opcional) baja el resultado; un `no ejecutado` obligatorio lo deja `no ejecutado`; uno opcional no lo baja."""
    failed = [s for s in subresults if s.result == FALLA]
    if failed:
        return FALLA, tuple(code for s in failed for code in s.missing)
    pending = [s for s in subresults if s.result == NO_EJECUTADO and s.mandatory]
    if pending:
        return NO_EJECUTADO, tuple(code for s in pending for code in s.missing)
    return PASA, ()


def from_subresults(
    outcome_id: str,
    expected: str,
    subresults: Sequence[SubOutcome],
    *,
    readings: Mapping[str, Any] | None = None,
    queries: Sequence[QueryResult] = (),
) -> Outcome:
    """Un `Outcome` cuyo resultado sale de combinar los sub-resultados."""
    result, missing = combine(subresults)
    return Outcome(
        outcome_id,
        result,
        expected,
        expected
        if result == PASA
        else "; ".join(f"{s.name}={s.result}" for s in subresults if s.result != PASA),
        missing,
        tuple(subresults),
        tuple(queries),
        dict(readings or {}),
    )


def to_evidence(
    outcome: Outcome,
    *,
    command: str,
    output: str,
    commit: str,
    images: Mapping[str, str],
    executed_at: datetime,
    operator: str,
) -> Evidence | None:
    """La `Evidence` de un resultado; `no ejecutado` no da ninguna (BR-U12-11)."""
    if outcome.result == NO_EJECUTADO:
        return None
    return Evidence(
        id=outcome.id,
        command=command,
        output=output,
        expected=outcome.expected,
        obtained=outcome.obtained,
        result="pasa" if outcome.result == PASA else "falla",
        commit=commit,
        images=images,
        executed_at=executed_at,
        operator=operator,
    )


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return {name: _plain(getattr(value, name)) for name in value.__dataclass_fields__}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def to_text(outcome: Outcome) -> str:
    """El resultado serializado (JSON) tal como lo escribira el Paso 13: pasa por `evidence.prepare` sin cambios."""
    return json.dumps(_plain(outcome), ensure_ascii=False, indent=2, sort_keys=True)
