"""Normalizacion y comparacion del realm contra Git (U02-T08; BR-U2-12, P-U2-05, INF-U2-09, decision R2).

`realm-drift` compara por proyeccion sobre Git: solo cuentan los campos que fija `realm.<env>.yaml`, y lo que Keycloak
agrega por defecto no cuenta. Las entidades se emparejan por su clave. Una de Git que falta en Keycloak y una de Keycloak
que no esta en Git son, cada una, una diferencia. Un valor de Git con un marcador `$(env:...)` sale de la boveda y Git no
lo conoce, pero conserva el texto literal que lo rodea: el de Keycloak debe empezar con lo que hay antes del primer marcador
y terminar con lo que hay despues del ultimo (decision S3). En una lista, los elementos de Git con marcador no se buscan por
valor: cada uno absorbe un elemento de mas de Keycloak que conserve su texto literal (decision S2). Los roles de un usuario y
los composites de un rol se comparan como conjunto exacto: lo que Git no declara se lee como vacio.

Las clases de entidades y los campos de secreto, ID y timestamp son listas exactas (abajo); no hay expresiones regulares
sobre el texto. Una ruta es la tupla de claves desde la raiz: los elementos de una lista comparten la ruta de la lista,
y las claves de `components` y `clientScopeMappings` (tipo de proveedor, cliente de `realm-management`) se escriben `*`.
"""

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

Path = tuple[str, ...]
ENV_MARKER: Final = "$(env:"
KeyOf = str | tuple[str, ...]

# --- clases de entidades y su clave (INF-U2-09) -----------------------------------------------------
# Las primeras ocho son las del diseno. Los niveles de abajo (mappers, ejecuciones, ambitos) no tienen clave en el diseno;
# se emparejan por `name`, por `priority` y por el cliente o ambito. Ninguna clave se supone unica: una repetida cuenta.
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
    ("scopeMappings",): ("client", "clientScope"),
    ("clientScopeMappings", "*"): ("client", "clientScope"),
}
# Claves de diccionario que agrupan listas de entidades (el segundo nivel de la ruta es un comodin).
WILDCARD_PARENTS: Final = frozenset(
    {
        ("components",),
        ("clientScopeMappings",),
        ("users", "clientRoles"),
        ("roles", "realm", "composites", "client"),
    }
)
# Campos que Git no declara y se leen como vacios (INF-U2-09, decision S1: de un usuario se comparan sus roles; D-8: de
# un rol, sus composites). Asi, un rol que Keycloak agrega y Git no declara cuenta.
ABSENT_AS_EMPTY: Final[Mapping[Path, Mapping[str, Any]]] = {
    ("users",): {"realmRoles": [], "clientRoles": {}},
    ("roles", "realm"): {"composites": {}},
    ("roles", "realm", "composites"): {"realm": [], "client": {}},
}
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
# `userSetupAllowed` solo existe en la exportacion de flujos.
UNREADABLE_FIELDS: Final[Mapping[Path, frozenset[str]]] = {
    ("authenticationFlows", "authenticationExecutions"): frozenset({"userSetupAllowed"}),
}

# --- lo que no se compara (decision S1 del usuario) ---------------------------------------------------
# El propio login cambia las acciones requeridas y las credenciales de un usuario (el primer login de `break-glass`).
NOT_COMPARED_FIELDS: Final[Mapping[Path, frozenset[str]]] = {
    ("users",): frozenset({"requiredActions", "credentials"}),
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
            "UPDATE_EMAIL",
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
    # `DefaultAuthenticationFlows.java` de 26.8.1: los alias de los flujos y subflujos que crea. El flag `builtIn` de
    # la respuesta no cuenta: lo pone el lado que se audita.
    ("authenticationFlows",): frozenset(
        {
            "registration",
            "registration form",
            "reset credentials",
            "Reset - Conditional OTP",
            "direct grant",
            "Direct Grant - Conditional OTP",
            "browser",
            "forms",
            "Browser - Conditional 2FA",
            "Browser - Conditional Organization",
            "Organization",
            "clients",
            "first broker login",
            "User creation or linking",
            "Handle Existing Account",
            "Account verification options",
            "Verify Existing Account by Re-authentication",
            "First broker login - Conditional 2FA",
            "First Broker Login - Conditional Organization",
            "saml ecp",
            "docker auth",
        }
    ),  # fmt: skip
}

# Entradas de un nivel anidado que Keycloak 26.8.1 crea en un realm nuevo, por ubicacion (como en `Difference.path`).
# Solo la entrada exacta es la de Keycloak: con otros roles o en otro contenedor, cuenta.
DEFAULT_ENTITIES: Final[Mapping[str, tuple[Mapping[str, Any], ...]]] = {
    # DefaultClientScopes.createOfflineAccessClientScope
    "scopeMappings": ({"clientScope": "offline_access", "roles": ["offline_access"]},),
    # RealmManager: `account-console` recibe `manage-account` y `view-groups` de `account`
    "clientScopeMappings.account": (
        {"client": "account-console", "roles": ["manage-account", "view-groups"]},
    ),
}

