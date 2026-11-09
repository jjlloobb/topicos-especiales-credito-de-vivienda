"""Archivo mensual de largo plazo (Paso 11; NFR-U3-04; P-U3-07; BR-U3-12).

`registry-{yyyy-mm}.ndjson.zst`: una linea por entrada (`seq`, `prev_hash`, `hash`, `canonical` en base64), comprimida con zstd, y
`registry-{yyyy-mm}.manifest.json`: `{from_seq, to_seq, head_hash, checkpoints, sha256, contract_versions, ...}` firmado con la
llave de checkpoints. El formato no depende de la version de PostgreSQL.

Cada checkpoint cubre una entrada de hasta una hora antes; para que el archivo se verifique **sin base de datos**, empieza en
`anchor_seq`: la entrada anterior al mes o la mas antigua que cubre un checkpoint del mes (lo que sea menor), y solo ancla el enlace.
Las columnas consultables no se archivan (salen de `canonical`), asi que `column_mismatch` es solo de la base.
"""

import base64
import hashlib
import io
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import zstandard
from vectra_contracts.canonical import canonicalize as jcs
from vectra_contracts.models.registry import IntegrityReason, IntegrityReport

from vectra_registry.chain import Row, decode
from vectra_registry.verify import ListSource, _checkpoint_fields, _signature_ok, verify


class ArchiveError(Exception):
    """El archivo no se puede leer (no es zstd, una linea mal formada)."""


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """`[inicio, siguiente)` en UTC del mes `AAAA-MM`."""
    try:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=UTC)  # noqa: DTZ007 - se fija UTC en la misma linea
    except ValueError as error:
        raise ValueError(f"mes invalido: {month!r} (AAAA-MM)") from error
    following = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)  # noqa: PLR2004
    return start, following


def archive_key(month: str) -> str:
    return f"registry-{month}.ndjson.zst"


def manifest_key(month: str) -> str:
    return f"registry-{month}.manifest.json"


class Writer:
    """Escribe el archivo de forma incremental: se le pasan los tramos leidos de la replica (<= 10 000 entradas)."""

    def __init__(self) -> None:
        self._buffer = io.BytesIO()
        self._stream = zstandard.ZstdCompressor(level=10).stream_writer(self._buffer, closefd=False)
        self.versions: set[str] = set()
        self.checkpoints: list[int] = []
        self.first: int | None = None
        self.last: Row | None = None

    def add(self, rows: Iterable[Row]) -> None:
        for row in rows:
            line = {
                "seq": row.seq,
                "prev_hash": row.prev_hash.hex(),
                "hash": row.hash.hex(),
                "canonical": base64.b64encode(row.canonical).decode(),
            }
            self._stream.write(json.dumps(line, separators=(",", ":")).encode() + b"\n")
            self.versions.add(row.contract_version)
            if row.entry_type == "checkpoint":
                self.checkpoints.append(row.seq)
            if self.first is None:
                self.first = row.seq
            self.last = row

    def finish(self) -> bytes:
        self._stream.close()  # type: ignore[no-untyped-call]
        return self._buffer.getvalue()


def manifest_message(manifest: Mapping[str, Any]) -> bytes:
    """Lo que firma la boveda: el manifiesto sin su firma, en JCS."""
    return jcs({k: v for k, v in manifest.items() if k != "signature"})


def build_manifest(writer: Writer, data: bytes, month: str, from_seq: int, key_fingerprint: str) -> dict[str, Any]:
    """El manifiesto del mes, sin firmar. `from_seq` es la primera entrada **del mes**; el archivo puede empezar antes (`anchor_seq`)."""
    assert writer.last is not None and writer.first is not None  # noqa: S101 - un archivo vacio no se cierra
    return {
        "month": month,
        "from_seq": from_seq,
        "to_seq": writer.last.seq,
        "anchor_seq": writer.first,
        "head_hash": writer.last.hash.hex(),
        "checkpoints": writer.checkpoints,
        "sha256": hashlib.sha256(data).hexdigest(),
        "contract_versions": sorted(writer.versions),
        "key_fingerprint": key_fingerprint,
    }


def _moment(text: object) -> datetime:
    if not isinstance(text, str):
        raise TypeError("sello de tiempo")
    return datetime.fromisoformat(text)


