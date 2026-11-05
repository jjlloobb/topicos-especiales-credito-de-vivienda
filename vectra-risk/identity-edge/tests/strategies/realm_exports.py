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
# Los flujos que crea Keycloak 26.8.1 (DefaultAuthenticationFlows.java), escritos aqui a mano, sin las listas de `realm_diff`.
KEYCLOAK_FLOWS = (
    "registration", "registration form", "reset credentials", "Reset - Conditional OTP", "direct grant",
    "Direct Grant - Conditional OTP", "browser", "forms", "Browser - Conditional 2FA", "clients",
    "first broker login", "User creation or linking", "Handle Existing Account", "Account verification options",
    "Verify Existing Account by Re-authentication", "First broker login - Conditional 2FA", "saml ecp", "docker auth",
)  # fmt: skip


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
        return resolve(node)
    return node


def resolve(text: str, filler: str = "resuelto") -> str:
    """El texto con cada `$(env:NOMBRE)` sustituido por un valor: lo literal que lo rodea se conserva (S3)."""
    out = ""
    while (start := text.find(MARKER)) >= 0:
        out += text[:start] + filler
        text = text[text.index(")", start) + 1 :]
    return out + text


def _noise(entity: dict[str, Any], ident: str, variant: str) -> None:
    entity["id"] = f"id-{ident}{variant}"
    entity["bearerOnly"] = False
    entity["frontchannelLogout"] = True


def keycloak_view(git: dict[str, Any], variant: str = "") -> dict[str, Any]:
    """`variant` cambia los secretos, IDs y timestamps (a mano, sin las listas de `realm_diff`)."""
    kc = _fill_markers(copy.deepcopy(git))
    kc["id"] = f"realm-uuid{variant}"
    kc["notBefore"] = 1730000000 + len(variant)
    kc["bruteForceStrategy"] = git["bruteForceStrategy"]  # H10: ya no es un valor por defecto: Git lo fija
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
    kc["clients"] += [
        {"clientId": name, "id": f"id-{name}"}
        for name in ("account", "broker", "realm-management", "account-console")
    ]
    kc["clientScopes"] += [{"name": "profile", "id": "id-profile"}]
    kc["roles"]["realm"] += [
        {"name": "offline_access", "id": "id-offline"},
        {"name": "uma_authorization", "id": "id-uma"},
        {
            "name": "default-roles-vectra",
            "id": "id-default",
            "composites": {
                "realm": ["offline_access", "uma_authorization"],
                "client": {"account": ["view-profile", "manage-account"]},
            },
        },
    ]
    kc["requiredActions"] += [{"alias": "VERIFY_EMAIL", "name": "Verify Email"}]
    # Valores por defecto de un realm nuevo de Keycloak 26.8.1 (DefaultClientScopes.java, RealmManager.java, ClientManager.java,
    # DefaultAuthenticationFlows.java), que Git no declara.
    kc["scopeMappings"].append({"clientScope": "offline_access", "roles": ["offline_access"]})
    kc["clientScopeMappings"]["account"] = [
        {"client": "account-console", "roles": ["view-groups", "manage-account"]}
    ]
    for client in kc["clients"]:
        if client.get("serviceAccountsEnabled"):
            client["defaultClientScopes"] = [*client.get("defaultClientScopes", []), "service_account"]
    for user in kc["users"]:
        user["realmRoles"] = [*user.get("realmRoles", []), "default-roles-vectra"]
    kc["authenticationFlows"] += [
        {"alias": alias, "builtIn": True, "authenticationExecutions": []} for alias in KEYCLOAK_FLOWS
    ]
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
