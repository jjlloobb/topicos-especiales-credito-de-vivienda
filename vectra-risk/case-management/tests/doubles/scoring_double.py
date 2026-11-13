"""Doble de `scoring-service` (F15) para el worker (U08-T04): resultados por caso e intento, latencia, 401, 4xx, 5xx y `version_mismatch`.

Valida cada solicitud con `ScoringRequest` de U0 y la guarda (`requests`, `headers`). Las respuestas son las de U0: `Recommendation`
(con `recommendation_from_wire`, nunca el token privado) y `FailClosed`. Los comportamientos se encolan (`queue`, para cualquier caso;
`by_case`, por caso) y cuando se acaban rige `default`:

- `"ok"` / `("ok", Outcome)`: `Recommendation` 200;
- `("fail", FailClosedCause)`: `FailClosed` 200 (`model_frozen` lleva `modelo_congelado`, las demas `en_sincronizacion`);
- `("status", n)`: respuesta con ese estado (401, 403, 422, 503...);
- `"drop"`: error de conexion;
- `"junk"`: 200 con un cuerpo que no es un `RecommendResult`.
"""

import asyncio
import json
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from case_strategies import recommendation_from_wire
from vectra_contracts.catalog import FailClosedCause, Outcome
from vectra_contracts.models.api import ScoringRequest
from vectra_contracts.models.explanation import FailClosed

Behavior = Any


class ScoringDouble:
    def __init__(self) -> None:
        self.requests: list[ScoringRequest] = []
        self.headers: list[dict[str, str]] = []
        self.queue: deque[Behavior] = deque()
        self.by_case: dict[UUID, deque[Behavior]] = defaultdict(deque)
        self.default: Behavior = "ok"
        self.delay = 0.0
        self.serving_version = "mv-1"
        self.reject_token: str | None = (
            None  # responde 401 mientras el token sea este (para el reintento por 401)
        )
        self.calls = 0
        self.in_flight = 0
        self.max_in_flight = 0
        self.arrivals: list[float] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def count(self, case_id: UUID) -> int:
        return sum(1 for r in self.requests if r.case_id == case_id)

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.arrivals.append(asyncio.get_event_loop().time())
        try:
            parsed = ScoringRequest.model_validate_json(
                request.content
            )  # lo que llega es un `ScoringRequest` valido
            self.requests.append(parsed)
            self.headers.append(dict(request.headers))
            if self.delay:
                await asyncio.sleep(self.delay)
            if (
                self.reject_token is not None
                and request.headers.get("authorization") == f"Bearer {self.reject_token}"
            ):
                return httpx.Response(401, json={"code": "unauthenticated"})
            behavior = self._next(parsed.case_id)
            if parsed.model_version_id != self.serving_version:
                behavior = ("fail", FailClosedCause.VERSION_MISMATCH)
            return self._respond(behavior, parsed)
        finally:
            self.in_flight -= 1

    def _next(self, case_id: UUID) -> Behavior:
        if self.by_case[case_id]:
            return self.by_case[case_id].popleft()
        if self.queue:
            return self.queue.popleft()
        return self.default

    @staticmethod
    def _respond(behavior: Behavior, request: ScoringRequest) -> httpx.Response:
        kind, arg = (behavior, None) if isinstance(behavior, str) else (behavior[0], behavior[1])
        if kind == "drop":
            raise httpx.ConnectError("scoring caido")
        if kind == "junk":
            return httpx.Response(200, json={"kind": "otra_cosa"})
        if kind == "status":
            return httpx.Response(arg, json={"code": "error"})
        if kind == "fail":
            frozen = arg is FailClosedCause.MODEL_FROZEN
            body = FailClosed(
                case_id=request.case_id,
                status="modelo_congelado" if frozen else "en_sincronizacion",
                cause=arg,
                retryable=not frozen,
                occurred_at=datetime.now(UTC),
            ).model_dump_json()
            return httpx.Response(200, content=body, headers={"content-type": "application/json"})
        outcome = arg or Outcome.FAVORABLE
        rec = recommendation_from_wire(outcome, case_id=request.case_id)
        return httpx.Response(
            200, content=rec.model_dump_json(), headers={"content-type": "application/json"}
        )


def body_of(response: httpx.Response) -> dict[str, Any]:
    return json.loads(response.content)  # type: ignore[no-any-return]
