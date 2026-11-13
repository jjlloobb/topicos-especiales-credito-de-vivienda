"""Latencia de deteccion de RT-2 (U12 Paso 3; BR-U12-07; INF-U12-03). Logica pura: sin E/S.

Inicio = el menor `recorded_at` de las `recommendation` del lote `stratified`; fin = el `recorded_at` de la entrada `freeze`. Medir desde la primera
entrada nunca subestima la latencia (puede sobrestimarla hasta ~3 min). `passed` es `latency_seconds <= 1 800`: 1 800 s exactos pasan. Un lote vacio, una
hora sin zona o fuera de UTC, o un `freeze` anterior al inicio son un error, no una medicion. Una corrida que supera el limite no es un error: se registra con
`passed = False`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

LIMIT: Final = timedelta(seconds=1_800)  # 30 min (NFR-U9-01)
RUNS: Final = (1, 2, 3, 4, 5)  # una corrida por version del proxy (BR-U12-07)


@dataclass(frozen=True)
class Rt2Measurement:
    run: int
    batch_first_recorded_at: datetime
    freeze_recorded_at: datetime
    latency_seconds: float
    passed: bool


def _utc(value: datetime, name: str) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"not_utc:{name}")
    return value.astimezone(UTC)


def measure(
    run: int, recommendation_recorded_at: Sequence[datetime], freeze_recorded_at: datetime
) -> Rt2Measurement:
    """La medicion de una corrida de RT-2 (`run` 1..5)."""
    if run not in RUNS:
        raise ValueError(f"run_out_of_range:{run}")
    if not recommendation_recorded_at:
        raise ValueError("empty_batch")
    first = min(_utc(value, "recommendation") for value in recommendation_recorded_at)
    freeze = _utc(freeze_recorded_at, "freeze")
    latency = freeze - first
    if latency < timedelta(0):
        raise ValueError("freeze_before_batch")
    return Rt2Measurement(
        run=run,
        batch_first_recorded_at=first,
        freeze_recorded_at=freeze,
        latency_seconds=latency.total_seconds(),
        passed=latency <= LIMIT,
    )
