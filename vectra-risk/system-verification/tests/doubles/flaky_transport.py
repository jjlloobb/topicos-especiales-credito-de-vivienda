"""Un transporte que falla antes de responder bien (U12-T09): envuelve otro (`LightGateway`) y, para las solicitudes que cumplen `match`, consume primero una lista de fallos.

Un fallo es un numero (la respuesta con ese estado, con o sin `Retry-After`) o una excepcion de `httpx` (un fallo de transporte: se lanza). `always` hace que toda solicitud que cumple `match` falle siempre.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

import httpx

Fault = int | Exception


class FlakyTransport(httpx.BaseTransport):
    def __init__(
        self,
        inner: httpx.BaseTransport,
        faults: list[Fault] | None = None,
        *,
        match: Callable[[httpx.Request], bool] = lambda request: True,
        always: Fault | None = None,
        retry_after: str | None = None,
    ) -> None:
        self.inner = inner
        self.faults: deque[Fault] = deque(faults or [])
        self.match = match
        self.always = always
        self.retry_after = retry_after
        self.injected = 0
        self.matched = 0
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.match(request):
            self.matched += 1
            fault = (
                self.always if self.always is not None else (self.faults.popleft() if self.faults else None)
            )
            if fault is not None:
                self.injected += 1
                if isinstance(fault, Exception):
                    raise fault
                headers = {"retry-after": self.retry_after} if self.retry_after else {}
                return httpx.Response(fault, content=b"", headers=headers)
        return self.inner.handle_request(request)


def reads_of_cases(request: httpx.Request) -> bool:
    """GET de la bandeja y del detalle de un caso (`/api/console/cases...`)."""
    return request.method == "GET" and request.url.path.startswith("/api/console/cases")


def submits(request: httpx.Request) -> bool:
    return request.method == "POST" and request.url.path.endswith("/intake/applications")
