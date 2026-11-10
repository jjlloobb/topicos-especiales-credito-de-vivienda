"""PostgreSQL real con Testcontainers para las pruebas de `case-db` (AUTONOMIA-01: sin cluster).

La imagen sale de `platform/data/chart/values.yaml` (la version de PostgreSQL de CloudNativePG) y los roles, de `clusters.case-db.roles`
y de los atributos que crea U1 (`templates/clusters.yaml`: `login: true`): no se duplican a mano. La migracion la corre
`case_migrator`, dueno de la base. Las pruebas se conectan **con cada rol real** (`session_user`), sin `SET ROLE` (`guard_transition`
depende de `session_user`, P-U1-08); el superusuario solo prepara y lee de vuelta los datos.
Patron de `governance/tests/integration/governance_pg.py`; no se importan las pruebas de U4.
"""

import os
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
CASE = ROOT / "case-management"
DATA_CHART = ROOT / "platform" / "data" / "chart"
MIGRATOR = "case_migrator"
MIGRATOR_PASSWORD = "migrator-pass"  # noqa: S105 (contenedor desechable)
# Plazos por omision de P-U8-05 que el Job de migracion pasa en las variables de `retention.*` (P-1).
RETENTION_DEFAULTS = {"decided_years": 10, "undecided_years": 2, "intake_keys_days": 30}
RETENTION_VARIABLES = {
    "decided_years": "RETENTION_DECIDED_YEARS",
    "undecided_years": "RETENTION_UNDECIDED_YEARS",
    "intake_keys_days": "RETENTION_INTAKE_KEYS_DAYS",
}


def u1_values() -> dict[str, object]:
    return yaml.safe_load((DATA_CHART / "values.yaml").read_text())  # type: ignore[no-any-return]


def u1_cluster() -> dict[str, object]:
    clusters = u1_values()["clusters"]
    assert isinstance(clusters, dict)
    return clusters["case-db"]  # type: ignore[no-any-return]


def u1_roles() -> list[str]:
    """Los roles gestionados de `case-db` tal como los declara U1."""
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


@contextmanager
def retention_environment(**years: int | str | None) -> Iterator[None]:
    """Fija las variables `RETENTION_*` del Job de migracion; `None` quita la variable."""
    values: dict[str, int | str | None] = {**RETENTION_DEFAULTS, **years}
    saved = {name: os.environ.get(name) for name in RETENTION_VARIABLES.values()}
    try:
        for column, name in RETENTION_VARIABLES.items():
            value = values[column]
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = str(value)
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def migrate(pg: PostgresContainer, dbname: str, revision: str = "head", **years: int | str | None) -> None:
    config = Config(str(CASE / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url(pg, dbname, MIGRATOR, MIGRATOR_PASSWORD))
    with retention_environment(**years):
        command.upgrade(config, revision)


def create_roles(pg: PostgresContainer) -> list[str]:
    """Crea los roles como los crea U1 (CloudNativePG `managed.roles`, `login: true`); la clave es el nombre del rol."""
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
    """Base propiedad de `case_migrator` (dueno de la base segun U1, `case-db.owner`)."""
    statement = sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(name), sql.Identifier(MIGRATOR))
    if template:
        statement += sql.SQL(" TEMPLATE {}").format(sql.Identifier(template))
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        conn.execute(statement)


def drop_database(pg: PostgresContainer, name: str) -> None:
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


Conn = psycopg.Connection[tuple[object, ...]]


class Db:
    """Una base de prueba: `as_role` abre una conexion con el usuario real del rol; `admin` es solo para preparar y leer de vuelta."""

    def __init__(self, pg: PostgresContainer, name: str) -> None:
        self.pg = pg
        self.name = name

    def admin(self) -> Conn:
        return psycopg.connect(admin_url(self.pg, self.name), autocommit=True)

    @contextmanager
    def as_role(self, role: str) -> Iterator[Conn]:
        """Conexion directa del rol (`session_user` = rol), sin `SET ROLE`; `autocommit`, para probar cada sentencia."""
        password = MIGRATOR_PASSWORD if role == MIGRATOR else role
        with psycopg.connect(url(self.pg, self.name, role, password), autocommit=True) as conn:
            yield conn

    def query(self, statement: str, *params: object) -> list[tuple[object, ...]]:
        with self.admin() as conn:
            return conn.execute(statement, params or None).fetchall()  # type: ignore[arg-type]

    def execute(self, statement: str, *params: object) -> None:
        """Escribe como superusuario, **sin triggers** (`session_replication_role = replica`): solo para dejar el escenario listo."""
        with self.admin() as conn:
            conn.execute("SET session_replication_role = replica")
            conn.execute(statement, params or None)  # type: ignore[arg-type]

    def migrate(self, revision: str = "head", **years: int | str | None) -> None:
        migrate(self.pg, self.name, revision, **years)


@pytest.fixture(scope="session")
def roles(pg: PostgresContainer) -> list[str]:
    assert u1_cluster()["owner"] == MIGRATOR
    return create_roles(pg)


@pytest.fixture(scope="session")
def template_db(pg: PostgresContainer, roles: list[str]) -> str:
    name = "case_template"
    create_database(pg, name)
    migrate(pg, name)
    return name


@pytest.fixture
def db(pg: PostgresContainer, template_db: str) -> Iterator[Db]:
    """Una copia de la base migrada, por prueba."""
    name = "t_" + uuid.uuid4().hex[:12]
    create_database(pg, name, template_db)
    yield Db(pg, name)
    drop_database(pg, name)


@pytest.fixture
def empty_db(pg: PostgresContainer, roles: list[str]) -> Iterator[Db]:
    """Una base vacia propiedad de `case_migrator`, para migrar dentro de la prueba."""
    name = "e_" + uuid.uuid4().hex[:12]
    create_database(pg, name)
    yield Db(pg, name)
    drop_database(pg, name)
