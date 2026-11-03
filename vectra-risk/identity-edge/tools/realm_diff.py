"""Normalizacion y comparacion del realm contra Git (U02-T08; BR-U2-12, P-U2-05, INF-U2-09, decision R2).

`realm-drift` compara por proyeccion sobre Git: solo cuentan los campos que fija `realm.<env>.yaml`, y lo que Keycloak
agrega por defecto no cuenta. Las entidades se emparejan por su clave. Una de Git que falta en Keycloak y una de Keycloak
que no esta en Git son, cada una, una diferencia. Un campo de Git con un marcador `$(env:...)` se excluye: su valor sale
de la boveda y Git no lo conoce.

Las clases de entidades y los campos de secreto, ID y timestamp son listas exactas (abajo); no hay expresiones regulares
sobre el texto. Una ruta es la tupla de claves desde la raiz: los elementos de una lista comparten la ruta de la lista,
y las claves de `components` y `clientScopeMappings` (tipo de proveedor, cliente de `realm-management`) se escriben `*`.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

Path = tuple[str, ...]
ENV_MARKER: Final = "$(env:"
KeyOf = str | tuple[str, ...]

# --- clases de entidades y su clave (INF-U2-09) -----------------------------------------------------
# Las primeras ocho son las del diseno. Los niveles de abajo (mappers, ejecuciones, credenciales, ambitos) no tienen
# clave en el diseno; se emparejan por `name`, `priority` (unica en un flujo), `type` y por el cliente o ambito.
ENTITY_KEYS: Final[Mapping[Path, KeyOf]] = {
    ("clients",): "clientId",
    ("clientScopes",): "name",
    ("roles", "realm"): "name",
    ("components", "*"): "name",
    ("authenticationFlows",): "alias",
    ("requiredActions",): "alias",
    ("authenticatorConfig",): "alias",
    ("users",): "username",
    ("clients", "protocolMappers"): "name",
    ("clientScopes", "protocolMappers"): "name",
    ("authenticationFlows", "authenticationExecutions"): "priority",
    ("users", "credentials"): "type",
    ("scopeMappings",): ("client", "clientScope"),
    ("clientScopeMappings", "*"): ("client", "clientScope"),
}
# Claves de diccionario que agrupan listas de entidades (el segundo nivel de la ruta es un comodin).
WILDCARD_PARENTS: Final = frozenset({("components",), ("clientScopeMappings",)})
# Clases cuyas entidades de Keycloak no se listan: los usuarios se leen uno a uno por su `username` de Git.
UNLISTED: Final = frozenset({("users",)})

# --- lo que se quita al normalizar ------------------------------------------------------------------
SECRET_FIELDS: Final[Mapping[Path, frozenset[str]]] = {
    ("clients",): frozenset({"secret", "registrationAccessToken"}),
    ("users", "credentials"): frozenset({"value", "secretData", "credentialData"}),
    ("components", "*", "config"): frozenset({"bindCredential"}),
    ("smtpServer",): frozenset({"password"}),
}
ID_FIELDS: Final[Mapping[Path, frozenset[str]]] = {
    (): frozenset({"id"}),
    ("clients",): frozenset({"id"}),
    ("clients", "protocolMappers"): frozenset({"id"}),
    ("clientScopes",): frozenset({"id"}),
    ("clientScopes", "protocolMappers"): frozenset({"id"}),
    ("roles", "realm"): frozenset({"id", "containerId"}),
    ("components", "*"): frozenset({"id", "parentId"}),
    ("authenticationFlows",): frozenset({"id"}),
    ("authenticationFlows", "authenticationExecutions"): frozenset({"id", "flowId"}),
    ("authenticatorConfig",): frozenset({"id"}),
    ("users",): frozenset({"id"}),
    ("users", "credentials"): frozenset({"id"}),
}
TIMESTAMP_FIELDS: Final[Mapping[Path, frozenset[str]]] = {
    (): frozenset({"notBefore"}),
    ("clients",): frozenset({"notBefore"}),
    ("users",): frozenset({"createdTimestamp", "notBefore"}),
    ("users", "credentials"): frozenset({"createdDate"}),
}

# --- lo que el Admin API no devuelve (se lee a mano en keycloak_admin.py o no se lee) ---------------
# `userSetupAllowed` solo existe en la exportacion de flujos; `temporary` solo se envia al crear una credencial.
UNREADABLE_FIELDS: Final[Mapping[Path, frozenset[str]]] = {
    ("authenticationFlows", "authenticationExecutions"): frozenset({"userSetupAllowed"}),
    ("users", "credentials"): frozenset({"temporary"}),
}

# --- lo que Keycloak trae sin que Git lo declare (Keycloak 26.8.1) ----------------------------------
# Solo cuenta como «sobra» lo que no esta aqui. Si Git declara una de estas, se compara como cualquier otra.
BUILT_IN_NAMES: Final[Mapping[Path, frozenset[str]]] = {
    ("clients",): frozenset(
        {"account", "account-console", "admin-cli", "broker", "realm-management", "security-admin-console"}
    ),
    ("clientScopes",): frozenset(
        {
            "acr",
            "address",
            "basic",
            "email",
            "microprofile-jwt",
            "offline_access",
            "organization",
            "phone",
            "profile",
            "role_list",
            "roles",
            "saml_organization",
            "service_account",
            "web-origins",
        }
    ),
    ("roles", "realm"): frozenset({"default-roles-vectra", "offline_access", "uma_authorization"}),
    ("requiredActions",): frozenset(
        {
            "CONFIGURE_RECOVERY_AUTHN_CODES",
            "CONFIGURE_TOTP",
            "TERMS_AND_CONDITIONS",
            "UPDATE_PASSWORD",
            "UPDATE_PROFILE",
            "VERIFY_EMAIL",
            "VERIFY_PROFILE",
            "delete_account",
            "delete_credential",
            "idp_link",
            "update_user_locale",
            "webauthn-register",
            "webauthn-register-passwordless",
        }
    ),
}

DifferenceKind = Literal["value", "missing-in-keycloak", "unexpected-in-keycloak"]


@dataclass(frozen=True)
class Difference:
    path: str
    kind: DifferenceKind
    git: Any = None
    keycloak: Any = None


def child_path(path: Path, key: str) -> Path:
    """La ruta de la clave `key` de un diccionario que esta en `path`."""
    return (*path, "*") if path in WILDCARD_PARENTS else (*path, key)


def _lookup(table: Mapping[Path, Any], path: Path) -> Any:
    return table.get(path)


def _key_of(path: Path, entity: Mapping[str, Any]) -> Any:
    names = ENTITY_KEYS[path]
    for name in (names,) if isinstance(names, str) else names:
        if name in entity:
            return entity[name]
    return None


# --- normalizacion ----------------------------------------------------------------------------------


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _sort_key(value: Any) -> tuple[int, str]:
    # Numeros antes que texto, para que la clave `priority` ordene 2 antes de 10.
    if isinstance(value, bool) or not isinstance(value, int | float):
        return (1, _canonical(value))
    return (0, f"{value:020.6f}")


def _normalize(node: Any, path: Path) -> Any:
    if isinstance(node, Mapping):
        dropped = (
            SECRET_FIELDS.get(path, frozenset())
            | ID_FIELDS.get(path, frozenset())
            | TIMESTAMP_FIELDS.get(path, frozenset())
        )
        return {
            key: _normalize(node[key], child_path(path, key))
            for key in sorted(node, key=str)
            if key not in dropped
        }
    if isinstance(node, Sequence) and not isinstance(node, str | bytes):
        items = [_normalize(item, path) for item in node]
        if path in ENTITY_KEYS and all(isinstance(item, dict) for item in items):
            return sorted(items, key=lambda item: _sort_key(_key_of(path, item)))
        return sorted(items, key=lambda item: _sort_key(item))
    return node


def normalize(realm: Mapping[str, Any]) -> dict[str, Any]:
    """El realm sin secretos, IDs internos ni timestamps, con las listas en un orden canonico. Idempotente."""
    return dict(_normalize(realm, ()))


# --- comparacion ------------------------------------------------------------------------------------


def _has_marker(value: Any) -> bool:
    if isinstance(value, str):
        return ENV_MARKER in value
    if isinstance(value, Mapping):
        return any(_has_marker(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_marker(v) for v in value)
    return False


def _is_built_in(path: Path, entity: Mapping[str, Any]) -> bool:
    if path == ("authenticationFlows",):
        return entity.get("builtIn") is True
    return _key_of(path, entity) in BUILT_IN_NAMES.get(path, frozenset())


def _where(path: Path, trail: str) -> str:
    return trail or ".".join(path) or "<realm>"


def _compare(git: Any, kc: Any, path: Path, trail: str, out: list[Difference]) -> None:
    if isinstance(git, dict):
        if not isinstance(kc, dict):
            out.append(Difference(_where(path, trail), "value", git, kc))
            return
        unreadable = UNREADABLE_FIELDS.get(path, frozenset())
        for key, value in git.items():
            if key in unreadable or _projects_out(value, child_path(path, key)):
                continue
            _compare(value, kc.get(key), child_path(path, key), f"{trail}.{key}" if trail else key, out)
        return
    if isinstance(git, list) and path in ENTITY_KEYS:
        _compare_entities(git, kc, path, trail, out)
        return
    if git != kc:
        out.append(Difference(_where(path, trail), "value", git, kc))


def _projects_out(value: Any, path: Path) -> bool:
    """El campo de Git no se compara: su valor sale de la boveda (`$(env:...)`)."""
    if isinstance(value, dict) or (isinstance(value, list) and path in ENTITY_KEYS):
        return False  # se recorre; el marcador excluye el campo que lo contiene
    return _has_marker(value)


def _compare_entities(git: list[Any], kc: Any, path: Path, trail: str, out: list[Difference]) -> None:
    if not isinstance(kc, list):
        out.append(Difference(_where(path, trail), "value", git, kc))
        return
    kc_by_key = {_key_of(path, e): e for e in kc if isinstance(e, dict)}
    git_keys = set()
    for entity in git:
        key = _key_of(path, entity)
        git_keys.add(key)
        where = f"{trail}[{key}]"
        if key not in kc_by_key:
            out.append(Difference(where, "missing-in-keycloak", entity, None))
        else:
            _compare(entity, kc_by_key[key], path, where, out)
    if path in UNLISTED:
        return
    for key, entity in kc_by_key.items():
        if key not in git_keys and not _is_built_in(path, entity):
            out.append(Difference(f"{trail}[{key}]", "unexpected-in-keycloak", None, entity))


def diff(git: Mapping[str, Any], keycloak: Mapping[str, Any]) -> list[Difference]:
    """Las diferencias de `keycloak` respecto de la proyeccion del realm de Git."""
    out: list[Difference] = []
    _compare(normalize(git), normalize(keycloak), (), "", out)
    return out


def drift_count(git: Mapping[str, Any], keycloak: Mapping[str, Any]) -> int:
    """El valor de `vectra_realm_drift`."""
    return len(diff(git, keycloak))
