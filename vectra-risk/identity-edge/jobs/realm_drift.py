#!/usr/bin/env python3
"""CronJob diario `realm-drift` (U02-T08; BR-U2-12, INF-U2-09): compara el realm de Keycloak con Git y empuja la cuenta.

Lee el realm de Git (`REALM_FILE`, el ConfigMap montado), arma lo que Keycloak tiene por F94 y empuja
`vectra_realm_drift` (el numero de diferencias) con `PUT /metrics/job/realm-drift` (F112). Cualquier error termina el
proceso con codigo distinto de 0 y no empuja nada: una lectura fallida no es «0 diferencias».
"""

import asyncio
import logging
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

import keycloak_admin as admin
import realm_diff
import yaml

LOG = logging.getLogger("realm-drift")
JOB: Final = "realm-drift"
REALM_FILE_ENV: Final = "REALM_FILE"


def metrics_body(drift: int) -> bytes:
    return f"# TYPE vectra_realm_drift gauge\nvectra_realm_drift {drift}\n".encode()


def push_url(pushgateway: str) -> str:
    return f"{pushgateway.rstrip('/')}/metrics/job/{JOB}"


async def run(
    git: Mapping[str, Any], reader: admin.KeycloakReader, put: admin.HttpPut, pushgateway: str
) -> int:
    differences = realm_diff.diff(git, await reader.export(git))
    for difference in differences:  # solo la ruta y el tipo: los valores pueden ser configuracion del banco
        LOG.warning("diferencia %s en %s", difference.kind, difference.path)
    await put(push_url(pushgateway), metrics_body(len(differences)))
    return len(differences)


async def run_from_env(
    http_get: admin.HttpGet | None = None,
    http_put: admin.HttpPut | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    env = os.environ if environ is None else environ
    git = yaml.safe_load(Path(env[REALM_FILE_ENV]).read_text(encoding="utf-8"))
    reader = admin.KeycloakReader(admin.fetch_from_env(http_get or admin.urllib_get))
    return await run(git, reader, http_put or admin.urllib_put, env[admin.PUSHGATEWAY_URL_ENV])


def main(runner: Callable[[], Any] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run((runner or run_from_env)())
    except Exception:
        LOG.exception("realm-drift fallo")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
