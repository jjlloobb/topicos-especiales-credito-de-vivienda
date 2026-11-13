"""Barrera de entorno (U12 Paso 2; NFR-U12-03, NFR-U12-32; INF-U12-01; BR-U12-10).

Dos comprobaciones de entorno: la del entorno configurado (`issuer` y host del gateway), antes de cualquier solicitud, y la del `iss` de un token ya
obtenido. La comparacion es **exacta**: sin sufijos ni subcadenas, para que produccion no pase por parecerse a staging. Nada de U12 corre en produccion
(BR-U12-10): produccion no esta en la lista.

Secciones (NFR-U12-30, las 14): en kind, todas; en staging, solo `prepare` (sin el parche de los Jobs de prueba), `decisions` (maximo 100 casos), `u11` y
`report` (P-6, recomendacion (a)). La reactivacion de una version congelada solo se permite dentro de la seccion `rt2`.

Barrera horaria de `decisions` (P-2, recomendacion (a); NFR-U12-32): si no puede terminar antes de las 23:00 UTC del mismo dia, no empieza. La duracion se
estima como `volumen / ritmo + volumen * DECISION_SECONDS_PER_CASE + MARGIN_SECONDS`; las constantes son valores iniciales que se miden en el Paso 18. El reloj se
inyecta: este modulo no lee la hora del sistema.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Final

import httpx


class GuardError(Exception):
    """La barrera se niega; el mensaje empieza por un codigo estable y no lleva credenciales."""


@dataclass(frozen=True)
class Environment:
    name: str
    host: str
    issuer: str


# Tomados de `identity-edge/gateway/values/{kind,staging}.yaml` (linea 2) y de `generated/<env>/securitypolicies.yaml`; una prueba los compara.
KIND: Final = Environment("kind", "vectra.localtest.me", "https://vectra.localtest.me/auth/realms/vectra")
STAGING: Final = Environment(
    "staging", "vectra.staging.banco.internal", "https://vectra.staging.banco.internal/auth/realms/vectra"
)
ENVIRONMENTS: Final = (KIND, STAGING)

SECTIONS: Final = (
    "prepare", "network", "decisions", "rt1", "rt4", "rt5", "rt3", "rt2-setup", "rt2", "load", "pii", "u11", "resilience", "report",
)  # fmt: skip
STAGING_SECTIONS: Final = ("prepare", "decisions", "u11", "report")
STAGING_MAX_DECISIONS: Final = 100

CUTOFF: Final = time(23, 0)  # UTC
DECISION_SECONDS_PER_CASE: Final = 1.0
MARGIN_SECONDS: Final = 300.0
REACTIVATION_SECTION: Final = "rt2"


def check_known(environment: Environment) -> None:
    """El entorno debe ser **uno de** `ENVIRONMENTS` (la misma instancia): uno armado a mano con el nombre `kind` no pasa (F-04 de la revision de U12-T01)."""
    if not any(environment is known for known in ENVIRONMENTS):
        raise GuardError("environment_not_allowed")


def check_environment(issuer: str, gateway_host: str) -> Environment:
    """El entorno cuyo `issuer` y host coinciden exactamente con los configurados; si no hay, error (antes de cualquier solicitud)."""
    for environment in ENVIRONMENTS:
        if environment.host == gateway_host and environment.issuer == issuer:
            return environment
    raise GuardError("environment_not_allowed")


def check_token_issuer(environment: Environment, iss: str) -> None:
    """El `iss` de un token ya obtenido debe ser el del realm del entorno."""
    check_known(environment)
    if iss != environment.issuer:
        raise GuardError("token_issuer_not_allowed")


def gateway_client(
    issuer: str,
    gateway_host: str,
    transport: httpx.BaseTransport | None = None,
    verify: ssl.SSLContext | bool = True,
) -> httpx.Client:
    """Un cliente HTTP hacia el gateway, creado solo si el entorno pasa la barrera: sin ella no se envia ninguna solicitud. `verify` es la CA del entorno."""
    environment = check_environment(issuer, gateway_host)
    return httpx.Client(base_url=f"https://{environment.host}", transport=transport, verify=verify)


def check_section(environment: Environment, section: str) -> None:
    check_known(environment)
    if section not in SECTIONS:
        raise GuardError(f"section_unknown:{section}")
    if environment.name != KIND.name and section not in STAGING_SECTIONS:
        raise GuardError(f"section_denied_in_{environment.name}:{section}")


def check_job_patch(environment: Environment) -> None:
    """El parche de los Jobs de prueba (seccion `prepare`) solo existe en kind."""
    check_section(environment, "prepare")
    if environment.name != KIND.name:
        raise GuardError(f"job_patch_denied_in_{environment.name}")


def check_reactivation(environment: Environment, section: str) -> None:
    """La reactivacion desde la herramienta solo se permite dentro de la seccion `rt2`; U12-T02 la llama antes de `resolve_frozen`."""
    check_section(environment, section)
    if section != REACTIVATION_SECTION:
        raise GuardError(f"reactivation_outside_rt2:{section}")


def estimated_duration(volume: int, rate: float) -> timedelta:
    if volume < 0 or rate <= 0:
        raise GuardError("decisions_volume_or_rate_invalid")
    return timedelta(seconds=volume / rate + volume * DECISION_SECONDS_PER_CASE + MARGIN_SECONDS)


def check_decisions(environment: Environment, now: datetime, volume: int, rate: float) -> None:
    """`decisions` no empieza si no puede terminar antes de las 23:00 UTC del mismo dia; en staging, maximo 100 casos."""
    check_section(environment, "decisions")
    if environment.name != KIND.name and volume > STAGING_MAX_DECISIONS:
        raise GuardError(f"decisions_volume_over_{STAGING_MAX_DECISIONS}_in_{environment.name}")
    if now.utcoffset() is None:
        raise GuardError("clock_without_timezone")
    start = now.astimezone(UTC)
    cutoff = datetime.combine(start.date(), CUTOFF, tzinfo=UTC)
    if start + estimated_duration(volume, rate) > cutoff:
        raise GuardError("decisions_would_end_after_23_utc")
