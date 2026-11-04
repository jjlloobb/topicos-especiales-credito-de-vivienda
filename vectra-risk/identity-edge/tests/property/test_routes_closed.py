"""PBT-U2-04: un path se enruta a un backend <=> coincide con una entrada de `routes.yaml`; lo demas bajo los
prefijos cerrados da 404 (U02-T09, Paso 7). El modelo lee los manifiestos generados; la referencia, `routes.yaml`."""

from typing import Any

import gateway_checks as gc
import gateway_design as gd
import route_gen
from hypothesis import given
from hypothesis import strategies as st

DOCS = {env: gc.load_env(env) for env in gc.ENVS}
ROUTES = route_gen.load_routes()
EXACT, PREFIX = gd.auth_entries()

SEGMENT = st.text(alphabet="abcxyzABCXYZ019-_.~", min_size=0, max_size=6)
SEPARATOR = st.sampled_from(["/", "//", "%2F", "%2f", "%5C", "%5c", "/./", "/../", "/%2e/"])
BASES = st.sampled_from(
    [
        "", "/", "/auth", "/auth/admin", "/auth/admin/realms/vectra", "/auth/realms/master", "/auth/realms/vectra",
        "/auth/realms/vectra/protocol/openid-connect", "/auth/resources", "/api", "/api/console", "/api/intake",
        "/api/intake/v1/intake/applications", "/api/promotion/v1/models", "/api/promotion/v1", "/grafana",
        "/federate", "/cases", "/callback", "/stepup-callback", "/AUTH/admin", "/Api/console",
        *EXACT, *PREFIX,
    ]
)  # fmt: skip
METHODS = st.sampled_from(["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])


@st.composite
def raw_paths(draw: st.DrawFn) -> str:
    path = draw(BASES)
    for _ in range(draw(st.integers(0, 3))):
        path += draw(SEPARATOR) + draw(SEGMENT)
    if draw(st.booleans()):
        path = "".join(c.swapcase() if draw(st.booleans()) else c for c in path)
    return path if path.startswith("/") else "/" + path


# --- la referencia: las entradas de routes.yaml, con su semantica propia --------------------------


def entries(routes: dict[str, Any]) -> list[tuple[str | None, str, str, str | None, dict[str, str]]]:
    """(servicio o None si es 404, tipo, camino, metodo, consulta) de `routes.yaml` con F09 deshabilitada."""
    found: list[tuple[str | None, str, str, str | None, dict[str, str]]] = []
    for r in routes["routes"]:
        if r.get("requires") == "f09":
            continue
        for rule in r["rules"]:
            for m in rule.get("matches", r.get("matches", [])):
                methods = rule.get("methods") or [None]
                for method in methods:
                    found.append((r["backend"]["service"], m["type"], m["path"], method, m.get("query", {})))
    for c in routes["closed"]:
        found.append((None, "PathPrefix", c["path"], None, {}))
    return found


def reference(routes: dict[str, Any], method: str, path: str, query: dict[str, str]) -> str | None:
    """Servicio al que va `path` segun `routes.yaml`, o None si da 404 (o no hay entrada)."""
    rank = {"Exact": 2, "RegularExpression": 1, "PathPrefix": 0}
    best: tuple[tuple[int, int, int, int], str | None] | None = None
    import re

    for service, kind, value, m_method, m_query in entries(routes):
        if m_method and m_method != method:
            continue
        if kind == "Exact" and path != value:
            continue
        if kind == "PathPrefix" and not (value == "/" or path == value or path.startswith(value + "/")):
            continue
        if kind == "RegularExpression" and not re.fullmatch(value, path):
            continue
        if any(query.get(k) != v for k, v in m_query.items()):
            continue
        key = (rank[kind], 0 if value == "/" else len(value), 1 if m_method else 0, len(m_query))
        if best is None or key > best[0]:
            best = (key, service)
    return None if best is None else best[1]


@given(method=METHODS, raw=raw_paths(), env=st.sampled_from(gc.ENVS))
def test_a_path_reaches_a_backend_iff_it_matches_an_entry_of_routes_yaml(method, raw, env):
    out = gc.route(DOCS[env], method, raw)
    path, _ = gc.normalize(raw)
    want = reference(ROUTES, method, path, {})
    assert not out.ambiguous
    assert out.redirected == any(token in raw.lower() for token in ("%2f", "%5c"))
    if want is None:
        assert (out.kind, out.status) == ("direct", 404), (method, raw, path)
    else:
        assert out.kind == "backend" and out.backend is not None and out.backend[0] == want, (method, raw, path)


def under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def in_the_list(path: str) -> bool:
    return path in EXACT or any(under(path, p) for p in PREFIX)


@given(method=METHODS, raw=raw_paths(), env=st.sampled_from(gc.ENVS))
def test_everything_under_auth_and_api_outside_the_entries_is_a_404(method, raw, env):
    out = gc.route(DOCS[env], method, raw)
    path, _ = gc.normalize(raw)
    if under(path, "/auth/admin") or under(path, "/auth/realms/master"):
        assert (out.kind, out.status) == ("direct", 404), raw
    if under(path, "/auth") and not in_the_list(path):
        assert (out.kind, out.status) == ("direct", 404), raw
    if under(path, "/auth") and in_the_list(path):
        assert out.backend == ("keycloak", "vectra-identity", 8443), raw
    if under(path, "/api") and not any(under(path, p) for p in ("/api/console",)) and path not in (
        "/api/intake/v1/intake/applications",
    ):
        promotion_ok = method == "GET" and path == "/api/promotion/v1/models"
        activation_ok = method == "POST" and path.startswith("/api/promotion/v1/models/") and path.endswith("/activation") and path.count("/") == 6
        if not (promotion_ok or activation_ok):
            assert (out.kind, out.status) == ("direct", 404), (method, raw)


@given(suffix=st.text(alphabet="abcxyz019-_", min_size=1, max_size=8), env=st.sampled_from(gc.ENVS))
def test_the_entries_of_the_list_still_reach_keycloak(suffix, env):
    for path in EXACT:
        assert gc.route(DOCS[env], "GET", path).backend == ("keycloak", "vectra-identity", 8443)
        assert gc.route(DOCS[env], "GET", path + suffix).status == 404
    for path in PREFIX:
        assert gc.route(DOCS[env], "GET", f"{path}/{suffix}").backend == ("keycloak", "vectra-identity", 8443)
        assert gc.route(DOCS[env], "GET", path + suffix).backend != ("keycloak", "vectra-identity", 8443)


@given(raw=raw_paths(), env=st.sampled_from(gc.ENVS))
def test_a_404_is_a_problem_and_never_names_the_route(raw, env):
    out = gc.route(DOCS[env], "GET", raw)
    if out.kind != "direct":
        return
    hrf = gc.find(DOCS[env], "HTTPRouteFilter", "problem-not-found")["spec"]["directResponse"]
    assert out.status == 404 and hrf["contentType"] == "application/problem+json"
    for word in ("auth", "api", "keycloak", "route", "envoy"):
        assert word not in hrf["body"]["inline"].replace("urn:vectra:problem:not_found", "").lower()
