"""Arranque de case-service (Paso 13; INF-U8-04, 06; NFR-U8-21, 22). `python -m vectra_case.app` es el punto de entrada.

- `build_app(settings=None, ...)` arma la app con `create_app` de U0 (las 9 rutas) sin leer el entorno ni abrir conexiones; los
  servicios se crean al arrancar (lifespan) o se inyectan (pruebas).
- Readiness (`/readyz`) solo mira `case-db`: governance, scoring, registro y core caidos no la afectan (P-U8-03).
- Al recibir `SIGTERM`, barridos, reconciliador y gauges dejan de tomar trabajo y terminan el lote en curso.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any, Final, cast

from fastapi import FastAPI
from vectra_common import service_token
from vectra_common.app_factory import create_app
from vectra_common.authn import Authenticator, authenticator_from_env
from vectra_common.ops_server import run_service
from vectra_contracts.models.api import Principal

from vectra_case import metrics
from vectra_case.api import Services, handlers
from vectra_case.credit import CreditReader
from vectra_case.db import Database, ready_probe
from vectra_case.db_gauges import DbGauges
from vectra_case.evidence import Evidence, Reconciler, RegistryClient
from vectra_case.governance_client import ServingConfigClient
from vectra_case.sweeps import Sweeper

SERVICE: Final = "case-service"
_TRUE: Final = {"true": True, "false": False}


@dataclass(frozen=True)
class Settings:
    """Variables obligatorias del Deployment (INF-U8-07): se leen del entorno y no hay valores por omision."""

    db_dsn: str
    governance_url: str
    registry_url: str
    core_enabled: bool
    core_url: str | None
    allow_test_scenarios: bool

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        e = env if env is not None else dict(os.environ)

        def flag(name: str) -> bool:
            value = e[name].lower()
            if value not in _TRUE:
                raise ValueError(f"{name} debe ser true o false")
            return _TRUE[value]

        core_enabled = flag("CASE_CORE_ENABLED")
        return cls(
            db_dsn=e["CASE_DB_DSN"],
            governance_url=e["CASE_GOVERNANCE_URL"],
            registry_url=e["CASE_REGISTRY_URL"],
            core_enabled=core_enabled,
            core_url=e["CASE_CORE_URL"] if core_enabled else None,
            allow_test_scenarios=flag("CASE_ALLOW_TEST_SCENARIOS"),
        )


@dataclass
class Background:
    reconciler: Reconciler
    sweeper: Sweeper
    gauges: DbGauges
    db: Database
    registry: RegistryClient
    governance: ServingConfigClient
    credit: CreditReader
    tasks: list["asyncio.Task[None]"]

    def stop(self) -> None:
        self.reconciler.stop()
        self.sweeper.stop()
        self.gauges.stop()


def build_services(settings: Settings) -> tuple[Services, Background]:
    db = Database(settings.db_dsn)
    registry = RegistryClient(
        settings.registry_url,
        service_token.provider_from_env("decision-registry-service", ("registry:append:case",)),
    )
    governance = ServingConfigClient(
        settings.governance_url,
        service_token.provider_from_env("governance-service", ("governance:read-serving",)),
    )
    credit = CreditReader(
        settings.core_enabled,
        settings.core_url,
        service_token.provider_from_env("core-banking-mock", ("core:read-credit",))
        if settings.core_enabled
        else None,
    )
    evidence = Evidence(db, registry)
    services = Services(db, evidence, credit, settings.allow_test_scenarios)
    background = Background(
        Reconciler(evidence), Sweeper(db, governance), DbGauges(db), db, registry, governance, credit, []
    )
    return services, background


class _LazyEnvAuthenticator:
    """Sin autenticador inyectado, `build_app()` no lee el entorno; el primer uso si (y sin variables, ninguna solicitud autentica)."""

    def __init__(self) -> None:
        self._real: Authenticator | None = None

    async def authenticate(self, authorization: str | None) -> Principal:
        if self._real is None:
            self._real = authenticator_from_env(SERVICE)
        return await self._real.authenticate(authorization)


def build_app(
    settings: Settings | None = None,
    *,
    authenticator: Any = None,
    services: Services | None = None,
    **create_kwargs: Any,
) -> FastAPI:
    holder: dict[str, Settings | None] = {"settings": settings}

    def readiness() -> bool:
        s = holder["settings"]
        return s is not None and ready_probe(s.db_dsn)

    app = create_app(
        SERVICE,
        handlers=handlers(),
        authenticator=authenticator or cast(Authenticator, _LazyEnvAuthenticator()),
        readiness=readiness,
        **create_kwargs,
    )
    app.state.services = services
    app.state.settings = settings
    app.state.background = None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        background: Background | None = None
        if app.state.services is None and settings is not None:
            app.state.services, background = build_services(settings)
            app.state.background = background
            background.tasks = [
                asyncio.create_task(background.reconciler.run_forever()),
                asyncio.create_task(background.sweeper.run_forever()),
                asyncio.create_task(background.gauges.run_forever()),
            ]
        try:
            yield
        finally:
            if background is not None:
                background.stop()
                await asyncio.gather(*background.tasks, return_exceptions=True)
                for closer in (
                    background.registry.aclose,
                    background.governance.aclose,
                    background.credit.aclose,
                    background.db.close,
                ):
                    with suppress(Exception):
                        await closer()

    app.router.lifespan_context = lifespan
    metrics.init_series()
    return app


def main() -> None:
    settings = Settings.from_env()
    run_service(build_app(settings, authenticator=authenticator_from_env(SERVICE)))


if __name__ == "__main__":
    main()
