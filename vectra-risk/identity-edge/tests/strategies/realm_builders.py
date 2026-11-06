"""Realms de ejemplo para las pruebas de `realm-lint` (no son los realms reales de U02-T04).

Usan la representacion de realm de Keycloak (la que importa `keycloak-config-cli`). Los
scopes de cada cliente salen de `SCOPE_HOLDERS` del catalogo de U0, no de una lista a mano;
las audiencias (domain-entities §2.2) si estan escritas aqui porque U0 no las cataloga.
"""

import copy
from typing import Any

from vectra_contracts.catalog import SCOPE_HOLDERS, Role, Scope

# Clientes que solo existen fuera de produccion (domain-entities §2.2).
NON_PROD_CLIENTS = frozenset({"channel-simulator", "verification-reader"})
NON_PROD_SCOPES = {"case-service": frozenset({Scope.CORE_READ_CREDIT.value})}

AUDIENCES = {
    "case-service": ["decision-registry-service", "governance-service"],
    "case-worker": ["scoring-service", "governance-service"],
    "scoring-service": ["explainability-service", "governance-service", "decision-registry-service"],
    "explainability-service": ["decision-registry-service", "governance-service"],
    "governance-service": ["bias-monitoring-service", "decision-registry-service"],
    "bias-monitoring-service": ["decision-registry-service"],
    "bias-monitoring-job": ["governance-service", "decision-registry-service"],
    "model-validation-job": ["governance-service"],
    "product-metrics": ["decision-registry-service"],
    "verification-reader": ["decision-registry-service"],
    "channel": ["case-service"],
    "channel-simulator": ["case-service"],
    "promotion-tool": ["governance-service"],
}
USER_AUDIENCES = [
    "console-bff",
    "case-service",
    "governance-service",
    "decision-registry-service",
    "bias-monitoring-service",
    "explainability-service",
]

BUSINESS_ROLES = tuple(r.value for r in Role)
MFA_ROLES = ("ingeniero_riesgo", "cro", "cumplimiento")
TOTP = "CONFIGURE_TOTP"


def audience_mapper(audience: str) -> dict[str, Any]:
    return {
        "name": f"aud-{audience}",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "config": {
            "included.client.audience": audience,
            "access.token.claim": "true",
            "id.token.claim": "false",
        },
    }


def roles_mapper() -> dict[str, Any]:
    return {
        "name": "roles",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-usermodel-realm-role-mapper",
        "config": {"claim.name": "roles", "multivalued": "true", "access.token.claim": "true"},
    }


def service_client(client_id: str, scopes: list[str], audiences: list[str]) -> dict[str, Any]:
    return {
        "clientId": client_id,
        "enabled": True,
        "publicClient": False,
        "serviceAccountsEnabled": True,
        "standardFlowEnabled": False,
        "clientAuthenticatorType": "client-jwt",
        "defaultClientScopes": [],
        "optionalClientScopes": sorted(scopes),
        "protocolMappers": [audience_mapper(a) for a in audiences],
    }


def service_clients(env: str) -> list[dict[str, Any]]:
    """Un cliente por titular del catalogo de U0 (promotion-tool es de usuario y se agrega aparte)."""
    held: dict[str, list[str]] = {}
    for scope, holders in SCOPE_HOLDERS.items():
        for holder in holders:
            if holder == "promotion-tool":
                continue
            held.setdefault(holder, []).append(scope.value)
    clients = []
    for client_id in sorted(held):
        if env == "prod" and client_id in NON_PROD_CLIENTS:
            continue
        scopes = [s for s in held[client_id] if not (env == "prod" and s in NON_PROD_SCOPES.get(client_id, ()))]
        audiences = list(AUDIENCES[client_id])
        if client_id == "case-service" and env != "prod":
            audiences.append("core-banking-mock")
        clients.append(service_client(client_id, scopes, audiences))
    # Clientes de administracion de INF-U2-05a: sin scopes del catalogo ni audiencias de servicio.
    clients += [service_client("keycloak-config-cli", [], []), service_client("keycloak-reader", [], [])]
    return clients


