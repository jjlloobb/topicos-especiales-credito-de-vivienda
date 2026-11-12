"""Doble en memoria del registro de decisiones (U3) para `case-service` (NFR-U8-53; PBT-U8-07).

Implementa lo que importa al reconciliador: BR-U3-05 (la ventana de +-5 min de `occurred_at` solo para llaves nuevas), BR-U3-06
(misma llave y mismo contenido de negocio -> el ack original; otro contenido -> 409; no se comparan `occurred_at`, `correlation_id`
ni `contract_version`) y BR-U0-37 (`check_business_time`, solo para llaves nuevas, 422). Se valida con las pruebas de ejemplo de
append de U3 (`test_registry_double.py`, copiadas y citadas; ninguna unidad importa las pruebas de otra).

Fallos programables: `down` (503 sin escribir), `lose_ack_next` (escribe y responde 503: el ack perdido tras el commit),
`delay` (segundos) y `fail_with` (un estado fijo). Mide `in_flight` y `max_in_flight`.
"""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import ValidationError
from vectra_contracts.models.registry import RegistryEntryIn
from vectra_contracts.validation import check_business_time

WINDOW = timedelta(seconds=300)
BUSINESS_FIELDS = (
    "entry_type",
    "idempotency_key",
    "actor",
    "case_id",
    "model_version_id",
    "policy_version_id",
    "payload",
)


def _now() -> datetime:
    return datetime.now(UTC)


class RegistryDouble:
    def __init__(self, clock: Callable[[], datetime] = _now) -> None:
        self.clock = clock
        self.entries: list[
            dict[str, Any]
        ] = []  # una por entrada escrita (con `seq`, `recorded_at`, `business`)
        self.requests: list[
            dict[str, Any]
        ] = []  # cada solicitud recibida (para ver `occurred_at` por intento)
        self.by_key: dict[str, dict[str, Any]] = {}
        self.down = False
        self.lose_ack_next = 0
        self.delay = 0.0
        self.fail_with: int | None = None
        self.in_flight = 0
        self.max_in_flight = 0
        self.arrivals: list[float] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    @staticmethod
    def _business(entry: RegistryEntryIn) -> str:
        data = entry.model_dump(mode="json", exclude_none=True)
        return json.dumps({k: data.get(k) for k in BUSINESS_FIELDS}, sort_keys=True)

    @staticmethod
    def _problem(status: int, code: str, reason: str | None = None) -> httpx.Response:
        body: dict[str, Any] = {"code": code, "status": status}
        if reason:
            body["invalid_params"] = [{"name": reason, "reason_code": reason}]
        return httpx.Response(status, json=body)

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.arrivals.append(asyncio.get_event_loop().time())
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            return self._process(request)
        finally:
            self.in_flight -= 1

    def _process(self, request: httpx.Request) -> httpx.Response:
        raw = json.loads(request.content)
        self.requests.append(raw)
        if self.down:
            return httpx.Response(503, json={"code": "dependency_unavailable"})
        if self.fail_with is not None:
            return httpx.Response(self.fail_with, json={})
        try:
            entry = RegistryEntryIn.model_validate_json(request.content)
        except ValidationError:
            return self._problem(422, "validation_error", "body")
        key = str(entry.idempotency_key)
        content = self._business(entry)
        existing = self.by_key.get(key)
        if existing is not None:  # BR-U3-06: se resuelve antes de la ventana y de BR-U0-37
            if existing["business"] != content:
                return self._problem(409, "conflict_state")
            return self._ack(existing)
        now = self.clock()
        if abs(entry.occurred_at - now) > WINDOW:  # BR-U3-05
            return self._problem(422, "validation_error", "occurred_at")
        payload = entry.payload.model_dump()
        error = check_business_time(payload, entry.occurred_at)  # BR-U0-37
        if error is not None:
            return self._problem(422, "validation_error", "payload." + error.field)
        row = {
            "seq": len(self.entries) + 1,
            "registry_entry_id": str(len(self.entries) + 1),
            "recorded_at": now,
            "business": content,
            "entry": entry,
        }
        self.entries.append(row)
        self.by_key[key] = row
        if self.lose_ack_next:
            self.lose_ack_next -= 1
            return httpx.Response(503, json={"code": "dependency_unavailable"})
        return self._ack(row)

    @staticmethod
    def _ack(row: dict[str, Any]) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "registry_entry_id": row["registry_entry_id"],
                "seq": row["seq"],
                "recorded_at": row["recorded_at"].isoformat(),
            },
        )

    def of_type(self, entry_type: str) -> list[dict[str, Any]]:
        return [r for r in self.entries if r["entry"].entry_type == entry_type]
