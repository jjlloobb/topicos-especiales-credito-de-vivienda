"""Apoyos de las pruebas de la CLI y del agregador: DSN por rol, siembra sobre una primaria sola, checkpoints firmados por la boveda.

El `checkpoint` real (BR-U3-08) no esta en esta tarea (decision de diseno pendiente: la firma cubre el `recorded_at` de la propia
entrada). Las pruebas lo escriben a mano, por SQL de superusuario, firmado por Transit: el `canonical` es el que el append escribiria.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

import vectra_contracts
from registry_pg import MIGRATOR_PASSWORD, Db, url
from registry_services import Vault
from seed import INSERT, seed, spec
from testcontainers.postgres import PostgresContainer
from vectra_registry.chain import canonicalize, format_timestamp, link

ONE_SECOND = timedelta(seconds=1)


def dsn(pg: PostgresContainer, db: Db, role: str) -> str:
    return url(pg, db.name, role, MIGRATOR_PASSWORD if role == "registry_migrator" else role)


class PrimaryOnly:
    """Lo que `seed` necesita de un cluster, sobre una primaria sin standby."""

    def __init__(self, db: Db) -> None:
        self.db = db

    def sync(self) -> None:
        return None


def seed_events(db: Db, count: int, start: datetime, step: timedelta = timedelta(minutes=1)) -> list[int]:
    """`count` entradas `model_event` registradas a `start`, `start + step`, ..."""
    return seed(PrimaryOnly(db), [spec("model_event", start + step * i) for i in range(count)], wait=False)  # type: ignore[arg-type]


def seed_specs(db: Db, specs: list[tuple[dict[str, Any], datetime]], **kwargs: Any) -> list[int]:
    return seed(PrimaryOnly(db), specs, wait=False, **kwargs)  # type: ignore[arg-type]


def add_checkpoint(db: Db, vault: Vault, *, covered: int | None = None) -> int:
    """Agrega una entrada `checkpoint` firmada por la boveda que cubre `covered` (por omision, la cabeza). Devuelve su `seq`."""
    with db.connect() as conn:
        head = conn.execute("SELECT seq, hash, recorded_at FROM registry_head").fetchone()
        assert head is not None
        seq, head_hash, head_recorded = int(head[0]), bytes(head[1]), head[2]  # type: ignore[call-overload]
        target = seq if covered is None else covered
        row = conn.execute("SELECT hash FROM registry_entries WHERE seq = %s", (target,)).fetchone()
        assert row is not None
        covered_hash = bytes(row[0]).hex()  # type: ignore[call-overload]
        recorded_at = head_recorded + ONE_SECOND
        new_seq = seq + 1
        signature = vault.sign(
            canonicalize(
                {"checkpoint_seq": target, "checkpoint_hash": covered_hash, "recorded_at": format_timestamp(recorded_at)}
            )
        )
        key = uuid.uuid5(uuid.NAMESPACE_URL, f"checkpoint:{new_seq}")
        body = {
            "seq": new_seq,
            "entry_type": "checkpoint",
            "idempotency_key": str(key),
            "actor": {"kind": "system", "id": "registry-checkpoint"},
            "occurred_at": recorded_at,
            "recorded_at": recorded_at,
            "correlation_id": "c" * 32,
            "contract_version": vectra_contracts.__version__,
            "payload": {
                "checkpoint_seq": target,
                "checkpoint_hash": covered_hash,
                "signature": signature,
                "key_fingerprint": hashlib.sha256(vault.public_key).hexdigest(),
            },
        }
        canonical = canonicalize(body)
        conn.execute(
            INSERT,
            (
                new_seq, key, "checkpoint", None, None, None, "system", "registry-checkpoint", None, recorded_at, recorded_at,
                "c" * 32, vectra_contracts.__version__, canonical, head_hash, link(head_hash, canonical),
            ),
        )  # fmt: skip
    return new_seq


def checkpoint_copy(db: Db, seq: int) -> tuple[int, bytes]:
    """`(checkpoint_seq, objeto WORM)` de la entrada `checkpoint` en `seq`."""
    from vectra_registry.chain import decode
    from vectra_registry.worm import checkpoint_object

    (row,) = db.query("SELECT canonical FROM registry_entries WHERE seq = %s", seq)
    body = decode(bytes(row[0]))  # type: ignore[call-overload]
    payload = body["payload"]
    return int(payload["checkpoint_seq"]), checkpoint_object(payload, body["recorded_at"])


def tamper(db: Db, seq: int, column: str, value: object) -> None:
    """Altera una fila como lo haria quien pudiera saltarse el trigger de solo-anexar (superusuario, `replica`)."""
    with db.connect() as conn:
        conn.execute("SET session_replication_role = replica")
        conn.execute(f"UPDATE registry_entries SET {column} = %s WHERE seq = %s", (value, seq))  # noqa: S608


# --- Siembra cruda para el agregador: solo `payload`, sin cadena valida ---------------------------------------------------------

RAW_INSERT = (
    "INSERT INTO registry_entries (seq, idempotency_key, entry_type, case_id, model_version_id, actor_kind, actor_id, "
    "occurred_at, recorded_at, correlation_id, contract_version, canonical, prev_hash, hash) "
    "VALUES (%s, %s, %s, %s, %s, 'service', 'svc', %s, %s, 'c', '0.1.0', %s, %s, %s)"
)
LABELS = {"sexo": "F", "rango_edad": "26-35", "region": "andina", "estrato": "3", "banda_capacidad_pago": "lt_20"}


def next_seq(db: Db) -> int:
    return int(db.query("SELECT max(seq) + 1 FROM registry_entries")[0][0])  # type: ignore[call-overload]


def raw_insert(db: Db, entries: list[dict[str, Any]], *, first_seq: int | None = None) -> list[int]:
    """Escribe entradas con el `payload` dado, a continuacion de la cabeza. La cadena de hashes **no** es valida: el agregador no la lee.

    Cada entrada: `entry_type`, `payload`, `case_id`, `model_version_id` y `recorded_at`.
    """
    seq = first_seq if first_seq is not None else next_seq(db)
    seqs: list[int] = []
    rows = []
    for entry in entries:
        body = {"seq": seq, "entry_type": entry["entry_type"], "payload": entry.get("payload", {})}
        rows.append(
            (
                seq, uuid.uuid4(), entry["entry_type"], entry.get("case_id"), entry.get("model_version_id"),
                entry["recorded_at"], entry["recorded_at"], json.dumps(body).encode(), bytes(32), bytes(32),
            )
        )  # fmt: skip
        seqs.append(seq)
        seq += 1
    with db.connect() as conn, conn.cursor() as cursor:
        cursor.executemany(RAW_INSERT, rows)
    return seqs


def rec(
    at: datetime,
    case: uuid.UUID,
    *,
    version: str = "mv-1",
    outcome: str = "favorable",
    labels: dict[str, str] | None = None,
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "entry_type": "recommendation",
        "case_id": case,
        "model_version_id": version,
        "recorded_at": recorded_at or at,
        "payload": {"evaluated_at": format_timestamp(at), "monitoring_labels": labels or LABELS, "outcome": outcome},
    }


def decision(at: datetime, case: uuid.UUID, ref: object, *, final: str = "favorable", kind: str = "sigue") -> dict[str, Any]:
    return {
        "entry_type": "human_decision",
        "case_id": case,
        "recorded_at": at,
        "payload": {"decided_at": format_timestamp(at), "final_outcome": final, "decision": kind, "recommendation_entry_id": str(ref)},
    }
