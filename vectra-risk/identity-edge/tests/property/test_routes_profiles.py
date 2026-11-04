"""PBT-U2-05: el perfil de cabeceras de cada ruta es el de su fila; solo `/grafana/**` y `/auth/**` admiten
`frame-ancestors 'self'`; toda ruta lleva `Cross-Origin-Opener-Policy: same-origin` (U02-T09, Paso 7)."""

import re

import gateway_checks as gc
import gateway_design as gd
from hypothesis import given
from hypothesis import strategies as st

DOCS = {env: gc.load_env(env) for env in gc.ENVS}
PROFILES = gd.profiles()
SEGMENT = st.text(alphabet="abcxyz019-_", min_size=1, max_size=8)

# (fila de la tabla de §4, camino de ejemplo dentro de la fila, metodo). El perfil sale de la ultima columna de la fila.
ROW_PATHS = {
    "/": lambda s: ("GET", f"/cases/{s}"),
    "/api/console/**": lambda s: ("GET", f"/api/console/v1/{s}"),
    "/api/intake/**": lambda s: ("POST", "/api/intake/v1/intake/applications"),
    "/api/promotion/**": lambda s: ("POST", f"/api/promotion/v1/models/{s}/activation"),
    "/auth/realms/vectra/**": lambda s: ("GET", f"/auth/realms/vectra/login-actions/{s}"),
    "/grafana/**": lambda s: ("GET", f"/grafana/d/{s}"),
    "/federate": lambda s: ("GET", "/federate"),  # F09 deshabilitada: la ruta cerrada lleva el perfil `api` de su fila
}


def row_profile(row: str) -> str:
    found = re.search(r"Perfil `(\w+)`", gd.route_rows()[row][6])
    assert found, row
    return found.group(1)


def expected_headers(profile: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in (PROFILES["common"], PROFILES[profile]):
        for name, value in {**part.set, **part.add}.items():
            out.setdefault(name, []).append(value)
    return out


def test_every_row_of_the_design_has_a_path_example():
    assert set(ROW_PATHS) == set(gd.route_rows())


@given(row=st.sampled_from(sorted(ROW_PATHS)), s=SEGMENT, env=st.sampled_from(gc.ENVS))
def test_the_profile_applied_to_a_path_is_the_one_of_its_row(row, s, env):
    method, path = ROW_PATHS[row](s)
    out = gc.route(DOCS[env], method, path)
    assert out.headers == expected_headers(row_profile(row)), (row, path, out.rule)


@given(row=st.sampled_from(sorted(ROW_PATHS)), s=SEGMENT, env=st.sampled_from(gc.ENVS))
def test_every_route_sends_the_opener_policy_and_the_common_headers(row, s, env):
    method, path = ROW_PATHS[row](s)
    headers = gc.route(DOCS[env], method, path).headers
    assert headers["Cross-Origin-Opener-Policy"] == ["same-origin"]
    for name, value in PROFILES["common"].set.items():
        assert headers[name] == [value]


@given(s=SEGMENT, kind=st.sampled_from(["/api", "/auth", "/grafana", "/federate", "/other"]), env=st.sampled_from(gc.ENVS))
def test_only_grafana_and_auth_admit_frame_ancestors_self(s, kind, env):
    out = gc.route(DOCS[env], "GET", f"{kind}/{s}")
    csp = " ".join(out.headers.get("Content-Security-Policy", []))
    allows_self = "frame-ancestors 'self'" in csp
    assert allows_self == (kind in ("/auth", "/grafana")), (kind, out.rule, csp)
    if not allows_self:
        assert "frame-ancestors 'none'" in csp
        assert out.headers["X-Frame-Options"] == ["DENY"]
