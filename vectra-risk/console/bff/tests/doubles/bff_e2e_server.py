"""Servidor de las pruebas con navegador (P-1 (a) de U10-T03; solo pruebas): el BFF real con los dobles de los cinco destinos y el
emisor OIDC de prueba (`bff_oidc`) en **un solo proceso**.

`python console/bff/tests/doubles/bff_e2e_server.py` (desde `vectra-risk/`). Variables de entorno:

| Variable                 | Uso                                                                                                  |
|--------------------------|------------------------------------------------------------------------------------------------------|
| `VECTRA_E2E_ORIGIN`      | Origen publico de la SPA (p. ej. `http://127.0.0.1:47173`): es el `iss` de los tokens y el de los `redirect_uri` |
| `VECTRA_E2E_PORT`        | Puerto donde escucha (obligatorio; nunca 8080 ni 8081, que son de `run_service`)                     |

Escucha solo en `127.0.0.1`. La SPA lo ve como el mismo origen: el servidor de Vite pasa `/auth/**` y `/api/**` hasta aqui.
`/auth/**` es del emisor; todo lo demas es el BFF.

`VECTRA_E2E_DEMO=1` carga el mundo de `bff_e2e_world` (casos en cada estado, congelamiento con paquete, modelos con informe) en lugar del de
`bff_world`. **Control solo de pruebas** (U10-T04, Paso 15): `/__e2e/**`, que NO pasa por el proxy de la SPA (la prueba le habla al puerto de los
dobles) y que el BFF real no tiene:

| Ruta                                      | Efecto                                                                                          |
|-------------------------------------------|-------------------------------------------------------------------------------------------------|
| `POST /__e2e/reset`                       | deja los dobles como al arrancar (estado, caidas, llamadas contadas) y apaga lo de abajo           |
| `POST /__e2e/down` `{double, down}`       | tumba (o levanta) un doble: `case`, `governance`, `registry`, `explainability` o `bias`           |
| `POST /__e2e/force-mfa-required` `{times}`| las proximas `times` resoluciones de congelamiento responden 403 `mfa_required` (el 403 inesperado) |
| `GET /__e2e/count?double=&method=&template=` | cuantas llamadas recibio el doble (p. ej. `POST /v1/cases/{id}/explanation-views`)                |
"""

import os
import sys
from pathlib import Path
from typing import Any, Final

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

_HERE = Path(__file__).resolve()
for _path in (_HERE.parent, _HERE.parents[2] / "src", _HERE.parents[4] / "contracts" / "tests"):  # noqa: E402
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import bff_tokens  # noqa: E402
import uvicorn  # noqa: E402
from bff_doubles import Doubles, Override, problem  # noqa: E402
from bff_oidc import OidcIssuer  # noqa: E402
from bff_e2e_world import populate_demo  # noqa: E402
from bff_world import populate  # noqa: E402
from strategies import auth as u0  # noqa: E402
from vectra_common.authn import Authenticator  # noqa: E402
from vectra_common.jwks_cache import JwksCache  # noqa: E402

from console_bff.app import build  # noqa: E402

FORBIDDEN_PORTS: Final = (8080, 8081)
ISSUER_PREFIX: Final = "/auth/"
CONTROL_PREFIX: Final = "/__e2e/"


class Server:
    """Despachador ASGI: `/auth/**` al emisor, `/__e2e/**` al control de pruebas, todo lo demas (y el ciclo de vida) al BFF."""

    def __init__(self, issuer: OidcIssuer, bff: Any, doubles: Doubles, *, demo: bool = False) -> None:
        self.issuer = issuer
        self.bff = bff
        self.doubles = doubles
        self.demo = demo
        self.force_mfa_required = 0
        self._issuer_app = issuer.app()
        self._control_app = Starlette(
            routes=[
                Route(f"{CONTROL_PREFIX}reset", self._reset, methods=["POST"]),
                Route(f"{CONTROL_PREFIX}down", self._down, methods=["POST"]),
                Route(f"{CONTROL_PREFIX}force-mfa-required", self._force_mfa, methods=["POST"]),
                Route(f"{CONTROL_PREFIX}count", self._count),
            ]
        )

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.bff(scope, receive, send)
        elif scope["path"].startswith(ISSUER_PREFIX):
            await self._issuer_app(scope, receive, send)
        elif scope["path"].startswith(CONTROL_PREFIX):
            await self._control_app(scope, receive, send)
        elif (
            self.force_mfa_required > 0
            and scope["method"] == "POST"
            and scope["path"].endswith("/frozen-resolution")
        ):
            self.force_mfa_required -= 1  # el 403 inesperado: el BFF real lo da cuando el plazo de MFA vence entre la lectura y el envio
            response = JSONResponse(
                problem(403, "mfa_required"), status_code=403, media_type="application/problem+json"
            )
            await response(scope, receive, send)
        else:
            await self.bff(scope, receive, send)

    # ---- control solo de pruebas ----------------------------------------------------------------------------------------
    def populate(self) -> None:
        (populate_demo if self.demo else populate)(self.doubles)

    async def _reset(self, _: Request) -> Response:
        for double in self.doubles.transports().values():
            double.default = Override()
            double.overrides.clear()
            double.calls.clear()
        self.force_mfa_required = 0
        self.populate()
        return JSONResponse({})

    async def _down(self, request: Request) -> Response:
        body = await request.json()
        double = self.doubles.transports().get(body.get("double"))
        if double is None:
            return JSONResponse({"error": "double"}, status_code=400)
        double.default = Override(down=True) if body.get("down", True) else Override()
        return JSONResponse({})

    async def _force_mfa(self, request: Request) -> Response:
        self.force_mfa_required = int((await request.json()).get("times", 1))
        return JSONResponse({})

    async def _count(self, request: Request) -> Response:
        double = self.doubles.transports().get(request.query_params.get("double", ""))
        if double is None:
            return JSONResponse({"error": "double"}, status_code=400)
        count = double.count(request.query_params.get("method"), request.query_params.get("template"))
        return JSONResponse({"count": count})


def build_server(origin: str, *, access_ttl: int = 300, demo: bool = False) -> Server:
    """El BFF real (30 rutas, dobles en los cinco destinos) validando los tokens del emisor de prueba."""
    doubles = Doubles()
    issuer = OidcIssuer(origin=origin, access_ttl=access_ttl)

    async def jwks() -> Any:
        return u0.jwks_document()

    authenticator = Authenticator(issuer=issuer.issuer, audience=bff_tokens.AUDIENCE, jwks=JwksCache(jwks))
    bff = build(doubles.urls(), authenticator=authenticator, transports=doubles.transports())
    server = Server(issuer, bff, doubles, demo=demo)
    server.populate()
    return server


def main() -> None:
    port = int(os.environ["VECTRA_E2E_PORT"])
    if port in FORBIDDEN_PORTS:
        raise SystemExit(f"el puerto {port} es de run_service: elige otro")
    server = build_server(os.environ["VECTRA_E2E_ORIGIN"], demo=os.environ.get("VECTRA_E2E_DEMO") == "1")
    uvicorn.run(server, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
