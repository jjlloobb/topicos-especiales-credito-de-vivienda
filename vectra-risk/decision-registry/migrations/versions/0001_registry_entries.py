"""registry_entries: tabla particionada, solo-anexar, indices, grants y genesis.

Revision ID: 0001
Revises:

Paso 2 del plan de U3. domain-entities §1 y §1.2; BR-U3-01, 02, 10; NFR-U3-31; P-U3-06; INF-U3-05.
Los roles los crea U1 (CloudNativePG, `platform/data`); aqui solo se dan los grants.
"""

import hashlib
import os
import uuid
from datetime import UTC, datetime

import vectra_contracts
from alembic import context, op
from vectra_contracts.canonical import canonicalize

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# P-U3-06: ~3,6 M entradas por ano (NFR-U3-30) con un margen de 3x; una particion por ano, el en curso y los dos siguientes.
PARTITION_SIZE = 10_800_000
PARTITION_YEARS = 3
# Catalogo de U0 §5.2 (`vectra_contracts.catalog.EntryType`), incluidos `genesis` y `checkpoint`.
ENTRY_TYPES = (
    "recommendation",
    "fail_closed",
    "human_decision",
    "explanation_view",
    "model_event",
    "policy_event",
    "data_source_event",
    "freeze",
    "frozen_resolution",
    "genesis",
    "checkpoint",
)
SCHEMA_VERSION = "1"
GENESIS_KEY = uuid.uuid5(uuid.NAMESPACE_URL, "urn:vectra:decision-registry:genesis")
FINGERPRINT_ENV = "REGISTRY_CHECKPOINT_KEY_FINGERPRINT"


def _fingerprint() -> str:
    value = context.config.attributes.get("checkpoint_key_fingerprint") or os.environ.get(FINGERPRINT_ENV)
    if not value:
        raise RuntimeError(f"la genesis lleva la huella de la llave de checkpoints: falta {FINGERPRINT_ENV}")
    return str(value)


def _genesis_row() -> dict[str, object]:
    """Entrada `seq = 0` (BR-U3-10): `canonical` es el JCS de domain-entities §1.1 y `hash = SHA-256(prev_hash || canonical)`."""
    now = datetime.now(UTC)
    stamp = now.isoformat().replace("+00:00", "Z")
    correlation_id = "0" * 32
    canonical = canonicalize(
        {
            "seq": 0,
            "entry_type": "genesis",
            "idempotency_key": str(GENESIS_KEY),
            "actor": {"kind": "system", "id": "system"},
            "occurred_at": stamp,
            "recorded_at": stamp,
            "correlation_id": correlation_id,
            "contract_version": vectra_contracts.__version__,
            "payload": {
                "schema_version": SCHEMA_VERSION,
                "contract_version": vectra_contracts.__version__,
                "checkpoint_key_fingerprint": _fingerprint(),
            },
        }
    )
    prev_hash = bytes(32)
    return {
        "key": GENESIS_KEY,
        "at": now,
        "correlation_id": correlation_id,
        "contract_version": vectra_contracts.__version__,
        "canonical": canonical,
        "prev_hash": prev_hash,
        "hash": hashlib.sha256(prev_hash + canonical).digest(),
    }


