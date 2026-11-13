"""Cliente de lectura de Loki (U12 Paso 5; INF-U12-03; NFR-U12-50): `/loki/api/v1/query_range`, por `port-forward` a un pod de `vectra-observability`, sin credencial."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Final

import httpx

from vectra_verification.clients.k8s_read import K8sRead
from vectra_verification.clients.prom import QueryResult, read

NAMESPACE: Final = "vectra-observability"
SELECTOR: Final = "app.kubernetes.io/name=loki"
REMOTE_PORT: Final = 3100


class LokiClient:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self._http = httpx.Client(base_url=base_url, transport=transport, timeout=30.0)

    @classmethod
    @contextmanager
    def through_port_forward(
        cls, k8s: K8sRead, *, transport: httpx.BaseTransport | None = None
    ) -> Iterator[LokiClient]:
        with k8s.port_forward(NAMESPACE, SELECTOR, REMOTE_PORT) as forward:
            client = cls(forward.base_url, transport=transport)
            try:
                yield client
            finally:
                client.close()

    def close(self) -> None:
        self._http.close()

    def query_range(self, expression: str, start: datetime, end: datetime, limit: int = 1000) -> QueryResult:
        params: dict[str, str | float] = {
            "query": expression,
            "start": int(start.timestamp() * 1e9),
            "end": int(end.timestamp() * 1e9),
            "limit": limit,
        }
        data = read(self._http, "/loki/api/v1/query_range", params)
        return QueryResult(
            expression, start, end, None, str(data.get("resultType", "")), list(data.get("result", []))
        )
