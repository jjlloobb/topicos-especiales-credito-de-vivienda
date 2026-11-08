"""Bases desechables en el cluster para las propiedades (una por ejemplo o por modulo)."""

import sys
import uuid
from pathlib import Path

import psycopg
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))

from registry_cluster import Cluster, ClusterDb  # noqa: E402
from registry_pg import Db, admin_url  # noqa: E402


def make_db(cluster: Cluster, template: str) -> ClusterDb:
    name = "p_" + uuid.uuid4().hex[:12]
    with psycopg.connect(admin_url(cluster.primary), autocommit=True) as conn:
        conn.execute("SET synchronous_commit = remote_apply")
        conn.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {} OWNER registry_migrator").format(sql.Identifier(name), sql.Identifier(template))
        )
    return ClusterDb(cluster, name, Db(cluster.primary, name))


def drop_db(cdb: ClusterDb) -> None:
    with psycopg.connect(admin_url(cdb.cluster.primary), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(cdb.name)))
