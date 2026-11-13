"""Dobles de Prometheus y de Loki (U12-T02): la forma `{"status": ..., "data": {...}}` de sus APIs de lectura. Guardan las solicitudes para las pruebas."""

from __future__ import annotations

import httpx


class ObsDouble(httpx.BaseTransport):
    def __init__(self, *, fail: bool = False) -> None:
        self.requests: list[httpx.Request] = []
        self.fail = fail

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail:
            return httpx.Response(
                400, json={"status": "error", "errorType": "bad_data", "error": "parse error"}
            )
        loki = request.url.path.startswith("/loki/")
        result_type = (
            "streams" if loki else ("matrix" if request.url.path.endswith("query_range") else "vector")
        )
        return httpx.Response(
            200, json={"status": "success", "data": {"resultType": result_type, "result": []}}
        )
