"""Primaria + standby sincrono con Testcontainers, para el servicio (P-U3-01, 02; PBT-U3-01; INF-U3-04).

Dos contenedores `postgres:<version>` en una red de Docker: la primaria, con `synchronous_standby_names = 'ANY 1 (standby1)'`
(el mismo `quorum` que configura CloudNativePG con `minSyncReplicas = 1`; P-U3-01) y un standby que se clona con
`pg_basebackup`. Los roles y la base migrada vienen de `registry_pg`: las mismas funciones que usa U1 y que las pruebas de
migraciones. Con el standby detenido o pausado, un commit con `remote_apply` no se confirma.
"""

import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import psycopg
import pytest
from psycopg import sql
from registry_pg import Db, admin_url, create_roles, create_template, postgres_image, url
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.postgres import PostgresContainer

REPLICATION_PASSWORD = "repl-pass"  # noqa: S105 (contenedor desechable)
STANDBY_NAME = "standby1"
SYNC_NAMES = f"ANY 1 ({STANDBY_NAME})"

STANDBY_SCRIPT = f"""
set -e
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  mkdir -p "$PGDATA" && chown postgres:postgres "$PGDATA" && chmod 700 "$PGDATA"
  gosu postgres pg_basebackup -h primary -U replicator -D "$PGDATA" -R -X stream -c fast \\
    -d "host=primary port=5432 user=replicator password={REPLICATION_PASSWORD} application_name={STANDBY_NAME}"
fi
exec docker-entrypoint.sh postgres -c hot_standby=on -c hot_standby_feedback=on -c max_standby_streaming_delay=2s
"""


