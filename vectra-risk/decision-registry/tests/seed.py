"""Siembra de la cadena por SQL (superusuario) con `recorded_at` elegido, para las pruebas de lectura.

El append real fija `recorded_at` con el reloj de la base; las pruebas de proyecciones, expediente y atraso necesitan entradas de
hace 2 h, 31 min o 60 dias. Esta siembra escribe las filas **como lo hace el append** (`build_canonical`, `link`, el hash de la
cabeza) pero con el sello pedido, asi que la cadena resultante verifica `integra`.
"""

import json
from datetime import UTC, datetime
from typing import Any

from entries import entry_dict
from vectra_registry.append import build_canonical
from vectra_registry.chain import link
from vectra_contracts.models.registry import RegistryEntryIn

from registry_cluster import ClusterDb

INSERT = (
    "INSERT INTO registry_entries (seq, idempotency_key, entry_type, case_id, model_version_id, policy_version_id, "
    "actor_kind, actor_id, actor_role, occurred_at, recorded_at, correlation_id, contract_version, canonical, prev_hash, hash) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


def seed(
    cdb: ClusterDb, specs: list[tuple[dict[str, Any], datetime]], *, contract_version: str = "0.1.0", wait: bool = True
) -> list[int]:
    """Escribe `(entrada, recorded_at)` en orden a continuacion de la cabeza y devuelve sus `seq`. Espera al standby (`wait`)."""
    seqs: list[int] = []
    with cdb.db.connect() as conn:
        conn.execute("SET synchronous_commit = " + ("remote_apply" if wait else "local"))
        head = conn.execute("SELECT seq, hash FROM registry_head").fetchone()
        assert head is not None
        seq, prev = int(head[0]), bytes(head[1])  # type: ignore[call-overload]
        rows = []
        for data, recorded_at in specs:
            seq += 1
            entry = RegistryEntryIn.model_validate_json(json.dumps(data))
            canonical = build_canonical(entry, seq, recorded_at)
            hash_ = link(prev, canonical)
            actor = entry.actor
            rows.append(
                (
                    seq, entry.idempotency_key, str(entry.entry_type), entry.case_id, entry.model_version_id,
                    entry.policy_version_id, actor.kind, actor.id, str(actor.role) if actor.role else None,
                    entry.occurred_at, recorded_at.astimezone(UTC), entry.correlation_id, contract_version, canonical,
                    prev, hash_,
                )
            )  # fmt: skip
            prev = hash_
            seqs.append(seq)
        with conn.cursor() as cursor:
            cursor.executemany(INSERT, rows)
    if wait:
        cdb.sync()
    return seqs


def spec(entry_type: str, recorded_at: datetime, **kwargs: Any) -> tuple[dict[str, Any], datetime]:
    """Una entrada valida de ese tipo cuyo `occurred_at` es `recorded_at` (como si se hubiera escrito entonces)."""
    return entry_dict(entry_type, now=recorded_at, **kwargs), recorded_at
