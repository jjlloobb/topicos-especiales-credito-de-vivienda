"""Cliente de lectura de Prometheus (U12 Paso 5; INF-U12-03; NFR-U12-50): `/api/v1/query` y `/api/v1/query_range`, por `port-forward` a un pod de `vectra-observability`, sin credencial.

Cada resultado devuelve tambien el texto de la consulta y su ventana, para que U12-T04 los guarde como evidencia (NFR-U12-50). `status: error` es un error.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

import httpx

from vectra_verification.clients.k8s_read import K8sRead

NAMESPACE: Final = "vectra-observability"
SELECTOR: Final = "app.kubernetes.io/name=prometheus"
REMOTE_PORT: Final = 9090


class ObsError(Exception):
    """Prometheus o Loki respondio un error o algo que no es la respuesta esperada. Sin credenciales: no las hay."""


@dataclass(frozen=True)
class QueryResult:
    query: str
    start: datetime | None
    end: datetime | None
    step: float | None
    result_type: str
    result: list[Any]


def read(http: httpx.Client, path: str, params: dict[str, str | float]) -> dict[str, Any]:
    try:
        response = http.get(path, params=params)
    except httpx.HTTPError as error:
        raise ObsError(f"unreachable:{type(error).__name__}") from None
    try:
        body = response.json()
    except ValueError:
        raise ObsError(f"response_shape:http_{response.status_code}") from None
    if (
        response.status_code != 200
        or not isinstance(body, dict)
        or body.get("status") != "success"
        or not isinstance(body.get("data"), dict)
    ):
        raise ObsError(
            f"query_failed:http_{response.status_code}:{body.get('errorType', '-') if isinstance(body, dict) else '-'}"
        )
    return dict(body["data"])


class PromClient:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self._http = httpx.Client(base_url=base_url, transport=transport, timeout=30.0)

    @classmethod
    @contextmanager
    def through_port_forward(
        cls, k8s: K8sRead, *, transport: httpx.BaseTransport | None = None
    ) -> Iterator[PromClient]:
        with k8s.port_forward(NAMESPACE, SELECTOR, REMOTE_PORT) as forward:
            client = cls(forward.base_url, transport=transport)
            try:
                yield client
            finally:
                client.close()

    def close(self) -> None:
        self._http.close()

    def query(self, expression: str, at: datetime | None = None) -> QueryResult:
        params: dict[str, str | float] = {"query": expression}
        if at is not None:
            params["time"] = at.timestamp()
        data = read(self._http, "/api/v1/query", params)
        return QueryResult(
            expression, at, at, None, str(data.get("resultType", "")), list(data.get("result", []))
        )

    def query_range(self, expression: str, start: datetime, end: datetime, step: float) -> QueryResult:
        params: dict[str, str | float] = {
            "query": expression,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        }
        data = read(self._http, "/api/v1/query_range", params)
        return QueryResult(
            expression, start, end, step, str(data.get("resultType", "")), list(data.get("result", []))
        )