class Cluster:
    """La primaria (un `PostgresContainer`, con la misma interfaz que usa `registry_pg`) y su standby."""

    def __init__(self, primary: PostgresContainer, standby: DockerContainer) -> None:
        self.primary = primary
        self.standby = standby

    def standby_url(self, dbname: str, user: str, password: str) -> str:
        host = self.standby.get_container_host_ip()
        return f"postgresql://{user}:{password}@{host}:{self.standby.get_exposed_port(5432)}/{dbname}"

    def sync_standbys(self) -> int:
        """Cuantos standbys sincronos (`sync` o `quorum`) transmiten ahora mismo."""
        with psycopg.connect(admin_url(self.primary), autocommit=True) as conn:
            row = conn.execute(
                "SELECT count(*) FROM pg_stat_replication WHERE state = 'streaming' AND sync_state IN ('sync', 'quorum')"
            ).fetchone()
        assert row is not None
        return int(row[0])  # type: ignore[call-overload]

    def wait_streaming(self, timeout: float = 90.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.sync_standbys() >= 1:
                    return
            except psycopg.Error:
                pass
            time.sleep(0.5)
        raise AssertionError("el standby no volvio a transmitir")

    def replay(self, action: str) -> None:
        """`pause` o `resume` del *replay* del standby: el WAL le llega (un commit `on` se confirmaria) pero no lo aplica."""
        with psycopg.connect(self.standby_url("postgres", "postgres", "postgres"), autocommit=True) as conn:
            conn.execute(f"SELECT pg_wal_replay_{action}()")

    def pause_standby(self) -> None:
        self.standby.get_wrapped_container().pause()

    def resume_standby(self) -> None:
        self.standby.get_wrapped_container().unpause()

    def stop_standby(self) -> None:
        self.standby.get_wrapped_container().stop(timeout=5)

    def start_standby(self) -> None:
        self.standby.get_wrapped_container().start()
        self.wait_streaming()


def _wait_standby(cluster: Cluster, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(cluster.standby_url("postgres", "postgres", "postgres"), autocommit=True) as conn:
                row = conn.execute("SELECT pg_is_in_recovery()").fetchone()
                if row and row[0]:
                    return
        except psycopg.Error:
            pass
        time.sleep(0.5)
    raise AssertionError("el standby no arranco")


@pytest.fixture(scope="session")
def cluster() -> Iterator[Cluster]:
    image = postgres_image()
    with Network() as network:
        primary = (
            PostgresContainer(image, username="postgres", password="postgres", dbname="postgres", driver=None)
            .with_network(network)
            .with_network_aliases("primary")
            .with_command(
                [
                    "postgres",
                    "-c", "wal_level=replica",
                    "-c", "max_wal_senders=10",
                    "-c", "hot_standby=on",
                    # El valor por omision es `on`: solo el append pide `remote_apply` (BR-U3-04), y una prueba lo comprueba.
                    "-c", "synchronous_commit=on",
                ]
            )  # fmt: skip
        )
        with primary:
            with psycopg.connect(admin_url(primary), autocommit=True) as conn:
                conn.execute(
                    sql.SQL("CREATE ROLE replicator REPLICATION LOGIN PASSWORD {}").format(
                        sql.Literal(REPLICATION_PASSWORD)
                    )
                )
            wrapped = primary.get_wrapped_container()
            code, output = wrapped.exec_run(
                ["bash", "-c", 'echo "host replication replicator all scram-sha-256" >> "$PGDATA/pg_hba.conf"']
            )
            assert code == 0, output
            with psycopg.connect(admin_url(primary), autocommit=True) as conn:
                conn.execute("SELECT pg_reload_conf()")
            standby = (
                DockerContainer(image)
                .with_network(network)
                .with_network_aliases("standby")
                .with_env("POSTGRES_PASSWORD", "postgres")
                .with_exposed_ports(5432)
                .with_kwargs(entrypoint=["bash", "-c", STANDBY_SCRIPT, "standby"])
            )
            with standby:
                found = Cluster(primary, standby)
                _wait_standby(found)
                with psycopg.connect(admin_url(primary), autocommit=True) as conn:
                    conn.execute(sql.SQL("ALTER SYSTEM SET synchronous_standby_names = {}").format(sql.Literal(SYNC_NAMES)))
                    conn.execute("SELECT pg_reload_conf()")
                found.wait_streaming()
                yield found


@pytest.fixture(scope="session")
def cluster_template(cluster: Cluster) -> str:
    create_roles(cluster.primary)
    return create_template(cluster.primary)


@dataclass
class ClusterDb:
    """Una base de prueba en el cluster: DSN por pool (P-U3-04) y las utilidades de superusuario de `Db`."""

    cluster: Cluster
    name: str
    db: Db

    def dsn(self, pool: str) -> str:
        primary = self.cluster.primary
        match pool:
            case "append" | "dossier":
                return url(primary, self.name, "registry_app", "registry_app")
            case "health":
                return url(primary, self.name, "registry_health", "registry_health")
            case "projections":
                return self.cluster.standby_url(self.name, "registry_verifier", "registry_verifier")
        raise KeyError(pool)

    def sync(self) -> None:
        """Espera a que el standby haya aplicado todo lo escrito hasta ahora (las lecturas de `projections` ven lo sembrado)."""
        with psycopg.connect(admin_url(self.cluster.primary, self.name), autocommit=True) as conn:
            conn.execute("SET synchronous_commit = remote_apply")
            conn.execute("SELECT pg_logical_emit_message(true, 'registry', 'sync')")

    def dsns(self) -> dict[str, str]:
        return {pool: self.dsn(pool) for pool in ("append", "dossier", "projections", "health")}


@pytest.fixture
def cdb(cluster: Cluster, cluster_template: str) -> Iterator[ClusterDb]:
    """Una copia de la base migrada, por prueba, creada en la primaria y ya replicada al standby."""
    name = "t_" + uuid.uuid4().hex[:12]
    with psycopg.connect(admin_url(cluster.primary), autocommit=True) as conn:
        conn.execute("SET synchronous_commit = remote_apply")  # el standby ya tiene la base cuando se la pide
        conn.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {} OWNER registry_migrator").format(
                sql.Identifier(name), sql.Identifier(cluster_template)
            )
        )
    yield ClusterDb(cluster, name, Db(cluster.primary, name))
    with psycopg.connect(admin_url(cluster.primary), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
