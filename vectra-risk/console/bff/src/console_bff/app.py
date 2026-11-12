"""Punto de entrada de `console-bff` (puertos 8080 y 8081): `python -m console_bff.app` (INF-U10-01; NFR-U10-60).

La configuracion llega **solo** por variables de entorno (las pone el `ConfigMap` del chart, Paso 18 de U10-T04). Si falta una
obligatoria, o hay una URL `https` sin `VECTRA_CA_BUNDLE`, el proceso termina con codigo 2 y el mensaje la nombra, antes de escuchar.

| Variable                                | Uso                                                              |
|-----------------------------------------|------------------------------------------------------------------|
| `VECTRA_CASE_URL`                       | `case-service` (U8)                                              |
| `VECTRA_GOVERNANCE_URL`                 | `governance-service` (U4)                                        |
| `VECTRA_REGISTRY_URL`                   | `decision-registry-service` (U3)                                 |
| `VECTRA_EXPLAINABILITY_URL`             | `explainability-service` (U7)                                    |
| `VECTRA_BIAS_URL`                       | `bias-monitoring-service` (U9)                                   |
| `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL` | validacion de los tokens de entrada (U0)                         |
| `VECTRA_CA_BUNDLE` (opcional)           | CA para cualquiera de las URL anteriores con `https`             |

Las sondas son solo del proceso (`readiness=None`): cada destino tiene su propio circuito, asi que `/readyz` es 200 con todos
caidos (INF-U10-01). Al apagar, `run_service` espera <= 10 s (`GRACEFUL_SHUTDOWN` de U0) y se cierran los cinco clientes.
El `preStop` de 5 s y `terminationGracePeriodSeconds` los pone el chart (Paso 18, P-5 (a)).
"""

import os
import signal
import sys
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Final

from fastapi import FastAPI
from vectra_common import process
from vectra_common.app_factory import create_app
from vectra_common.authn import Authenticator
from vectra_common.ops_server import run_service
from vectra_contracts.errors import ContractViolation

from console_bff.clients import DESTINATIONS, Upstreams
from console_bff.routes import SERVICE, build_handlers, verify_object_rules

URL_VARIABLES: Final = {
    "case": "VECTRA_CASE_URL",
    "governance": "VECTRA_GOVERNANCE_URL",
    "registry": "VECTRA_REGISTRY_URL",
    "explainability": "VECTRA_EXPLAINABILITY_URL",
    "bias": "VECTRA_BIAS_URL",
}
#: Las obligatorias son exactamente las que pondra el `ConfigMap` del chart (U10-T04 compara los nombres).
REQUIRED: Final = (*URL_VARIABLES.values(), "VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL")
OPTIONAL: Final = ("VECTRA_CA_BUNDLE",)
EXIT_CONFIG: Final = 2


class ConfigError(Exception):
    """Falta una variable obligatoria o algo de la configuracion no se puede usar. El mensaje la nombra, nunca su valor."""


def urls_from_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Las URL de los cinco destinos. Falla si falta una obligatoria o si hay `https` sin `VECTRA_CA_BUNDLE`."""
    env = os.environ if environ is None else environ
    missing = [name for name in REQUIRED if not env.get(name)]
    if missing:
        raise ConfigError(f"faltan variables de entorno obligatorias: {', '.join(missing)}")
    secure = [
        name for name in (*URL_VARIABLES.values(), "VECTRA_JWKS_URL") if env[name].startswith("https://")
    ]
    if secure and not env.get("VECTRA_CA_BUNDLE"):
        raise ConfigError("falta VECTRA_CA_BUNDLE: hay URL https y la verificacion nunca se desactiva")
    return {destination: env[URL_VARIABLES[destination]] for destination in DESTINATIONS}


def build(
    urls: Mapping[str, str],
    *,
    authenticator: Authenticator | None = None,
    transports: Mapping[str, Any]
    | None = None,  # un `httpx.AsyncBaseTransport` por destino (las pruebas): sin importar httpx
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    """`create_app` con las 30 rutas, los cinco clientes **con breaker** y la readiness solo del proceso."""
    verify_object_rules()  # antes de crear clientes: una ruta sin regla declarada no arranca (P-U10-01)
    process.ensure_service()
    upstreams = Upstreams(urls, transports=transports, wall_clock=clock)
    app = create_app(
        SERVICE, handlers=build_handlers(upstreams), authenticator=authenticator, readiness=None, clock=clock
    )
    app.state.upstreams = upstreams

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> Any:
        try:
            yield
        finally:
            await upstreams.aclose()

    app.router.lifespan_context = lifespan
    return app


def build_app() -> FastAPI:
    return build(urls_from_env())


def _exit_clean(_signum: int, _frame: object) -> None:
    """uvicorn, tras un apagado ordenado por una senal, **vuelve a emitirla** con el manejador que tenia antes: con el de
    fabrica el proceso moriria con `-SIGTERM` aunque todo cerro bien. Con este, el apagado ordenado termina con codigo 0
    (INF-U10-01: `SIGTERM` -> codigo 0 en <= 10 s). Una senal que llegue antes de escuchar tambien termina con 0."""
    raise SystemExit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, _exit_clean)
    try:
        app = build_app()
    except (ConfigError, ContractViolation) as error:
        sys.stderr.write(f"console-bff no arranca: {error}\n")
        raise SystemExit(EXIT_CONFIG) from None
    run_service(app)


__all__ = ["REQUIRED", "ConfigError", "build", "build_app", "main", "urls_from_env"]

if (
    __name__ == "__main__"
):  # pragma: no cover - el arranque real lo prueba `test_service_shutdown.py` en un proceso aparte
    main()
