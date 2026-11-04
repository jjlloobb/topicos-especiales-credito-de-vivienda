"""Valores del diseno de las rutas del gateway (U02-T09, Paso 7), leidos de los documentos.

Nada de esto es una lista a mano: sale de domain-entities §4 y §4.1, business-rules (BR-U2-08, 10),
nfr-design-patterns (P-U2-02, P-U2-06) e infrastructure-design (INF-U2-01, INF-U2-10).
"""

import re
from dataclasses import dataclass
from pathlib import Path

from design_values import DOMAIN_ENTITIES, INFRASTRUCTURE, section, table_rows

_ROOT = Path(__file__).resolve().parents[3]
_FD = _ROOT / "aidlc-docs" / "construction" / "identity-edge"
BUSINESS_RULES = (_FD / "functional-design" / "business-rules.md").read_text(encoding="utf-8")
NFR_PATTERNS = (_FD / "nfr-design" / "nfr-design-patterns.md").read_text(encoding="utf-8")
NFR_REQUIREMENTS = (_FD / "nfr-requirements" / "nfr-requirements.md").read_text(encoding="utf-8")
LOGICAL_COMPONENTS = (_FD / "nfr-design" / "logical-components.md").read_text(encoding="utf-8")
CLUSTER_STORE = _ROOT / "platform" / "secrets" / "cluster-secret-store-prod.yaml"

ENVS = ("kind", "staging", "prod")
# Los textos de diseno son atributos del modulo y las secciones se calculan al usarlas: una prueba puede alterar el
# diseno en memoria (`monkeypatch.setattr(gd, "INFRASTRUCTURE", ...)`) y el oraculo lo lee alterado.


def _routes_section() -> str:
    return section(DOMAIN_ENTITIES, "## 4. Rutas del gateway (Envoy Gateway)")


def _profiles_section() -> str:
    return section(DOMAIN_ENTITIES, "### 4.1 Perfiles de cabeceras (Q9)")


def _inf_10() -> str:
    return section(INFRASTRUCTURE, "### INF-U2-10")


def _p_u2_02() -> str:
    return section(NFR_PATTERNS, "### P-U2-02 — Timeouts, reintentos y outlier detection (Q4)")


def _p_u2_06() -> str:
    return section(NFR_PATTERNS, "### P-U2-06 — Claves de rate limit solo de datos verificados (Q2)")


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
    rows = {row[0]: row[1] for row in table_rows(_profiles_section()) if len(row) == 2 and row[0] != "Perfil"}
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
    for row in table_rows(_routes_section()):
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
        "console": int(re.search(r"(\d+) req/(?:s|min) por `sub`", rows["/api/console/**"][4]).group(1)),  # type: ignore[union-attr]
        "intake-channel": int(re.search(r"`channel` (\d+) req/(?:s|min)", rows["/api/intake/**"][4]).group(1)),  # type: ignore[union-attr]
        "intake-channel-simulator": int(
            re.search(r"`channel-simulator` (\d+) req/(?:s|min)", rows["/api/intake/**"][4]).group(1)  # type: ignore[union-attr]
        ),
        "promotion": int(re.search(r"(\d+) req/(?:s|min) por `sub`", rows["/api/promotion/**"][4]).group(1)),  # type: ignore[union-attr]
        "auth": int(re.search(r"(\d+) req/(?:s|min) por IP", rows["/auth/realms/vectra/**"][4]).group(1)),  # type: ignore[union-attr]
        "federate": int(re.search(r"(\d+) req/(?:s|min)", rows["/federate"][4]).group(1)),  # type: ignore[union-attr]
        "global": int(re.search(r"Límite global: (\d+) req/(?:s|min)", _routes_section()).group(1)),  # type: ignore[union-attr]
    }
    return numbers


def timeouts() -> dict[str, str]:
    """P-U2-02: `/api/console/**` -> `15s`."""
    found = {}
    for row in table_rows(_p_u2_02()):
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
    for line in _routes_section().splitlines():
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
    found = re.search(r"URL interna `(https://[^`]+)`", _inf_10())
    assert found, "INF-U2-10 sin la URL de la JWKS"
    return found.group(1)


# --- el resto de los valores que fija el diseno -----------------------------------------------


