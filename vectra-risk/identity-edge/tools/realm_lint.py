"""`realm-lint`: valida los `realm.{kind,staging,prod}.yaml` de U2 (Pasos 2 y 3 del plan).

Uso: `uv run python identity-edge/tools/realm_lint.py <ruta>...`
Sale con 0 si todo es valido, con 1 si hay violaciones (una linea por violacion, con el
archivo y la regla) y con 2 si un archivo no se puede leer o su entorno no se reconoce.

Entradas:
- `realm.<env>.yaml` con `<env>` en {kind, staging, prod}: el realm, en la representacion de
  Keycloak que importa `keycloak-config-cli`. El entorno sale del nombre del archivo.
- `group-role-map.yaml`: `groups: {<grupo LDAP>: <rol>}` (BR-U2-15).

Los scopes validos salen del catalogo de U0 (`vectra_contracts.catalog`), no de una lista aqui.
"""

import json
import re
import sys
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from vectra_contracts.catalog import SCOPE_HOLDERS, Role, Scope

ENVIRONMENTS = ("kind", "staging", "prod")
NON_PROD = ("kind", "staging")

BUSINESS_ROLES = frozenset(r.value for r in Role)
OPERACION = "operacion"
REALM_ADMIN = "realm-admin"
# En Keycloak `realm-admin` es un rol de cliente de `realm-management`.
REALM_MANAGEMENT = "realm-management"
# Roles que no pueden salir de LDAP: `realm-admin` es solo de break-glass y del keycloak-config-cli.
LDAP_ROLES = BUSINESS_ROLES | {OPERACION}
# MFA obligatorio (TOTP como required action): BR-U2-03, `operacion` (domain-entities §1.1) y break-glass.
MFA_REQUIRED_ROLES = frozenset({Role.INGENIERO_RIESGO.value, Role.CRO.value, Role.CUMPLIMIENTO.value}) | {
    OPERACION,
    REALM_ADMIN,
}
TOTP_ACTION = "CONFIGURE_TOTP"
# Credencial OTP con la semilla por referencia (U02-T05, forma unica de domain-entities §3):
# `credentials: [{type: otp, secretData: '{"value":"$(env:SYNTH_<USUARIO>_TOTP_SEED)"}', credentialData: '{...,"secretEncoding":"BASE32"}'}]`.
# `secretData` y `credentialData` son String JSON (CredentialRepresentation de Keycloak); `<USUARIO>` es el nombre del
# usuario en mayusculas con `_` en vez de `-`. Cualquier otra forma es invalida.
OTP_CREDENTIAL = "otp"
OTP_SECRET_ENCODING = "BASE32"  # noqa: S105
BREAK_GLASS = "break-glass"
# Clientes de administracion de INF-U2-05a (enmienda del 2026-11-02): sus cuentas de servicio son las unicas
# con roles de `realm-management`. `keycloak-config-cli` escribe (`realm-admin`); `keycloak-reader` solo lee.
ADMIN_CLIENT_ROLES: Mapping[str, frozenset[str]] = {
    "keycloak-config-cli": frozenset({REALM_ADMIN}),
    "keycloak-reader": frozenset({"view-realm"}),
}

CATALOG_SCOPES = frozenset(s.value for s in Scope)
FORBIDDEN_ACCESS_CLAIMS = frozenset({"preferred_username", "email", "name"})



def _scopes_held_by(client: str) -> frozenset[str]:
    return frozenset(scope.value for scope, holders in SCOPE_HOLDERS.items() if client in holders)


# El unico titular de `governance:freeze` en el catalogo de U0 (revision del FD de U9, 2026-10-08).
(FREEZE_ONLY_CLIENT,) = SCOPE_HOLDERS[Scope.GOVERNANCE_FREEZE]
# Clientes con scopes exactos (Paso 2, NFR-U11-20, INF-U12-03): los que el catalogo les asigna.
EXACT_SCOPES = {client: _scopes_held_by(client) for client in ("verification-reader", "product-metrics")}
# Clientes que no existen en produccion.
NON_PROD_ONLY_CLIENTS = ("channel-simulator", "verification-reader")
CORE_SCOPE = Scope.CORE_READ_CREDIT.value
CORE_AUDIENCE = "core-banking-mock"

