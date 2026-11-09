"""Cadena de hashes de U3: `canonicalize`, `link` y `decode` (Paso 3 del plan; BR-U3-09, 10; domain-entities §1.1).

Funciones puras, sin E/S (contrato `pure-no-io` de import-linter). El hash se calcula y se verifica sobre los **bytes
guardados** en `canonical` (BR-U3-09): `decode` solo los lee; nada en esta unidad vuelve a serializar una entrada guardada.
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from vectra_contracts.canonical import canonicalize as jcs

#: BR-U3-10: la genesis (`seq = 0`) lleva 32 bytes en cero como `prev_hash`.
GENESIS_PREV_HASH = bytes(32)
HASH_LENGTH = 32


@dataclass(frozen=True)
class Row:
    """Una fila de `registry_entries` (domain-entities §1): columnas consultables, `canonical` y la cadena de hashes."""

    seq: int
    idempotency_key: UUID
    entry_type: str
    case_id: UUID | None
    model_version_id: str | None
    policy_version_id: str | None
    actor_kind: str
    actor_id: str
    actor_role: str | None
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: str
    contract_version: str
    canonical: bytes
    prev_hash: bytes
    hash: bytes


def format_timestamp(moment: datetime) -> str:
    """ISO 8601 en UTC con microsegundos y `Z` (`2026-11-08T10:00:00.000000Z`), el formato de los sellos de `canonical`.

    La migracion `0001` escribe la genesis con este mismo formato (`timespec="microseconds"`). Un `datetime` sin zona es un error.
    """
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("un sello de tiempo del registro lleva zona horaria")
    return moment.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _plain(value: object) -> object:
    """Los `datetime` salen en el formato fijo, los `date` en ISO y los `UUID` como texto; el resto lo decide JCS."""
    if isinstance(value, datetime):
        return format_timestamp(value)
    if isinstance(value, date):  # un `date` del payload (por ejemplo `window_start`): ISO 8601 sin hora
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        mapping: Mapping[str, object] = value
        return {key: _plain(inner) for key, inner in mapping.items()}
    if isinstance(value, list | tuple):
        return [_plain(inner) for inner in value]
    return value


def canonicalize(entry: object) -> bytes:
    """Bytes JCS (RFC 8785) de una entrada nueva: los sellos de tiempo se fijan con `format_timestamp` y no hay flotantes."""
    return jcs(_plain(entry))


def link(prev_hash: bytes, canonical: bytes) -> bytes:
    """`SHA-256(prev_hash || canonical)` (BR-U3-09). La genesis enlaza con `GENESIS_PREV_HASH`."""
    if len(prev_hash) != HASH_LENGTH:
        raise ValueError("prev_hash tiene 32 bytes")
    return hashlib.sha256(prev_hash + canonical).digest()


def _no_float(text: str) -> object:
    raise ValueError("el JSON canonico no admite flotantes")


def decode(canonical: bytes) -> dict[str, Any]:
    """Lee los bytes guardados como un objeto JSON (sin contratos: un campo opcional nuevo no cambia nada, PBT-U3-05).

    `ValueError` si no es UTF-8, no es JSON, no es un objeto o trae flotantes.
    """
    try:
        value = json.loads(canonical.decode("utf-8"), parse_float=_no_float, parse_constant=_no_float)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("canonical no es JSON valido") from error
    if not isinstance(value, dict):
        raise ValueError("canonical no es un objeto JSON")
    return value
