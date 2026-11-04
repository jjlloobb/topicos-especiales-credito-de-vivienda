"""Valores del diseno de las rutas del gateway (U02-T09, Paso 7), leidos de los documentos.

Nada de esto es una lista a mano: sale de domain-entities §4 y §4.1, business-rules (BR-U2-08, 10),
nfr-design-patterns (P-U2-02, P-U2-06) e infrastructure-design (INF-U2-01, INF-U2-10).
"""

import re
from dataclasses import dataclass
from pathlib import Path

from design_values import DOMAIN_ENTITIES, INFRASTRUCTURE, section, table_rows

_FD = Path(__file__).resolve().parents[3] / "aidlc-docs" / "construction" / "identity-edge"
BUSINESS_RULES = (_FD / "functional-design" / "business-rules.md").read_text(encoding="utf-8")
NFR_PATTERNS = (_FD / "nfr-design" / "nfr-design-patterns.md").read_text(encoding="utf-8")

ENVS = ("kind", "staging", "prod")
_ROUTES_SECTION = section(DOMAIN_ENTITIES, "## 4. Rutas del gateway (Envoy Gateway)")
_PROFILES_SECTION = section(DOMAIN_ENTITIES, "### 4.1 Perfiles de cabeceras (Q9)")
_INF_10 = section(INFRASTRUCTURE, "### INF-U2-10")


def hostnames() -> dict[str, str]:
    """INF-U2-01: el hostname publico por entorno."""
    body = section(INFRASTRUCTURE, "### INF-U2-01")
    return {row[0]: row[1].strip("`") for row in table_rows(body) if row[0] in ENVS}


# --- §4.1 perfiles de cabeceras ----------------------------------------------------------------

COMMON_PROFILE_ROW = "Todos"


def _ticks(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


def _split_header(text: str) -> tuple[str, str]:
    name, _, value = text.partition(": ")
    return name, value


@dataclass(frozen=True)
class Profile:
    """Las cabeceras que el perfil fija (`set`) o agrega (`add`) en la respuesta."""

    set: dict[str, str]
    add: dict[str, str]


def profiles() -> dict[str, Profile]:
    """domain-entities §4.1. Incluye la clave `common` (fila «Todos»)."""
    rows = {row[0]: row[1] for row in table_rows(_PROFILES_SECTION) if len(row) == 2 and row[0] != "Perfil"}
    common = dict(_split_header(t) for t in _ticks(rows[COMMON_PROFILE_ROW]))
    page_ticks = _ticks(rows["`spa` y `api`"])
    page = {"X-Frame-Options": _split_header(page_ticks[0])[1], "Content-Security-Policy": page_ticks[1]}
    grafana = dict(_split_header(t) for t in _ticks(rows["`grafana`"]))
    auth_csp = _ticks(rows["`auth`"])[0]
    return {
        "common": Profile(common, {}),
        "spa": Profile(page, {}),
        "api": Profile(page, {}),
        "grafana": Profile(grafana, {}),
        "auth": Profile({}, {"Content-Security-Policy": auth_csp}),
    }


# --- §4 tabla de rutas ------------------------------------------------------------------------


def route_rows() -> dict[str, list[str]]:
    """Fila de la tabla de §4 por la ruta (primera celda sin comillas)."""
    rows = {}
    for row in table_rows(_ROUTES_SECTION):
        if len(row) == 7 and row[0].startswith("`/"):
            rows[row[0].split("`")[1]] = row
    return rows


def body_limit(row_key: str) -> str | None:
    """«64 KiB» -> `64Ki`; las filas con «—» o «Por defecto» no llevan limite."""
    cell = route_rows()[row_key][5]
    found = re.fullmatch(r"(\d+) KiB", cell)
    return f"{found.group(1)}Ki" if found else None


def rate_limit_numbers() -> dict[str, int]:
    rows = route_rows()
    numbers = {
        "console": int(re.search(r"(\d+) req/s por `sub`", rows["/api/console/**"][4]).group(1)),  # type: ignore[union-attr]
        "intake-channel": int(re.search(r"`channel` (\d+) req/s", rows["/api/intake/**"][4]).group(1)),  # type: ignore[union-attr]
        "intake-channel-simulator": int(
            re.search(r"`channel-simulator` (\d+) req/s", rows["/api/intake/**"][4]).group(1)  # type: ignore[union-attr]
        ),
        "promotion": int(re.search(r"(\d+) req/s por `sub`", rows["/api/promotion/**"][4]).group(1)),  # type: ignore[union-attr]
        "auth": int(re.search(r"(\d+) req/min por IP", rows["/auth/realms/vectra/**"][4]).group(1)),  # type: ignore[union-attr]
        "federate": int(re.search(r"(\d+) req/s", rows["/federate"][4]).group(1)),  # type: ignore[union-attr]
        "global": int(re.search(r"Límite global: (\d+) req/s", _ROUTES_SECTION).group(1)),  # type: ignore[union-attr]
    }
    return numbers


def timeouts() -> dict[str, str]:
    """P-U2-02: `/api/console/**` -> `15s`."""
    found = {}
    for row in table_rows(section(NFR_PATTERNS, "### P-U2-02 — Timeouts, reintentos y outlier detection (Q4)")):
        if row[0].startswith("`/") and (m := re.fullmatch(r"(\d+) s", row[1])):
            found[row[0].strip("`")] = f"{m.group(1)}s"
    return found


def business_roles() -> list[str]:
    body = section(DOMAIN_ENTITIES, "### 1.1 Roles de negocio (realm roles)")
    return [m.group(1) for row in table_rows(body) if (m := re.fullmatch(r"`(\w+)`", row[0]))]


# --- V1: la lista de /auth/** -----------------------------------------------------------------

AUTH_BASE = "/auth/realms/vectra/"


def auth_entries() -> tuple[list[str], list[str]]:
    """(exactos, prefijos) de la enmienda V1 de domain-entities §4, como caminos completos."""
    exact: list[str] = []
    prefix: list[str] = []
    for line in _ROUTES_SECTION.splitlines():
        stripped = line.strip()
        if stripped.startswith("- exactos:"):
            exact += [AUTH_BASE + t for t in _ticks(stripped)]
        elif stripped.startswith("- por prefijo:"):
            prefix += [AUTH_BASE + t.rstrip("/") for t in _ticks(stripped)]
        elif stripped.startswith("- además `/auth/resources/`"):
            prefix.append("/auth/resources")
    return exact, prefix


def retry_after() -> dict[str, str]:
    """BR-U2-08 (V5): `1` en los limites por segundo y `60` en los de `/auth/**`."""
    line = next(ln for ln in BUSINESS_RULES.splitlines() if ln.startswith("`Retry-After` tiene un valor fijo"))
    found = re.search(r"`(\d+)` en los límites por segundo y `(\d+)` en los de `/auth/\*\*`", line)
    assert found, "BR-U2-08 sin los valores de Retry-After"
    return {"second": found.group(1), "auth": found.group(2)}


# --- INF-U2-10 destinos -----------------------------------------------------------------------


def jwks_uri() -> str:
    found = re.search(r"URL interna `(https://[^`]+)`", _INF_10)
    assert found, "INF-U2-10 sin la URL de la JWKS"
    return found.group(1)
