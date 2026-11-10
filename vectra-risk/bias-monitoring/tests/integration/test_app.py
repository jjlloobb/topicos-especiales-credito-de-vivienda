"""Paso 9: el servicio contra los dobles (BR-U9-13, 17, 18, 19; P-U9-03, 05; NFR-U9-12, 32, 33, 41; US-304, US-306, US-307)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pydantic import TypeAdapter
from builders import compare_request, uniform
from prometheus_client.parser import text_string_to_metric_families
from scenario import NOW, POLICY, make_deps, seed
from service_support import SERVICE, TODAY, Service, service, utc, write_policy
from vectra_bias import app as bias_app
from vectra_bias import config
from vectra_bias.run import run_once
from vectra_common import process
from vectra_common.metrics import CIRCUIT_STATE, REGISTRY
from vectra_contracts.catalog import LOG_RECORD_FIELDS
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.monitoring import DisparityView, FreezeRecord, FreezeSummary, PrePostReport
from vectra_contracts.routes import REGISTRY as ROUTES
from world import World, freeze_record

DISCLAIMER = "mide y alerta, no certifica"
ROOT = Path(__file__).resolve().parents[3]


def run(coro):
    return asyncio.run(coro)


def disparity_world(**kwargs) -> World:
    world = World()
    seed(world, "v1", TODAY, days=5, model="high", human="low", **kwargs)
    return world


# --- P-1: la app exige los cuatro handlers -----------------------------------------------------------------------------------


def test_create_app_without_the_disparity_handler_is_a_contract_violation(monkeypatch):
    from vectra_common.app_factory import create_app

    world = World()
    handlers = bias_app.build_handlers(
        None,
        POLICY,
        None,
        lambda: NOW,  # type: ignore[arg-type]
    )
    missing = {k: v for k, v in handlers.items() if k != ("GET", "/v1/disparity")}
    with pytest.raises(ContractViolation) as error:
        create_app(SERVICE, handlers=missing, authenticator=None, readiness=None)  # noqa: F841
    assert "/v1/disparity" in str(error.value)
    assert world  # el doble no se usa: el contrato falla antes de leer nada


def test_the_four_routes_of_the_contract_are_served_with_the_handlers_keyed_by_the_contract():
    handlers = bias_app.build_handlers(None, POLICY, None, lambda: NOW)  # type: ignore[arg-type]
    assert set(handlers) == {(r.method, r.path) for r in ROUTES[SERVICE]}
    assert len(handlers) == 4


# --- el dashboard: disclaimer, version, ventana, atributo ---------------------------------------------------------------------


def test_the_dashboard_separates_model_and_human_and_carries_the_disclaimer():
    world = disparity_world()
    response = run(Service(world).get("/v1/disparity?version=v1", role="cro"))
    assert response.status_code == 200
    view = DisparityView.model_validate_json(response.text)
    assert view.disclaimer == DISCLAIMER
    # oraculo a mano: region con amazonia 0,5 y andina 0,7 en las tres bandas -> diferencia 0,2000 por banda, agregada 0,2000
    assert view.model.population == "modelo" and view.human.population == "humana"
    assert view.model.model_aggregate == "0.2000" and view.model.trigger_attribute == "region"
    assert view.human.model_aggregate == "0.0000"
    region = next(a for a in view.model.attributes if a.attribute == "region")
    assert region.aggregate == "0.2000" and {b.difference for b in region.bands} == {"0.2000"}
    assert view.model.departure_rates is None
    # humana con tasas 0,5: 0,5 de `se_aparta` (las no favorables) en cada grupo y banda con >= n_min decisiones
    assert view.human.departure_rates and {d.rate for d in view.human.departure_rates} == {"0.5000"}
    assert view.window.to_day == TODAY and view.window.from_day == TODAY - timedelta(
        days=4
    )  # 5 dias de datos
    assert view.computed_at == NOW and view.invalid_entries == 0


def test_small_cells_come_without_a_rate_or_an_aggregate():
    world = World()
    seed(world, "v1", TODAY, days=1, model="high", human="low", n=10)  # 10 < n_min = 30
    view = DisparityView.model_validate_json(run(Service(world).get("/v1/disparity?version=v1")).text)
    cells = [c for a in view.model.attributes for c in a.cells]
    assert cells and all(c.status == "muestra_insuficiente" and c.rate is None for c in cells)
    assert view.model.model_aggregate is None and view.model.trigger_attribute is None


def test_the_attribute_filter_keeps_only_that_attribute():
    world = disparity_world()
    view = DisparityView.model_validate_json(
        run(Service(world).get("/v1/disparity?version=v1&attribute=sexo")).text
    )
    assert (
        [a.attribute for a in view.model.attributes]
        == [a.attribute for a in view.human.attributes]
        == ["sexo"]
    )
    assert view.model.model_aggregate == "0.0000"  # la agregada de `sexo`, no la de `region` (0,2000)


def test_the_window_filter_sets_the_start_and_defaults_to_the_policy_window():
    world = World()
    seed(world, "v1", TODAY, days=60, model="low", human="low", n=40)
    service_ = Service(world)
    by_default = DisparityView.model_validate_json(run(service_.get("/v1/disparity?version=v1")).text)
    seven = DisparityView.model_validate_json(run(service_.get("/v1/disparity?version=v1&window=7")).text)
    assert by_default.window.from_day == TODAY - timedelta(days=29)  # `window_days` de la politica: 30
    assert seven.window.from_day == TODAY - timedelta(days=6)
    assert run(service_.get("/v1/disparity?version=v1&window=15")).status_code == 422  # solo 7, 30 o 90


def test_invalid_entries_are_the_sum_of_the_requested_ranges():
    world = World()
    seed(world, "v1", TODAY, days=2, model="low", human="low", invalid_per_day=3)
    view = DisparityView.model_validate_json(run(Service(world).get("/v1/disparity?version=v1")).text)
    assert view.invalid_entries == 6  # 3 por dia en `modelo`, 2 dias


def test_with_a_version_that_version_and_without_it_the_one_with_the_most_recent_recommendations():
    world = World()
    seed(world, "v-old", TODAY - timedelta(days=3), days=3, model="low", human="low")
    seed(world, "v-new", TODAY, days=3, model="low", human="low")
    service_ = Service(world)
    assert (
        DisparityView.model_validate_json(
            run(service_.get("/v1/disparity?version=v-old")).text
        ).model_version_id
        == "v-old"
    )
    assert (
        DisparityView.model_validate_json(run(service_.get("/v1/disparity")).text).model_version_id == "v-new"
    )


def test_without_a_version_and_without_data_the_answer_is_404_and_a_version_without_data_is_all_insufficient():
    world = World()
    assert run(Service(world).get("/v1/disparity")).status_code == 404
    view = DisparityView.model_validate_json(run(Service(world).get("/v1/disparity?version=none")).text)
    assert view.model.model_aggregate is None and view.invalid_entries == 0


# --- BR-U9-13: los cinco parametros salen del ConfigMap ----------------------------------------------------------------------


TEST_POLICY = config.MonitoringPolicy(
    threshold_pp=Decimal(7), n_min=40, window_days=20, schedule="4,14,24,34,44,54 * * * *", stale_after_s=7200
)


def test_the_policy_file_of_the_test_gives_the_five_parameters_in_the_dashboard_and_in_the_package(tmp_path):
    path = write_policy(tmp_path / "values-monitoring-policy.yaml", TEST_POLICY)
    loaded = config.load_policy(path)
    assert loaded == TEST_POLICY  # lo que lee el servicio de `VECTRA_POLICY_PATH`
    world = World()
    seed(world, "v1", TODAY, days=3, model="high", human="low")
    # una corrida real de `run` con esa politica: el `freeze` llega al doble de U4 y el doble de U3 lo devuelve
    outcome = run(run_once(make_deps(world, lambda: NOW, policy=loaded)))
    assert outcome.report.complete and world.governance.frozen == {"v1"}
    package = world.governance.packages[0].model_dump(mode="json")
    world.registry.freezes = [
        {
            "freeze_id": "freeze-v1",
            "model_version_id": "v1",
            "frozen_at": NOW.isoformat(),
            "context_package": {**package, "data_sources": [], "initial_disparity": {"attributes": []}},
            "resolutions": [],
        }
    ]
    process.reset_for_tests()  # `run` es un proceso batch; el servicio, otro
    service_ = Service(world, policy=loaded)
    view = DisparityView.model_validate_json(run(service_.get("/v1/disparity?version=v1")).text)
    assert (view.threshold_pp, view.n_min, view.window_days, view.schedule, view.stale_after_s) == (
        "7.0000", 40, 20, "4,14,24,34,44,54 * * * *", 7200,
    )  # fmt: skip
    record = FreezeRecord.model_validate_json(run(service_.get("/v1/freezes/freeze-v1")).text)
    inside = record.context_package
    assert (inside.threshold_pp, inside.n_min, inside.window_days, inside.schedule, inside.stale_after_s) == (
        "7.0000", 40, 20, "4,14,24,34,44,54 * * * *", 7200,
    )  # fmt: skip
    assert inside.trigger_attribute == "region"


# --- congelamientos -----------------------------------------------------------------------------------------------------


def two_resolutions_world(day_of_reactivation: datetime) -> World:
    world = World()
    seed(world, "v1", TODAY, days=6, model="low", human="low", n=100)
    world.registry.freezes = [
        freeze_record(
            "v1",
            TODAY_START - timedelta(days=5),
            [("investigar", day_of_reactivation - timedelta(hours=5)), ("reactivar", day_of_reactivation)],
        ),
        freeze_record("v2", TODAY_START - timedelta(days=4)),
    ]
    return world


TODAY_START = utc(TODAY.year, TODAY.month, TODAY.day)


def test_investigar_followed_by_reactivar_shows_the_reactivation_and_restarts_the_window_the_day_after():
    day_d = TODAY - timedelta(days=2)
    reactivated = utc(day_d.year, day_d.month, day_d.day, 23, 50)
    world = two_resolutions_world(reactivated)
    service_ = Service(world)
    summaries = json.loads(run(service_.get("/v1/freezes")).text)
    by_version = {s["model_version_id"]: s for s in summaries}
    assert by_version["v1"]["resolution"] == {
        "action": "reactivar",
        "recorded_at": reactivated.isoformat().replace("+00:00", "Z"),
    }
    assert "resolution" not in by_version["v2"]
    view = DisparityView.model_validate_json(run(service_.get("/v1/disparity?version=v1")).text)
    assert view.window.from_day == day_d + timedelta(days=1)  # BR-U9-08: mide desde D + 1
    assert view.window.to_day == TODAY


def test_the_list_of_freezes_is_a_list_of_summaries_with_the_trigger_and_the_aggregate_of_the_package():
    world = World()
    world.registry.freezes = [freeze_record("v1", NOW - timedelta(days=1))]
    response = run(Service(world).get("/v1/freezes", role="cro"))
    assert response.status_code == 200
    [summary] = TypeAdapter(list[FreezeSummary]).validate_json(response.text)
    assert (summary.freeze_id, summary.trigger_attribute, summary.model_aggregate, summary.resolution) == (
        "freeze-v1", "region", None, None,
    )  # fmt: skip


def test_a_freeze_by_id_is_the_freeze_record_of_u0_and_an_unknown_id_is_404():
    world = World()
    world.registry.freezes = [freeze_record("v1", NOW - timedelta(days=1)), freeze_record("v2", NOW)]
    service_ = Service(world)
    found = run(service_.get("/v1/freezes/freeze-v2"))
    assert found.status_code == 200
    record = FreezeRecord.model_validate_json(found.text)
    assert record.freeze_id == "freeze-v2" and record.model_version_id == "v2"
    assert record.context_package.initial_disparity.attributes == []
    missing = run(service_.get("/v1/freezes/freeze-none"))
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"


# --- compare ------------------------------------------------------------------------------------------------------------------


def _compare(service_: Service, request, headers=None):
    return run(
        service_.client.post(
            "/v1/source-comparisons",
            content=request.model_dump_json(),
            headers={"content-type": "application/json", **(headers or service("bias:compare"))},
        )
    )


def test_compare_answers_a_pre_post_report_with_the_disclaimer_to_governance():
    service_ = Service(World())
    response = _compare(service_, compare_request("fuente-7", uniform(0.5, 100), uniform(0.6, 100)))
    assert response.status_code == 200
    report = PrePostReport.model_validate_json(response.text)
    assert report.disclaimer == DISCLAIMER and report.source_id == "fuente-7" and not report.truncated


def test_compare_with_a_group_or_a_band_outside_the_catalog_is_a_422_validation_error():
    service_ = Service(World())
    request = compare_request("f", uniform(0.5, 100), uniform(0.5, 100))
    bad_group = json.loads(request.model_dump_json())
    bad_group["pre"][2]["cells"][0]["group"] = "Bogota"
    bad_band = json.loads(request.model_dump_json())
    bad_band["post"][0]["cells"][0]["band"] = "lt_99"
    for body in (bad_group, bad_band):
        response = run(
            service_.client.post(
                "/v1/source-comparisons",
                content=json.dumps(body),
                headers={"content-type": "application/json", **service("bias:compare")},
            )
        )
        assert response.status_code == 422 and response.json()["code"] == "validation_error"
        assert "Bogota" not in response.text


# --- autorizacion --------------------------------------------------------------------------------------------------------------


def test_a_role_not_allowed_is_a_403_with_the_authz_denied_event():
    world = World()
    world.registry.freezes = [freeze_record("v1", NOW)]
    service_ = Service(world)
    denied = [
        run(service_.get("/v1/freezes/freeze-v1", role="cro")),
        run(service_.get("/v1/disparity", role="analista")),
        _compare(
            service_,
            compare_request("f", uniform(0.5, 100), uniform(0.5, 100)),
            service("registry:read:monitoring"),
        ),
    ]
    assert [r.status_code for r in denied] == [403, 403, 403]
    assert len(service_.events("authz.denied")) == 3
    assert world.registry.calls == []  # nada llego al registro


# --- frases prohibidas (BR-U0-94; US-307) ------------------------------------------------------------------------------------


def _forbidden():
    spec = importlib.util.spec_from_file_location(
        "forbidden_phrases", ROOT / "contracts/tools/forbidden_phrases.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_lint_of_forbidden_phrases_finds_one_and_no_response_of_the_four_routes_has_any():
    lint = _forbidden()
    patterns = lint.load_patterns()
    assert lint.find_violations("el modelo es unbiased", patterns)  # la lista de U0 se carga y detecta
    world = disparity_world()
    world.registry.freezes = [freeze_record("v1", NOW)]
    service_ = Service(world)
    bodies = [
        run(service_.get("/v1/disparity?version=v1")).text,
        run(service_.get("/v1/freezes")).text,
        run(service_.get("/v1/freezes/freeze-v1")).text,
        _compare(service_, compare_request("f", uniform(0.5, 100), uniform(0.6, 100))).text,
    ]
    assert all(bodies)
    assert [lint.find_violations(body, patterns) for body in bodies] == [[], [], [], []]
    assert lint.find_violations(DISCLAIMER, patterns) == []


# --- registro caido -------------------------------------------------------------------------------------------------------------


class Down(httpx.AsyncBaseTransport):
    """El registro caido: toda llamada falla con un error de conexion y se cuenta."""

    def __init__(self) -> None:
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        raise httpx.ConnectError("registry down", request=request)


def test_with_the_registry_down_at_startup_the_pod_is_ready_and_the_query_is_a_503_without_data():
    down = Down()
    service_ = Service(World(), transport=down)
    ops = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=service_.app.state.ops_app), base_url="http://ops"
    )
    assert run(ops.get("/readyz")).status_code == 200 and run(ops.get("/healthz")).status_code == 200
    response = run(service_.get("/v1/disparity?version=v1"))
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
    assert "model" not in response.json() and "attributes" not in response.text
    assert run(service_.get("/v1/freezes")).status_code == 503


def test_after_20_failed_calls_the_circuit_opens_and_the_double_gets_no_more_calls():
    down = Down()
    service_ = Service(World(), transport=down)
    for _ in range(20):
        assert run(service_.get("/v1/disparity?version=v1")).status_code == 503
    assert down.calls == 20
    assert CIRCUIT_STATE.labels(dependency="registry")._value.get() == 2
    for _ in range(5):
        assert run(service_.get("/v1/disparity?version=v1")).status_code == 503
    assert down.calls == 20  # circuito abierto: ni una llamada mas


def test_a_registry_5xx_and_a_malformed_answer_are_503s_too():
    world = disparity_world()
    service_ = Service(world)
    world.registry.status = 500
    assert run(service_.get("/v1/freezes")).status_code == 503
    world.registry.status = None
    world.registry.freezes = [{"freeze_id": "x"}]  # no valida contra U0
    assert run(service_.get("/v1/disparity?version=v1")).status_code == 503


# --- logs (NFR-U9-32) ----------------------------------------------------------------------------------------------------------


def test_a_query_served_from_the_cache_logs_the_viewer_not_the_one_who_filled_the_cache():
    world = disparity_world()
    service_ = Service(world)
    run(service_.get("/v1/disparity?version=v1", subject="alicia"))
    reads = len(world.registry.calls)
    run(service_.get("/v1/disparity?version=v1", role="cro", subject="bruno"))
    assert len(world.registry.calls) == reads  # la segunda salio de la cache
    viewed = service_.events("disparity.viewed")
    assert [e["principal_subject"] for e in viewed] == ["alicia", "bruno"]
    assert [e["principal_role"] for e in viewed] == ["cumplimiento", "cro"]
    assert {e["model_version_id"] for e in viewed} == {"v1"}
    assert (
        viewed[1]["window_from"] == (TODAY - timedelta(days=4)).isoformat()
        and viewed[1]["window_to"] == TODAY.isoformat()
    )


def test_pbt_u0_07_the_two_events_use_only_fields_of_the_catalog_in_strict_mode(monkeypatch):
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    world = disparity_world()
    world.registry.freezes = [freeze_record("v1", NOW)]
    service_ = Service(world)
    assert run(service_.get("/v1/disparity?version=v1")).status_code == 200
    assert run(service_.get("/v1/freezes/freeze-v1")).status_code == 200
    viewed, context = service_.events("disparity.viewed"), service_.events("freeze_context.viewed")
    assert len(viewed) == len(context) == 1
    assert set(viewed[0]) <= LOG_RECORD_FIELDS and set(context[0]) <= LOG_RECORD_FIELDS
    assert {"principal_subject", "principal_role", "model_version_id", "window_from", "window_to"} <= set(
        viewed[0]
    )
    assert {"principal_subject", "principal_role", "model_version_id"} <= set(context[0])
    assert "window_from" not in context[0]


# --- metricas (NFR-U9-41) ---------------------------------------------------------------------------------------------------


ALLOWED_LABELS = {"service", "route_template", "method", "status", "code", "result", "dependency", "event"}
FORBIDDEN_LABELS = {
    "model_version_id",
    "freeze_id",
    "source_id",
    "principal_subject",
    "principal_role",
    "principal_kind",
}


def test_metrics_expose_the_http_and_cache_series_without_identifiers_in_the_labels():
    world = disparity_world()
    world.registry.freezes = [freeze_record("v1", NOW)]
    service_ = Service(world)
    run(service_.get("/v1/disparity?version=v1"))
    run(service_.get("/v1/disparity?version=v1"))
    run(service_.get("/v1/freezes/freeze-v1"))
    ops = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=service_.app.state.ops_app), base_url="http://ops"
    )
    text = run(ops.get("/metrics")).text
    families = {f.name: f for f in text_string_to_metric_families(text)}
    assert any(
        s.labels.get("service") == SERVICE and s.labels.get("route_template") == "/v1/disparity"
        for s in families["vectra_http_request_duration_seconds"].samples
    )
    assert {s.labels["result"] for s in families["vectra_bias_cache_lookups"].samples if s.name.endswith("_total")} == {
        "hit", "miss", "coalesced",
    }  # fmt: skip
    assert "vectra_bias_cache_entries" in families
    seen: set[str] = set()
    for name, family in families.items():
        if name.startswith("vectra_"):
            for sample in family.samples:
                seen |= set(sample.labels) - {
                    "le"
                }  # `le` es el borde de cada bucket del histograma, no una etiqueta propia
    assert seen <= ALLOWED_LABELS, seen - ALLOWED_LABELS
    assert not seen & FORBIDDEN_LABELS
    assert not any(
        label in text for label in ('model_version_id="', 'freeze_id="', 'source_id="', "principal_")
    )
    assert REGISTRY  # el registro es el de U0
