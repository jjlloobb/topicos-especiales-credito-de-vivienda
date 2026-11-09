"""API de `decision-registry-service` (Pasos 7 a 9 del plan; P-U0-12; BR-U3-03, 13b, 14, 15).

La app sale de `create_app` de U0 con las siete rutas del `RouteContract` de `decision-registry-service`
(`vectra_contracts.routes`): la autenticacion, la autorizacion por scope o rol, el limite de cuerpo y los `Problem` los pone la
fabrica. Aqui solo estan los handlers y el ciclo de vida (readiness, gauges y cierre de los pools).

Hacia la base se usa `psycopg` (no `deps.call`, que es para HTTP). La unica dependencia por HTTP de esta unidad es la bóveda
(Transit), y es de los CronJobs: el servicio de la API no tiene acceso a ella (P-U3-08).
"""

import json
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
from vectra_common.app_factory import Handler, RequestContext, create_app, respond
from vectra_common.authn import Authenticator
from vectra_common.errors import NotFound
from vectra_contracts.models.monitoring import MonitoringQuery
from vectra_contracts.models.registry import EntryFilter, IntegrityCheckRequest
from vectra_contracts.routes import REGISTRY

from vectra_registry import append, dossier, queries
from vectra_registry.health import Gauges, Health
from vectra_registry.pools import Pools

SERVICE = "decision-registry-service"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ServiceConfig:
    """Lo que el servicio necesita ademas de los pools: las llaves publicas de checkpoints (32 bytes crudos) y los relojes."""

    public_keys: Sequence[bytes] = ()
    clock: Callable[[], datetime] = _utc_now
    #: Solo para pruebas: reemplaza a `clock_timestamp()` de la base como fuente de `recorded_at`.
    db_clock: Callable[[], datetime] | None = None
    health: Health | None = None
    gauges: Gauges | None = field(default=None)


def _json(body: Any, status: int = 200) -> Response:
    return Response(json.dumps(body, ensure_ascii=False), status_code=status, media_type="application/json")


def handlers(pools: Pools, config: ServiceConfig) -> dict[tuple[str, str], Handler]:
    async def post_entry(ctx: RequestContext) -> BaseModel:
        assert ctx.body is not None  # noqa: S101 - el contrato declara `request_model`
        outcome = await append.append_authorized(
            pools,
            ctx.body,  # type: ignore[arg-type]
            ctx.principal.scopes,
            clock=ctx.request.app.state.clock,
            db_clock=config.db_clock,
        )
        return outcome.ack

    async def get_entries(ctx: RequestContext) -> Response:
        assert isinstance(ctx.query, EntryFilter)  # noqa: S101
        return _json(await queries.list_entries(pools, ctx.principal.scopes, ctx.query))

    async def daily_query(ctx: RequestContext) -> BaseModel:
        assert isinstance(ctx.body, MonitoringQuery)  # noqa: S101
        return await queries.monitoring_daily(pools, ctx.principal.scopes, ctx.body, ctx.request.app.state.clock())

    async def get_freezes(ctx: RequestContext) -> Response:
        return _json(await queries.monitoring_freezes(pools, ctx.principal.scopes))

    async def get_dossier(ctx: RequestContext) -> Response:
        try:
            case_id = UUID(ctx.path_params["case_id"])
        except ValueError as error:
            raise NotFound() from error
        return _json(await dossier.build_dossier(pools, case_id, config.public_keys))

    async def post_check(ctx: RequestContext) -> Response | BaseModel:
        assert isinstance(ctx.body, IntegrityCheckRequest)  # noqa: S101
        ref, created = await dossier.request_check(pools, ctx.body, ctx.principal.subject, ctx.request.app.state.clock())
        return respond(ref, 202) if created else ref

    async def get_check(ctx: RequestContext) -> BaseModel:
        return await dossier.check_status(pools, ctx.path_params["id"])

    return {
        ("POST", "/v1/entries"): post_entry,
        ("GET", "/v1/entries"): get_entries,
        ("POST", "/v1/monitoring/daily:query"): daily_query,
        ("GET", "/v1/monitoring/freezes"): get_freezes,
        ("GET", "/v1/dossiers/{case_id}"): get_dossier,
        ("POST", "/v1/integrity-checks"): post_check,
        ("GET", "/v1/integrity-checks/{id}"): get_check,
    }


def create_service_app(
    pools: Pools, config: ServiceConfig | None = None, *, authenticator: Authenticator | None = None
) -> FastAPI:
    """La app del servicio (puerto 8080) y, en `app.state.ops_app`, el servidor de 8081 con `/readyz` = `Health.is_ready`."""
    cfg = config or ServiceConfig()
    health = cfg.health or Health(pools.health)
    gauges = cfg.gauges or Gauges(pools, cfg.clock)
    app = create_app(
        SERVICE,
        REGISTRY[SERVICE],
        handlers(pools, cfg),
        authenticator=authenticator,
        readiness=health.is_ready,
        clock=cfg.clock,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await health.start()
        await gauges.start()
        try:
            yield
        finally:
            await gauges.stop()
            await health.stop()
            await pools.close()

    app.router.lifespan_context = lifespan
    app.state.health = health
    app.state.gauges = gauges
    return app
