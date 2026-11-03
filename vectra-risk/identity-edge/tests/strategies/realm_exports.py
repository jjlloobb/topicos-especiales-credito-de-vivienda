"""Exportaciones de realm para las pruebas de `realm_diff` (U02-T08): lo que Keycloak devuelve, derivado del realm de Git.

`keycloak_view(git)` es el mismo realm tal como lo veria el Admin API: con los valores que Git toma de `$(env:...)`,
secretos, IDs internos y timestamps que Git no tiene, campos por defecto, entidades propias de Keycloak y el orden
distinto. Debe dar 0 diferencias contra Git; cada prueba lo altera en un solo punto.
"""

import copy
from pathlib import Path
from typing import Any

import yaml

REALM_DIR = Path(__file__).resolve().parents[2] / "keycloak" / "realm"
ENVS = ("kind", "staging", "prod")
MARKER = "$(env:"


def load_git(env: str) -> dict[str, Any]:
    data = yaml.safe_load((REALM_DIR / f"realm.{env}.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _fill_markers(node: Any) -> Any:
    """Lo que Keycloak tiene donde Git trae una referencia a la boveda: otro valor."""
    if isinstance(node, dict):
        return {k: _fill_markers(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_fill_markers(v) for v in node]
    if isinstance(node, str) and MARKER in node:
        return "valor-de-la-boveda"
    return node


def _noise(entity: dict[str, Any], ident: str, variant: str) -> None:
    entity["id"] = f"id-{ident}{variant}"
    entity["bearerOnly"] = False
    entity["frontchannelLogout"] = True


def keycloak_view(git: dict[str, Any], variant: str = "") -> dict[str, Any]:
    """`variant` cambia los secretos, IDs y timestamps (a mano, sin las listas de `realm_diff`)."""
    kc = _fill_markers(copy.deepcopy(git))
    kc["id"] = f"realm-uuid{variant}"
    kc["notBefore"] = 1730000000 + len(variant)
    kc["bruteForceStrategy"] = "MULTIPLE"  # un valor por defecto que Git no fija
    for client in kc["clients"]:
        _noise(client, client["clientId"], variant)
        client["secret"] = f"secreto-de-keycloak{variant}"
        client["notBefore"] = len(variant)
        for mapper in client.get("protocolMappers", []):
            mapper["id"] = f"id-{client['clientId']}-{mapper['name']}"
    for scope in kc["clientScopes"]:
        scope["id"] = f"id-{scope['name']}"
        for mapper in scope.get("protocolMappers", []):
            mapper["id"] = f"id-{scope['name']}-{mapper['name']}"
    for role in kc["roles"]["realm"]:
        role.update(
            id=f"id-{role['name']}", composite=False, clientRole=False, containerId=f"realm-uuid{variant}"
        )
    for flow in kc["authenticationFlows"]:
        flow["id"] = f"id-{flow['alias']}"
        for execution in flow["authenticationExecutions"]:
            execution["id"] = f"id-{flow['alias']}-{execution['priority']}"
    for config in kc["authenticatorConfig"]:
        config["id"] = f"id-{config['alias']}"
    for user in kc["users"]:
        user["id"] = f"id-{user['username']}"
        user["createdTimestamp"] = 1730000001 + len(variant)
        user["notBefore"] = 0
        for credential in user.get("credentials", []):
            credential["id"] = f"cred-{user['username']}-{credential['type']}"
            credential["createdDate"] = 1730000002 + len(variant)
            credential["value"] = f"otro-valor{variant}"
            credential["secretData"] = f"otro-secreto{variant}"
            credential["credentialData"] = f"otros-datos{variant}"
    for providers in kc.get("components", {}).values():
        for component in providers:
            component["id"] = f"id-{component['name']}"
            component["parentId"] = f"realm-uuid{variant}"
    # Entidades propias de Keycloak, que Git no declara.
    kc["clients"] += [{"clientId": "account", "id": "id-account"}, {"clientId": "broker", "id": "id-broker"}]
    kc["clientScopes"] += [{"name": "profile", "id": "id-profile"}]
    kc["roles"]["realm"] += [{"name": "offline_access", "id": "id-offline"}]
    kc["requiredActions"] += [{"alias": "VERIFY_EMAIL", "name": "Verify Email"}]
    kc["authenticationFlows"] += [{"alias": "browser", "builtIn": True, "authenticationExecutions": []}]
    # El orden de las listas de entidades no cuenta.
    for key in (
        "clients",
        "clientScopes",
        "requiredActions",
        "authenticationFlows",
        "authenticatorConfig",
        "users",
    ):
        kc[key].reverse()
    kc["roles"]["realm"].reverse()
    return kc
