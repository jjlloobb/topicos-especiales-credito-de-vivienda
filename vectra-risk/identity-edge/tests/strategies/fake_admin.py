"""Un Admin API de Keycloak falso para los usuarios de carga (U02-T15, CA-4), sin red.

Sirve por `httpx.MockTransport` solo lo que usa `seed_users.py`: token de `admin-cli`, usuarios, roles del realm y reinicio de
contrasena. Los roles salen del realm de kind. Anota cada peticion para comprobar la idempotencia.
"""

import json
import uuid
from typing import Any
from urllib.parse import unquote

import httpx

ADMIN_PASSWORD = "admin-pass"  # noqa: S105


class FakeAdmin:
    def __init__(self, realm: dict[str, Any], realm_name: str = "vectra") -> None:
        self.roles = {r["name"]: {"id": f"role-{r['name']}", "name": r["name"]} for r in realm["roles"]["realm"]}
        self.prefix = f"/auth/admin/realms/{realm_name}"
        self.users: dict[str, dict[str, Any]] = {}  # id -> usuario
        self.mapped: dict[str, list[str]] = {}  # id -> roles
        self.passwords: dict[str, str] = {}
        self.requests: list[tuple[str, str]] = []

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle), base_url="http://keycloak.test")

    def count(self, method: str, suffix: str = "") -> int:
        return sum(1 for m, p in self.requests if m == method and p.endswith(suffix))

    def by_name(self, username: str) -> dict[str, Any] | None:
        return next((u for u in self.users.values() if u["username"] == username), None)

    def handle(self, request: httpx.Request) -> httpx.Response:
        path, method = unquote(request.url.path), request.method
        self.requests.append((method, path))
        if path == "/auth/realms/master/protocol/openid-connect/token":
            form = dict(x.split("=", 1) for x in request.content.decode().split("&"))
            if form.get("password") != ADMIN_PASSWORD:
                return httpx.Response(401, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "admin-token", "expires_in": 60})
        assert request.headers.get("Authorization") == "Bearer admin-token", "peticion de administracion sin token"
        assert path.startswith(self.prefix), path
        rest = path[len(self.prefix) :]
        body = json.loads(request.content) if request.content else None
        if rest == "/users" and method == "GET":
            params = request.url.params
            assert params.get("exact") == "true", "la busqueda de usuario no es exacta"
            found = self.by_name(params["username"])
            return httpx.Response(200, json=[{**found, "id": found["id"]}] if found else [])
        if rest == "/users" and method == "POST":
            if self.by_name(body["username"]):
                return httpx.Response(409, json={"errorMessage": "User exists with same username"})
            user_id = str(uuid.uuid4())
            credentials = body.get("credentials", [])
            self.users[user_id] = {
                "id": user_id, "username": body["username"], "enabled": body.get("enabled", True),
                "requiredActions": body.get("requiredActions", []),
                "otp": any(c["type"] in ("otp", "totp") for c in credentials),
            }  # fmt: skip
            for cred in credentials:
                if cred["type"] == "password":
                    self.passwords[user_id] = cred["value"]
            self.mapped[user_id] = []
            return httpx.Response(201, headers={"Location": f"http://keycloak.test{self.prefix}/users/{user_id}"})
        if rest.startswith("/roles/") and method == "GET":
            role = self.roles.get(rest.split("/")[2])
            return httpx.Response(200, json=role) if role else httpx.Response(404, json={})
        parts = rest.split("/")
        if len(parts) >= 3 and parts[1] == "users" and parts[2] in self.users:
            user_id = parts[2]
            tail = "/".join(parts[3:])
            if tail == "role-mappings/realm" and method == "GET":
                return httpx.Response(200, json=[self.roles[n] for n in self.mapped[user_id]])
            if tail == "role-mappings/realm" and method == "POST":
                self.mapped[user_id] += [r["name"] for r in body if r["name"] not in self.mapped[user_id]]
                return httpx.Response(204)
            if tail == "reset-password" and method == "PUT":
                self.passwords[user_id] = body["value"]
                return httpx.Response(204)
            if tail == "" and method == "DELETE":
                del self.users[user_id], self.mapped[user_id]
                self.passwords.pop(user_id, None)
                return httpx.Response(204)
        raise AssertionError(f"ruta desconocida: {method} {path}")
