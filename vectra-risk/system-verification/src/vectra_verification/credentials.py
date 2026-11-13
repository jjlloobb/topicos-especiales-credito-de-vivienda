"""Credenciales de la verificacion (U12 Paso 2; NFR-U12-04; BR-U12-03). Solo en memoria.

Lee la boveda por su API HTTP KV v2 con `httpx` (P-5, recomendacion (a)): `GET <VAULT_ADDR>/v1/<montaje>/data/<ruta>`, con la cabecera `X-Vault-Token`.
`VAULT_ADDR` y `VAULT_TOKEN` son los del entorno del proceso (la sesion del operador). Montaje `secret` en kind y `vectra` en staging, en las rutas y
propiedades donde ESO las lee para el realm (U2; `platform/kind/vault_paths.py`): las llaves de `channel-simulator` y `verification-reader`, y las contraseñas
y semillas TOTP de los usuarios sinteticos. Fuera de kind, pedir una credencial de `cumplimiento-*` da error **antes** de cualquier solicitud (excepcion de
FR-BIA-05), y las propiedades `SYNTH_CUMPLIMIENTO_*` del secreto compartido se descartan sin guardarse.

Nada se escribe a disco; `repr()` y `str()` de los objetos no muestran ningun secreto. El TOTP lo calcula `pyotp` con el instante inyectado.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final
from urllib.parse import urlsplit

import httpx
import pyotp

from vectra_verification.guard import KIND, Environment, GuardError, check_known

MOUNTS: Final = {"kind": "secret", "staging": "vectra"}
CLIENTS: Final = ("channel-simulator", "verification-reader")
USERS: Final = ("analista-1", "analista-2", "ingeniero-1", "cro-1", "cumplimiento-1")
CLIENT_KEY_PROPERTY: Final = "private-key"
SYNTHETIC_USERS_PATH: Final = "identity/synthetic-users"
# F-04: la direccion de la boveda a la que se conecta de verdad. El servicio de la boveda de kind (`platform/operators/vault-kind.yaml`) y un `port-forward` local
# (`127.0.0.1` o `localhost`); la de produccion no esta. Con un transporte inyectado (pruebas) no sale ninguna solicitud y la direccion no se mira.
ALLOWED_VAULT_HOSTS: Final = ("vault.vault.svc", "127.0.0.1", "localhost")
# El token de desarrollo de la boveda de kind es la palabra `root` y esta escrito en `platform/operators/vault-kind.yaml`: no es un secreto, y como valor a buscar
# rechazaria toda evidencia que diga `/dev/root` o el logger `root` (F-09). Solo se excluye ese valor exacto y solo en kind: un token real (`hvs.…`) sigue protegido.
DEV_VAULT_TOKEN: Final = "root"  # noqa: S105


class CredentialsError(Exception):
    """Error al obtener una credencial; el mensaje no lleva el token ni ningun valor."""


class Secret:
    """Un valor secreto: no se muestra en `repr()` ni en `str()`; `reveal()` lo entrega a quien lo va a usar."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Secret(***)"


def _property(user: str, suffix: str) -> str:
    return f"SYNTH_{user.upper().replace('-', '_')}_{suffix}"


def _vault_addr_allowed(addr: str) -> bool:
    parts = urlsplit(addr)
    return parts.scheme in ("http", "https") and parts.hostname in ALLOWED_VAULT_HOSTS


