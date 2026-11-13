"""Base comun de los clientes `gateway` y `bff` (U12 Paso 5; INF-U12-03; NFR-U12-50; P-10).

Cada solicitud lleva `X-Test-Scenario: <escenario>.<prefijo>` y un `traceparent` `00-<32 hex>-<16 hex>-01` cuyos 8 primeros hex son el prefijo de la corrida (el resto, al azar por
solicitud). Ambas cabeceras y el `Authorization` se ponen en **un solo sitio**, un gancho del cliente (`_decorate`), no en cada metodo. El cliente se crea con
`guard.gateway_client`: si el entorno no pasa la barrera (produccion), no se envia ninguna solicitud. Un error es un `Problem`: `status`, `code` y `reason`; el `Authorization` nunca va en el mensaje.
"""

from __future__ import annotations

import re
import secrets
import ssl
from collections.abc import Callable
from typing import Any, Final

import httpx
from pydantic import BaseModel, ValidationError
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.api import Problem
from vectra_contracts.outcome import read_wire

from vectra_verification import guard
from vectra_verification.guard import Environment

SCENARIO_PATTERN: Final = re.compile(
    r"^[A-Za-z0-9_.:-]{1,100}$"
)  # `X-Test-Scenario` de U8 (`case-management/src/vectra_case/intake.py`)
IDEMPOTENCY_PATTERN: Final = re.compile(r"^[\x21-\x7e]{1,128}$")
PREFIX_PATTERN: Final = re.compile(r"^[0-9a-f]{8}$")
TRACEPARENT_PATTERN: Final = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-01$")
RETRY_AFTER_MAX: Final = 60.0
TIMEOUT: Final = 30.0


class ApiError(Exception):
    """Un `Problem` (o un fallo de transporte, con `status = 0`). El mensaje no lleva el `Authorization` ni el cuerpo."""

    def __init__(
        self,
        status: int,
        code: str | None = None,
        reason: str | None = None,
        retry_after: float | None = None,
        invalid_params: tuple[tuple[str, str], ...] | None = None,
    ) -> None:
        super().__init__(f"http_{status}:{code or '-'}:{reason or '-'}")
        self.status = status
        self.code = code
        self.reason = reason
        self.retry_after = retry_after
        self.invalid_params = invalid_params  # (`name`, `reason_code`) de un 422 `validation_error` (U12-T03: RT-3 lee el motivo del rechazo de U4)


class RunTag:
    """El escenario y el prefijo de la corrida (8 hex que recibe el cliente; U12-T04 los deriva del `runId`)."""

    def __init__(self, scenario: str, prefix: str) -> None:
        if not PREFIX_PATTERN.fullmatch(prefix):
            raise ValueError("run_prefix_invalid")
        self.scenario = scenario
        self.prefix = prefix
        if not SCENARIO_PATTERN.fullmatch(self.header_value):
            raise ValueError("scenario_invalid")

    @property
    def header_value(self) -> str:
        return f"{self.scenario}.{self.prefix}"

    def traceparent(self) -> str:
        return f"00-{self.prefix}{secrets.token_hex(12)}-{secrets.token_hex(8)}-01"


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    try:
        return min(max(float(raw), 0.0), RETRY_AFTER_MAX) if raw is not None else None
    except ValueError:
        return None


def error_of(response: httpx.Response) -> ApiError:
    """El `Problem` de una respuesta que no es 2xx; si no es un `Problem` valido, solo el estado."""
    retry = _retry_after(response)
    try:
        problem = Problem.model_validate_json(response.content)
    except ValidationError:
        return ApiError(response.status_code, retry_after=retry)
    params = (
        tuple((p.name, p.reason_code) for p in problem.invalid_params) if problem.invalid_params else None
    )
    return ApiError(
        response.status_code,
        problem.code.value,
        problem.reason.value if problem.reason else None,
        retry,
        params,
    )


class ApiClient:
    """Un cliente del gateway. `bearer` entrega el token vigente en cada solicitud (asi un refresco se ve en la siguiente)."""

    def __init__(
        self,
        environment: Environment,
        bearer: Callable[[], str],
        tag: RunTag,
        *,
        transport: httpx.BaseTransport | None = None,
        verify: ssl.SSLContext | bool = True,
    ) -> None:
        self._environment = environment
        self._bearer = bearer
        self.tag = tag
        self._http = guard.gateway_client(environment.issuer, environment.host, transport, verify)
        self._http.timeout = httpx.Timeout(TIMEOUT)
        self._http.event_hooks["request"].append(self._decorate)
        self.requests_sent = 0

    def _decorate(self, request: httpx.Request) -> None:
        """El unico sitio donde se ponen la cabecera de escenario, el `traceparent` y el `Authorization`."""
        request.headers["X-Test-Scenario"] = self.tag.header_value
        request.headers["traceparent"] = self.tag.traceparent()
        request.headers["Authorization"] = f"Bearer {self._bearer()}"
        self.requests_sent += 1

    def close(self) -> None:
        self._http.close()

    def _send(
        self,
        method: str,
        path: str,
        *,
        body: BaseModel | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        content = body.model_dump_json().encode() if body is not None else None
        merged = (
            {"Content-Type": "application/json", **(headers or {})}
            if content is not None
            else dict(headers or {})
        )
        try:
            response = self._http.request(method, path, content=content, params=params, headers=merged)
        except httpx.TimeoutException:
            raise ApiError(0, "timeout") from None
        except httpx.HTTPError as error:
            raise ApiError(0, f"transport_{type(error).__name__}") from None
        if not response.is_success:
            raise error_of(response)
        return response

    @staticmethod
    def _parse[M: BaseModel](response: httpx.Response, model: type[M]) -> M:
        """Una respuesta 2xx que no valida es un error, no un dato. Un modelo que contiene `Recommendation` (`CaseDetail`) solo se lee con `read_wire` (U00-T03), como hacen el BFF y U8."""
        try:
            if "Recommendation" in str(model.model_fields.get("recommendation", "")):
                return read_wire(model, response.content)
            return model.model_validate_json(response.content)
        except (ValidationError, ContractViolation):
            raise ApiError(response.status_code, "invalid_response") from None
