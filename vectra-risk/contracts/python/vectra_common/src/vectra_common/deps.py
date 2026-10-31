"""Llamadas a dependencias (P-U0-07, NFR-U0-23). Unico modulo que importa `httpx`."""

import os
import ssl
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any, Literal

import httpx
from vectra_contracts.errors import ContractViolation

from vectra_common import deadline as deadline_module
from vectra_common import process
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_common.logging import correlation_id_var, span_id_var
from vectra_common.metrics import CIRCUIT_STATE

CA_BUNDLE_ENV = "VECTRA_CA_BUNDLE"


class CircuitState(IntEnum):
    """Valores de `vectra_circuit_state` (NFR-U0-23 (g))."""

    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2


@dataclass(frozen=True)
class BreakerConfig:
    """Ventana deslizante, o `consecutive_failures`; declarar los dos es un error (i)."""

    open_for: float
    window_size: int | None = None
    failure_ratio: float | None = None
    consecutive_failures: int | None = None
    close_after: int = 1

    def __post_init__(self) -> None:
        window = self.window_size is not None or self.failure_ratio is not None
        if window and self.consecutive_failures is not None:
            raise ContractViolation("ventana y consecutive_failures son excluyentes")
        if not window and self.consecutive_failures is None:
            raise ContractViolation("el breaker necesita ventana o consecutive_failures")
        if window and (self.window_size is None or self.failure_ratio is None):
            raise ContractViolation("la ventana necesita window_size y failure_ratio")


class CircuitBreaker:
    """Maquina de estados del breaker; un estado por proceso y dependencia."""

    #: Solo tienen valor desde que el circuito se abre; `_refresh` y `_open` los fijan.
    _opened_at: float
    _successes: int
    _probes_in_flight: int

    def __init__(
        self, dependency: str, config: BreakerConfig, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._dependency = dependency
        self._config = config
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._window: deque[int] = deque(maxlen=config.window_size)  # 1 = fallo, 0 = exito
        self._consecutive = 0
        self._publish()

    @property
    def state(self) -> CircuitState:
        self._refresh()
        return self._state

    def _publish(self) -> None:
        CIRCUIT_STATE.labels(dependency=self._dependency).set(int(self._state))

    def _set(self, state: CircuitState) -> None:
        self._state = state
        self._publish()

    def _refresh(self) -> None:
        if self._state is CircuitState.OPEN and self._clock() - self._opened_at >= self._config.open_for:
            self._set(CircuitState.HALF_OPEN)
            self._successes = 0
            self._probes_in_flight = 0

    def allow(self) -> bool:
        self._refresh()
        if self._state is CircuitState.OPEN:
            return False
        if self._state is CircuitState.HALF_OPEN:
            if self._probes_in_flight == 1:
                return False
            self._probes_in_flight = 1
        return True

    def _open(self) -> None:
        self._opened_at = self._clock()
        self._window.clear()
        self._consecutive = 0
        self._set(CircuitState.OPEN)

    def on_success(self) -> None:
        if self._state is CircuitState.HALF_OPEN:
            self._probes_in_flight = 0
            self._successes += 1
            if self._successes >= self._config.close_after:
                self._set(CircuitState.CLOSED)
            return
        self._consecutive = 0
        self._window.append(0)

    def on_failure(self) -> None:
        if self._state is CircuitState.HALF_OPEN:
            self._open()
            return
        limit = self._config.consecutive_failures
        if limit is not None:
            self._consecutive += 1
            if self._consecutive >= limit:
                self._open()
            return
        self._window.append(1)
        ratio = self._config.failure_ratio
        assert ratio is not None  # BreakerConfig lo garantiza sin `consecutive_failures`
        if len(self._window) == self._config.window_size and sum(self._window) / len(self._window) >= ratio:
            self._open()


def _verify_context(base_url: str) -> ssl.SSLContext | bool:
    """Con https, la CA sale de `VECTRA_CA_BUNDLE`; sin el archivo no se arranca."""
    if not base_url.startswith("https://"):
        return True
    path = os.environ.get(CA_BUNDLE_ENV)
    if not path or not os.path.isfile(path):
        raise ContractViolation(f"{CA_BUNDLE_ENV} no apunta a un archivo: nunca se desactiva la verificacion")
    return ssl.create_default_context(cafile=path)


class DependencyClient:
    """Un `httpx.AsyncClient` por dependencia, con su limite de conexiones."""

    def __init__(
        self,
        dependency: str,
        base_url: str,
        breaker: BreakerConfig | Literal["disabled"],
        max_connections: int,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        kind = process.current()
        if breaker == "disabled":
            if kind != "batch":
                raise ContractViolation('breaker="disabled" solo en procesos batch')
            self.breaker: CircuitBreaker | None = None
        else:
            self.breaker = CircuitBreaker(dependency, breaker, clock)
        self._wall_clock = wall_clock
        self._client = httpx.AsyncClient(
            base_url=base_url,
            limits=httpx.Limits(max_connections=max_connections),
            verify=_verify_context(base_url),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _send(
        self, method: str, path: str, timeout: float, headers: dict[str, str], content: bytes | None
    ) -> httpx.Response:
        request_timeout = httpx.Timeout(timeout)
        return await self._client.request(
            method, path, headers=headers, content=content, timeout=request_timeout
        )

    def budget(self, timeout: float, deadline: datetime | None) -> float:
        """NFR-U0-23 (b): nunca supera el presupuesto restante."""
        if deadline is None:
            return timeout
        return min(timeout, (deadline - self._wall_clock()).total_seconds())


def _propagated_headers(extra: Mapping[str, str] | None, deadline: datetime | None) -> dict[str, str]:
    headers = dict(extra or {})
    correlation = correlation_id_var.get()
    span = span_id_var.get()
    if correlation and span:
        headers["traceparent"] = f"00-{correlation}-{span}-01"
    if deadline is not None:
        headers[deadline_module.HEADER] = deadline_module.to_header(deadline)
    return headers


async def call(
    client: DependencyClient,
    method: str,
    path: str,
    *,
    timeout: float,
    deadline: datetime | None = None,
    headers: Mapping[str, str] | None = None,
    content: bytes | None = None,
) -> httpx.Response:
    """`timeout` es obligatorio. Solo cuentan como fallo timeouts, conexion y 5xx (c)."""
    effective = client.budget(timeout, deadline)
    if effective <= 0:
        raise DependencyTimeout()
    breaker = client.breaker
    if breaker is not None and not breaker.allow():
        raise DependencyUnavailable()
    try:
        response = await client._send(
            method, path, effective, _propagated_headers(headers, deadline), content
        )  # noqa: SLF001
    except httpx.TimeoutException as exc:
        if breaker is not None:
            breaker.on_failure()
        raise DependencyTimeout() from exc
    except httpx.TransportError as exc:
        if breaker is not None:
            breaker.on_failure()
        raise DependencyUnavailable() from exc
    if breaker is not None:
        if response.status_code >= 500:
            breaker.on_failure()
        else:
            breaker.on_success()
    return response


async def fetch_json_once(url: str, timeout: float, transport: httpx.AsyncBaseTransport | None = None) -> Any:
    """Una sola solicitud, sin breaker: la cache de JWKS ya limita los refrescos (P-U0-06)."""
    try:
        async with httpx.AsyncClient(
            verify=_verify_context(url), transport=transport, timeout=timeout
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError, ssl.SSLError) as exc:
        raise DependencyUnavailable() from exc