def user_clients() -> list[dict[str, Any]]:
    console = {
        "clientId": "vectra-console",
        "enabled": True,
        "publicClient": True,
        "standardFlowEnabled": True,
        "attributes": {
            "pkce.code.challenge.method": "S256",
            "post.logout.redirect.uris": "https://vectra.example.org/",
        },
        "redirectUris": [
            "https://vectra.example.org/callback",
            "https://vectra.example.org/stepup-callback",
        ],
        "webOrigins": ["https://vectra.example.org"],
        "defaultClientScopes": [],
        "optionalClientScopes": [],
        "protocolMappers": [audience_mapper(a) for a in USER_AUDIENCES]
        + [roles_mapper()]
        + [
            {  # `name` solo en el ID token, que consume la SPA (domain-entities §1.3).
                "name": "name-id-token",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-property-mapper",
                "config": {
                    "claim.name": "name",
                    "user.attribute": "firstName",
                    "id.token.claim": "true",
                    "access.token.claim": "false",
                },
            }
        ],
    }
    promotion = {
        "clientId": "promotion-tool",
        "enabled": True,
        "publicClient": True,
        "standardFlowEnabled": True,
        "attributes": {"pkce.code.challenge.method": "S256"},
        "redirectUris": ["http://127.0.0.1"],
        "defaultClientScopes": [],
        "optionalClientScopes": [Scope.GOVERNANCE_PROMOTION.value],
        "protocolMappers": [audience_mapper("governance-service"), roles_mapper()],
    }
    grafana = {
        "clientId": "grafana",
        "enabled": True,
        "publicClient": False,
        "standardFlowEnabled": True,
        "clientAuthenticatorType": "client-jwt",
        "redirectUris": ["https://vectra.example.org/grafana/login/generic_oauth"],
        "defaultClientScopes": [],
        "optionalClientScopes": [],
        "protocolMappers": [roles_mapper()],
    }
    return [console, promotion, grafana]


def user(username: str, roles: list[str], *, totp: bool | None = None) -> dict[str, Any]:
    needs_totp = any(r in MFA_ROLES or r in ("operacion", "realm-admin") for r in roles)
    actions = [TOTP] if (needs_totp if totp is None else totp) else []
    return {"username": username, "enabled": True, "realmRoles": roles, "requiredActions": actions}


def break_glass() -> dict[str, Any]:
    """`realm-admin` es un rol de cliente de `realm-management` en Keycloak."""
    return {
        "username": "break-glass",
        "enabled": True,
        "realmRoles": [],
        "clientRoles": {"realm-management": ["realm-admin"]},
        "requiredActions": [TOTP],
    }


def synthetic_users() -> list[dict[str, Any]]:
    names = {"analista": "analista", "ingeniero_riesgo": "ingeniero", "cro": "cro", "cumplimiento": "cumplimiento"}
    users = [user(f"{short}-{n}", [role]) for role, short in names.items() for n in (1, 2)]
    users += [user(f"operacion-{n}", ["operacion"]) for n in (1, 2)]
    return users


def update_password_action() -> dict[str, Any]:
    """H12 (BR-U2-03): la accion requerida `UPDATE_PASSWORD`, registrada y habilitada, como la crea Keycloak 26.8.1."""
    return {"alias": "UPDATE_PASSWORD", "name": "Update Password", "providerId": "UPDATE_PASSWORD", "enabled": True, "defaultAction": False, "priority": 57}


def valid_realm(env: str) -> dict[str, Any]:
    """Un realm que `realm-lint` acepta, para `env` en {kind, staging, prod}."""
    users = [break_glass()] if env == "prod" else synthetic_users()
    return {
        "realm": "vectra",
        "enabled": True,
        "passwordPolicy": "length(14) and notUsername and notEmail and passwordHistory(5) and hashAlgorithm(argon2)",
        "bruteForceProtected": True,
        "bruteForceStrategy": "LINEAR",
        "permanentLockout": True,
        "failureFactor": 5,
        "waitIncrementSeconds": 60,
        "maxFailureWaitSeconds": 900,
        "maxDeltaTimeSeconds": 43200,
        "maxTemporaryLockouts": 15,
        "accessTokenLifespan": 300,
        "ssoSessionIdleTimeout": 1800,
        "ssoSessionMaxLifespan": 36000,
        "requiredActions": [update_password_action()],
        "users": users,
        "clients": user_clients() + service_clients(env),
    }


def find_client(realm: dict[str, Any], client_id: str) -> dict[str, Any]:
    return next(c for c in realm["clients"] if c["clientId"] == client_id)


def find_user(realm: dict[str, Any], username: str) -> dict[str, Any]:
    return next(u for u in realm["users"] if u["username"] == username)


def realm_copy(env: str) -> dict[str, Any]:
    return copy.deepcopy(valid_realm(env))
