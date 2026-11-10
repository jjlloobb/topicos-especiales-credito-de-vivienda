"""Ventana de cada version (BR-U9-08, BR-U9-15; domain-entities §1.2). Pura: recibe «hoy», no lee el reloj."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from vectra_contracts.models.monitoring import FreezeRecord, VersionWindow

BEFORE_SHIFT_DAYS = 7  # «antes» termina 7 dias antes de hoy (BR-U9-15)
RECENT_DAYS = 7  # «ultimos 7 dias»: de hoy - 6 a hoy


@dataclass(frozen=True)
class Span:
    from_day: date
    to_day: date


@dataclass(frozen=True)
class VersionRanges:
    """Los cuatro rangos de una version. `None` = sin datos posibles (el rango cae antes del inicio de la ventana)."""

    window_start: date
    before: Span | None
    after: Span | None
    last_7_days: Span | None
    human_after: Span | None


def last_reactivation(records: Iterable[FreezeRecord]) -> dict[str, datetime]:
    """`recorded_at` de la ultima `reactivar` por version, entre todas las resoluciones (`investigar` y luego `reactivar`
    son dos; cuenta la `reactivar`, BR-U9-19)."""
    latest: dict[str, datetime] = {}
    for record in records:
        for resolution in record.resolutions:
            if resolution.action == "reactivar":
                current = latest.get(record.model_version_id)
                if current is None or resolution.recorded_at > current:
                    latest[record.model_version_id] = resolution.recorded_at
    return latest


def evaluated_versions(versions: Sequence[VersionWindow], today: date) -> list[str]:
    """Versiones con recomendaciones hoy o ayer (BR-U9-08), en orden estable."""
    seen = {v.model_version_id for v in versions if v.population == "modelo" and v.last_day >= today - timedelta(days=1)}
    return sorted(seen)


def window_start(first_day: date, reactivated_at: datetime | None) -> date:
    """El mas tardio entre el primer dia con datos y el dia siguiente (fecha UTC) al `recorded_at` de la ultima `reactivar`."""
    if reactivated_at is None:
        return first_day
    return max(first_day, reactivated_at.astimezone(UTC).date() + timedelta(days=1))


def _clip(nominal_from: date, nominal_to: date, start: date) -> Span | None:
    first = max(nominal_from, start)
    return Span(first, nominal_to) if first <= nominal_to else None


def version_ranges(today: date, window_days: int, first_day: date, reactivated_at: datetime | None) -> VersionRanges:
    """Los rangos de BR-U9-15 desde `window_days` (con 30: antes de hoy-36 a hoy-7, despues de hoy-29 a hoy, 7 dias de hoy-6 a hoy).

    Todos respetan el inicio de la ventana. Con menos de 7 dias de datos el rango «antes» queda vacio (`None` = `sin_datos`).
    """
    start = window_start(first_day, reactivated_at)
    after_from = today - timedelta(days=window_days - 1)
    before_to = today - timedelta(days=BEFORE_SHIFT_DAYS)
    after = _clip(after_from, today, start)
    return VersionRanges(
        window_start=start,
        before=_clip(before_to - timedelta(days=window_days - 1), before_to, start),
        after=after,
        last_7_days=_clip(today - timedelta(days=RECENT_DAYS - 1), today, start),
        human_after=after,
    )
