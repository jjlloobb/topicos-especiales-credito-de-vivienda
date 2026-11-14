"""Prometheus de mentira para `u11` (U12-T04): los cuatro paneles de `product.json` y la alerta `ProductMetricsStale`."""

import httpx
from vectra_verification.scenarios import u11


class Prom(httpx.BaseTransport):
    """Prometheus de mentira: `values` da el valor por expresion (ausente = vector vacio); `stale` pone la alerta en firing; `down` responde 503."""

    def __init__(
        self, *, absent: tuple[str, ...] = (), stale: bool = False, down: bool = False, value: str = "0.4"
    ) -> None:
        self.absent, self.stale, self.down, self.value = absent, stale, down, value
        self.queries: list[str] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503, json={"status": "error", "errorType": "unavailable", "error": "x"})
        expression = request.url.params["query"]
        self.queries.append(expression)
        if expression == u11.STALE:
            result = (
                [{"metric": {"alertname": "ProductMetricsStale"}, "value": [1.0, "1"]}] if self.stale else []
            )
        elif any(a in expression for a in self.absent):
            result = []
        else:
            result = [{"metric": {}, "value": [1.0, self.value]}]
        return httpx.Response(
            200, json={"status": "success", "data": {"resultType": "vector", "result": result}}
        )
