"""Doble de U3 (F28): `GET /v1/entries` con `projection=metrics` (Paso 4; INF-U11-06).

Implementa `entry_type`, `recorded_from`, `seq_after`, `limit` (<= 1 000) y `next_seq_after` con la forma de `_metrics` de
`decision-registry` (la recomendacion resuelta dentro de cada `human_decision`, o `null`). Cuenta las conexiones simultaneas y falla
si ve 2 (el pool `projections` de U3 tiene una por replica); inyecta fallos por numero de pagina y latencia. Acepta un token de
prueba; ninguna prueba toca Keycloak.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

TOKEN = "token-de-prueba"


class SimultaneousConnections(AssertionError):  # noqa: N818
    """El doble vio dos lecturas a la vez: U11 rompio NFR-U11-01."""


class FakeToken:
    """`TokenSource` de prueba (`vectra_common.deps.TokenSource`)."""

    async def token(self) -> str:
        return TOKEN

    def invalidate(self) -> None:
        pass


class RegistryDouble:
    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self.entries: list[dict[str, Any]] = sorted(entries or [], key=lambda item: item["seq"])
        self.requests: list[dict[str, str]] = []  # los parametros de cada solicitud, en orden
        self.fail_requests: set[int] = set()  # numeros de solicitud (desde 1) que responden 503
        self.fail_all = False
        self.timeout_requests: set[int] = set()
        self.latency = 0.0
        self.active = 0
        self.max_active = 0
        self.calls = 0

    # -- datos --
    def add(self, items: list[dict[str, Any]]) -> None:
        self.entries = sorted([*self.entries, *items], key=lambda item: item["seq"])

    # -- el transporte --
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.active > 1:
                raise SimultaneousConnections(f"{self.active} conexiones simultaneas")
            self.calls += 1
            number = self.calls
            params = dict(request.url.params)
            self.requests.append(params)
            if self.latency:
                await asyncio.sleep(self.latency)
            if request.headers.get("authorization") != f"Bearer {TOKEN}":
                return httpx.Response(401, json={"title": "unauthorized"})
            if number in self.timeout_requests:
                raise httpx.ReadTimeout("timeout inyectado", request=request)
            if self.fail_all or number in self.fail_requests:
                return httpx.Response(503, json={"title": "dependency_unavailable"})
            return self._page(request.url.path, params)
        finally:
            self.active -= 1

    def _page(self, path: str, params: Mapping[str, str]) -> httpx.Response:
        if path != "/v1/entries" or params.get("projection") != "metrics":
            return httpx.Response(422, json={"title": "bad_request"})
        limit = int(params.get("limit", "1000"))
        if not 1 <= limit <= 1000:
            return httpx.Response(422, json={"title": "limit_out_of_range"})
        after = int(params["seq_after"]) if "seq_after" in params else -1
        recorded_from = (
            datetime.fromisoformat(params["recorded_from"]).astimezone(UTC)
            if "recorded_from" in params
            else None
        )
        rows = [
            item
            for item in self.entries
            if item["seq"] > after
            and item["entry_type"] == params.get("entry_type", item["entry_type"])
            and (recorded_from is None or datetime.fromisoformat(item["recorded_at"]) >= recorded_from)
        ]
        page, more = rows[:limit], len(rows) > limit
        body = {"items": page, "next_seq_after": page[-1]["seq"] if more else None}
        return httpx.Response(
            200, content=json.dumps(body).encode(), headers={"content-type": "application/json"}
        )