class Credentials:
    def __init__(
        self,
        environment: Environment,
        vault_addr: str,
        vault_token: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if environment.name not in MOUNTS:
            raise CredentialsError("environment_without_vault")
        try:
            check_known(
                environment
            )  # F-04: tiene que ser uno de `guard.ENVIRONMENTS`, no uno armado a mano con el nombre `kind`
        except GuardError:
            raise CredentialsError("environment_not_allowed") from None
        if transport is None and not _vault_addr_allowed(vault_addr):
            raise CredentialsError("vault_addr_not_allowed")
        self._environment = environment
        self._mount = MOUNTS[environment.name]
        self._token = vault_token
        self._http = httpx.Client(
            base_url=vault_addr, transport=transport, headers={"X-Vault-Token": vault_token}
        )
        self._clients: dict[str, Secret] = {}
        self._synthetic: dict[str, Secret] | None = None

    @classmethod
    def from_environ(
        cls,
        environment: Environment,
        environ: Mapping[str, str],
        transport: httpx.BaseTransport | None = None,
    ) -> Credentials:
        """Con `VAULT_ADDR` y `VAULT_TOKEN` del entorno del proceso (deployment-architecture §2b)."""
        if not environ.get("VAULT_ADDR") or not environ.get("VAULT_TOKEN"):
            raise CredentialsError("vault_session_missing")
        return cls(environment, environ["VAULT_ADDR"], environ["VAULT_TOKEN"], transport)

    def __repr__(self) -> str:
        return f"Credentials(environment={self._environment.name!r}, loaded={len(self.held_properties())})"

    def _read(self, path: str) -> dict[str, Any]:
        try:
            response = self._http.get(f"/v1/{self._mount}/data/{path}")
        except httpx.HTTPError as error:
            raise CredentialsError(f"vault_unreachable:{path}:{type(error).__name__}") from None
        if response.status_code != 200:
            raise CredentialsError(f"vault_status_{response.status_code}:{path}")
        try:
            data = response.json()["data"]["data"]
        except (ValueError, KeyError, TypeError):
            raise CredentialsError(f"vault_response_shape:{path}") from None
        if not isinstance(data, dict):
            raise CredentialsError(f"vault_response_shape:{path}")
        return data

    def client_key(self, client: str) -> Secret:
        """La llave privada de `channel-simulator` o de `verification-reader`."""
        if client not in CLIENTS:
            raise CredentialsError(f"client_unknown:{client}")
        if client not in self._clients:
            data = self._read(f"identity/clients/{client}")
            if CLIENT_KEY_PROPERTY not in data:
                raise CredentialsError(f"vault_property_missing:{client}")
            self._clients[client] = Secret(str(data[CLIENT_KEY_PROPERTY]))
        return self._clients[client]

    def _users(self, user: str) -> dict[str, Secret]:
        if user not in USERS:
            raise CredentialsError(f"user_unknown:{user}")
        if user.startswith("cumplimiento-") and self._environment.name != KIND.name:
            raise CredentialsError(f"user_denied_in_{self._environment.name}:{user}")
        if self._synthetic is None:
            data = self._read(SYNTHETIC_USERS_PATH)
            wanted = {
                _property(u, suffix)
                for u in USERS
                for suffix in ("PASSWORD", "TOTP_SEED")
                if not (u.startswith("cumplimiento-") and self._environment.name != KIND.name)
            }
            self._synthetic = {name: Secret(str(value)) for name, value in data.items() if name in wanted}
        return self._synthetic

    def user_password(self, user: str) -> Secret:
        users = self._users(user)
        name = _property(user, "PASSWORD")
        if name not in users:
            raise CredentialsError(f"vault_property_missing:{user}")
        return users[name]

    def user_totp_seed(self, user: str) -> Secret:
        users = self._users(user)
        name = _property(user, "TOTP_SEED")
        if name not in users:
            raise CredentialsError(f"vault_property_missing:{user}")
        return users[name]

    def totp(self, user: str, at: datetime) -> str:
        """El codigo TOTP de `user` en el instante `at`: `pyotp.TOTP(semilla).at(at)`. La espera por reuso del codigo es del Paso 5."""
        return pyotp.TOTP(self.user_totp_seed(user).reveal()).at(at)

    def held_properties(self) -> frozenset[str]:
        """Los nombres de lo que hay en memoria (para pruebas y diagnostico; nunca los valores)."""
        held = {f"client:{name}" for name in self._clients}
        held.update(self._synthetic or {})
        return frozenset(held)

    def secret_values(self) -> frozenset[str]:
        """Todo lo secreto que se cargo, incluido el token de la boveda: lo que `evidence.ensure_clean` no debe encontrar en una salida."""
        values = {secret.reveal() for secret in self._clients.values()}
        values.update(secret.reveal() for secret in (self._synthetic or {}).values())
        if not (self._environment.name == KIND.name and self._token == DEV_VAULT_TOKEN):
            values.add(self._token)
        return frozenset(values)