def _ticks_of(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


def rate_limit_units() -> dict[str, str]:
    """`req/s` -> `Second`, `req/min` -> `Minute`, por contador de §4."""
    rows = route_rows()
    unit = {"req/s": "Second", "req/min": "Minute"}

    def of(row: str, pattern: str) -> str:
        found = re.search(pattern, rows[row][4])
        assert found, (row, pattern)
        return unit[found.group(1)]

    out = {
        "console": of("/api/console/**", r"\d+ (req/s|req/min) por `sub`"),
        "intake-channel": of("/api/intake/**", r"`channel` \d+ (req/s|req/min)"),
        "intake-channel-simulator": of("/api/intake/**", r"`channel-simulator` \d+ (req/s|req/min)"),
        "promotion": of("/api/promotion/**", r"\d+ (req/s|req/min) por `sub`"),
        "auth": of("/auth/realms/vectra/**", r"\d+ (req/s|req/min) por IP"),
        "federate": of("/federate", r"\d+ (req/s|req/min)"),
    }
    found = re.search(r"Límite global: \d+ (req/s|req/min)", _routes_section())
    assert found
    out["global"] = unit[found.group(1)]
    return out


@dataclass(frozen=True)
class AuthRow:
    """La columna «Autenticación» de §4 de una ruta con JWT."""

    azp: list[str]  # los de todos los entornos
    non_prod_azp: list[str]  # los que el diseno marca «solo en los realms que no son de produccion»
    roles: list[str] | None
    scopes: list[str]
    acr: str | None


def auth_row(row_key: str) -> AuthRow:
    cell = route_rows()[row_key][3]
    ticks = _ticks_of(cell)
    scopes = [t for t in ticks if re.fullmatch(r"[a-z]+:[a-z]+", t)]
    acr = next((t.split("= ")[1] for t in ticks if t.startswith("acr = ")), None)
    if "cualquier rol de negocio" in cell:
        roles: list[str] | None = business_roles()
    else:
        known = set(business_roles())
        roles = [t for t in ticks if t in known] or None
    if "azp" in ticks:  # «`azp` = `channel` (F04) o `channel-simulator` (F07, solo en los realms que no son de produccion)»
        azp = ticks[ticks.index("azp") + 1 :]
        non_prod = [t for t in azp if t == "channel-simulator"]
        assert "no son de producción" in cell or not non_prod
    else:
        azp = [t for t in ticks if t not in scopes and t not in (roles or []) and not t.startswith("acr")][:1]
        non_prod = []
    return AuthRow(azp, non_prod, roles, scopes, acr)


def jwks_cache_duration() -> str:
    found = re.search(r"`cacheDuration` de (\d+) min", _inf_10())
    assert found, "INF-U2-10 sin cacheDuration"
    return f"{int(found.group(1)) * 60}s"


def jwt_issuer_path() -> str:
    found = re.search(r"https://<hostname público>(/[\w/]+)`", _inf_10())
    assert found, "INF-U2-10 sin la ruta del issuer"
    return found.group(1)


@dataclass(frozen=True)
class Outlier:
    consecutive_5xx: int
    base_ejection_time: str
    max_ejection_percent: int
    local_origin_failures: int  # en `/api/console/**` cuentan solo los errores de conexion; el mismo umbral


def outlier() -> Outlier:
    text = _p_u2_02()
    found = re.search(r"(\d+) errores 5xx consecutivos sacan un pod del balanceo por (\d+) s, hasta el (\d+) %", text)
    assert found, "P-U2-02 sin el outlier"
    assert "solo los errores de conexión" in text
    return Outlier(int(found.group(1)), f"{found.group(2)}s", int(found.group(3)), int(found.group(1)))


@dataclass(frozen=True)
class Retry:
    num_retries: int
    trigger: str
    budget_percent: int
    routes: list[str]  # las filas de P-U2-02 cuyos reintentos dicen «Solo ...»


def retry() -> Retry:
    rows = {r[0].strip("`"): r for r in table_rows(_p_u2_02()) if r[0].startswith("`/")}
    console = rows["/api/console/**"][2]
    found = re.search(r"(\d+) reintento ante `([\w-]+)`, presupuesto del (\d+) %", console)
    assert found, "P-U2-02 sin la cifra de reintentos de la consola"
    assert "Cifras de los «solo `GET`/`HEAD`»" in _p_u2_02() or "Cifras de los «solo `GET`/`HEAD`»" in NFR_PATTERNS
    no_retry = set(re.findall(r"^- `(/[\w/*]+)` no reintenta", _p_u2_02(), re.MULTILINE))  # X1: `/auth/**` no reintenta
    retried = [k for k, r in rows.items() if r[2].startswith("Solo") and k not in no_retry]
    return Retry(int(found.group(1)), found.group(2), int(found.group(3)), retried)


def no_retry_routes() -> set[str]:
    return set(re.findall(r"^- `(/[\w/*]+)` no reintenta", _p_u2_02(), re.MULTILINE))


def trusted_hops() -> int:
    """NFR-U2-23 (W2): con el balanceador L4 y `externalTrafficPolicy: Local` no se confia en ningun salto."""
    line = NFR_REQUIREMENTS[NFR_REQUIREMENTS.index("| NFR-U2-23 |") :].splitlines()[0]
    if "no confía en ningún salto" in line:
        return 0
    found = re.search(r"\((\d+) salto\)", line)
    assert found, "NFR-U2-23 sin los saltos"
    return int(found.group(1))


def escaped_slashes_action() -> str:
    found = re.search(r"`%2F` y `%5C` se tratan con `(\w+)`", BUSINESS_RULES)
    assert found, "BR-U2-10 sin escapedSlashesAction"
    return found.group(1)


def merge_slashes() -> bool:
    found = re.search(r"las barras dobles se (fusionan|mantienen)", BUSINESS_RULES)
    assert found, "BR-U2-10 sin la fusion de barras"
    return found.group(1) == "fusionan"


def internal_prefix() -> str:
    found = re.search(r"prefijo reservado `([\w-]+)`", _p_u2_06())
    assert found, "P-U2-06 sin el prefijo"
    return found.group(1)


def internal_headers() -> list[str]:
    """Las cabeceras que el gateway copia del JWT (tabla de P-U2-06)."""
    return sorted(set(re.findall(r"`(x-vectra-(?:sub|azp))`", _p_u2_06())))


def response_removals() -> tuple[list[str], list[str]]:
    """(cabeceras, prefijos) de BR-U2-14: «Se ocultan las cabeceras `server` y `x-envoy-*`»."""
    found = re.search(r"Se ocultan las cabeceras `(\w+)` y `([\w-]+)\*`", BUSINESS_RULES)
    assert found, "BR-U2-14 sin las cabeceras ocultas"
    return [found.group(1)], [found.group(2)]


def destinations() -> dict[str, tuple[str, int]]:
    """Service -> (namespace, puerto) de los «Destinos» de INF-U2-10."""
    text = _inf_10()
    block = text[text.index("- **Destinos**") :]
    block = block[: block.index("- **Tamaño por ruta**")]
    found: dict[str, tuple[str, int]] = {}
    for line in block.splitlines()[1:]:
        pending: list[tuple[str, int]] = []
        for name, port, ns in re.findall(r"`([\w-]+)` (\d+)(?: \(`([\w-]+)`\))?", line):
            pending.append((name, int(port)))
            if ns:
                found.update({n: (ns, p) for n, p in pending})
                pending = []
    return found


def gateway_ref() -> tuple[str, str, str]:
    """(nombre, namespace, listener) del `Gateway` (INF-U2-10, V9)."""
    found = re.search(r"`([\w-]+)` en `([\w-]+)`, con el listener `(\w+)`", _inf_10())
    assert found, "INF-U2-10 sin el Gateway"
    return found.group(1), found.group(2), found.group(3)


def grant_namespaces() -> list[str]:
    found = re.search(r"namespace de destino \(([^)]*)\)", _inf_10())
    assert found, "INF-U2-10 sin los namespaces de los grants"
    return _ticks_of(found.group(1))


def securitypolicy_grant() -> tuple[str, str, str]:
    """(namespace del grant, grupo, Service): D-1, el de `vectra-identity` admite tambien la SecurityPolicy."""
    found = re.search(r"El de `([\w-]+)` admite además la `SecurityPolicy` \(`([\w.]+)`\) de `[\w-]+`, solo hacia el Service `([\w-]+)`", _inf_10())
    assert found, "INF-U2-10 sin el grant de la SecurityPolicy"
    return found.group(1), found.group(2), found.group(3)


@dataclass(frozen=True)
class Rewrite:
    source: str
    target: str


def rewrites() -> list[Rewrite]:
    """V3: «`/api/...` llega como `/v1/...`»."""
    line = next(ln for ln in _routes_section().splitlines() if ln.startswith("- **Reescritura** (V3)"))
    sources = re.findall(r"`(/api/[^`]*/v\d+/[^`]*)`", line)
    targets = [t for t in re.findall(r"`(/v\d+/[^`]+)`", line) if "..." not in t]
    assert len(sources) == len(targets) > 0, "V3 con otra forma"
    return [Rewrite(a, b) for a, b in zip(sources, targets, strict=True)]


def promotion_query() -> tuple[str, str]:
    line = next(ln for ln in _routes_section().splitlines() if ln.startswith("- **Reescritura** (V3)"))
    found = re.search(r"con `(\w+)=(\w+)`", line)
    assert found, "V3 sin la consulta de promocion"
    return found.group(1), found.group(2)


@dataclass(frozen=True)
class Cookie:
    name: str
    ttl: str
    attributes: dict[str, str]


def cookie() -> Cookie:
    """V6 y la fila `/` de §4: nombre, atributos y TTL."""
    row = route_rows()["/"][2]
    name = re.search(r"cookie\*{0,2} `([\w-]+)`", row)
    attrs = re.search(r"`[\w-]+` \(([^;]*);", row[row.index("cookie") :])
    v6 = next(ln for ln in _routes_section().splitlines() if ln.startswith("- **Cookie `"))
    ttl = re.search(r"TTL (\d+) s", v6)
    path = re.search(r"`path=([^`]+)`", v6)
    assert name and attrs and ttl and path, "domain-entities §4 sin la cookie"
    attributes = {"Path": path.group(1)}
    for token in _ticks_of(attrs.group(1)):
        key, _, value = token.partition("=")
        attributes[key] = value
    return Cookie(name.group(1), f"{ttl.group(1)}s", attributes)


@dataclass(frozen=True)
class Federate:
    secret: str
    namespace: str
    key: str
    property: str
    store_name: str
    store_kind: str


def federate() -> Federate:
    """V7 (domain-entities §4) y el `ClusterSecretStore` de U1."""
    line = next(ln for ln in _routes_section().splitlines() if ln.startswith("- **F09** (V7)"))
    found = re.search(r"Secret `([\w-]+)` en `([\w-]+)`, con la clave `([.\w]+)`.*bóveda `([\w/]+)`, propiedad `([.\w]+)`", line)
    assert found, "V7 sin el Secret de F09"
    import yaml

    store = yaml.safe_load(CLUSTER_STORE.read_text(encoding="utf-8"))
    assert found.group(3) == found.group(5)
    return Federate(found.group(1), found.group(2), found.group(4), found.group(5), store["metadata"]["name"], store["kind"])


def closed_prefixes() -> list[str]:
    """BR-U2-10: `/api/` y `/auth/` son prefijos cerrados, y `/federate` da 404 con F09 deshabilitada."""
    found = re.search(r"- `(/\w+)/` y `(/\w+)/` son prefijos cerrados", BUSINESS_RULES)
    assert found, "BR-U2-10 sin los prefijos cerrados"
    prefixes = [found.group(1), found.group(2)]
    federate_line = next(ln for ln in BUSINESS_RULES.splitlines() if "`/federate` da 404" in ln)
    prefixes.append(re.search(r"`(/federate)` da 404", federate_line).group(1))  # type: ignore[union-attr]
    return sorted(prefixes)


def error_statuses() -> list[int]:
    """BR-U2-14: «(401, 403, 404, 413, 429, 503)»."""
    found = re.search(r"\(((?:\d{3}(?:, )?)+)\) son `Problem`", BUSINESS_RULES)
    assert found, "BR-U2-14 sin los estados"
    return [int(x) for x in found.group(1).split(", ")]


def intake_method() -> str:
    """§4: «`/api/intake/**` (solo `POST /v1/intake/applications`)»."""
    found = re.search(r"solo `(\w+) /v1/intake/applications`", " ".join(route_rows()["/api/intake/**"]) + _routes_section())
    assert found, "§4 sin el metodo de intake"
    return found.group(1)


def promotion_methods() -> list[str]:
    """V3: «(solo `GET`, con `state=aprobado`)» y «(solo `POST`)», en el orden de `rewrites()`."""
    line = next(ln for ln in _routes_section().splitlines() if ln.startswith("- **Reescritura** (V3)"))
    found = re.findall(r"\(solo `(\w+)`", line)
    assert len(found) == 2, "V3 con otra forma"
    return found


def auth_counters() -> dict[str, list[str]]:
    """V1: los dos contadores de `/auth/**`, con los caminos (relativos al realm) que cuenta cada uno."""
    line = next(ln for ln in _routes_section().splitlines() if ln.startswith("- **Límite de `/auth/**`**"))
    login = re.search(r"uno de login \(([^)]*)\)", line)
    token = re.search(r"otro de token \(([^)]*)\)", line)
    assert login and token, "V1 sin los contadores"
    return {"login": _ticks_of(login.group(1)), "token": _ticks_of(token.group(1))}


def authentication_kind(row_key: str) -> str:
    """`jwt`, `basic` o `none`, segun la columna «Autenticación» de §4."""
    cell = route_rows()[row_key][3]
    if "JWT" in cell:
        return "jwt"
    if "Basic auth" in cell or "basic auth" in cell:
        return "basic"
    return "none"


def read_methods() -> list[str]:
    """P-U2-02: «Solo `GET`/`HEAD`»."""
    rows = {r[0].strip("`"): r for r in table_rows(_p_u2_02()) if r[0].startswith("`/")}
    found = re.match(r"Solo ((?:`\w+`/?)+):", rows["/api/console/**"][2])
    assert found, "P-U2-02 sin los metodos de solo lectura"
    return _ticks_of(found.group(1))


def closed_profile(prefix: str) -> str:
    """El perfil de la fila de §4 que cae bajo el prefijo cerrado (`/api` -> `api`, `/auth` -> `auth`, `/federate` -> `api`)."""
    for key, row in route_rows().items():
        if key == prefix or key.startswith(prefix + "/"):
            found = re.search(r"Perfil `(\w+)`", row[6])
            assert found, key
            return found.group(1)
    raise AssertionError(f"ninguna fila de §4 bajo {prefix}")


def closed_errors() -> list[int]:
    """D-2 y D-6 (BR-U2-10): el cierre reescribe el 404 y su politica no declara 429."""
    assert "responseOverride` de 404" in _inf_10() or "responseOverride` de 404" in BUSINESS_RULES
    declares_429 = "no declara 429" not in BUSINESS_RULES
    return sorted([404, 429] if declares_429 else [404])


def federate_path() -> str:
    """La fila `/federate` de §4."""
    assert "/federate" in route_rows()
    return "/federate"


# --- Paso 8 (U02-T10): Gateway, Certificate, EnvoyProxy, EnvoyPatchPolicy ------------------------


def _inf_02() -> str:
    return section(INFRASTRUCTURE, "### INF-U2-02")


def _inf_06() -> str:
    return section(INFRASTRUCTURE, "### INF-U2-06")


def _logical_components() -> str:
    return LOGICAL_COMPONENTS


def _p_u2_01() -> str:
    return section(NFR_PATTERNS, "### P-U2-01")


def _p_u2_07() -> str:
    return section(NFR_PATTERNS, "### P-U2-07")


def issuers() -> dict[str, str]:
    """INF-U2-01: `vectra-internal-ca` en kind; el ejemplo `banco-ca` en staging y prod."""
    body = section(INFRASTRUCTURE, "### INF-U2-01")
    line = next(ln for ln in body.splitlines() if ln.startswith("- `ClusterIssuer` del certificado interno"))
    kind = re.search(r"`([\w-]+)` en kind", line)
    bank = re.search(r"el ejemplo es `([\w-]+)`", line)
    assert kind and bank, "INF-U2-01 sin los ClusterIssuer"
    return {"kind": kind.group(1), "staging": bank.group(1), "prod": bank.group(1)}


def listener_port() -> int:
    found = re.search(r"listener HTTPS \((\d+)\)", _inf_02())
    assert found, "INF-U2-02 sin el puerto del listener"
    return int(found.group(1))


def envoy_images() -> tuple[dict[str, str], str, dict[str, str], str]:
    """(repositorio de Envoy por entorno, su digest, repositorio del shutdown-manager por entorno, su digest): W4 y X3."""
    text = _inf_02()
    w4 = next(ln for ln in text.splitlines() if ln.startswith("  - **Imagen del data plane**"))
    envoy = re.search(r"\(W4\): `(registro[\w./-]+)` \(`(kind-registry[\w.:/-]+)` en kind\)", w4)
    envoy_digest = re.search(r"digest `(sha256:[0-9a-f]{64})`, que va en los values", w4)
    shutdown = re.search(r"Es `(registro[\w./-]+)` \(`(kind-registry[\w.:/-]+)` en kind\)", w4)
    shutdown_digest = re.search(r"digest de upstream `(sha256:[0-9a-f]{64})`", w4)
    assert envoy and envoy_digest and shutdown and shutdown_digest, "INF-U2-02 sin las imagenes del data plane"
    by_env = lambda bank, local: {"kind": local, "staging": bank, "prod": bank}  # noqa: E731
    return (
        by_env(envoy.group(1), envoy.group(2)),
        envoy_digest.group(1),
        by_env(shutdown.group(1), shutdown.group(2)),
        shutdown_digest.group(1),
    )


def infrastructure_labels() -> dict[str, str]:
    """X3: `vectra.io/criticality: high` en `Gateway.spec.infrastructure.labels`."""
    found = re.search(r"`(vectra\.io/criticality): (\w+)` va en `Gateway\.spec\.infrastructure\.labels`", _inf_02())
    assert found, "INF-U2-02 sin la etiqueta de criticidad"
    return {found.group(1): found.group(2)}


def service_spec() -> tuple[str, str, dict[str, str]]:
    """W2: (tipo, externalTrafficPolicy, etiquetas) del Service del data plane."""
    found = re.search(r"`(LoadBalancer)` con `externalTrafficPolicy: (\w+)` y la etiqueta `([\w./-]+): ([\w-]+)`", _inf_02())
    assert found, "INF-U2-02 sin el Service"
    return found.group(1), found.group(2), {found.group(3): found.group(4)}


def scaling() -> tuple[int, int, int, int]:
    """W5: (minimo, maximo, objetivo de CPU en %, minAvailable del PDB)."""
    found = re.search(r"`envoyHpa` de (\d+) a (\d+) réplicas con un objetivo de CPU del (\d+) %, y `envoyPDB` con `minAvailable: (\d+)`", _inf_02())
    assert found, "INF-U2-02 sin el escalado"
    return tuple(int(g) for g in found.groups())  # type: ignore[return-value]


def spread_key() -> str:
    """El reparto es por zona (tabla de INF-U2-02 y Kyverno `require-spread-and-pdb`)."""
    found = re.search(r"spread por (zona|nodo)", _inf_02())
    assert found, "INF-U2-02 sin el reparto"
    return {"zona": "topology.kubernetes.io/zone", "nodo": "kubernetes.io/hostname"}[found.group(1)]


def envoy_resources() -> dict[str, dict[str, str]]:
    row = next(r for r in table_rows(_inf_06()) if r[0] == "Envoy (data plane)")
    out = {}
    for key, cell in (("requests", row[1]), ("limits", row[2])):
        cpu, mem = (p.strip() for p in cell.split("/"))
        out[key] = {"cpu": cpu.replace(" CPU", ""), "memory": mem.replace(" MiB", "Mi").replace(" GiB", "Gi")}
    return out


def envoy_priority() -> str:
    row = next(r for r in table_rows(_logical_components()) if r[0].startswith("Envoy (data plane)"))
    return row[-1].strip("`")


def access_log_fields() -> list[str]:
    """P-U2-07: los campos del access log, en orden."""
    line = next(ln for ln in _p_u2_07().splitlines() if ln.startswith("- Campos:"))
    return _ticks_of(line.replace("(el `trace-id` de `traceparent`)", ""))[: line.count("`") // 2]


def tracing() -> tuple[str, str, int, int]:
    """W6: (Service, namespace, puerto, muestreo en %)."""
    found = re.search(r"tracing OpenTelemetry hacia `([\w-]+)\.([\w-]+)\.svc:(\d+)` \(F61\) con muestreo del (\d+) %", _inf_02())
    assert found, "INF-U2-02 sin el tracing"
    return found.group(1), found.group(2), int(found.group(3)), int(found.group(4))


def fail_closed() -> tuple[bool, int]:
    """P-U2-01: `failure_mode_deny: true` y `status_on_error: 503`."""
    found = re.search(r"`failure_mode_deny: (true|false)` y `status_on_error: (\d+)`", _p_u2_01())
    assert found, "P-U2-01 sin el modo de fallo"
    return found.group(1) == "true", int(found.group(2))