# domain-entities §6 y BR-U2-05, 06. Campos exactos de BR-U2-05: con `permanentLockout: true`,
# `maxTemporaryLockouts = 3` y `failureFactor = 5`, el 4.o bloqueo (fallo 20 en `maxDeltaTimeSeconds`,
# 12 h) es permanente; la espera crece `waitIncrementSeconds` por serie hasta `maxFailureWaitSeconds`.
REALM_PARAMETERS: Mapping[str, Any] = {
    "accessTokenLifespan": 300,
    "ssoSessionIdleTimeout": 1800,
    "ssoSessionMaxLifespan": 36000,
    "bruteForceProtected": True,
    "failureFactor": 5,
    "waitIncrementSeconds": 60,
    "maxFailureWaitSeconds": 900,
    "maxDeltaTimeSeconds": 43200,
    "permanentLockout": True,
    "maxTemporaryLockouts": 3,
}
# NFR-U2-24.
PASSWORD_MIN_LENGTH = 14
PASSWORD_MIN_HISTORY = 5
PASSWORD_HASH = "argon2"  # noqa: S105


@dataclass(frozen=True)
class Violation:
    rule: str
    where: str
    message: str

    def format(self, file: str) -> str:
        return f"{file}: [{self.rule}] {self.where}: {self.message}"


# --- utilidades de lectura tolerante ---------------------------------------------------------


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _str_list(value: Any) -> list[str]:
    return [x for x in _list(value) if isinstance(x, str)]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(realm: Mapping[str, Any], key: str, out: list[Violation]) -> Iterator[dict[str, Any]]:
    """Los elementos de `realm[key]`; un elemento que no es un mapa es una violacion."""
    value = realm.get(key, [])
    if not isinstance(value, list):
        out.append(Violation("estructura-invalida", key, "debe ser una lista"))
        return
    for i, item in enumerate(value):
        if isinstance(item, dict):
            yield item
        else:
            out.append(Violation("estructura-invalida", f"{key}[{i}]", "debe ser un mapa"))


# --- usuarios (BR-U2-01, 03; domain-entities §1.1, §3) ---------------------------------------


def _is_service_account(user: Mapping[str, Any], service_clients: frozenset[str]) -> bool:
    """Cuenta de servicio: el usuario cuyo `serviceAccountClientId` apunta a un cliente del mismo realm con
    `serviceAccountsEnabled: true`, y nada mas (ni el prefijo del nombre ni sus roles). CA-5."""
    target = user.get("serviceAccountClientId")
    return isinstance(target, str) and target in service_clients


def otp_seed_reference(username: str) -> str:
    return f"$(env:SYNTH_{username.upper().replace('-', '_')}_TOTP_SEED)"


def _json_object(raw: Any) -> dict[str, Any]:
    """El objeto de un String JSON; `{}` si no es un String, no es JSON o no es un objeto."""
    if not isinstance(raw, str):
        return {}
    try:
        return _dict(json.loads(raw))
    except ValueError:
        return {}


def _has_referenced_otp(user: Mapping[str, Any]) -> bool:
    """Alguna credencial `otp` con la forma unica: semilla `$(env:SYNTH_<USUARIO>_TOTP_SEED)` del propio usuario
    en `secretData` y `secretEncoding: BASE32` en `credentialData`. Se miran todas las credenciales."""
    username = user.get("username")
    if not isinstance(username, str):
        return False
    expected = otp_seed_reference(username)
    for credential in _list(user.get("credentials")):
        credential = _dict(credential)
        if credential.get("type") != OTP_CREDENTIAL:
            continue
        seed = _json_object(credential.get("secretData")).get("value")
        encoding = _json_object(credential.get("credentialData")).get("secretEncoding")
        if seed == expected and encoding == OTP_SECRET_ENCODING:
            return True
    return False


