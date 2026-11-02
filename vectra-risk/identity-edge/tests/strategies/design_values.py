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
