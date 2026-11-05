"""Configuracion de las pruebas e2e de U2 (U02-T14). La colección no necesita ninguna variable de entorno.

Al ejecutar, `e2e_support.need` hace fallar la prueba con un error explícito si falta una variable: nunca se salta con `skip`.
Variables: ver `e2e_support.ENV_VARS`. Los navegadores (`playwright install`) se instalan en el Paso 16.
"""

import os
import secrets
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import e2e_support as support
import httpx
import pytest
from hypothesis import HealthCheck, settings

# `e2e_support` y los generadores (tests/strategies/) no son paquetes: se importan por nombre, también desde una copia del directorio.
_TESTS = Path(os.environ.get("VECTRA_E2E_TESTS_DIR") or Path(__file__).resolve().parents[1])
for _dir in (_TESTS / "strategies", Path(__file__).resolve().parent):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

# H8: perfil de PBT-U2-08, con pocos ejemplos: cada ejemplo hace logins reales contra Keycloak y crea un usuario efímero.
settings.register_profile(
    "kind-e2e",
    max_examples=5,
    stateful_step_count=15,
    deadline=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.filter_too_much],
)


@pytest.fixture(scope="session")
def gateway() -> Iterator[httpx.Client]:
    """Cliente del gateway: TLS verificado contra `VECTRA_E2E_CA_BUNDLE`, sin redirecciones automáticas."""
    with support.gateway_client() as client:
        yield client


@pytest.fixture(scope="session")
def admin() -> Iterator[support.Admin]:
    """Admin API de Keycloak por port-forward (BR-U2-12)."""
    with support.Admin.connect() as session:
        yield session


@pytest.fixture(scope="session")
def loki() -> Iterator[support.Loki]:
    with support.Loki.connect() as session:
        yield session


@pytest.fixture
def ephemeral_user(admin: support.Admin) -> Iterator[Callable[..., support.Account]]:
    """Fábrica de usuarios efímeros: se crean por la Admin API y se borran al terminar."""
    created: list[support.Account] = []

    def make(role: str = "analista", required_actions: list[str] | None = None) -> support.Account:
        account = admin.create_user(f"e2e-{secrets.token_hex(4)}", secrets.token_urlsafe(24), role, required_actions or [])
        created.append(account)
        return account

    yield make
    for account in created:
        admin.delete_user(account.user_id)


@pytest.fixture
def approver_without_totp(ephemeral_user: Callable[..., support.Account]) -> support.Account:
    """H5: un usuario con un rol de aprobador (BR-U2-03) y `CONFIGURE_TOTP` pendiente."""
    return ephemeral_user(role=support.approver_role(), required_actions=["CONFIGURE_TOTP"])


@pytest.fixture
def console_token(gateway: httpx.Client) -> str:
    """Token de acceso de un usuario sintético de `vectra-console` (analista), por el flujo OIDC con PKCE."""
    return support.user_access_token(gateway, "analista-1")


@pytest.fixture
def channel_token(gateway: httpx.Client) -> str:
    """Token de servicio del cliente `channel` con el scope de `/api/intake/**`."""
    return support.service_token(gateway, "channel", scope=support.intake_scope())
