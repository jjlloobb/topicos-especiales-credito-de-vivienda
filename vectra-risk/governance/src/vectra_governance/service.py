"""Punto de entrada de `governance-service` (puertos 8080 y 8081; Paso 10 de U4, completado en U04-T08).

La configuracion llega por variables de entorno. Las **obligatorias** son exactamente las que pone el Deployment del chart
(`governance/chart/templates/service.yaml`); una prueba compara los nombres con el render. Si falta una, el servicio no arranca y
el mensaje la nombra.

| Variable                                          | Uso                                                                      |
|---------------------------------------------------|--------------------------------------------------------------------------|
| `GOVERNANCE_DATABASE_DSN`, `PGUSER`, `PGPASSWORD` | `governance-db` (F41); libpq lee el usuario y la clave del entorno         |
| `GOVERNANCE_S3_ENDPOINT`, `_ACCESS_KEY`, `_SECRET_KEY` | model-store (F47), credencial `minio-governance`                     |
| `GOVERNANCE_VALIDATION_IMAGE`, `_DATASET`         | imagen y dataset del `model-validation-job`                              |
| `GOVERNANCE_CALLBACK_URL`                         | a donde el Job devuelve el informe (F32)                                 |
| `GOVERNANCE_JOB_S3_ENDPOINT`, `GOVERNANCE_JOB_TOKEN_URL` | endpoint S3 y URL del token que recibe el Job |
| `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL`, `VECTRA_CA_BUNDLE` | validacion de tokens (U0, F50)                                 |

El chart (U04-T08, ronda 2) tambien entrega `GOVERNANCE_REGISTRY_URL` (F24), `GOVERNANCE_BIAS_URL` (F25), `VECTRA_CLIENT_ID`,
`VECTRA_CLIENT_KEY_PATH` (la llave `private_key_jwt` montada de solo lectura) y `VECTRA_TOKEN_URL` (el token propio; `GOVERNANCE_JOB_TOKEN_URL`
es solo para el Job). Sin valores por omision. **Opcionales**: `VECTRA_CLIENT_KEY_ID` y `GOVERNANCE_REPLICA` (por omision `HOSTNAME`). Si la llave
no existe al arrancar, el servicio avisa (`log.warning`), sirve `serving-config` y las transiciones quedan `pendiente_registro` (503; P-U4-03).

El cliente de Kubernetes (K01) es in-cluster: `KUBERNETES_SERVICE_HOST`/`_PORT`, el token del ServiceAccount y su CA, leidos en
cada llamada. Fuera del cluster (un `docker run`) crear un Job falla con 503, no al arrancar.
"""

import asyncio
import logging
import os
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from fastapi import FastAPI
from vectra_common.authn import Authenticator, authenticator_from_env
from vectra_common.errors import DependencyUnavailable
from vectra_common.ops_server import run_service
from vectra_common.service_token import ServiceTokenProvider
from vectra_contracts.catalog import Scope

from vectra_governance.api import SERVICE, ApiConfig, ApiDeps, create_governance_app
from vectra_governance.background import Background
from vectra_governance.clients import HttpSourceComparer
from vectra_governance.convergence import ServingConfigCache
from vectra_governance.evidence import Evidence, HttpRegistryClient, RegistryUnavailable
from vectra_governance.k8s_jobs import KubernetesJobs
from vectra_governance.pools import Pools
from vectra_governance.s3_store import S3PackageStore

log = logging.getLogger(__name__)

#: Variables que el chart pone en el Deployment y que el servicio exige.
REQUIRED: Final = (
    "GOVERNANCE_DATABASE_DSN",
    "PGUSER",
    "PGPASSWORD",
    "GOVERNANCE_S3_ENDPOINT",
    "GOVERNANCE_S3_ACCESS_KEY",
    "GOVERNANCE_S3_SECRET_KEY",
    "GOVERNANCE_VALIDATION_IMAGE",
    "GOVERNANCE_VALIDATION_DATASET",
    "GOVERNANCE_CALLBACK_URL",
    "GOVERNANCE_JOB_S3_ENDPOINT",
    "GOVERNANCE_JOB_TOKEN_URL",
    "GOVERNANCE_REGISTRY_URL",
    "GOVERNANCE_BIAS_URL",
    "VECTRA_CLIENT_ID",
    "VECTRA_CLIENT_KEY_PATH",
    "VECTRA_TOKEN_URL",
    "VECTRA_ASSERTION_AUDIENCE",
    "VECTRA_OIDC_ISSUER",
    "VECTRA_JWKS_URL",
    "VECTRA_CA_BUNDLE",
)
#: Variables opcionales (el chart no las pone): el id de la llave y el nombre de la replica.
OPTIONAL: Final = ("VECTRA_CLIENT_KEY_ID", "GOVERNANCE_REPLICA")
SERVICEACCOUNT: Final = Path("/var/run/secrets/kubernetes.io/serviceaccount")
REGISTRY_AUDIENCE: Final = "decision-registry-service"
BIAS_AUDIENCE: Final = "bias-monitoring-service"

TokenFactory = Callable[[str, tuple[Scope, ...]], Callable[[], str]]


class ConfigError(Exception):
    """Falta una variable obligatoria. El mensaje las nombra (nunca lleva sus valores)."""


@dataclass(frozen=True)
class ServiceConfig:
    dsn: str
    replica: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    ca_bundle: str
    api: ApiConfig
    registry_url: str
    bias_url: str
    client_id: str
    client_key_path: str
    client_key_id: str | None
    token_url: str
    assertion_audience: str


