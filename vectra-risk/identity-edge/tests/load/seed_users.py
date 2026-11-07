"""Crea y borra los 200 usuarios de carga `load-001..200` por la Admin API de Keycloak (U02-T15, J1).

Solo para kind: no van al realm versionado. Lo ejecuta el operador en el Paso 16, con la Admin API por port-forward:

    VECTRA_E2E_ADMIN_URL=https://127.0.0.1:8443/auth VECTRA_E2E_ADMIN_USER=... VECTRA_E2E_ADMIN_PASSWORD=... \\
    K6_LOAD_PASSWORD=... uv run python identity-edge/tests/load/seed_users.py create      # o `delete`

Los usuarios no tienen credencial OTP ni acciones requeridas, y llevan `LOAD_ROLE`: un rol al que BR-U2-03 no exige MFA y cuyo
subflujo del realm (`vectra-mfa-<rol>`) lleva `conditional-user-configured`, asi que entra con la contrasena sola. Es idempotente:
una segunda corrida borra y vuelve a crear cada `load-NNN` (con `passwordHistory(5)` Keycloak no deja reponer la misma contrasena, y asi
tampoco quedan bloqueos, acciones pendientes ni OTP); el resultado es el mismo conjunto de usuarios. `delete` solo toca los nombres `load-NNN`.
"""

import argparse
import os
import sys
from typing import Any

import httpx

LOAD_ROLE = "analista"
PREFIX = "load-"
DEFAULT_COUNT = 200
REALM = "vectra"


class Seeder:
    def __init__(
        self, http: httpx.Client, base: str, admin_user: str, admin_password: str, load_password: str, realm: str = REALM
    ) -> None:
        self.http = http
        self.base = base.rstrip("/")
        self.admin_user, self.admin_password = admin_user, admin_password
        self.load_password = load_password
        self.realm = realm
        self._token = ""

    def _headers(self) -> dict[str, str]:
        if not self._token:
            response = self.http.post(
                f"{self.base}/realms/master/protocol/openid-connect/token",
                data={
                    "grant_type": "password", "client_id": "admin-cli",
                    "username": self.admin_user, "password": self.admin_password,
                },
            )  # fmt: skip
            if response.status_code != 200:
                raise RuntimeError(f"token de administracion: HTTP {response.status_code}")
            self._token = response.json()["access_token"]
        return {"Authorization": f"Bearer {self._token}"}

    def _call(self, method: str, path: str, expect: tuple[int, ...], **kwargs: Any) -> httpx.Response:
        response = self.http.request(
            method, f"{self.base}/admin/realms/{self.realm}{path}", headers=self._headers(), **kwargs
        )
        if response.status_code == 401 and self._token:  # el token de administracion dura poco: se pide otro una vez
            self._token = ""
            response = self.http.request(
                method, f"{self.base}/admin/realms/{self.realm}{path}", headers=self._headers(), **kwargs
            )
        if response.status_code not in expect:
            raise RuntimeError(f"{method} {path}: HTTP {response.status_code} {response.text[:200]}")
        return response

    @staticmethod
    def names(count: int) -> list[str]:
        return [f"{PREFIX}{i:03d}" for i in range(1, count + 1)]

    def _find(self, username: str) -> str | None:
        found = self._call("GET", "/users", (200,), params={"username": username, "exact": "true"}).json()
        return str(found[0]["id"]) if found else None

    def create(self, count: int = DEFAULT_COUNT) -> None:
        role = self._call("GET", f"/roles/{LOAD_ROLE}", (200,)).json()
        for username in self.names(count):
            existing = self._find(username)
            if existing is not None:
                # Keycloak 26.8.1 rechaza con 400 reusar la contrasena vigente (passwordHistory(5), HistoryPasswordPolicyProvider.validate
                # lineas 56-64), asi que no se puede "reponer" la misma contrasena; ademas un usuario viejo puede estar bloqueado, con
                # acciones pendientes u OTP. Se borra y se vuelve a crear: sin historial ni residuos.
                self._call("DELETE", f"/users/{existing}", (204,))
            body = {
                "username": username, "enabled": True, "emailVerified": False, "requiredActions": [],
                "credentials": [{"type": "password", "value": self.load_password, "temporary": False}],
            }  # fmt: skip
            created = self._call("POST", "/users", (201,), json=body)
            user_id = created.headers["location"].rsplit("/", 1)[1]
            mapped = self._call("GET", f"/users/{user_id}/role-mappings/realm", (200,)).json()
            if LOAD_ROLE not in {r["name"] for r in mapped}:
                self._call("POST", f"/users/{user_id}/role-mappings/realm", (204,), json=[role])

    def delete(self, count: int = DEFAULT_COUNT) -> None:
        for username in self.names(count):
            user_id = self._find(username)
            if user_id is not None:
                self._call("DELETE", f"/users/{user_id}", (204,))


def _need(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"falta la variable de entorno {name} (ver identity-edge/tests/load/README.md)")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("action", choices=("create", "delete"))
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    args = parser.parse_args(argv)
    ca = os.environ.get("VECTRA_E2E_ADMIN_CA_BUNDLE") or os.environ.get("VECTRA_E2E_CA_BUNDLE") or True
    with httpx.Client(verify=ca, timeout=30.0) as http:
        seeder = Seeder(
            http, _need("VECTRA_E2E_ADMIN_URL"), _need("VECTRA_E2E_ADMIN_USER"), _need("VECTRA_E2E_ADMIN_PASSWORD"),
            _need("K6_LOAD_PASSWORD"),
        )  # fmt: skip
        getattr(seeder, args.action)(args.count)
    print(f"{args.action}: {args.count} usuarios {PREFIX}NNN")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
