"""Fixtures de integracion (U12-T02): Keycloak real con el realm de kind (una instancia por sesion de pytest) y el entorno dinamico registrado en `guard.ENVIRONMENTS`."""

import subprocess
import time
from collections.abc import Iterator

import pytest
from external_paths import use_u8_doubles
from keycloak_tc import KeycloakStack, keycloak_stack

from vectra_verification import guard


def _foreign_keycloaks() -> list[str]:
    out = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}} {{.Image}}"], capture_output=True, text=True, check=True
    ).stdout  # noqa: S603, S607
    return [
        line for line in out.splitlines() if ("keycloak" in line.lower()) and not line.startswith("u12t02-")
    ]


@pytest.fixture(scope="session")
def keycloak() -> Iterator[KeycloakStack]:
    """Si otro codificador o el revisor tiene un Keycloak (~1 GiB), espera: la memoria no alcanza para dos."""
    deadline = time.monotonic() + 900
    while _foreign_keycloaks() and time.monotonic() < deadline:
        time.sleep(10)
    with keycloak_stack() as stack:
        yield stack


@pytest.fixture(scope="session")
def real_environment(keycloak: KeycloakStack) -> Iterator[guard.Environment]:
    environment = guard.Environment("kind", keycloak.host, keycloak.issuer)
    patch = pytest.MonkeyPatch()
    patch.setattr(guard, "ENVIRONMENTS", (*guard.ENVIRONMENTS, environment))
    yield environment
    patch.undo()


# PostgreSQL de Testcontainers para `case-service` real (CA-11): los fixtures son los de U8 (`case_pg`): una primaria, los roles de U1 y una copia migrada por prueba.
use_u8_doubles()
from case_pg import db, pg, roles, template_db  # noqa: E402, F401
