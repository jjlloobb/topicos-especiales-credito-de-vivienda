"""Constructor de cadenas para las pruebas de `chain`, `verify` y `projections` (sin base de datos).

Escribe las entradas como lo hara el append del Bloque D: `canonicalize` sobre los campos de domain-entities §1.1,
`link(prev_hash, canonical)` para el hash y un `checkpoint` firmado con Ed25519 sobre `JCS({checkpoint_seq,
checkpoint_hash, recorded_at})` (BR-U3-08).
"""

import base64
import hashlib
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from vectra_registry.chain import GENESIS_PREV_HASH, Row, canonicalize, decode, format_timestamp, link

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
CONTRACT = "0.1.0"
CASES = [uuid.uuid5(uuid.NAMESPACE_URL, f"case-{i}") for i in range(4)]


class Signer:
    """Una llave Ed25519 de checkpoints y su huella (SHA-256 de la llave publica cruda)."""

    def __init__(self, seed: int = 1) -> None:
        self.private = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(f"key-{seed}".encode()).digest())
        self.public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.fingerprint = hashlib.sha256(self.public).hexdigest()

    def sign(self, checkpoint_seq: int, checkpoint_hash: str, recorded_at: str) -> str:
        message = canonicalize(
            {"checkpoint_seq": checkpoint_seq, "checkpoint_hash": checkpoint_hash, "recorded_at": recorded_at}
        )
        return base64.b64encode(self.private.sign(message)).decode()


def entry_fields(
    seq: int, entry_type: str, payload: dict[str, object], recorded_at: datetime, **extra: object
) -> dict[str, object]:
    fields: dict[str, object] = {
        "seq": seq,
        "entry_type": entry_type,
        "idempotency_key": str(uuid.uuid5(uuid.NAMESPACE_URL, f"entry-{seq}")),
        "actor": {"kind": "service", "id": f"svc-{seq % 3}"},
        "occurred_at": recorded_at - timedelta(seconds=1),
        "recorded_at": recorded_at,
        "correlation_id": f"{seq:032x}",
        "contract_version": CONTRACT,
        "payload": payload,
    }
    fields.update(extra)
    return fields


def row_of(fields: dict[str, object], prev_hash: bytes) -> Row:
    """La fila de `registry_entries` para esos campos: columnas consultables + `canonical` + `hash`."""
    canonical = canonicalize(fields)
    actor = fields["actor"]
    assert isinstance(actor, dict)
    case_id = fields.get("case_id")
    return Row(
        seq=int(str(fields["seq"])),
        idempotency_key=uuid.UUID(str(fields["idempotency_key"])),
        entry_type=str(fields["entry_type"]),
        case_id=uuid.UUID(str(case_id)) if case_id else None,
        model_version_id=fields.get("model_version_id"),  # type: ignore[arg-type]
        policy_version_id=fields.get("policy_version_id"),  # type: ignore[arg-type]
        actor_kind=actor["kind"],
        actor_id=actor["id"],
        actor_role=actor.get("role"),
        occurred_at=fields["occurred_at"],  # type: ignore[arg-type]
        recorded_at=fields["recorded_at"],  # type: ignore[arg-type]
        correlation_id=str(fields["correlation_id"]),
        contract_version=str(fields["contract_version"]),
        canonical=canonical,
        prev_hash=prev_hash,
        hash=link(prev_hash, canonical),
    )


def build_chain(
    kinds: list[str],
    signer: Signer,
    checkpoint_every: int | None = 5,
    step: timedelta = timedelta(minutes=10),
    start: datetime = T0,
) -> list[Row]:
    """Genesis + una entrada por cada tipo de `kinds`; tras cada `checkpoint_every` entradas, un `checkpoint` firmado."""
    rows: list[Row] = []
    clock = start

    def append(entry_type: str, payload: dict[str, object], **extra: object) -> None:
        nonlocal clock
        seq = len(rows)
        prev = rows[-1].hash if rows else GENESIS_PREV_HASH
        rows.append(row_of(entry_fields(seq, entry_type, payload, clock, **extra), prev))
        clock += step

    append(
        "genesis",
        {"schema_version": "1", "contract_version": CONTRACT, "checkpoint_key_fingerprint": signer.fingerprint},
    )
    since = 0
    for i, kind in enumerate(kinds):
        extra: dict[str, object] = {}
        if kind in {"recommendation", "human_decision"}:
            extra = {"case_id": str(CASES[i % len(CASES)]), "model_version_id": f"m{i % 2}"}
        append(kind, {"n": i, "texto": f"caso {i} ñandú"}, **extra)
        since += 1
        if checkpoint_every is not None and since == checkpoint_every:
            since = 0
            covered = rows[-1]
            append(
                "checkpoint",
                {
                    "checkpoint_seq": covered.seq,
                    "checkpoint_hash": covered.hash.hex(),
                    "signature": signer.sign(covered.seq, covered.hash.hex(), format_timestamp(clock)),
                    "key_fingerprint": signer.fingerprint,
                },
            )
    return rows


def worm_of(rows: list[Row]) -> dict[int, dict[str, object]]:
    """Las copias de los checkpoints en el bucket WORM: `checkpoints/{checkpoint_seq}.json`."""
    copies: dict[int, dict[str, object]] = {}
    for row in rows:
        if row.entry_type == "checkpoint":
            body = decode(row.canonical)
            payload = body["payload"]
            assert isinstance(payload, dict)
            copies[int(payload["checkpoint_seq"])] = {**payload, "recorded_at": body["recorded_at"]}
    return copies


def rewrite_from(rows: list[Row], k: int, edit: Callable[[dict[str, Any]], None] | None = None) -> list[Row]:
    """Reescribe la cadena desde `k` (cambia el contenido de esa entrada con `edit`; por omision marca el payload) y recalcula
    todos los enlaces y hashes: una cadena internamente consistente que solo los checkpoints pueden delatar (PBT-U3-03)."""

    def mark(body: dict[str, Any]) -> None:
        body["payload"] = {**body["payload"], "reescrito": True}

    out = list(rows[:k])
    for row in rows[k:]:
        body = decode(row.canonical)
        if row.seq == k:
            (edit or mark)(body)
        prev = out[-1].hash if out else GENESIS_PREV_HASH
        canonical = canonicalize(body)
        out.append(replace(row, canonical=canonical, prev_hash=prev, hash=link(prev, canonical)))
    return out
