"""CA-1 (Paso 10): `create_app` arranca con las 21 rutas de `governance-service` y los scopes y roles del contrato se imponen.

Sin base de datos: la app se arma con la capa de servicio sobre una base de prueba y solo se miran las rutas y el 403 de la
autorizacion (que la pone la fabrica de U0 antes del handler).
"""

import pytest
from api_support import ApiWorld
from fastapi.routing import APIRoute
from vectra_contracts.catalog import Role
from vectra_contracts.routes import REGISTRY, RouteContract
from vectra_governance.api import SERVICE, build_handlers

pytestmark = pytest.mark.integration

CONTRACT = REGISTRY[SERVICE]


def concrete(route: RouteContract) -> str:
    return route.path.replace("{id}", "mv-x").replace("{run_id}", "00000000-0000-0000-0000-000000000000")


def test_the_app_has_exactly_the_21_routes_of_the_contract(world: ApiWorld) -> None:
    mounted = {(method, route.path) for route in world.app.router.routes if isinstance(route, APIRoute) for method in route.methods}
    declared = {(r.method, r.path) for r in CONTRACT}
    assert len(declared) == 21
    assert mounted == declared  # ni falta ni sobra ninguna
    assert set(build_handlers(world.deps)) == declared


@pytest.mark.parametrize("route", [r for r in CONTRACT if r.scopes], ids=lambda r: f"{r.method} {r.path}")
async def test_a_route_with_scopes_answers_403_to_a_token_without_them(world: ApiWorld, route: RouteContract) -> None:
    others = {"scope": "registry:read:metrics"}  # un scope que existe, pero no es el de la ruta
    roles = sorted(route.roles, key=lambda r: r.value)
    headers = world.user(roles[0].value, **others) if roles else world.service("some-client", others["scope"])
    response = await world.client.request(route.method, concrete(route), headers=headers, json={})
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "forbidden"


@pytest.mark.parametrize("route", [r for r in CONTRACT if r.roles], ids=lambda r: f"{r.method} {r.path}")
async def test_a_route_with_roles_answers_403_to_other_roles(world: ApiWorld, route: RouteContract) -> None:
    intruder = next(role for role in (Role.ANALISTA, Role.CRO, Role.INGENIERO_RIESGO) if role not in route.roles)
    scope = " ".join(s.value for s in route.scopes)  # el scope no basta sin el rol
    response = await world.client.request(
        route.method, concrete(route), headers=world.user(intruder.value, scope=scope or None), json={}
    )
    assert response.status_code == 403, response.text


async def test_a_request_without_token_is_401(world: ApiWorld) -> None:
    response = await world.client.get("/v1/models")
    assert response.status_code == 401
