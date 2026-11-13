"""core-banking-mock (Paso 17; BR-U8-22; INF-U8-02, 03; P-U8-06; NFR-U8-26, 45; US-603). `python -m core_banking_mock.app` arranca.

FastAPI sin base de datos: los creditos salen de `credits.json` (`/app/fixtures/credits.json` en la imagen; las pruebas pasan el del
repositorio). `create_app` de U0 trae las dos rutas de `REGISTRY["core-banking-mock"]`, la autenticacion, la autorizacion y las
sondas (8081, `/metrics` incluido). Solo lectura: `GET /v1/credits/{id}`. `POST /v1/credits/{id}/status` existe solo para la
demostracion de RT-5 y siempre responde 403: el scope `core:write-credit` no lo tiene nadie, y aun con un token que lo trajera el
handler rechaza. No importa `vectra_case` ni `httpx` (los clientes son de `case-service`).
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, cast

from fastapi import FastAPI
from vectra_common.app_factory import Handler, RequestContext, create_app
from vectra_common.authn import Authenticator, authenticator_from_env
from vectra_common.errors import Forbidden, NotFound
from vectra_common.ops_server import run_service
from vectra_contracts.catalog import CreditStatus
from vectra_contracts.models.api import CreditStatusView

from core_banking_mock.auth import SERVICE, LazyEnvAuthenticator, WriteAttemptMiddleware

DEFAULT_FIXTURES: Final = Path("/app/fixtures/credits.json")


def load_credits(path: Path) -> dict[str, CreditStatus]:
    """`Credit` de domain-entities §5: `case_id`, `status` y `updated_at`; aqui solo importan los dos primeros."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["case_id"]): CreditStatus(row["status"]) for row in rows}


def handlers(fixtures: Path) -> Mapping[tuple[str, str], Handler]:
    credits: dict[str, CreditStatus] = {}

    async def get_credit(ctx: RequestContext) -> CreditStatusView:
        if not credits:  # carga perezosa: `build_app()` no necesita el archivo
            credits.update(load_credits(fixtures))
        credit_id = ctx.path_params["id"]
        status = credits.get(credit_id)
        if status is None:
            raise NotFound()
        return CreditStatusView(credit_id=credit_id, status=status)

    async def write_credit(_: RequestContext) -> None:
        raise Forbidden()  # la escritura del mock se rechaza siempre (AUTONOMIA-03)

    return {
        ("GET", "/v1/credits/{id}"): get_credit,
        ("POST", "/v1/credits/{id}/status"): write_credit,
    }


def build_app(authenticator: Any = None, *, fixtures: Path = DEFAULT_FIXTURES) -> FastAPI:
    app = create_app(
        SERVICE,
        handlers=handlers(fixtures),
        authenticator=authenticator or cast(Authenticator, LazyEnvAuthenticator()),
    )
    app.add_middleware(WriteAttemptMiddleware)  # el mas externo: ve la respuesta final
    return app


def main() -> None:
    run_service(build_app(authenticator_from_env(SERVICE)))


if __name__ == "__main__":
    main()