# Elementos de una lista de valores que Keycloak agrega por su cuenta y no cuentan como «de mas».
DEFAULT_LIST_ELEMENTS: Final[Mapping[Path, frozenset[str]]] = {
    # Los roles que Keycloak da a todo usuario: la misma lista que la de roles propios (una sola fuente).
    ("users", "realmRoles"): BUILT_IN_NAMES[("roles", "realm")],
}
# Lo mismo, pero solo en un cliente con `serviceAccountsEnabled`: ClientManager.enableServiceAccount agrega el scope
# `service_account` a los clientes con cuenta de servicio.
SERVICE_ACCOUNT_LIST_ELEMENTS: Final[Mapping[Path, frozenset[str]]] = {
    ("clients", "defaultClientScopes"): frozenset({"service_account"}),
}
# Los composites que Keycloak 26.8.1 da a sus roles de realm: `default-roles-<realm>` lleva `offline_access` y
# `uma_authorization` (KeycloakModelUtils.setupOfflineRole y setupAuthorizationServices) y los roles `view-profile` y
# `manage-account` del cliente `account` (RealmManager, `AccountRoles.DEFAULT`). Los otros dos no tienen composites.
BUILT_IN_ROLE_COMPOSITES: Final[Mapping[str, Mapping[str, Any]]] = {
    "default-roles-vectra": {
        "realm": ["offline_access", "uma_authorization"],
        "client": {"account": ["manage-account", "view-profile"]},
    },
    "offline_access": {},
    "uma_authorization": {},
}

DifferenceKind = Literal[
    "value",
    "missing-in-keycloak",
    "unexpected-in-keycloak",
    "duplicate-key-in-git",
    "duplicate-key-in-keycloak",
]


@dataclass(frozen=True)
class Difference:
    path: str
    kind: DifferenceKind
    git: Any = None
    keycloak: Any = None


DUPLICATE: Final[Mapping[str, DifferenceKind]] = {
    "git": "duplicate-key-in-git",
    "keycloak": "duplicate-key-in-keycloak",
}


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


def _literals(text: str) -> tuple[str, str]:
    """El texto antes del primer marcador y el posterior al ultimo (decision S3)."""
    first = text.index(ENV_MARKER)
    last = text.rindex(ENV_MARKER)
    return text[:first], text[text.index(")", last) + 1 :]


def _keeps_literals(git_text: str, value: Any) -> bool:
    """El valor de Keycloak es una cadena que empieza y termina con el literal de Git, sin solaparse."""
    if not isinstance(value, str):
        return False
    prefix, suffix = _literals(git_text)
    return len(value) >= len(prefix) + len(suffix) and value.startswith(prefix) and value.endswith(suffix)


def _is_built_in(path: Path, trail: str, entity: Mapping[str, Any]) -> bool:
    if path == ("authenticationFlows",):
        # Lista exacta de alias Y el flag: el flag solo no basta (lo pone el lado auditado), y la lista sola tampoco.
        return entity.get("builtIn") is True and _key_of(path, entity) in BUILT_IN_NAMES[path]
    if _key_of(path, entity) in BUILT_IN_NAMES.get(path, frozenset()):
        return True
    return any(_normalize(d, path) == entity for d in DEFAULT_ENTITIES.get(trail, ()))


def _where(path: Path, trail: str) -> str:
    return trail or ".".join(path) or "<realm>"


def _join(trail: str, key: str) -> str:
    return f"{trail}.{key}" if trail else key


def _exempt(path: Path, owner: Mapping[str, Any]) -> frozenset[str]:
    found = DEFAULT_LIST_ELEMENTS.get(path, frozenset())
    if owner.get("serviceAccountsEnabled") is True:
        found = found | SERVICE_ACCOUNT_LIST_ELEMENTS.get(path, frozenset())
    return found


def _compare(
    git: Any, kc: Any, path: Path, trail: str, out: list[Difference], exempt: frozenset[str] = frozenset()
) -> None:
    if isinstance(git, dict):
        if kc is None and not git:
            return
        if not isinstance(kc, dict):
            out.append(Difference(_where(path, trail), "value", git, kc))
            return
        skipped = UNREADABLE_FIELDS.get(path, frozenset()) | NOT_COMPARED_FIELDS.get(path, frozenset())
        fields = {**copy_empty(ABSENT_AS_EMPTY.get(path, {})), **git}
        for key, value in fields.items():
            if key in skipped:
                continue
            child = child_path(path, key)
            _compare(value, kc.get(key), child, _join(trail, key), out, _exempt(child, kc))
        if path in WILDCARD_PARENTS:  # un contenedor que Keycloak tiene y Git no: sus entradas sobran
            for key in kc.keys() - fields.keys():
                child = child_path(path, key)
                if child in ENTITY_KEYS:
                    _compare_entities([], kc[key], child, _join(trail, key), out)
                else:
                    _compare_values([], kc[key], child, _join(trail, key), out, frozenset())
        return
    if isinstance(git, list) and path in ENTITY_KEYS:
        _compare_entities(git, kc, path, trail, out)
    elif isinstance(git, list):
        _compare_values(git, kc if kc is not None or git else [], path, trail, out, exempt)
    elif isinstance(git, str) and ENV_MARKER in git:
        if not _keeps_literals(git, kc):
            out.append(Difference(_where(path, trail), "value", git, kc))
    elif git != kc:
        out.append(Difference(_where(path, trail), "value", git, kc))