def config_from_env(environ: Mapping[str, str] | None = None) -> ServiceConfig:
    env = os.environ if environ is None else environ
    missing = [name for name in REQUIRED if not env.get(name)]
    if missing:
        raise ConfigError(f"faltan variables de entorno obligatorias: {', '.join(missing)}")
    return ServiceConfig(
        dsn=env["GOVERNANCE_DATABASE_DSN"],
        replica=env.get("GOVERNANCE_REPLICA") or env.get("HOSTNAME") or "local",
        s3_endpoint=env["GOVERNANCE_S3_ENDPOINT"],
        s3_access_key=env["GOVERNANCE_S3_ACCESS_KEY"],
        s3_secret_key=env["GOVERNANCE_S3_SECRET_KEY"],
        ca_bundle=env["VECTRA_CA_BUNDLE"],
        api=ApiConfig(
            validation_image=env["GOVERNANCE_VALIDATION_IMAGE"],
            validation_dataset=env["GOVERNANCE_VALIDATION_DATASET"],
            callback_url=env["GOVERNANCE_CALLBACK_URL"],
            job_s3_endpoint=env["GOVERNANCE_JOB_S3_ENDPOINT"],
            job_token_url=env["GOVERNANCE_JOB_TOKEN_URL"],
            assertion_audience=env["VECTRA_ASSERTION_AUDIENCE"],
        ),
        registry_url=env["GOVERNANCE_REGISTRY_URL"],
        bias_url=env["GOVERNANCE_BIAS_URL"],
        client_id=env["VECTRA_CLIENT_ID"],
        client_key_path=env["VECTRA_CLIENT_KEY_PATH"],
        client_key_id=env.get("VECTRA_CLIENT_KEY_ID") or None,
        token_url=env["VECTRA_TOKEN_URL"],
        assertion_audience=env["VECTRA_ASSERTION_AUDIENCE"],
    )


def service_tokens(config: ServiceConfig) -> TokenFactory:
    """Token de servicio sincrono (`private_key_jwt`, U0) para los clientes `httpx` sincronos. La llave se lee al primer uso:
    sin ella el servicio arranca y la llamada falla con `DependencyUnavailable` (no con un 500)."""

    def factory(audience: str, scopes: tuple[Scope, ...]) -> Callable[[], str]:
        lock = threading.Lock()
        provider: ServiceTokenProvider | None = None

        def token() -> str:
            nonlocal provider
            with lock:  # una sola llamada a la vez: el proveedor guarda el token y lo renueva
                if provider is None:
                    try:
                        key = Path(config.client_key_path).read_text(encoding="utf-8")
                    except OSError as error:
                        raise DependencyUnavailable() from error
                    provider = ServiceTokenProvider(
                        config.client_id,
                        config.token_url,
                        key,
                        audience,
                        tuple(scope.value for scope in scopes),
                        assertion_audience=config.assertion_audience,
                        key_id=config.client_key_id,
                    )
                return asyncio.run(provider.token())

        return token

    return factory


def kubernetes_client(environ: Mapping[str, str]) -> KubernetesJobs:
    """K01 in-cluster: la API en `KUBERNETES_SERVICE_HOST`, el token (que rota) y la CA del ServiceAccount."""
    host = environ.get("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
    port = environ.get("KUBERNETES_SERVICE_PORT", "443")
    ca = SERVICEACCOUNT / "ca.crt"

    def token() -> str:
        try:
            return (SERVICEACCOUNT / "token").read_text(encoding="utf-8").strip()
        except OSError as error:
            raise DependencyUnavailable() from error

    return KubernetesJobs(f"https://{host}:{port}", token, verify=str(ca) if ca.is_file() else True)


def build_app(
    environ: Mapping[str, str] | None = None,
    *,
    authenticator: Authenticator | None = None,
    tokens: TokenFactory | None = None,
) -> FastAPI:
    """Arma `ApiDeps` desde el entorno y la app. `authenticator` y `tokens` son para las pruebas (por omision, Keycloak de U0).

    La validacion de tokens (`authenticator_from_env`) lee `os.environ`; `environ` solo reemplaza al resto de la configuracion."""
    env = os.environ if environ is None else environ
    config = config_from_env(env)
    if not Path(config.client_key_path).is_file():
        log.warning(
            "no existe la llave del cliente %s: el servicio sirve serving-config, pero no puede firmar el token del registro "
            "(las transiciones quedan pendiente_registro)",
            config.client_id,
        )
    if authenticator is None:
        authenticator = authenticator_from_env(SERVICE)  # lee `os.environ` (U0): issuer, JWKS y CA
    make_token = tokens or service_tokens(config)
    pools = Pools(config.dsn, config.replica)
    registry_token = make_token(REGISTRY_AUDIENCE, (Scope.REGISTRY_APPEND_GOVERNANCE,))

    def registry_bearer() -> str:
        try:
            return registry_token()
        except DependencyUnavailable as error:
            raise RegistryUnavailable() from error

    evidence = Evidence(pools, HttpRegistryClient(config.registry_url, registry_bearer))
    jobs = kubernetes_client(env)
    deps = ApiDeps(
        evidence=evidence,
        cache=ServingConfigCache(pools, clock=evidence.clock),
        store=S3PackageStore(
            config.s3_endpoint,
            config.s3_access_key,
            config.s3_secret_key,
            verify=config.ca_bundle if config.s3_endpoint.startswith("https://") else True,
        ),
        jobs=jobs,
        comparer=HttpSourceComparer(config.bias_url, make_token(BIAS_AUDIENCE, (Scope.BIAS_COMPARE,))),
        config=config.api,
        background=Background(evidence, jobs),
    )
    return create_governance_app(deps, authenticator=authenticator)


def main() -> None:
    run_service(build_app())


__all__ = ["REQUIRED", "ConfigError", "ServiceConfig", "build_app", "config_from_env", "main"]

if __name__ == "__main__":  # pragma: no cover
    main()
