"""PostgreSQL real con Testcontainers para las pruebas de `governance-db` (NFR-U4-30; AUTONOMIA-01: sin cluster).

La imagen sale de `platform/data/chart/values.yaml` (la version de PostgreSQL de CloudNativePG) y los roles, de la lista
`governance-db.roles` y de los atributos que crea U1 (`templates/clusters.yaml`: `login: true`): no se duplican a mano.
La imagen de CloudNativePG no trae el entrypoint de Docker, asi que se usa la oficial de la misma version (`17.9-trixie`).
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
GOVERNANCE = ROOT / "governance"
DATA_CHART = ROOT / "platform" / "data" / "chart"
MIGRATOR = "gov_migrator"
MIGRATOR_PASSWORD = "migrator-pass"  # noqa: S105 (contenedor desechable)


def u1_values() -> dict[str, object]:
    return yaml.safe_load((DATA_CHART / "values.yaml").read_text())  # type: ignore[no-any-return]


def u1_cluster() -> dict[str, object]:
    clusters = u1_values()["clusters"]
    assert isinstance(clusters, dict)
    return clusters["governance-db"]  # type: ignore[no-any-return]


def u1_roles() -> list[str]:
    """Los roles gestionados de `governance-db` tal como los declara U1."""
    template = (DATA_CHART / "templates" / "clusters.yaml").read_text()
    assert re.search(r"^\s*login: true\s*$", template, re.M), "U1 ya no crea los roles con login"
    return list(u1_cluster()["roles"])  # type: ignore[call-overload]


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


def migrate(pg: PostgresContainer, dbname: str, revision: str = "head") -> None:
    config = Config(str(GOVERNANCE / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url(pg, dbname, MIGRATOR, MIGRATOR_PASSWORD))
    command.upgrade(config, revision)


def create_roles(pg: PostgresContainer) -> list[str]:
    """Crea los roles como los crea U1 (CloudNativePG `managed.roles`, `login: true`)."""
    names = u1_roles()
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        for name in names:
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(name), sql.Literal(MIGRATOR_PASSWORD if name == MIGRATOR else name)
                )
            )
    return names


def create_database(pg: PostgresContainer, name: str, template: str | None = None) -> None:
    """Base propiedad de `gov_migrator` (dueno de la base segun U1, `governance-db.owner`)."""
    statement = sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(name), sql.Identifier(MIGRATOR))
    if template:
        statement += sql.SQL(" TEMPLATE {}").format(sql.Identifier(template))
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        conn.execute(statement)


@pytest.fixture(scope="session")
def roles(pg: PostgresContainer) -> list[str]:
    assert u1_cluster()["owner"] == MIGRATOR
    return create_roles(pg)


@pytest.fixture(scope="session")
def template_db(pg: PostgresContainer, roles: list[str]) -> str:
    name = "governance_template"
    create_database(pg, name)
    migrate(pg, name)
    return name


class Db:
    """Una base de prueba: conexiones de superusuario y `SET ROLE` a cada rol de U1."""

    def __init__(self, pg: PostgresContainer, name: str) -> None:
        self.pg = pg
        self.name = name

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

    def migrate(self, revision: str = "head") -> None:
        migrate(self.pg, self.name, revision)


def drop_database(pg: PostgresContainer, name: str) -> None:
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def db(pg: PostgresContainer, template_db: str) -> Iterator[Db]:
    """Una copia de la base migrada, por prueba: nadie tiene `DELETE`, asi que no se limpian las filas."""
    name = "t_" + uuid.uuid4().hex[:12]
    create_database(pg, name, template_db)
    yield Db(pg, name)
    drop_database(pg, name)


@pytest.fixture
def empty_db(pg: PostgresContainer, roles: list[str]) -> Iterator[Db]:
    """Una base vacia propiedad de `gov_migrator`, para migrar revision por revision."""
    name = "e_" + uuid.uuid4().hex[:12]
    create_database(pg, name)
    yield Db(pg, name)
    drop_database(pg, name)
