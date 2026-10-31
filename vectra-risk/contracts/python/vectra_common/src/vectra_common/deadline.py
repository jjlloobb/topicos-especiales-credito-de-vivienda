"""Lectura de `x-vectra-deadline` (NFR-U0-23 (b), (h); P-U0-07)."""

from collections.abc import Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Final

from vectra_common.errors import DeadlineExceeded

HEADER: Final = "x-vectra-deadline"
current_deadline: Final[ContextVar[datetime | None]] = ContextVar("vectra_deadline", default=None)


def parse(value: str) -> datetime | None:
    """Instante absoluto en RFC 3339 con zona; cualquier otra cosa es una cabecera mal formada."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def read(headers: Mapping[str, str], now: datetime) -> datetime | None:
    """Descarta la mal formada; una vencida agota el presupuesto (504 inmediato)."""
    raw = headers.get(HEADER)
    if raw is None:
        return None
    deadline = parse(raw)
    if deadline is None:
        return None
    if deadline <= now:
        raise DeadlineExceeded()
    return deadline


def to_header(deadline: datetime) -> str:
    return deadline.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
