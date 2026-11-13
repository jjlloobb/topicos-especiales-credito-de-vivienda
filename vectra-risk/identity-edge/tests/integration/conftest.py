"""Fixtures de la prueba de integracion del realm (U02-T22). Arranca Docker: NO entra en `make test` ni en `make check` (solo se colecta); se corre con `make integration`."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
for _dir in (_HERE, _HERE.parent / "strategies"):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import realm_stack as rs  # noqa: E402


@pytest.fixture(scope="session")
def stack() -> Iterator[rs.Stack]:
    """Un Keycloak vacio con el realm de Git importado **sin editar** (`realm.kind.yaml`) como lo importa el Job de kind. Un solo contenedor para toda la sesion."""
    rs.SCRATCH.mkdir(parents=True, exist_ok=True)
    with rs.keycloak_stack() as keycloak:
        started = rs.time.monotonic()
        keycloak.import_realm(rs.REALM_FILE)
        rs.measure(f"realm {rs.REALM_FILE.name} importado en {rs.time.monotonic() - started:.0f} s")
        yield keycloak
