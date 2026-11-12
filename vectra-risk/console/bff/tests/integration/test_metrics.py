"""Paso 6 (CA-3): histogramas por ruta y `vectra_bff_dependency_duration_seconds{dependency, route}` (P-U10-11; NFR-U10-34)."""

import bff_metrics
import bff_tokens
import bff_world as w
from bff_support import Bff
from vectra_contracts.routes import REGISTRY

from console_bff.clients import DESTINATIONS

ALL = bff_tokens.bearer(bff_tokens.ROLES)
DEPENDENCY_COUNT = "vectra_bff_dependency_duration_seconds_count"
HTTP_COUNT = "vectra_http_request_duration_seconds_count"


async def test_after_a_request_the_route_histogram_has_the_service_and_the_route_template(bff: Bff) -> None:
    """«Histogramas por ruta» es el de U0 (no se duplica): `service="console-bff"` y la plantilla, nunca el id."""
    before = (
        bff_metrics.value(
            await bff_metrics.scrape(bff),
            HTTP_COUNT,
            service="console-bff",
            route_template="/api/console/cases/{id}",
            method="GET",
            status="200",
        )
        or 0
    )
    response = await bff.client.get(f"/api/console/cases/{w.CASE_LISTO}", headers=ALL)
    assert response.status_code == 200
    after = bff_metrics.value(
        await bff_metrics.scrape(bff),
        HTTP_COUNT,
        service="console-bff",
        route_template="/api/console/cases/{id}",
        method="GET",
        status="200",
    )
    assert after == before + 1
    assert w.CASE_LISTO not in str(await bff_metrics.scrape(bff))


async def test_the_dependency_histogram_is_observed_around_every_destination_call_including_the_pre_reads(
    bff: Bff,
) -> None:
    series = await bff_metrics.scrape(bff)
    labels = {"dependency": "case", "route": "/api/console/cases/{id}/decision"}
    before = bff_metrics.value(series, DEPENDENCY_COUNT, **labels) or 0
    response = await bff.client.post(
        f"/api/console/cases/{w.CASE_LISTO}/decision",
        headers=ALL,
        json=w.REQUESTS["post_api_console_cases_id_decision"].body,
    )
    assert response.status_code == 200
    # la lectura previa (get_case) y la escritura (record_decision): dos observaciones del mismo destino y ruta
    assert bff_metrics.value(await bff_metrics.scrape(bff), DEPENDENCY_COUNT, **labels) == before + 2


async def test_the_dependency_histogram_also_records_a_failed_call(bff: Bff) -> None:
    labels = {"dependency": "bias", "route": "/api/console/freezes"}
    before = bff_metrics.value(await bff_metrics.scrape(bff), DEPENDENCY_COUNT, **labels) or 0
    bff.doubles.bias.down()
    assert (await bff.client.get("/api/console/freezes", headers=ALL)).status_code == 503
    assert bff_metrics.value(await bff_metrics.scrape(bff), DEPENDENCY_COUNT, **labels) == before + 1


async def test_dependency_and_route_labels_are_closed_sets_and_never_an_identifier(bff: Bff) -> None:
    """NFR-U10-34: tras llamar a los 30 endpoints, `dependency` es uno de los cinco destinos y `route` una de las 30 plantillas."""
    for endpoint in w.ENDPOINTS:
        url = endpoint.path + (f"?{endpoint.query}" if endpoint.query else "")
        response = await bff.client.request(
            endpoint.method, url, headers={**ALL, **endpoint.headers}, json=endpoint.body
        )
        assert response.status_code < 300, (endpoint.operation_id, response.text)
    series = await bff_metrics.scrape(bff)
    templates = {r.path for r in REGISTRY["console-bff"]}
    seen = series[DEPENDENCY_COUNT]
    assert {labels["dependency"] for labels, _ in seen} == set(DESTINATIONS)
    assert {labels["route"] for labels, _ in seen} <= templates
    for labels, _ in seen:
        assert set(labels) == {"dependency", "route"}
    # y ninguna etiqueta de ninguna serie del BFF lleva un identificador de los usados en la prueba
    text = " ".join(
        str(labels)
        for name in series
        if name.startswith(("vectra_bff", "vectra_console"))
        for labels, _ in series[name]
    )
    for identifier in (w.CASE_LISTO, w.CASE_DECIDIDO, "mv-activo", "chk-1", "freeze-mv-1", "pv-1", "ds-1"):
        assert identifier not in text


async def test_the_circuit_state_is_published_for_each_of_the_five_destinations(bff: Bff) -> None:
    series = await bff_metrics.scrape(bff)
    states = {labels["dependency"]: number for labels, number in series["vectra_circuit_state"]}
    assert set(DESTINATIONS) <= set(states)