def _check_users(realm: Mapping[str, Any], env: str, out: list[Violation]) -> None:
    service_clients = frozenset(
        str(c.get("clientId"))
        for c in _list(realm.get("clients"))
        if isinstance(c, dict) and c.get("serviceAccountsEnabled") is True
    )
    for user in _items(realm, "users", out):
        name = str(user.get("username", "?"))
        where = f"usuario {name}"
        roles = _str_list(user.get("realmRoles"))
        if REALM_ADMIN in _str_list(_dict(user.get("clientRoles")).get(REALM_MANAGEMENT)):
            roles.append(REALM_ADMIN)
        service_account = _is_service_account(user, service_clients)
        if service_account:
            user_roles = sorted(set(_str_list(user.get("realmRoles"))) & (BUSINESS_ROLES | {OPERACION}))
            if user_roles:
                out.append(
                    Violation(
                        "cuenta-de-servicio-con-rol-de-usuario",
                        where,
                        f"la cuenta de servicio de `{user['serviceAccountClientId']}` no puede tener roles de usuario {user_roles} (domain-entities §2)",
                    )
                )
            management = set(_str_list(_dict(user.get("clientRoles")).get(REALM_MANAGEMENT)))
            if REALM_ADMIN in _str_list(user.get("realmRoles")):
                management.add(REALM_ADMIN)
            allowed = ADMIN_CLIENT_ROLES.get(str(user["serviceAccountClientId"]), frozenset())
            if management - allowed:
                out.append(
                    Violation(
                        "rol-de-administracion-no-permitido",
                        where,
                        f"la cuenta de servicio de `{user['serviceAccountClientId']}` no puede tener "
                        f"{sorted(management - allowed)} de `{REALM_MANAGEMENT}`; admitido: {sorted(allowed)} (INF-U2-05a)",
                    )
                )
        business = [r for r in roles if r in BUSINESS_ROLES]
        if len(business) > 1:
            out.append(
                Violation("un-rol-de-negocio", where, f"tiene {len(business)} roles de negocio {sorted(business)} (BR-U2-01)")
            )
        if OPERACION in roles and business:
            out.append(
                Violation("operacion-con-rol-de-negocio", where, f"`{OPERACION}` no puede ir con {sorted(business)}")
            )
        required = sorted(set(roles) & MFA_REQUIRED_ROLES)
        has_totp = TOTP_ACTION in _str_list(user.get("requiredActions")) or _has_referenced_otp(user)
        if required and not service_account and not has_totp:
            out.append(
                Violation(
                    "mfa-obligatorio",
                    where,
                    f"el rol {required} exige la required action {TOTP_ACTION} o una credencial `{OTP_CREDENTIAL}` "
                    f"con la forma de domain-entities §3 (BR-U2-03)",
                )
            )
        if env == "prod" and name != BREAK_GLASS and not service_account:
            out.append(
                Violation(
                    "usuario-local-en-prod",
                    where,
                    f"el realm de produccion solo admite el usuario local `{BREAK_GLASS}`; el resto sale de LDAP",
                )
            )


# --- clientes -------------------------------------------------------------------------------


def _client_scopes(client: Mapping[str, Any]) -> list[str]:
    return _str_list(client.get("defaultClientScopes")) + _str_list(client.get("optionalClientScopes"))


def _audiences(client: Mapping[str, Any]) -> set[str]:
    audiences: set[str] = set()
    for mapper in _list(client.get("protocolMappers")):
        config = _dict(_dict(mapper).get("config"))
        if _dict(mapper).get("protocolMapper") == "oidc-audience-mapper":
            for key in ("included.client.audience", "included.custom.audience"):
                if isinstance(config.get(key), str):
                    audiences.add(config[key])
    return audiences


def _check_scopes(client_id: str, scopes: Sequence[str], out: list[Violation]) -> None:
    where = f"cliente {client_id}"
    for scope in scopes:
        if scope == Scope.CORE_WRITE_CREDIT.value:
            out.append(Violation("core-write-credit-prohibido", where, f"ningun cliente puede tener `{scope}` (AUTONOMIA-03)"))
        elif scope not in CATALOG_SCOPES:
            out.append(Violation("scope-fuera-del-catalogo", where, f"`{scope}` no esta en el catalogo de scopes de U0"))
    if Scope.GOVERNANCE_FREEZE.value in scopes and client_id != FREEZE_ONLY_CLIENT:
        out.append(
            Violation(
                "governance-freeze-solo-en-el-job",
                where,
                f"`{Scope.GOVERNANCE_FREEZE.value}` solo puede tenerlo `{FREEZE_ONLY_CLIENT}`; {client_id} no",
            )
        )


def _has_wildcard(value: str) -> bool:
    return "*" in value


