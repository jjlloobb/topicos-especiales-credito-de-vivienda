"""Fabrica unica de aplicacion (P-U0-01, P-U0-12)."""

import json
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, cast, get_args, get_origin

from fastapi import FastAPI, Request, Security
from fastapi.responses import Response
from fastapi.routing import APIRoute
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from vectra_contracts.catalog import LogEvent, ProblemCode
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.api import Principal
from vectra_contracts.routes import HARD_MAX_BODY, REGISTRY, RouteContract

from vectra_common import deadline as deadline_module
from vectra_common import logging as vlog
from vectra_common import process, telemetry
from vectra_common.authn import Authenticator, authenticator_from_env
from vectra_common.authz import require
from vectra_common.errors import (
    MalformedRequest,
    NotFound,
    PayloadTooLarge,
    UnsupportedMediaType,
    VectraError,
    problem_body,
    to_problem,
    validation_failed,
)
from vectra_common.metrics import AUTHZ_DENIED, HTTP_DURATION
from vectra_common.ops_server import create_ops_app

PIPELINE: Final = (
    "TelemetryMiddleware",
    "AuthnMiddleware",
    "AuthzDependency",
    "BodyGuard",
    "PydanticStrict",
    "handler",
    "ProblemHandler",
    "AccessLog",
)
_DENIED: Final = {ProblemCode.UNAUTHENTICATED, ProblemCode.FORBIDDEN, ProblemCode.MFA_REQUIRED}
_UNMATCHED: Final = "unmatched"


@dataclass(frozen=True)
class RequestContext:
    """Lo que recibe un handler: siempre autenticado, autorizado y validado."""

    request: Request
    principal: Principal
    body: BaseModel | None
    query: BaseModel | None
    path_params: Mapping[str, str]
    correlation_id: str
    deadline: datetime | None


Handler = Callable[[RequestContext], Awaitable[BaseModel | Response | None]]
HandlerKey = tuple[str, str]


def _route_template(scope: Scope) -> str:
    route = scope.get("route")
    if route is not None:
        return str(route.path)
    app = scope.get("app")
    if app is not None:
        for candidate in app.router.routes:
            match, _ = candidate.matches(scope)
            if match.value == 2:
                return str(candidate.path)
    return _UNMATCHED


