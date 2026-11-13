"""Lectura del Admin API de Keycloak por F94 para `realm-drift` y `signing-key-age` (U02-T08; INF-U2-05a, INF-U2-09).

Solo lee. El token sale de `vectra_common.service_token` (`private_key_jwt` ES256 de `keycloak-reader`); no hay otro
firmante. El transporte (`HttpGet`, `HttpPut`) se inyecta para probar sin red. Los usuarios se piden uno a uno por su
`username` de Git (`GET /users?username=...&exact=true`): nunca se lista `/users` sin filtro.
"""

import asyncio
import json
import os
import ssl
import urllib.request
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Final, Protocol
from urllib.parse import quote, urlencode

import realm_diff
from vectra_common.service_token import provider_from_env

ADMIN_URL_ENV: Final = "KEYCLOAK_ADMIN_URL"
PUSHGATEWAY_URL_ENV: Final = "PUSHGATEWAY_URL"
CA_BUNDLE_ENV: Final = "VECTRA_CA_BUNDLE"
TIMEOUT: Final = 30.0
# Las secciones del realm que se leen una a una; el resto del documento sale de `GET /admin/realms/vectra`.
READ_SEPARATELY: Final = frozenset(
    {
        "clients", "clientScopes", "roles", "components", "authenticationFlows", "requiredActions",
        "authenticatorConfig", "users", "scopeMappings", "clientScopeMappings",
        "defaultDefaultClientScopes", "defaultOptionalClientScopes",
    }
)  # fmt: skip

HttpGet = Callable[[str, Mapping[str, str]], Awaitable[Any]]
HttpPut = Callable[[str, bytes], Awaitable[None]]
Fetch = Callable[[str, Mapping[str, str] | None], Awaitable[Any]]


class TokenSource(Protocol):
    async def token(self) -> str: ...


def make_fetch(base_url: str, tokens: TokenSource, http_get: HttpGet) -> Fetch:
    """`GET <base_url><path>?<query>` con el token de servicio. `path` empieza por `/`."""

    async def fetch(path: str, query: Mapping[str, str] | None = None) -> Any:
        url = base_url.rstrip("/") + path + (f"?{urlencode(query)}" if query else "")
        return await http_get(
            url, {"Authorization": f"Bearer {await tokens.token()}", "Accept": "application/json"}
        )

    return fetch


def _context() -> ssl.SSLContext:
    bundle = os.environ[CA_BUNDLE_ENV]  # nunca se desactiva la verificacion
    return ssl.create_default_context(cafile=bundle)


async def urllib_get(url: str, headers: Mapping[str, str]) -> Any:
    def call() -> Any:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")  # noqa: S310
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=_context()) as answer:  # noqa: S310
            return json.loads(answer.read())

    return await asyncio.to_thread(call)


async def urllib_put(url: str, body: bytes) -> None:
    def call() -> None:
        request = urllib.request.Request(url, data=body, method="PUT")  # noqa: S310
        with urllib.request.urlopen(request, timeout=TIMEOUT):  # noqa: S310
            pass

    await asyncio.to_thread(call)


def fetch_from_env(http_get: HttpGet = urllib_get) -> Fetch:
    """El token de `keycloak-reader` (`VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_ASSERTION_AUDIENCE`, `VECTRA_CLIENT_KEY_PATH`) y la URL del Admin API."""
    return make_fetch(os.environ[ADMIN_URL_ENV], provider_from_env("keycloak", ()), http_get)


def _q(value: str) -> str:
    return quote(value, safe="")


def _names(mappings: Any) -> list[str]:
    return [str(m["name"]) for m in mappings or []]


