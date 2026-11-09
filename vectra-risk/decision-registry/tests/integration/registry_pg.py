"""PostgreSQL real con Testcontainers para las pruebas de `registry-db` (NFR-U3-50; AUTONOMIA-01: sin cluster).

La imagen sale de `platform/data/chart/values.yaml` (la version de PostgreSQL de CloudNativePG, INF-U3-05) y los roles, de la
misma lista y de los mismos atributos que crea U1 (`values.yaml` y `templates/clusters.yaml`): no se duplican a mano.
La imagen de CloudNativePG no trae el entrypoint de Docker, asi que se usa la imagen oficial de la misma version (`17.9-trixie`).
"""

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
import yaml
from alembic import command
from alembic.config import Config
from psycopg import sql
from testcontainers.postgres import PostgresContainer

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "decision-registry"
DATA_CHART = ROOT / "platform" / "data" / "chart"
FINGERPRINT = "sha256:" + "ab" * 32
MIGRATOR_PASSWORD = "migrator-pass"  # noqa: S105 (contenedor desechable)


def u1_values() -> dict[str, object]:
    return yaml.safe_load((DATA_CHART / "values.yaml").read_text())  # type: ignore[no-any-return]


def u1_roles() -> list[str]:
    """Los roles gestionados de `registry-db` tal como los declara U1."""
    clusters = u1_values()["clusters"]
    assert isinstance(clusters, dict)
    return list(clusters["registry-db"]["roles"])


def u1_role_attributes(role: str) -> dict[str, object]:
    """Atributos del rol segun `clusters.yaml` de U1: `login: true` para todos; `inRoles: [pg_monitor]` solo en `registry_health`."""
    template = (DATA_CHART / "templates" / "clusters.yaml").read_text()
    assert re.search(r"^\s*login: true\s*$", template, re.M), "U1 ya no crea los roles con login"
    in_roles = bool(re.search(r'eq \. "' + role + r'"\s*}}\s*\n\s*inRoles: \[pg_monitor\]', template))
    return {"login": True, "in_roles": ["pg_monitor"] if in_roles else []}


def postgres_image() -> str:
    image = str(u1_values()["imageName"])
    match = re.search(r":(\d+\.\d+)-system-([a-z]+)", image)
    assert match, f"no se reconoce la version de PostgreSQL en {image}"
    return f"postgres:{match.group(1)}-{match.group(2)}"


@pytest.fixture(scope="session")
def pg() -> Iterator[PostgresContainer]:
    with PostgresContainer(
        postgres_image(), username="postgres", password="postgres", dbname="postgres"
    ) as container:
        yield container


def url(pg: PostgresContainer, dbname: str, user: str, password: str) -> str:
    return f"postgresql://{user}:{password}@{pg.get_container_host_ip()}:{pg.get_exposed_port(5432)}/{dbname}"


def admin_url(pg: PostgresContainer, dbname: str = "postgres") -> str:
    return url(pg, dbname, "postgres", "postgres")


def migrate(pg: PostgresContainer, dbname: str, fingerprint: str | None = FINGERPRINT) -> None:
    config = Config(str(REGISTRY / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url(pg, dbname, "registry_migrator", MIGRATOR_PASSWORD))
    if fingerprint is not None:
        config.attributes["checkpoint_key_fingerprint"] = fingerprint
    command.upgrade(config, "head")


def create_roles(pg: PostgresContainer) -> list[str]:
    """Crea los roles como los crea U1 (CloudNativePG `managed.roles`)."""
    names = u1_roles()
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        for name in names:
            attrs = u1_role_attributes(name)
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(name),
                    sql.Literal(MIGRATOR_PASSWORD if name == "registry_migrator" else name),
                )
            )
            for parent in attrs["in_roles"]:  # type: ignore[attr-defined]
                conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(parent), sql.Identifier(name)))
    return names


def create_template(pg: PostgresContainer) -> str:
    """Base `registry_template` ya migrada por `registry_migrator` (dueno de la base, como en U1)."""
    name = "registry_template"
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER registry_migrator").format(sql.Identifier(name)))
    migrate(pg, name)
    return name


@pytest.fixture(scope="session")
def roles(pg: PostgresContainer) -> list[str]:
    return create_roles(pg)


@pytest.fixture(scope="session")
def template_db(pg: PostgresContainer, roles: list[str]) -> str:
    return create_template(pg)


class Db:
    """Una base de prueba: conexiones de superusuario y `SET ROLE` a cada rol de U1."""

    def __init__(self, pg: PostgresContainer, name: str) -> None:
        self.pg = pg
        self.name = name
        self._next_seq = 1

    def connect(self) -> psycopg.Connection[tuple[object, ...]]:
        return psycopg.connect(admin_url(self.pg, self.name), autocommit=True)

    @contextmanager
    def as_role(self, role: str) -> Iterator[psycopg.Connection[tuple[object, ...]]]:
        with self.connect() as conn:
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
            yield conn

    def query(self, statement: str, *params: object) -> list[tuple[object, ...]]:
        with self.connect() as conn:
            return conn.execute(statement, params or None).fetchall()  # type: ignore[arg-type]

    def insert_entry(
        self, role: str = "registry_app", seq: int | None = None, key: uuid.UUID | None = None
    ) -> int:
        """Inserta una entrada con el rol dado y devuelve su `seq`."""
        if seq is None:
            seq = self._next_seq
            self._next_seq += 1
        with self.as_role(role) as conn:
            conn.execute(
                "INSERT INTO registry_entries (seq, idempotency_key, entry_type, actor_kind, actor_id, occurred_at, "
                "recorded_at, correlation_id, contract_version, canonical, prev_hash, hash) "
                "VALUES (%s, %s, 'model_event', 'service', 'svc', now(), now(), 'c', '0.1.0', %s, %s, %s)",
                (seq, key or uuid.uuid4(), b"{}", bytes(32), bytes(32)),
            )
        return seq


@pytest.fixture
def db(pg: PostgresContainer, template_db: str) -> Iterator[Db]:
    """Una copia de la base migrada, por prueba: el trigger de solo-anexar impide limpiar las filas."""
    name = "t_" + uuid.uuid4().hex[:12]
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {} OWNER registry_migrator").format(
                sql.Identifier(name), sql.Identifier(template_db)
            )
        )
    yield Db(pg, name)
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
