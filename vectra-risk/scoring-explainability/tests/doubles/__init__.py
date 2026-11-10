"""Dobles HTTP de U3, U4 y U6 para U7 (Paso 8 a 13). Siguen los contratos de `vectra_contracts`; ninguno inventa campos.

Cada doble es una app ASGI de Starlette con `calls` (lo que recibio) y conmutadores de falla; se conectan a los clientes de U7
por `httpx.ASGITransport` (en proceso) o, para la prueba de apagado, se sirven con uvicorn en un hilo (`servers.py`).
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from starlette.requests import Request


@dataclass
class Call:
    method: str
    path: str
    query: str
    headers: dict[str, str]
    body: bytes


@dataclass
class Recorder:
    calls: list[Call] = field(default_factory=list)

    async def record(self, request: Request) -> Call:
        call = Call(
            request.method,
            request.url.path,
            request.url.query,
            {name.lower(): value for name, value in request.headers.items()},
            await request.body(),
        )
        self.calls.append(call)
        return call

    def count(self, fragment: str = "") -> int:
        return sum(1 for call in self.calls if fragment in call.path or fragment in call.query)


class Faults:
    """Conmutadores de falla comunes: `delay` antes de responder, `status` fijo y un 503 por `fail_next` llamadas."""

    def __init__(self) -> None:
        self.delay: float = 0.0
        self.status: int | None = None
        self.fail_next: int = 0

    async def gate(self) -> int | None:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_next > 0:
            self.fail_next -= 1
            return 503
        return self.status


def problem(status: int, code: str, reason: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": f"urn:vectra:problem:{code}",
        "title": code,
        "status": status,
        "code": code,
        "correlation_id": "0" * 32,
    }
    if reason is not None:
        body["reason"] = reason
    return body