class KeycloakReader:
    """Arma, con el Admin API, el documento que `realm_diff` compara contra el realm de Git."""

    def __init__(self, fetch: Fetch) -> None:
        self._fetch = fetch

    async def realm(self) -> dict[str, Any]:
        found = await self._fetch("", None)
        assert isinstance(found, dict)
        return found

    async def keys(self) -> dict[str, Any]:
        found = await self._fetch("/keys", None)
        assert isinstance(found, dict)
        return found

    async def export(self, git: Mapping[str, Any]) -> dict[str, Any]:
        """El realm tal como lo ve Keycloak, con las secciones que Git fija. Los usuarios, solo los de Git."""
        doc = {k: v for k, v in (await self.realm()).items() if k not in READ_SEPARATELY}
        clients = await self._fetch("/clients", None)
        scopes = await self._fetch("/client-scopes", None)
        doc["clients"] = clients
        doc["clientScopes"] = scopes
        doc["roles"] = {"realm": await self._roles(clients)}
        doc["requiredActions"] = await self._fetch("/authentication/required-actions", None)
        doc["defaultDefaultClientScopes"] = _names(await self._fetch("/default-default-client-scopes", None))
        doc["defaultOptionalClientScopes"] = _names(
            await self._fetch("/default-optional-client-scopes", None)
        )
        doc["authenticationFlows"], doc["authenticatorConfig"] = await self._flows(
            {f["alias"] for f in git.get("authenticationFlows", [])}
        )
        doc["scopeMappings"], doc["clientScopeMappings"] = await self._scope_mappings(clients, scopes)
        doc["components"] = await self._components(git)
        doc["users"] = await self._users(git, clients)
        return doc

    async def _roles(self, clients: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Los roles de realm con sus composites (`composites: {realm: [...], client: {clientId: [...]}}`)."""
        client_ids = {c["id"]: c["clientId"] for c in clients}
        roles = []
        for role in await self._fetch("/roles", None):
            composites: dict[str, Any] = {}
            if role.get("composite"):
                realm_names: list[str] = []
                client_names: dict[str, list[str]] = {}
                for child in await self._fetch(f"/roles/{_q(role['name'])}/composites", None):
                    if child.get("clientRole"):
                        client_names.setdefault(client_ids[child["containerId"]], []).append(child["name"])
                    else:
                        realm_names.append(child["name"])
                composites = {"realm": realm_names, "client": client_names}
            roles.append({**role, "composites": composites})
        return roles

    async def _flows(self, declared: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        flows: list[dict[str, Any]] = []
        configs: dict[str, dict[str, Any]] = {}
        for flow in await self._fetch("/authentication/flows", None):
            # Un flujo de Keycloak (alias de la lista exacta de `realm_diff` y `builtIn`): sin ejecuciones ni configuraciones.
            keycloak_own = (
                flow.get("builtIn") is True
                and flow["alias"] in realm_diff.BUILT_IN_NAMES[("authenticationFlows",)]
            )
            if keycloak_own and flow["alias"] not in declared:
                flows.append(flow)
                continue
            executions = []
            for info in await self._fetch(f"/authentication/flows/{_q(flow['alias'])}/executions", None):
                if info.get("level", 0) != 0:
                    continue  # las de un subflujo son del flujo de ese subflujo
                execution: dict[str, Any] = {
                    "authenticatorFlow": bool(info.get("authenticationFlow", False)),
                    "requirement": info["requirement"],
                    "priority": info["priority"],
                }
                if execution["authenticatorFlow"]:
                    execution["flowAlias"] = info["displayName"]
                else:
                    execution["authenticator"] = info["providerId"]
                if info.get("authenticationConfig"):
                    config = await self._fetch(
                        f"/authentication/config/{_q(info['authenticationConfig'])}", None
                    )
                    execution["authenticatorConfig"] = config["alias"]
                    configs[config["alias"]] = config
                executions.append(execution)
            flows.append({**flow, "authenticationExecutions": executions})
        return flows, list(configs.values())

    async def _scope_mappings(
        self, clients: list[dict[str, Any]], scopes: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        realm_level: list[dict[str, Any]] = []
        client_level: dict[str, list[dict[str, Any]]] = {}
        owners = [("client", c["clientId"], f"/clients/{_q(c['id'])}") for c in clients]
        owners += [("clientScope", s["name"], f"/client-scopes/{_q(s['id'])}") for s in scopes]
        for field, name, base in owners:
            mappings = await self._fetch(f"{base}/scope-mappings", None) or {}
            if roles := _names(mappings.get("realmMappings")):
                realm_level.append({field: name, "roles": roles})
            for container, mapped in (mappings.get("clientMappings") or {}).items():
                if roles := _names(mapped.get("mappings")):
                    client_level.setdefault(container, []).append({field: name, "roles": roles})
        return realm_level, client_level

    async def _components(self, git: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """Solo los tipos que Git declara: el resto de los componentes son de Keycloak (llaves, proveedores)."""
        return {kind: await self._fetch("/components", {"type": kind}) for kind in git.get("components", {})}

    async def _users(self, git: Mapping[str, Any], clients: list[dict[str, Any]]) -> list[dict[str, Any]]:
        client_ids = {c["clientId"]: c["id"] for c in clients}
        users: list[dict[str, Any]] = []
        for declared in git.get("users", []):
            found = await self._fetch("/users", {"username": declared["username"], "exact": "true"})
            matches = [u for u in found if u.get("username") == declared["username"]]
            if not matches:
                continue  # una entidad de Git que falta en Keycloak
            user = dict(matches[0])
            mappings = await self._fetch(f"/users/{_q(user['id'])}/role-mappings", None) or {}
            user["realmRoles"] = _names(mappings.get("realmMappings"))
            user["clientRoles"] = {
                container: _names(mapped.get("mappings"))
                for container, mapped in (mappings.get("clientMappings") or {}).items()
            }
            if target := declared.get("serviceAccountClientId"):
                account = (
                    await self._fetch(f"/clients/{_q(client_ids[target])}/service-account-user", None)
                    if target in client_ids
                    else {}
                )
                if account.get("id") == user["id"]:
                    user["serviceAccountClientId"] = target
            users.append(user)
        return users