def copy_empty(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {k: type(v)() for k, v in fields.items()}


def _compare_values(
    git: list[Any], kc: Any, path: Path, trail: str, out: list[Difference], exempt: frozenset[str]
) -> None:
    """Lista de valores (S2 y S3): los elementos de Git sin marcador se buscan por valor y los que faltan cuentan; cada
    elemento de Keycloak que sobra cuenta, salvo los que Keycloak agrega solo y uno por cada elemento de Git con
    marcador que conserve su texto literal."""
    where = _where(path, trail)
    if not isinstance(kc, list):
        out.append(Difference(where, "value", git, kc))
        return
    patterns = [e for e in git if _has_marker(e)]
    remaining = Counter(_canonical(e) for e in kc)
    for element in (e for e in git if not _has_marker(e)):
        if remaining[_canonical(element)] > 0:
            remaining[_canonical(element)] -= 1
        else:
            out.append(Difference(f"{where}[{_canonical(element)}]", "missing-in-keycloak", element, None))
    extras: list[Any] = []
    leftover = Counter(remaining)
    for element in kc:
        key = _canonical(element)
        if leftover[key] > 0:
            leftover[key] -= 1
            if element not in exempt:
                extras.append(element)
    for element in _unplaced(patterns, extras):
        out.append(Difference(f"{where}[{_canonical(element)}]", "unexpected-in-keycloak", None, element))


def _unplaced(patterns: list[Any], extras: list[Any]) -> list[Any]:
    """Los elementos de `extras` que quedan sin pareja en un emparejamiento maximo con los marcadores de Git."""
    matched: dict[int, int] = {}

    def fits(pattern: Any, element: Any) -> bool:
        return _keeps_literals(pattern, element) if isinstance(pattern, str) else True

    def place(index: int, seen: set[int]) -> bool:
        for slot, pattern in enumerate(patterns):
            if slot in seen or not fits(pattern, extras[index]):
                continue
            seen.add(slot)
            if slot not in matched or place(matched[slot], seen):
                matched[slot] = index
                return True
        return False

    for index in range(len(extras)):
        place(index, set())
    placed = set(matched.values())
    return [e for i, e in enumerate(extras) if i not in placed]


def _compare_entities(git: list[Any], kc: Any, path: Path, trail: str, out: list[Difference]) -> None:
    if not isinstance(kc, list):
        out.append(Difference(_where(path, trail), "value", git, kc))
        return
    git_by_key = _index(git, path, trail, "git", out)
    kc_by_key = _index(kc, path, trail, "keycloak", out)
    for key, entity in git_by_key.items():
        where = f"{trail}[{key}]"
        if key not in kc_by_key:
            out.append(Difference(where, "missing-in-keycloak", entity, None))
        else:
            _compare(entity, kc_by_key[key], path, where, out)
    if path in UNLISTED:
        return
    for key, entity in kc_by_key.items():
        if key in git_by_key:
            continue
        if not _is_built_in(path, trail, entity):
            out.append(Difference(f"{trail}[{key}]", "unexpected-in-keycloak", None, entity))
        elif path == ("roles", "realm") and key in BUILT_IN_ROLE_COMPOSITES:
            # Un rol propio de Keycloak solo se compara en sus composites, contra los de 26.8.1.
            baseline = {"name": key, "composites": BUILT_IN_ROLE_COMPOSITES[key]}
            _compare(_normalize(baseline, path), entity, path, f"{trail}[{key}]", out)


def _index(entities: list[Any], path: Path, trail: str, side: str, out: list[Difference]) -> dict[Any, Any]:
    """Las entidades por clave. Una clave repetida (en cualquiera de los dos lados) es una diferencia por cada repeticion."""
    found: dict[Any, Any] = {}
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        key = _key_of(path, entity)
        if key in found:
            out.append(Difference(f"{trail}[{key}]", DUPLICATE[side], None, entity))
        else:
            found[key] = entity
    return found


def diff(git: Mapping[str, Any], keycloak: Mapping[str, Any]) -> list[Difference]:
    """Las diferencias de `keycloak` respecto de la proyeccion del realm de Git."""
    out: list[Difference] = []
    _compare(normalize(git), normalize(keycloak), (), "", out)
    return out


def drift_count(git: Mapping[str, Any], keycloak: Mapping[str, Any]) -> int:
    """El valor de `vectra_realm_drift`."""
    return len(diff(git, keycloak))