def _check_client(client: Mapping[str, Any], env: str, out: list[Violation]) -> None:
    client_id = str(client.get("clientId", "?"))
    where = f"cliente {client_id}"
    scopes = _client_scopes(client)
    _check_scopes(client_id, scopes, out)

    # Clientes que no existen en produccion y clientes con scopes exactos.
    if env == "prod" and client_id in NON_PROD_ONLY_CLIENTS:
        out.append(Violation("cliente-solo-no-productivo", where, f"`{client_id}` solo existe en kind y staging"))
    if client_id in EXACT_SCOPES:
        held = set(scopes)
        if held != EXACT_SCOPES[client_id]:
            out.append(
                Violation(
                    "scopes-exactos",
                    where,
                    f"debe tener exactamente {sorted(EXACT_SCOPES[client_id])}, tiene {sorted(held)}",
                )
            )
    if env == "prod" and client_id == "case-service":
        if CORE_SCOPE in scopes:
            out.append(Violation("case-service-core-en-prod", where, f"no puede tener `{CORE_SCOPE}` en produccion"))
        if CORE_AUDIENCE in _audiences(client):
            out.append(Violation("case-service-core-en-prod", where, f"no puede tener la audiencia `{CORE_AUDIENCE}` en produccion"))

    # Autenticacion (BR-U2-09): sin secretos compartidos; los de servicio con private_key_jwt.
    if client.get("serviceAccountsEnabled") is True:
        if "secret" in client:
            out.append(Violation("cliente-con-secreto", where, "un cliente de servicio no debe tener `secret` (BR-U2-09)"))
        if client.get("clientAuthenticatorType") != "client-jwt":
            out.append(Violation("servicio-sin-private-key-jwt", where, "un cliente de servicio usa `clientAuthenticatorType: client-jwt` (BR-U2-09)"))
    for field in ("defaultClientScopes", "optionalClientScopes"):
        if not isinstance(client.get(field), list):
            out.append(
                Violation(
                    "scopes-por-defecto-heredados",
                    where,
                    f"falta `{field}` explicito (puede ser []): Keycloak aplicaria los scopes por defecto del realm",
                )
            )

    # Redirect URIs exactas, sin comodines.
    uris = _str_list(client.get("redirectUris")) + _str_list(client.get("webOrigins"))
    post_logout = _dict(client.get("attributes")).get("post.logout.redirect.uris")
    if isinstance(post_logout, str):
        uris += [u for u in post_logout.split("##") if u]
    for uri in uris:
        if _has_wildcard(uri):
            out.append(Violation("redirect-uri-con-comodin", where, f"`{uri}` tiene comodin"))


# --- claims prohibidos en el access token (domain-entities §1.3) ---------------------------


def _forbidden_claim_mappers(owner: str, mappers: Iterable[Any], out: list[Violation]) -> None:
    for mapper in mappers:
        config = _dict(_dict(mapper).get("config"))
        claim = config.get("claim.name")
        emits = str(config.get("access.token.claim", "true")).lower() != "false"
        if claim in FORBIDDEN_ACCESS_CLAIMS and emits:
            out.append(
                Violation(
                    "claim-prohibido-en-access-token",
                    owner,
                    f"el mapper `{_dict(mapper).get('name', '?')}` emite `{claim}` en el access token",
                )
            )


def _check_claims(realm: Mapping[str, Any], out: list[Violation]) -> None:
    for definition in _items(realm, "clientScopes", out):
        _forbidden_claim_mappers(
            f"client scope {definition.get('name', '?')}", _list(definition.get("protocolMappers")), out
        )
    for client in _items(realm, "clients", []):
        client_id = str(client.get("clientId", "?"))
        _forbidden_claim_mappers(f"cliente {client_id}", _list(client.get("protocolMappers")), out)


# --- parametros del realm (domain-entities §6, NFR-U2-24) ----------------------------------


def _check_parameters(realm: Mapping[str, Any], out: list[Violation]) -> None:
    for key, expected in REALM_PARAMETERS.items():
        actual = realm.get(key)
        # `1 == True` en Python: comparar tambien el tipo para no aceptar `true` donde va un numero.
        if actual != expected or type(actual) is not type(expected):
            out.append(Violation("parametro-del-realm", f"realm {key}", f"debe ser {expected!r}, es {actual!r}"))


_TERM = re.compile(r"^\s*(\w+)(?:\((.*)\))?\s*$")


def _check_password_policy(realm: Mapping[str, Any], out: list[Violation]) -> None:
    policy = realm.get("passwordPolicy")
    where = "realm passwordPolicy"
    if not isinstance(policy, str):
        out.append(Violation("politica-de-contrasenas", where, "falta `passwordPolicy` (NFR-U2-24)"))
        return
    terms: dict[str, str | None] = {}
    for part in policy.split(" and "):
        match = _TERM.match(part)
        if match:
            terms[match.group(1)] = match.group(2)

    def number(name: str) -> int | None:
        raw = terms.get(name)
        return int(raw) if raw is not None and raw.strip().isdigit() else None

    problems = []
    length = number("length")
    if length is None or length < PASSWORD_MIN_LENGTH:
        problems.append(f"length >= {PASSWORD_MIN_LENGTH}")
    for flag in ("notUsername", "notEmail"):
        if flag not in terms:
            problems.append(flag)
    history = number("passwordHistory")
    if history is None or history < PASSWORD_MIN_HISTORY:
        problems.append(f"passwordHistory >= {PASSWORD_MIN_HISTORY}")
    if terms.get("hashAlgorithm") != PASSWORD_HASH:
        problems.append(f"hashAlgorithm({PASSWORD_HASH})")
    if "forceExpiredPasswordChange" in terms:
        problems.append("sin forceExpiredPasswordChange (sin vencimiento periodico)")
    if problems:
        out.append(Violation("politica-de-contrasenas", where, f"incumple NFR-U2-24: {', '.join(problems)}"))


