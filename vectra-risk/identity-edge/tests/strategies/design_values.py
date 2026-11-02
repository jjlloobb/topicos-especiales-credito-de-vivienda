"""Valores del diseno de U2 leidos de los documentos, para comparar los realms contra ellos.

Nada de esto es una lista a mano: sale de `domain-entities.md`, `business-rules.md` e
`infrastructure-design.md` (§2.1, §2.2, §3 y §1.3 de domain-entities; BR-U2-05; INF-U2-01).
"""

import re
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_FD = _ROOT / "aidlc-docs" / "construction" / "identity-edge"
DOMAIN_ENTITIES = (_FD / "functional-design" / "domain-entities.md").read_text(encoding="utf-8")
BUSINESS_RULES = (_FD / "functional-design" / "business-rules.md").read_text(encoding="utf-8")
INFRASTRUCTURE = (_FD / "infrastructure-design" / "infrastructure-design.md").read_text(encoding="utf-8")

NON_PROD_MARK = re.compile(r"solo\W+kind y staging", re.IGNORECASE)  # tolera `**solo**`


def section(text: str, heading: str) -> str:
    """El texto desde `heading` hasta el siguiente encabezado del mismo nivel o superior."""
    level = len(heading) - len(heading.lstrip("#"))
    start = text.index(heading)
    rest = text[start + len(heading) :]
    end = re.search(rf"^#{{1,{level}}} ", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if line.startswith("|") and not re.match(r"^\|[\s\-|]+\|?$", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def _split_top_level(cell: str) -> list[str]:
    parts, depth, current = [], 0, ""
    for ch in cell:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return [p.strip() for p in parts if p.strip()]


@dataclass(frozen=True)
class Item:
    name: str
    non_prod_only: bool = False


def _items(cell: str) -> list[Item]:
    items = []
    for part in _split_top_level(cell):
        found = re.match(r"`([^`]+)`", part)
        if found:
            items.append(Item(found.group(1), bool(NON_PROD_MARK.search(part))))
    return items


@dataclass(frozen=True)
class ServiceClient:
    client_id: str
    scopes: list[Item]
    audiences: list[Item]
    non_prod_only: bool


def service_clients() -> list[ServiceClient]:
    """Las filas de domain-entities §2.2."""
    body = section(DOMAIN_ENTITIES, "### 2.2 Identidades de servicio (client credentials, `private_key_jwt`)")
    clients = []
    for client_cell, scope_cell, audience_cell in (r[:3] for r in table_rows(body) if len(r) >= 3):
        found = re.match(r"`([a-z-]+)`", client_cell)
        if not found:
            continue
        non_prod = bool(NON_PROD_MARK.search(client_cell)) or "no son de producción" in audience_cell
        clients.append(ServiceClient(found.group(1), _items(scope_cell), _items(audience_cell), non_prod))
    return clients


def user_audiences() -> list[str]:
    """La fila `aud` de domain-entities §1.3."""
    for row in table_rows(section(DOMAIN_ENTITIES, "### 1.3 Claims del token de usuario")):
        if row[0] == "`aud`":
            return re.findall(r"`([^`]+)`", row[1])
    raise LookupError("domain-entities §1.3 sin la fila `aud`")


def user_client_ids() -> list[str]:
    body = section(DOMAIN_ENTITIES, "### 2.1 Clientes de usuario")
    return [m.group(1) for row in table_rows(body) if (m := re.match(r"`([a-z-]+)`", row[0]))]


def hostnames() -> dict[str, str]:
    """INF-U2-01: el hostname publico por entorno."""
    body = section(INFRASTRUCTURE, "### INF-U2-01")
    return {row[0]: row[1].strip("`") for row in table_rows(body) if row[0] in ("kind", "staging", "prod")}


def synthetic_usernames() -> list[str]:
    """domain-entities §3 (fila kind / staging) y §1.1 (`operacion-1` y `operacion-2`)."""
    for row in table_rows(section(DOMAIN_ENTITIES, "## 3. Usuarios por entorno (Q11)")):
        if row[0].startswith("kind"):
            names = re.findall(r"`([a-z]+-\d)`", row[2])
            break
    else:
        raise LookupError("domain-entities §3 sin la fila kind / staging")
    names += re.findall(r"`(operacion-\d)`", section(DOMAIN_ENTITIES, "### 1.1 Roles de negocio (realm roles)"))
    return names


def brute_force_fields() -> dict[str, object]:
    """Los campos de Keycloak de BR-U2-05 (`clave: valor`)."""
    line = next(ln for ln in BUSINESS_RULES.splitlines() if ln.startswith("Campos de Keycloak:"))
    fields: dict[str, object] = {}
    for key, value in re.findall(r"`(\w+): (\w+)`", line):
        fields[key] = {"true": True, "false": False}.get(value, int(value) if value.isdigit() else value)
    return fields


# --- agregados de la ronda 2: todo sale del diseno enmendado --------------------------------

PUBLIC_HOSTNAME = "$(env:PUBLIC_HOSTNAME)"  # INF-U2-01 (enmienda D3): el realm no repite los hostnames


def public_hostname_contract() -> bool:
    return PUBLIC_HOSTNAME in INFRASTRUCTURE


def _seconds(text: str) -> int:
    return int(re.sub(r"\D", "", text))


def token_and_session_parameters() -> dict[str, int]:
    """domain-entities §6 (vidas de BR-U2-06) con el nombre del campo de Keycloak."""
    out: dict[str, int] = {}
    for row in table_rows(section(DOMAIN_ENTITIES, "## 6. Parámetros versionados")):
        if row[0] == "Access token":
            out["accessTokenLifespan"] = _seconds(row[1])
        elif row[0] == "SSO idle / max":
            idle, maximum = row[1].split("/")
            out["ssoSessionIdleTimeout"] = _seconds(idle)
            out["ssoSessionMaxLifespan"] = _seconds(maximum)
    return out


def mfa_max_age() -> int:
    for row in table_rows(section(DOMAIN_ENTITIES, "## 6. Parámetros versionados")):
        if row[0] == "`mfa_max_age`":
            return _seconds(row[1])
    raise LookupError("domain-entities §6 sin `mfa_max_age`")


def loa_map() -> dict[str, int]:
    found = re.search(r"Mapeo de LoA de Keycloak: `(\w+)` = (\d), `(\w+)` = (\d)", DOMAIN_ENTITIES)
    assert found is not None
    return {found.group(1): int(found.group(2)), found.group(3): int(found.group(4))}


def mfa_required_roles() -> set[str]:
    """Roles con MFA obligatorio: la columna MFA de §1.1 y `operacion` (su parrafo dice «MFA obligatorio»)."""
    roles = {
        row[0].strip("`")
        for row in table_rows(section(DOMAIN_ENTITIES, "### 1.1 Roles de negocio (realm roles)"))
        if "Obligatorio" in row[1]
    }
    paragraph = section(DOMAIN_ENTITIES, "### 1.1 Roles de negocio (realm roles)")
    start = paragraph.index("**`operacion`**")
    if "MFA obligatorio" in paragraph[start : start + 400]:
        roles.add("operacion")
    return roles


def optional_mfa_roles() -> set[str]:
    return {
        row[0].strip("`")
        for row in table_rows(section(DOMAIN_ENTITIES, "### 1.1 Roles de negocio (realm roles)"))
        if row[0].startswith("`") and "Obligatorio" not in row[1] and "Disponible" in row[1]
    }


def users_per_role() -> int:
    found = re.search(r"(\d+) usuarios sintéticos por rol", DOMAIN_ENTITIES)
    assert found is not None
    return int(found.group(1))


def _client_row(client_id: str) -> list[str]:
    body = section(DOMAIN_ENTITIES, "### 2.1 Clientes de usuario")
    return next(r for r in table_rows(body) if r[0] == f"`{client_id}`")


def console_uris() -> dict[str, list[str]]:
    """Redirect URIs, post-logout y origenes de `vectra-console` (§2.1 y rutas de §4), con `<host>`."""
    notes = _client_row("vectra-console")[4]
    spa = section(DOMAIN_ENTITIES, "## 4. Rutas del gateway (Envoy Gateway)")
    login = re.search(r"`(/callback)` del login", spa)
    step_up = re.search(r"`(/stepup-callback)`", notes)
    post_logout = re.search(r"exactas: `(https://<host>/)`", notes)
    assert login and step_up and post_logout
    host = PUBLIC_HOSTNAME
    return {
        "redirectUris": [f"https://{host}{login.group(1)}", f"https://{host}{step_up.group(1)}"],
        "post_logout": [post_logout.group(1).replace("<host>", host)],
        "webOrigins": [f"https://{host}"],
    }


def promotion_tool() -> dict[str, object]:
    row = _client_row("promotion-tool")
    loopback = re.search(r"`(http://127\.0\.0\.1):\{puerto\}`", row[2])
    audience = re.search(r"aud = ([\w-]+)`?", row[3].replace("`", ""))
    scope = re.search(r"scope opcional `([^`]+)`, asignable solo al rol `([^`]+)`", row[3])
    assert loopback and audience and scope
    return {
        "redirectUris": [loopback.group(1)],
        "audience": audience.group(1),
        "scope": scope.group(1),
        "role": scope.group(2),
    }


def grafana_callback() -> str:
    for row in table_rows(section(DOMAIN_ENTITIES, "## 4. Rutas del gateway (Envoy Gateway)")):
        if row[0] == "`/grafana/**`":
            found = re.search(r"callback `(https://<host>[^`]+)`", row[3])
            assert found
            return found.group(1).replace("<host>", PUBLIC_HOSTNAME)
    raise LookupError("domain-entities §4 sin `/grafana/**`")


def loa_max_age() -> int:
    """domain-entities §6: validez del nivel de autenticacion dentro de la sesion SSO."""
    for row in table_rows(section(DOMAIN_ENTITIES, "## 6. Parámetros versionados")):
        if row[0].startswith("`loa-max-age`"):
            return _seconds(row[1])
    raise LookupError("domain-entities §6 sin `loa-max-age`")


def domain_audience() -> dict[str, str]:
    """domain-entities §2.2: tabla prefijo del scope -> audiencia."""
    body = section(DOMAIN_ENTITIES, "### 2.2 Identidades de servicio (client credentials, `private_key_jwt`)")
    out = {
        row[0].strip("`").rstrip(":"): row[1].strip("`")
        for row in table_rows(body)
        if re.fullmatch(r"`[a-z]+:`", row[0])
    }
    assert out, "domain-entities §2.2 sin la tabla prefijo -> audiencia"
    return out


def scope_audience(scope: str) -> str:
    return domain_audience()[scope.split(":")[0]]
