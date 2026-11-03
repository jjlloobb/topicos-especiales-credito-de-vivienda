"""Un Keycloak y un Pushgateway falsos, sin red (U02-T08, CA-3).

`FakeKeycloak` sirve el Admin API con la forma de sus respuestas, a partir de un documento de realm (el de
`realm_exports.keycloak_view`): el mismo documento que el job debe reconstruir. Anota cada peticion.
"""

import base64
import copy
import datetime
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


class FakeKeycloak:
    def __init__(
        self, base_url: str, realm: Mapping[str, Any], keys: Mapping[str, Any] | None = None
    ) -> None:
        self.base_url = base_url
        self.realm = copy.deepcopy(dict(realm))
        self.keys = keys or {"active": {}, "keys": []}
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.tokens_seen: set[str] = set()
        self.expected_token = "token-de-keycloak-reader"  # noqa: S105

    # --- transporte inyectado en `keycloak_admin` ---------------------------------------------------

    async def get(self, url: str, headers: Mapping[str, str]) -> Any:
        assert url.startswith(self.base_url), url
        self.tokens_seen.add(headers["Authorization"])
        assert headers["Authorization"] == f"Bearer {self.expected_token}"
        parts = urlsplit(url)
        path = unquote(parts.path[len(urlsplit(self.base_url).path) :])
        query = dict(parse_qsl(parts.query))
        self.requests.append((path, query))
        return copy.deepcopy(self._route(path, query))

    # --- rutas --------------------------------------------------------------------------------------

    def _clients(self) -> list[dict[str, Any]]:
        return [{**c, "id": f"cid-{c['clientId']}"} for c in self.realm["clients"]]

    def _scopes(self) -> list[dict[str, Any]]:
        return [{**s, "id": f"sid-{s['name']}"} for s in self.realm["clientScopes"]]

    def _route(self, path: str, query: dict[str, str]) -> Any:
        realm = self.realm
        if path == "":
            top = {k: v for k, v in realm.items() if k not in _SECTIONS}
            return {**top, "id": "realm-uuid", "defaultSignatureAlgorithm": "RS256", "clients": None}
        if path == "/clients":
            return self._clients()
        if path == "/client-scopes":
            return self._scopes()
        if path == "/roles":
            return realm["roles"]["realm"]
        if path == "/authentication/required-actions":
            return realm["requiredActions"]
        if path in ("/default-default-client-scopes", "/default-optional-client-scopes"):
            key = "defaultDefaultClientScopes" if "default-default" in path else "defaultOptionalClientScopes"
            return [{"id": f"sid-{n}", "name": n} for n in realm.get(key, [])]
        if path == "/authentication/flows":
            return [
                {k: v for k, v in f.items() if k != "authenticationExecutions"}
                for f in realm["authenticationFlows"]
            ]
        if path.startswith("/authentication/flows/") and path.endswith("/executions"):
            return self._executions(path.split("/")[3])
        if path.startswith("/authentication/config/"):
            alias = path.rsplit("/", 1)[1].removeprefix("cfg-")
            return {
                **next(c for c in realm["authenticatorConfig"] if c["alias"] == alias),
                "id": f"cfg-{alias}",
            }
        if path.endswith("/scope-mappings"):
            return self._scope_mappings(path)
        if path == "/components":
            return realm.get("components", {}).get(query["type"], [])
        if path == "/users":
            assert "username" in query, "se listo /users sin filtro"
            assert query.get("exact") == "true", "la busqueda de usuario no es exacta"
            return [
                {**u, "id": f"uid-{u['username']}"}
                for u in realm["users"]
                if u["username"] == query["username"]
            ]
        if path.startswith("/users/"):
            return self._user(path)
        if path.startswith("/clients/") and path.endswith("/service-account-user"):
            owner = path.split("/")[2].removeprefix("cid-")
            return {"id": f"uid-service-account-{owner}", "username": f"service-account-{owner}"}
        if path == "/keys":
            return self.keys
        raise AssertionError(f"ruta desconocida: {path}")

    def _executions(self, alias: str) -> list[dict[str, Any]]:
        flow = next(f for f in self.realm["authenticationFlows"] if f["alias"] == alias)
        infos: list[dict[str, Any]] = []
        for index, e in enumerate(flow["authenticationExecutions"]):
            is_flow = bool(e.get("authenticatorFlow"))
            info: dict[str, Any] = {
                "id": f"ex-{alias}-{index}",
                "requirement": e["requirement"],
                "priority": e["priority"],
                "index": index,
                "level": 0,
                "authenticationFlow": is_flow,
                "displayName": e["flowAlias"] if is_flow else e["authenticator"].title(),
            }
            if not is_flow:
                info["providerId"] = e["authenticator"]
            if "authenticatorConfig" in e:
                info["authenticationConfig"] = f"cfg-{e['authenticatorConfig']}"
            infos.append(info)
            if is_flow:  # las ejecuciones del subflujo vienen aplanadas, un nivel mas abajo
                infos.append(
                    {
                        "id": "child",
                        "requirement": "REQUIRED",
                        "priority": 1,
                        "level": 1,
                        "index": 0,
                        "authenticationFlow": False,
                        "providerId": "hijo",
                        "displayName": "Hijo",
                    }
                )
        return infos

    def _scope_mappings(self, path: str) -> dict[str, Any]:
        _, kind, ident, _ = path.split("/")
        field, name = (
            ("client", ident.removeprefix("cid-"))
            if kind == "clients"
            else ("clientScope", ident.removeprefix("sid-"))
        )
        result: dict[str, Any] = {"realmMappings": None, "clientMappings": None}
        for entry in self.realm.get("scopeMappings", []):
            if entry.get(field) == name:
                result["realmMappings"] = [{"name": r} for r in entry["roles"]]
        for container, entries in self.realm.get("clientScopeMappings", {}).items():
            for entry in entries:
                if entry.get(field) == name:
                    result["clientMappings"] = {
                        **(result["clientMappings"] or {}),
                        container: {"client": container, "mappings": [{"name": r} for r in entry["roles"]]},
                    }
        return result

    def _user(self, path: str) -> Any:
        _, _, ident, what = path.split("/")
        user = next(u for u in self.realm["users"] if f"uid-{u['username']}" == ident)
        if what == "role-mappings":
            return {
                "realmMappings": [{"name": r} for r in user.get("realmRoles", [])],
                "clientMappings": {
                    c: {"client": c, "mappings": [{"name": r} for r in roles]}
                    for c, roles in user.get("clientRoles", {}).items()
                },
            }
        if what == "credentials":
            return [
                {"id": f"cred-{user['username']}-{c['type']}", "type": c["type"], "createdDate": 1}
                for c in user.get("credentials", [])
            ]
        raise AssertionError(path)


_SECTIONS = frozenset(
    {
        "clients", "clientScopes", "roles", "components", "authenticationFlows", "requiredActions",
        "authenticatorConfig", "users", "scopeMappings", "clientScopeMappings",
        "defaultDefaultClientScopes", "defaultOptionalClientScopes",
    }
)  # fmt: skip


class FakePushgateway:
    def __init__(self) -> None:
        self.puts: list[tuple[str, str]] = []

    async def put(self, url: str, body: bytes) -> None:
        self.puts.append((url, body.decode()))


def certificate(not_before: datetime.datetime) -> str:
    """Un certificado autofirmado, en DER base64 como lo devuelve `GET /keys`."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "vectra")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_before + datetime.timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )
    return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()


def ec_key_pair() -> tuple[str, str]:
    """(PEM privada, PEM publica) de una llave ES256."""
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private, public