def row_of_line(line: Mapping[str, Any]) -> Row:
    """La fila que describe una linea del archivo; las columnas salen de `canonical`."""
    canonical = base64.b64decode(line["canonical"], validate=True)
    body = decode(canonical)
    actor = body["actor"]
    case = body.get("case_id")
    return Row(
        seq=int(line["seq"]),
        idempotency_key=UUID(str(body["idempotency_key"])),
        entry_type=str(body["entry_type"]),
        case_id=UUID(case) if case is not None else None,
        model_version_id=body.get("model_version_id"),
        policy_version_id=body.get("policy_version_id"),
        actor_kind=actor["kind"],
        actor_id=actor["id"],
        actor_role=actor.get("role"),
        occurred_at=_moment(body["occurred_at"]),
        recorded_at=_moment(body["recorded_at"]),
        correlation_id=body["correlation_id"],
        contract_version=body["contract_version"],
        canonical=canonical,
        prev_hash=bytes.fromhex(line["prev_hash"]),
        hash=bytes.fromhex(line["hash"]),
    )


def read_rows(data: bytes) -> list[Row]:
    """Descomprime y lee el NDJSON. `ArchiveError` si no es zstd o una linea esta mal formada."""
    try:
        text = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)).read()
        return [row_of_line(json.loads(line)) for line in text.splitlines() if line]
    except (zstandard.ZstdError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise ArchiveError("el archivo mensual no se puede leer") from error


def _report(found: tuple[int, IntegrityReason] | None, manifest: Mapping[str, Any], entries: int, checkpoints: int) -> IntegrityReport:
    now = datetime.now(UTC)
    low = int(manifest.get("from_seq", 0)) if isinstance(manifest.get("from_seq"), int) else 0
    high = int(manifest.get("to_seq", low)) if isinstance(manifest.get("to_seq"), int) else low
    return IntegrityReport(
        mode="range",
        from_seq=low,
        to_seq=max(high, low),
        entries_checked=entries,
        checkpoints_checked=checkpoints,
        result="inconsistente" if found else "integra",
        first_inconsistent_seq=found[0] if found else None,
        reason=found[1] if found else None,
        started_at=now,
        finished_at=now,
    )


def verify_archive(data: bytes, manifest: Mapping[str, Any], public_keys: Iterable[bytes]) -> IntegrityReport:
    """`verify --source archive`: firma del manifiesto, `sha256` del archivo, la cadena del mes y `head_hash`. Sin base de datos.

    Un manifiesto con firma invalida es `checkpoint_signature`; un archivo cuyo `sha256` o `head_hash` no coinciden, o que no se
    puede leer, es `hash`; el resto lo informa `verify` (modo `range`). El primer `seq` inconsistente de los fallos del archivo
    entero es `from_seq` del manifiesto.
    """
    keys = {hashlib.sha256(key).hexdigest(): key for key in public_keys}
    start = manifest.get("from_seq")
    start = start if isinstance(start, int) and not isinstance(start, bool) else 0
    key = keys.get(str(manifest.get("key_fingerprint")))
    signature = manifest.get("signature")
    if key is None or not isinstance(signature, str) or not _signature_ok(key, signature, manifest_message(manifest)):
        return _report((start, "checkpoint_signature"), manifest, 0, 0)
    if hashlib.sha256(data).hexdigest() != manifest.get("sha256"):
        return _report((start, "hash"), manifest, 0, 0)
    try:
        rows = read_rows(data)
        anchor = int(manifest["anchor_seq"])
        last = int(manifest["to_seq"])
    except (ArchiveError, KeyError, TypeError, ValueError):
        return _report((start, "hash"), manifest, 0, 0)
    if not rows or rows[0].seq != anchor or rows[-1].seq != last or rows[-1].hash.hex() != manifest.get("head_hash"):
        return _report((start, "hash"), manifest, len(rows), 0)
    # La primera linea solo ancla el enlace (salvo la genesis, que es parte de la cadena).
    inner = verify(
        "range", ListSource(rows), public_keys=keys.values(), from_seq=0 if anchor == 0 else anchor + 1, to_seq=last
    )
    stated = [r.seq for r in rows if r.entry_type == "checkpoint"]
    if stated != manifest.get("checkpoints") and inner.result == "integra":
        return _report((start, "checkpoint_mismatch"), manifest, inner.entries_checked, inner.checkpoints_checked)
    return inner.model_copy(update={"from_seq": start}) if inner.result == "integra" else inner


def checkpoint_fields_of(row: Row) -> tuple[int, str, str, str] | None:
    """`(checkpoint_seq, checkpoint_hash, signature, key_fingerprint)` de una fila `checkpoint`, o `None`."""
    return _checkpoint_fields(decode(row.canonical))
