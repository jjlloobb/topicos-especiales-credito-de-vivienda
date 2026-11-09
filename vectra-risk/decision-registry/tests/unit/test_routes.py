"""Paso 9: las rutas de U3 son `RouteContract` de U0 (P-U0-12) y el OpenAPI las incluye (P-U3-01; BR-U3-03, 14, 13b).

Sin base de datos: la app se arma con pools sin conectar (las conexiones se abren a pedido).
"""

from pathlib import Path

import pytest
import yaml
from strategies import auth as u0_auth
from vectra_common.app_factory import audit_routes
from vectra_contracts.catalog import Role, Scope
from vectra_contracts.routes import REGISTRY
from vectra_registry.api import SERVICE, create_service_app, handlers
from vectra_registry.pools import Pools

ROOT = Path(__file__).resolve().parents[3]
ROUTES = {(r.method, r.path): r for r in REGISTRY[SERVICE]}
DSN = "postgresql://nadie:nada@127.0.0.1:1/nada"


def pools() -> Pools:
    return Pools.build({name: DSN for name in ("append", "dossier", "projections", "health")})


def test_las_siete_rutas_de_u3_estan_en_el_registro_de_contratos_de_u0() -> None:
    assert set(ROUTES) == {
        ("POST", "/v1/entries"),
        ("GET", "/v1/entries"),
        ("POST", "/v1/monitoring/daily:query"),
        ("GET", "/v1/monitoring/freezes"),
        ("GET", "/v1/dossiers/{case_id}"),
        ("POST", "/v1/integrity-checks"),
        ("GET", "/v1/integrity-checks/{id}"),
    }


def test_post_y_get_entries_usan_any_scopes_y_el_handler_decide_por_tipo_o_proyeccion() -> None:
    post, get = ROUTES[("POST", "/v1/entries")], ROUTES[("GET", "/v1/entries")]
    assert post.scopes == frozenset() and get.scopes == frozenset()
    assert post.any_scopes == {Scope.REGISTRY_APPEND_CASE, Scope.REGISTRY_APPEND_SCORING, Scope.REGISTRY_APPEND_GOVERNANCE}
    assert get.any_scopes == {Scope.REGISTRY_READ_EXPLANATION, Scope.REGISTRY_READ_METRICS, Scope.REGISTRY_READ_MONITORING}
    assert post.max_body_bytes == 80 * 1024  # 64 KiB de canonical + el sobre


def test_scopes_roles_y_mfa_de_las_demas_rutas() -> None:
    daily, freezes = ROUTES[("POST", "/v1/monitoring/daily:query")], ROUTES[("GET", "/v1/monitoring/freezes")]
    assert daily.scopes == freezes.scopes == {Scope.REGISTRY_READ_MONITORING} and daily.read_only
    assert ROUTES[("GET", "/v1/dossiers/{case_id}")].roles == {Role.CRO, Role.CUMPLIMIENTO}
    check, status = ROUTES[("POST", "/v1/integrity-checks")], ROUTES[("GET", "/v1/integrity-checks/{id}")]
    assert (check.roles, check.mfa, check.alternate_statuses) == ({Role.CRO}, True, {202})
    assert (status.roles, status.mfa) == ({Role.CRO}, False)


def test_la_app_tiene_un_handler_por_ruta_y_toda_ruta_lleva_requisitos() -> None:
    assert set(handlers(pools(), __import__("vectra_registry.api", fromlist=["ServiceConfig"]).ServiceConfig())) == set(ROUTES)
    app = create_service_app(pools(), authenticator=u0_auth.authenticator())
    audit_routes(app)  # no lanza: cada ruta lleva el marcador de `require`
    assert app.state.ops_app is not None


def test_el_openapi_versionado_incluye_las_rutas_de_u3() -> None:
    spec = yaml.safe_load((ROOT / "contracts" / "openapi" / "decision-registry-service.yaml").read_text())
    for method, path in ROUTES:
        assert method.lower() in spec["paths"][path], (method, path)
    assert "202" in spec["paths"]["/v1/integrity-checks"]["post"]["responses"]


@pytest.mark.parametrize("path", sorted({p for _, p in ROUTES}))
def test_cada_ruta_del_openapi_esta_en_el_registro(path: str) -> None:
    spec = yaml.safe_load((ROOT / "contracts" / "openapi" / "decision-registry-service.yaml").read_text())
    assert path in spec["paths"]