# --- API ------------------------------------------------------------------------------------


def lint_realm(realm: Any, env: str) -> list[Violation]:
    """Las violaciones de un realm para `env` en {kind, staging, prod}."""
    if env not in ENVIRONMENTS:
        raise ValueError(f"entorno desconocido: {env!r}")
    if not isinstance(realm, dict):
        return [Violation("estructura-invalida", "realm", "el archivo debe ser un mapa")]
    out: list[Violation] = []
    _check_users(realm, env, out)
    for client in _items(realm, "clients", out):
        _check_client(client, env, out)
    _check_claims(realm, out)
    _check_parameters(realm, out)
    _check_password_policy(realm, out)
    return out


def lint_group_role_map(mapping: Any) -> list[Violation]:
    """Valida `group-role-map.yaml` (BR-U2-15): `groups: {<grupo>: <rol de negocio o operacion>}`."""
    where = "group-role-map"
    groups = mapping.get("groups") if isinstance(mapping, dict) else None
    if not isinstance(groups, dict) or not groups:
        return [Violation("group-role-map-invalido", where, "debe tener `groups` con al menos un grupo")]
    out = []
    for group, role in groups.items():
        if not isinstance(group, str) or not group.strip():
            out.append(Violation("group-role-map-invalido", where, f"grupo invalido: {group!r}"))
        elif role not in LDAP_ROLES:
            out.append(Violation("group-role-map-invalido", where, f"el grupo `{group}` mapea a `{role}`; admite {sorted(LDAP_ROLES)}"))
    return out


def resolve_ldap_role(groups: Iterable[str], group_role_map: Mapping[str, str]) -> str | None:
    """El rol que recibe un usuario LDAP segun la tabla (BR-U2-01, 15): el de su unico grupo mapeado, o ninguno.

    Con dos o mas grupos mapeados no recibe ningun rol. La tabla se valida con el mismo codigo que la CLI
    (`lint_group_role_map`); una tabla invalida lanza `ValueError`. Es el modelo de referencia de PBT-U2-02:
    el cumplimiento en Keycloak (`ROLE_CONFLICT`) queda fuera de esta tarea.
    """
    violations = lint_group_role_map({"groups": dict(group_role_map)})
    if violations:
        raise ValueError("; ".join(v.message for v in violations))
    mapped = {g for g in groups if g in group_role_map}
    if len(mapped) != 1:
        return None
    return group_role_map[next(iter(mapped))]


# --- CLI ------------------------------------------------------------------------------------

_REALM_FILE = re.compile(r"^realm\.(?P<env>[^.]+)\.ya?ml$")
GROUP_ROLE_MAP_FILE = "group-role-map.yaml"


def _lint_file(path: Path) -> list[Violation]:
    """Las violaciones de un archivo; `ValueError` si no se puede leer o no se reconoce."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"no se puede leer: {exc}") from exc
    if path.name == GROUP_ROLE_MAP_FILE:
        return lint_group_role_map(data)
    match = _REALM_FILE.match(path.name)
    if match is None or match["env"] not in ENVIRONMENTS:
        raise ValueError(
            f"no se reconoce el entorno por el nombre; se espera realm.<{'|'.join(ENVIRONMENTS)}>.yaml o {GROUP_ROLE_MAP_FILE}"
        )
    return lint_realm(data, match["env"])


def main(argv: Sequence[str]) -> int:
    if not argv:
        print("uso: realm_lint.py <realm.{kind,staging,prod}.yaml | group-role-map.yaml>...", file=sys.stderr)  # noqa: T201
        return 2
    failed, unreadable = False, False
    for arg in argv:
        try:
            violations = _lint_file(Path(arg))
        except ValueError as exc:
            print(f"{arg}: [archivo-no-valido] {exc}", file=sys.stderr)  # noqa: T201
            unreadable = True
            continue
        for violation in violations:
            print(violation.format(arg), file=sys.stderr)  # noqa: T201
        failed = failed or bool(violations)
    if unreadable:
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
