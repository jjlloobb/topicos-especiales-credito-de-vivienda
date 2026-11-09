"""Punto de entrada de `decision-registry-service` (puertos 8080 y 8081).

La configuracion llega por variables de entorno (las llena el chart del Bloque F con los Secrets de ESO):

- `REGISTRY_RW_APP_DSN`: primaria con `registry_app` (pools `append` y `dossier`);
- `REGISTRY_RW_HEALTH_DSN`: primaria con `registry_health` (pool `health`);
- `REGISTRY_RO_VERIFIER_DSN`: replica `-ro` con `registry_verifier` (pool `projections`);
- `REGISTRY_CHECKPOINT_PUBLIC_KEYS`: llaves publicas Ed25519 de checkpoints, en base64 de los 32 bytes crudos, separadas por comas.

El servicio no tiene acceso a la boveda ni al bucket WORM (P-U3-08): las llaves publicas le llegan como configuracion.
"""

import base64
import os

from fastapi import FastAPI
from vectra_common.ops_server import run_service

from vectra_registry.api import SERVICE, ServiceConfig, create_service_app
from vectra_registry.pools import Pools


def config_from_env() -> tuple[Pools, ServiceConfig]:
    dsns = {
        "append": os.environ["REGISTRY_RW_APP_DSN"],
        "dossier": os.environ["REGISTRY_RW_APP_DSN"],
        "health": os.environ["REGISTRY_RW_HEALTH_DSN"],
        "projections": os.environ["REGISTRY_RO_VERIFIER_DSN"],
    }
    raw = os.environ.get("REGISTRY_CHECKPOINT_PUBLIC_KEYS", "")
    keys = [base64.b64decode(part, validate=True) for part in raw.split(",") if part.strip()]
    return Pools.build(dsns), ServiceConfig(public_keys=keys)


def build_app() -> FastAPI:
    pools, config = config_from_env()
    return create_service_app(pools, config)


def main() -> None:
    run_service(build_app())


__all__ = ["SERVICE", "build_app", "config_from_env", "main"]

if __name__ == "__main__":  # pragma: no cover
    main()
