"""Lectura de `/metrics` del puerto 8081 de la app (`app.state.ops_app`), como lo hace Prometheus."""

import httpx
from bff_support import Bff
from prometheus_client.parser import text_string_to_metric_families


async def scrape(bff: Bff) -> dict[str, list[tuple[dict[str, str], float]]]:
    """nombre de la serie (con su sufijo) -> [(etiquetas, valor)], de la salida de texto de `GET /metrics`."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=bff.app.state.ops_app), base_url="http://ops.test"
    ) as ops:
        response = await ops.get("/metrics")
    assert response.status_code == 200
    return parse(response.text)


def parse(text: str) -> dict[str, list[tuple[dict[str, str], float]]]:
    series: dict[str, list[tuple[dict[str, str], float]]] = {}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            series.setdefault(sample.name, []).append((dict(sample.labels), sample.value))
    return series


def value(series: dict[str, list[tuple[dict[str, str], float]]], name: str, **labels: str) -> float | None:
    for found, number in series.get(name, []):
        if all(found.get(k) == v for k, v in labels.items()):
            return number
    return None