class TelemetryMiddleware:
    """Capa 1: `traceparent` → `correlation_id` (BR-U0-62) y span."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        header = headers.get(b"traceparent", b"").decode("latin-1")
        incoming = telemetry.parse_traceparent(header)
        trace_id = incoming[0] if incoming else telemetry.new_trace_id()
        span_id = telemetry.new_span_id()
        wanted = telemetry.traceparent_sampled(header)
        span = telemetry.start_span(
            f"{scope['method']}", trace_id, incoming[1] if incoming else None, span_id, wanted
        )
        sampled = bool(span.get_span_context().trace_flags.sampled) if span is not None else wanted
        correlation_token = vlog.correlation_id_var.set(trace_id)
        span_token = vlog.span_id_var.set(span_id)
        sampled_token = vlog.trace_sampled_var.set(sampled)

        async def send_with_trace(message: Message) -> None:
            if message["type"] == "http.response.start":
                value = telemetry.format_traceparent(trace_id, span_id, sampled).encode("latin-1")
                message.setdefault("headers", []).append((b"traceparent", value))
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace)
        finally:
            if span is not None:
                span.set_attribute("route_template", _route_template(scope))
                span.end()
            vlog.correlation_id_var.reset(correlation_token)
            vlog.span_id_var.reset(span_token)
            vlog.trace_sampled_var.reset(sampled_token)


class AccessLogMiddleware:
    """Capa 8: un `LogRecord` por solicitud y el histograma HTTP."""

    def __init__(self, app: ASGIApp, service: str) -> None:
        self.app = app
        self.service = service

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = {"code": 500}

        async def capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            elapsed = time.perf_counter() - started
            template = _route_template(scope)
            HTTP_DURATION.labels(
                service=self.service,
                route_template=template,
                method=scope["method"],
                status=str(status["code"]),
            ).observe(elapsed)
            vlog.log_access(
                status=status["code"],
                http_method=scope["method"],
                route_template=template,
                duration_ms=round(elapsed * 1000, 3),
            )


class ProblemHandlerMiddleware:
    """Capa 7: `VectraError` → `Problem`; lo demas → `internal_error` (BR-U0-60)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = {"value": False}

        async def tracked(message: Message) -> None:
            if message["type"] == "http.response.start":
                started["value"] = True
            await send(message)

        try:
            await self.app(scope, receive, tracked)
        except VectraError as error:
            self._record_denied(scope, error)
            await self._respond(error, send, started["value"])
        except Exception as exc:  # noqa: BLE001 - toda excepcion se traduce (BR-U0-60)
            vlog.log_exception(exc, ProblemCode.INTERNAL_ERROR.value)
            await self._respond(VectraError(), send, started["value"])

    @staticmethod
    def _record_denied(scope: Scope, error: VectraError) -> None:
        if error.code not in _DENIED:
            return
        template = _route_template(scope)
        AUTHZ_DENIED.labels(code=error.code.value, route_template=template).inc()
        principal = scope.get("vectra_principal")
        fields: dict[str, Any] = {"route_template": template, "error_code": error.code.value}
        if principal is not None:
            fields["principal_subject"] = principal.subject
        vlog.log_event(LogEvent.AUTHZ_DENIED, **fields)

    @staticmethod
    async def _respond(error: VectraError, send: Send, already_started: bool) -> None:
        if already_started:
            raise RuntimeError("la respuesta ya habia empezado")
        problem = to_problem(error, vlog.correlation_id_var.get() or "")
        body = problem_body(problem)
        await send(
            {
                "type": "http.response.start",
                "status": problem.status,
                "headers": [
                    (b"content-type", b"application/problem+json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class AuthnMiddleware:
    """Capa 2: autentica toda solicitud del puerto 8080 (BR-U0-70)."""

    def __init__(self, app: ASGIApp, authenticator: Authenticator) -> None:
        self.app = app
        self.authenticator = authenticator

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raw = dict(scope["headers"]).get(b"authorization")
        principal = await self.authenticator.authenticate(raw.decode("latin-1") if raw else None)
        scope["vectra_principal"] = principal
        await self.app(scope, receive, send)


async def _read_limited(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise PayloadTooLarge()
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > limit:
            raise PayloadTooLarge()
    return bytes(chunks)


async def _body_guard(request: Request, contract: RouteContract) -> BaseModel | None:
    """Capas 4 y 5: tipo de contenido, tamano, JSON valido y esquema estricto."""
    if contract.request_model is None:
        return None
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "application/json":
        raise UnsupportedMediaType()
    raw = await _read_limited(request, contract.max_body_bytes)
    try:
        json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise MalformedRequest() from exc
    try:
        return contract.request_model.model_validate_json(raw)
    except ValidationError as exc:
        raise validation_failed(exc) from exc


def _is_list(annotation: Any) -> bool:
    return any(get_origin(arg) is list for arg in (annotation, *get_args(annotation)))


def parse_query(request: Request, model: type[BaseModel]) -> BaseModel:
    """Los parametros llegan como texto: se convierten con el esquema; lo que sobra es 422.

    Un filtro de lista admite `state=a&state=b` y `state=a,b` (`GET /v1/models?state=activo,congelado`).
    """
    values: dict[str, Any] = {}
    for name in set(request.query_params.keys()):
        raw = request.query_params.getlist(name)
        field = model.model_fields.get(name)
        if field is not None and _is_list(field.annotation):
            values[name] = [part for item in raw for part in item.split(",")]
        else:
            values[name] = raw[-1] if len(raw) == 1 else raw
    try:
        return model.model_validate(values, strict=False)
    except ValidationError as exc:
        raise validation_failed(exc) from exc


def respond(model: BaseModel | None, status: int) -> Response:
    """Para un estado alterno del contrato: 202 con cuerpo, o 304 sin el."""
    if model is None:
        return Response(status_code=status)
    return Response(model.model_dump_json(exclude_none=True), status_code=status, media_type="application/json")


def _endpoint(contract: RouteContract, handler: Handler) -> Callable[[Request], Awaitable[Response]]:
    async def endpoint(request: Request) -> Response:
        now: datetime = request.app.state.clock()
        deadline = deadline_module.read(request.headers, now)
        token = deadline_module.current_deadline.set(deadline)
        try:
            query = parse_query(request, contract.query_model) if contract.query_model else None
            body = await _body_guard(request, contract)
            context = RequestContext(
                request=request,
                principal=cast(Principal, request.scope["vectra_principal"]),
                body=body,
                query=query,
                path_params=request.path_params,
                correlation_id=vlog.correlation_id_var.get() or "",
                deadline=deadline,
            )
            result = await handler(context)
        finally:
            deadline_module.current_deadline.reset(token)
        if isinstance(result, Response):
            return result
        if result is None:
            return Response(status_code=204)
        return Response(result.model_dump_json(exclude_none=True), media_type="application/json")

    return endpoint


def check_contract(route: RouteContract) -> None:
    """Falla al arrancar: deny by default, `POST` de lectura y limite de cuerpo."""
    if not route.scopes and not route.any_scopes and not route.roles:
        raise ContractViolation(f"{route.method} {route.path}: sin scopes ni roles (BR-U0-71)")
    declared = route.scopes | route.any_scopes
    if (
        route.method == "POST"
        and declared
        and all(s.is_read for s in declared)
        and not route.roles
        and not route.read_only
    ):
        raise ContractViolation(f"{route.method} {route.path}: POST con solo scopes de lectura sin read_only")
    if route.read_only and route.method != "POST":
        raise ContractViolation(f"{route.method} {route.path}: read_only solo aplica a POST")
    if route.max_body_bytes > HARD_MAX_BODY:
        raise ContractViolation(f"{route.method} {route.path}: max_body_bytes supera {HARD_MAX_BODY}")


def audit_routes(app: FastAPI) -> None:
    """Toda ruta del puerto 8080 lleva el marcador de `require` (P-U0-02)."""
    for route in app.router.routes:
        if isinstance(route, APIRoute):
            markers = [
                dep.dependency for dep in route.dependencies if hasattr(dep.dependency, "vectra_requirement")
            ]
            if not markers:
                raise ContractViolation(f"{route.path}: ruta sin requisitos declarados")


def create_app(
    service_name: str,
    contract: Sequence[RouteContract] | None = None,
    handlers: Mapping[HandlerKey, Handler] | None = None,
    *,
    authenticator: Authenticator | None = None,
    readiness: Callable[[], bool] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    """Unica forma de crear una app de servicio. Falla si falta o sobra un handler."""
    process.ensure_service()
    routes = list(contract) if contract is not None else REGISTRY[service_name]
    bound = dict(handlers or {})
    declared = {(route.method, route.path) for route in routes}
    if declared != bound.keys():
        raise ContractViolation(
            f"handlers no coinciden con el contrato: faltan {sorted(declared - bound.keys())}, "
            f"sobran {sorted(bound.keys() - declared)}"
        )
    vlog.configure(service_name)
    telemetry.configure(service_name)
    app = FastAPI(title=service_name, openapi_url=None, docs_url=None, redoc_url=None)
    app.state.clock = clock
    app.state.pipeline = PIPELINE
    app.state.ops_app = create_ops_app(readiness, init_process=False)

    async def not_found(_: Request, exc: StarletteHTTPException) -> Response:
        raise NotFound() from exc

    app.add_exception_handler(StarletteHTTPException, not_found)  # type: ignore[arg-type]
    for route in routes:
        check_contract(route)
        dependency = require(route.scopes, route.roles, route.any_scopes, route.mfa, route.mfa_max_age)
        app.add_api_route(
            route.path,
            _endpoint(route, bound[(route.method, route.path)]),
            methods=[route.method],
            dependencies=[Security(dependency)],
            include_in_schema=False,
        )
    audit_routes(app)
    auth = authenticator or authenticator_from_env(service_name)
    # add_middleware apila de afuera hacia adentro en orden inverso.
    app.add_middleware(AuthnMiddleware, authenticator=auth)
    app.add_middleware(ProblemHandlerMiddleware)
    app.add_middleware(AccessLogMiddleware, service=service_name)
    app.add_middleware(TelemetryMiddleware)
    return app