def upgrade() -> None:
    entry_types = ", ".join(f"'{t}'" for t in ENTRY_TYPES)
    op.execute(
        f"""
        CREATE TABLE registry_entries (
            seq               bigint      NOT NULL,
            idempotency_key   uuid        NOT NULL,
            entry_type        text        NOT NULL CHECK (entry_type IN ({entry_types})),
            case_id           uuid,
            model_version_id  text,
            policy_version_id text,
            actor_kind        text        NOT NULL,
            actor_id          text        NOT NULL,
            actor_role        text,
            occurred_at       timestamptz NOT NULL,
            recorded_at       timestamptz NOT NULL,
            correlation_id    text        NOT NULL,
            contract_version  text        NOT NULL,
            canonical         bytea       NOT NULL CHECK (octet_length(canonical) <= 65536),
            prev_hash         bytea       NOT NULL CHECK (octet_length(prev_hash) = 32),
            hash              bytea       NOT NULL CHECK (octet_length(hash) = 32),
            CONSTRAINT registry_entries_pkey PRIMARY KEY (seq),
            CONSTRAINT registry_entries_seq_nonneg CHECK (seq >= 0),
            -- BR-U3-10: una sola genesis. `seq` es llave, asi que `seq = 0` es unico y solo la genesis puede ocuparlo.
            CONSTRAINT registry_entries_single_genesis CHECK ((entry_type = 'genesis') = (seq = 0))
        ) PARTITION BY RANGE (seq)
        """
    )
    first_year = datetime.now(UTC).year
    for i in range(PARTITION_YEARS):
        op.execute(
            f"CREATE TABLE registry_entries_{first_year + i} PARTITION OF registry_entries "
            f"FOR VALUES FROM ({i * PARTITION_SIZE}) TO ({(i + 1) * PARTITION_SIZE})"
        )
    # Red de seguridad (P-U3-06): si recibe filas, falto una particion (alerta RegistryDefaultPartitionUsed, SEV1).
    op.execute("CREATE TABLE registry_entries_default PARTITION OF registry_entries DEFAULT")

    # Una tabla particionada no admite un UNIQUE que no incluya `seq`: la unicidad global de `idempotency_key` vive en una
    # tabla aparte, alimentada por un trigger, con la misma proteccion de solo-anexar. El indice por particion sirve a la busqueda.
    op.execute("CREATE INDEX registry_entries_idempotency_key_idx ON registry_entries (idempotency_key)")
    op.execute("CREATE INDEX registry_entries_case_id_idx ON registry_entries (case_id)")
    op.execute("CREATE INDEX registry_entries_entry_type_idx ON registry_entries (entry_type)")
    # Para el `aggregator reset` (busca la primera entrada de los ultimos 181 dias).
    op.execute("CREATE INDEX registry_entries_recorded_at_idx ON registry_entries (recorded_at)")

    op.execute(
        """
        CREATE TABLE registry_idempotency_keys (
            idempotency_key uuid   PRIMARY KEY,
            seq             bigint NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION registry_record_idempotency_key() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        BEGIN
            INSERT INTO registry_idempotency_keys (idempotency_key, seq) VALUES (NEW.idempotency_key, NEW.seq);
            RETURN NEW;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION registry_record_idempotency_key() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER registry_entries_idempotency AFTER INSERT ON registry_entries "
        "FOR EACH ROW EXECUTE FUNCTION registry_record_idempotency_key()"
    )

    # BR-U3-02: solo-anexar, tambien contra el superusuario. `UPDATE` y `DELETE` van por fila en la tabla madre (PostgreSQL clona
    # el trigger a cada particion, tambien a las futuras); `TRUNCATE` solo admite triggers por sentencia, que no se clonan: se crea
    # en la madre y en cada particion (una migracion que agregue una particion debe llamar a `registry_guard_truncate`).
    op.execute(
        """
        CREATE FUNCTION registry_forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'la tabla % es solo de anexar (BR-U3-02): % no permitido', TG_TABLE_NAME, TG_OP;
        END $$
        """
    )
    for table in ("registry_entries", "registry_idempotency_keys"):
        op.execute(
            f"CREATE TRIGGER {table}_no_update_delete BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION registry_forbid_mutation()"
        )
    for table in (
        "registry_entries",
        "registry_idempotency_keys",
        *(f"registry_entries_{first_year + i}" for i in range(PARTITION_YEARS)),
        "registry_entries_default",
    ):
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION registry_forbid_mutation()"
        )

    # Cabeza del registro (domain-entities §1.2: `SELECT` sobre la vista de cabeza).
    op.execute("CREATE VIEW registry_head AS SELECT * FROM registry_entries ORDER BY seq DESC LIMIT 1")

    # Grants (domain-entities §1.2). `registry_migrator` es el dueno; `registry_health` solo tiene `pg_monitor` (lo da CloudNativePG).
    op.execute("GRANT SELECT, INSERT ON registry_entries TO registry_app")
    op.execute("GRANT SELECT ON registry_head TO registry_app")
    op.execute("GRANT SELECT ON registry_entries, registry_head TO registry_verifier")
    op.execute("GRANT SELECT ON registry_entries TO registry_ondemand")
    op.execute("GRANT SELECT ON registry_entries TO registry_aggregator")

    # Genesis (BR-U3-10): la primera entrada.
    genesis = _genesis_row()
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO registry_entries (seq, idempotency_key, entry_type, actor_kind, actor_id, occurred_at, recorded_at,
                                      correlation_id, contract_version, canonical, prev_hash, hash)
        VALUES (0, %(key)s, 'genesis', 'system', 'system', %(at)s, %(at)s, %(correlation_id)s, %(contract_version)s,
                %(canonical)s, %(prev_hash)s, %(hash)s)
        """,
        genesis,
    )


def downgrade() -> None:
    raise RuntimeError("el registro es solo de anexar: no hay downgrade (BR-U3-02)")
