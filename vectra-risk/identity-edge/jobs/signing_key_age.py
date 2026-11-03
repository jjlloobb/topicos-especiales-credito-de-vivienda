#!/usr/bin/env python3
"""CronJob horario `signing-key-age` (U02-T08; P-U2-05, INF-U2-09, decision R4): fecha de creacion de la llave de firma activa.

Elige, en `GET /admin/realms/vectra/keys`, la llave `ACTIVE` de uso `SIG` con mayor prioridad del algoritmo de firma por
defecto del realm, y empuja el `notBefore` de su certificado como `vectra_signing_key_created_timestamp_seconds{kid,algorithm}`
con `PUT /metrics/job/signing-key-age` (F112). `SigningKeyAgeHigh` calcula `time() - metrica > 80 d`.
Sin llave elegible, sin certificado o con dos llaves empatadas, termina con codigo distinto de 0 y no empuja nada.
"""

import asyncio
import base64
import binascii
import logging
import os
import sys
from collections.abc import Callable, Mapping
from typing import Any, Final

import keycloak_admin as admin
from cryptography import x509

LOG = logging.getLogger("signing-key-age")
JOB: Final = "signing-key-age"
METRIC: Final = "vectra_signing_key_created_timestamp_seconds"


class NoSigningKey(Exception):
    """No hay una llave de firma activa de la que leer la fecha."""


def active_signing_key(keys: Mapping[str, Any], algorithm: str) -> Mapping[str, Any]:
    candidates = [
        k
        for k in keys.get("keys", [])
        if k.get("status") == "ACTIVE" and k.get("use") == "SIG" and k.get("algorithm") == algorithm
    ]
    if not candidates:
        raise NoSigningKey(f"ninguna llave ACTIVE de uso SIG con el algoritmo {algorithm}")
    top = max(int(k.get("providerPriority", 0)) for k in candidates)
    best = [k for k in candidates if int(k.get("providerPriority", 0)) == top]
    if len(best) != 1:
        raise NoSigningKey(f"{len(best)} llaves {algorithm} empatadas con la prioridad {top}")
    return best[0]


def created_at(key: Mapping[str, Any]) -> int:
    """El `notBefore` del certificado de la llave, en segundos."""
    certificate = key.get("certificate")
    if not certificate:
        raise NoSigningKey(f"la llave {key.get('kid')} no tiene certificado")
    try:
        parsed = x509.load_der_x509_certificate(base64.b64decode(certificate, validate=True))
    except (binascii.Error, ValueError) as exc:
        raise NoSigningKey(f"el certificado de la llave {key.get('kid')} no se puede leer") from exc
    return int(parsed.not_valid_before_utc.timestamp())


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def metrics_body(kid: str, algorithm: str, created: int) -> bytes:
    labels = f'kid="{_label(kid)}",algorithm="{_label(algorithm)}"'
    return f"# TYPE {METRIC} gauge\n{METRIC}{{{labels}}} {created}\n".encode()


def push_url(pushgateway: str) -> str:
    return f"{pushgateway.rstrip('/')}/metrics/job/{JOB}"


async def run(reader: admin.KeycloakReader, put: admin.HttpPut, pushgateway: str) -> int:
    realm = await reader.realm()
    algorithm = str(realm.get("defaultSignatureAlgorithm") or "").strip()
    if not algorithm:  # sin algoritmo no hay llave que elegir, y suponer uno falsearia la metrica
        raise NoSigningKey("el realm no trae defaultSignatureAlgorithm")
    key = active_signing_key(await reader.keys(), algorithm)
    created = created_at(key)
    await put(push_url(pushgateway), metrics_body(str(key["kid"]), algorithm, created))
    return created


async def run_from_env(
    http_get: admin.HttpGet | None = None,
    http_put: admin.HttpPut | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    env = os.environ if environ is None else environ
    reader = admin.KeycloakReader(admin.fetch_from_env(http_get or admin.urllib_get))
    return await run(reader, http_put or admin.urllib_put, env[admin.PUSHGATEWAY_URL_ENV])


def main(runner: Callable[[], Any] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run((runner or run_from_env)())
    except Exception:
        LOG.exception("signing-key-age fallo")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
