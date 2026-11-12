"""Clientes de los cinco destinos del BFF y la llamada de una solicitud (BR-U10-02, 03; P-U10-03, 04; NFR-U10-11, 30..33).

- Un `DependencyClient` de U0 por destino (`case`, `governance`, `registry`, `explainability`, `bias`), cada uno con su
  circuit breaker (los umbrales de U7, `config`) y su tope de conexiones. El nombre es la etiqueta `dependency` de
  `vectra_circuit_state` y de las metricas del BFF.
- **Sin reintentos** (NFR-U10-33): los clientes no llevan `token_source`, que es lo que hace a `deps.call` reintentar ante un 401.
  El BFF reenvia el `Authorization` del usuario tal cual.
- **Presupuesto** (NFR-U10-31): `x-vectra-deadline` = el reloj de la app al entrar + `DEADLINE_BUDGET_SECONDS`; si la
  solicitud ya trae un plazo menor, rige el menor (U0 NFR-U0-23 (b)). El timeout efectivo de cada llamada lo recorta `deps`.
- **Timeout = 503** (P-2 (a) de U10-T02): todo `DependencyTimeout` de un destino se vuelve `DependencyUnavailable`. El
  `deadline_exceeded` (504) queda solo para la solicitud que **entra** con el plazo vencido, que lo lanza U0 antes del handler.

Este modulo no importa `httpx`: el transporte de las pruebas se inyecta tal cual por `transports`.
"""

import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final
from urllib.parse import quote, urlencode

from pydantic import BaseModel
from starlette.responses import Response
from vectra_common import deps, process
from vectra_common.app_factory import RequestContext
from vectra_common.deps import BreakerConfig, DependencyClient
from vectra_common.errors import DependencyTimeout, DependencyUnavailable, NotFound, problem_body

from console_bff import config
from console_bff.errors import translate_error
from console_bff.metrics import DEPENDENCY_DURATION

DESTINATIONS: Final = ("case", "governance", "registry", "explainability", "bias")
BREAKER: Final = BreakerConfig(
    open_for=config.BREAKER_OPEN_FOR_SECONDS,
    window_size=config.BREAKER_WINDOW_SIZE,
    failure_ratio=config.BREAKER_FAILURE_RATIO,
    window_seconds=config.BREAKER_WINDOW_SECONDS,
)
_UNMATCHED: Final = "unmatched"
_FORWARDED: Final = ("authorization", "idempotency-key")


@dataclass(frozen=True)
class Reply:
    """La respuesta de un destino: solo lo que el BFF usa (estado y cuerpo)."""

    status: int
    body: bytes

    @property
    def is_success(self) -> bool:
        return 200 <= self.status < 300


class UpstreamProblem(Exception):  # noqa: N818 - lleva la respuesta de error ya traducida (BR-U10-04)
    """Un destino respondio un error: se entrega el `Problem` traducido por `errors.translate_error`."""

    def __init__(self, response: Response) -> None:
        super().__init__(response.status_code)
        self.response = response


def problem_response(status: int, body: bytes, correlation_id: str) -> Response:
    """La respuesta de error de un destino, como `Problem` sin `detail` ni trazas (BR-U10-04)."""
    problem = translate_error(status, body, correlation_id)
    return Response(problem_body(problem), status_code=problem.status, media_type="application/problem+json")


def query_string(query: BaseModel | Mapping[str, Any] | None) -> str:
    """La query validada por U0, serializada desde el modelo (no desde los bytes de entrada)."""
    if query is None:
        return ""
    values = query.model_dump(mode="json", exclude_none=True) if isinstance(query, BaseModel) else dict(query)
    pairs: list[tuple[str, str]] = []
    for name, value in values.items():
        for item in value if isinstance(value, list) else [value]:
            pairs.append((name, str(item).lower() if isinstance(item, bool) else str(item)))
    return urlencode(pairs)


def quote_segment(value: str) -> str:
    """Un valor listo para ir como **un** segmento de la ruta de un destino: nunca sube de nivel ni agrega segmentos."""
    if value in (".", ".."):
        raise NotFound()
    return quote(value, safe="")


def path_id(ctx: RequestContext) -> str:
    """El `{id}` de la ruta del BFF, como segmento de la ruta del destino."""
    return quote_segment(ctx.path_params["id"])


def route_template(ctx: RequestContext) -> str:
    """La plantilla de la ruta del BFF (etiqueta `route` de las metricas): nunca un identificador."""
    route = ctx.request.scope.get("route")
    return str(route.path) if route is not None else _UNMATCHED


class Upstreams:
    """Los cinco clientes; se crean al armar la app y se cierran al apagarla (`aclose`)."""

    def __init__(
        self,
        urls: Mapping[str, str],
        *,
        transports: Mapping[str, Any] | None = None,
        wall_clock: Any = None,
    ) -> None:
        process.ensure_service()  # `DependencyClient` exige el tipo de proceso; el BFF es siempre un servicio
        extra: dict[str, Any] = {} if wall_clock is None else {"wall_clock": wall_clock}
        transports = transports or {}
        self.clients: Final = {
            name: DependencyClient(
                name,
                urls[name],
                BREAKER,
                config.CONNECTIONS_PER_REPLICA[name],
                transport=transports.get(name),
                **extra,
            )
            for name in DESTINATIONS
        }

    async def aclose(self) -> None:
        for client in self.clients.values():
            await client.aclose()


class Calls:
    """Las llamadas de **una** solicitud: el token, el plazo y la plantilla de ruta se fijan una vez."""

    def __init__(self, upstreams: Upstreams, ctx: RequestContext) -> None:
        self._upstreams = upstreams
        self.ctx = ctx
        entered: datetime = ctx.request.app.state.clock()
        budget = entered + timedelta(seconds=config.DEADLINE_BUDGET_SECONDS)
        self.deadline = budget if ctx.deadline is None else min(budget, ctx.deadline)
        self._route = route_template(ctx)
        self._headers = {
            name: value for name in _FORWARDED if (value := ctx.request.headers.get(name)) is not None
        }

    async def send(
        self,
        destination: str,
        operation: str,
        method: str,
        path: str,
        *,
        query: BaseModel | Mapping[str, Any] | None = None,
        body: BaseModel | None = None,
    ) -> Reply:
        """Una llamada, sin reintento. Timeout, conexion o circuito abierto -> `DependencyUnavailable` (503)."""
        timeout = config.OPERATION_TIMEOUT_SECONDS[f"{destination}.{operation}"]
        qs = query_string(query)
        headers = dict(self._headers)
        content: bytes | None = None
        if body is not None:
            content = body.model_dump_json(exclude_none=True).encode()
            headers["content-type"] = "application/json"
        started = time.perf_counter()
        try:
            response = await deps.call(
                self._upstreams.clients[destination],
                method,
                f"{path}?{qs}" if qs else path,
                timeout=timeout,
                deadline=self.deadline,
                headers=headers,
                content=content,
            )
        except DependencyTimeout:
            raise DependencyUnavailable() from None
        finally:
            # P-U10-11: el sobrecosto del BFF = la duracion de la ruta menos la de sus dependencias.
            DEPENDENCY_DURATION.labels(dependency=destination, route=self._route).observe(
                time.perf_counter() - started
            )
        return Reply(response.status_code, response.content)

    async def fetch(self, *args: Any, **kwargs: Any) -> Reply:
        """Como `send`, pero un error del destino sale como `UpstreamProblem` con su `Problem` traducido."""
        reply = await self.send(*args, **kwargs)
        if not reply.is_success:
            raise UpstreamProblem(problem_response(reply.status, reply.body, self.ctx.correlation_id))
        return reply
