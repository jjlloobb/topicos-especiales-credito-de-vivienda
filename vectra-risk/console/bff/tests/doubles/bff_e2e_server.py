"""Servidor de las pruebas con navegador (P-1 (a) de U10-T03; solo pruebas): el BFF real con los dobles de los cinco destinos y el
emisor OIDC de prueba (`bff_oidc`) en **un solo proceso**.

`python console/bff/tests/doubles/bff_e2e_server.py` (desde `vectra-risk/`). Variables de entorno:

| Variable                 | Uso                                                                                                  |
|--------------------------|------------------------------------------------------------------------------------------------------|
| `VECTRA_E2E_ORIGIN`      | Origen publico de la SPA (p. ej. `http://127.0.0.1:47173`): es el `iss` de los tokens y el de los `redirect_uri` |
| `VECTRA_E2E_PORT`        | Puerto donde escucha (obligatorio; nunca 8080 ni 8081, que son de `run_service`)                     |

Escucha solo en `127.0.0.1`. La SPA lo ve como el mismo origen: el servidor de Vite pasa `/auth/**` y `/api/**` hasta aqui.
`/auth/**` es del emisor; todo lo demas es el BFF.
"""

import os
import sys
from pathlib import Path
from typing import Any, Final

_HERE = Path(__file__).resolve()
for _path in (_HERE.parent, _HERE.parents[2] / "src", _HERE.parents[4] / "contracts" / "tests"):  # noqa: E402
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import bff_tokens  # noqa: E402
import uvicorn  # noqa: E402
from bff_doubles import Doubles  # noqa: E402
from bff_oidc import OidcIssuer  # noqa: E402
from bff_world import populate  # noqa: E402
from strategies import auth as u0  # noqa: E402
from vectra_common.authn import Authenticator  # noqa: E402
from vectra_common.jwks_cache import JwksCache  # noqa: E402

from console_bff.app import build  # noqa: E402

FORBIDDEN_PORTS: Final = (8080, 8081)
ISSUER_PREFIX: Final = "/auth/"


class Server:
    """Despachador ASGI: `/auth/**` al emisor, todo lo demas (y el ciclo de vida) al BFF."""

    def __init__(self, issuer: OidcIssuer, bff: Any) -> None:
        self.issuer = issuer
        self.bff = bff
        self._issuer_app = issuer.app()

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope["path"].startswith(ISSUER_PREFIX):
            await self._issuer_app(scope, receive, send)
        else:
            await self.bff(scope, receive, send)


def build_server(origin: str, *, access_ttl: int = 300) -> Server:
    """El BFF real (30 rutas, dobles en los cinco destinos) validando los tokens del emisor de prueba."""
    doubles = Doubles()
    populate(doubles)
    issuer = OidcIssuer(origin=origin, access_ttl=access_ttl)

    async def jwks() -> Any:
        return u0.jwks_document()

    authenticator = Authenticator(issuer=issuer.issuer, audience=bff_tokens.AUDIENCE, jwks=JwksCache(jwks))
    bff = build(doubles.urls(), authenticator=authenticator, transports=doubles.transports())
    return Server(issuer, bff)


def main() -> None:
    port = int(os.environ["VECTRA_E2E_PORT"])
    if port in FORBIDDEN_PORTS:
        raise SystemExit(f"el puerto {port} es de run_service: elige otro")
    server = build_server(os.environ["VECTRA_E2E_ORIGIN"])
    uvicorn.run(server, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
