"""CA-7 y CA-8: los clientes con dobles (U12 Paso 5; INF-U12-03; NFR-U12-02, 50) y los dobles ligeros contra el contrato (lecciones de la enmienda §8)."""

import inspect
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from contract_world import (
    BFF_SPEC,
    CASE_SPEC,
    INTAKE_GATEWAY,
    ContractError,
    LightGateway,
    case_detail_json,
    check_served,
    problem,
)
from fake_clock import FakeClock
from kubectl_double import KubectlDouble, pod
from obs_double import ObsDouble
from registry_read_double import ENTRIES_PARAMS, REGISTRY_SPEC, RegistryReadDouble, freeze_item, metrics_item
from vault_double import CountingTransport
from vectra_contracts.models import api as api_models
from vectra_contracts.models import application as app_models
from vectra_contracts.models.api import DecisionIn
from vectra_contracts.models.governance import FrozenResolutionIn, ModelApprovalIn, ModelRegistration
from vectra_contracts.models.registry import FreezeProjection, MetricsProjection

from vectra_verification import guard
from vectra_verification.clients._api import SCENARIO_PATTERN, TRACEPARENT_PATTERN, ApiError, RunTag
from vectra_verification.clients.bff import BffClient
from vectra_verification.clients.gateway import GatewayClient
from vectra_verification.clients.k8s_read import K8sError, K8sRead
from vectra_verification.clients.loki import LokiClient
from vectra_verification.clients.prom import ObsError, PromClient
from vectra_verification.clients.registry import RegistryClient
from vectra_verification.guard import GuardError

TAG = RunTag("decisions", "3fa9c2d1")
CASE_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
APPLICATION = app_models.ApplicationIn.model_validate_json(
    '{"full_name":"Ana Gomez","document_type":"CC","document_number":"1020304050","birth_date":"1985-03-14","phone":"3001234567","email":"ana@example.com","address":"Cra 7 # 45-10",'
    '"municipality_code":"11001","department_code":"11","monthly_income":8000000,"other_income":0,"employment_type":"asalariado","employment_months":48,"monthly_obligations":500000,'
    '"max_days_past_due_12m":0,"property_value":300000000,"requested_amount":150000000,"term_months":180,"proposed_rate_ea":"0.1200","property_condition":"usada","channel":"web"}'
)


class Session:
    def __init__(self, user: str = "analista-1", step_up: bool = False) -> None:
        self.user, self.step_up, self.refreshed = user, step_up, 0

    def bearer(self) -> str:
        return f"tok-{self.user}"

    def refresh(self) -> None:
        self.refreshed += 1


def _gateway_world(environment: guard.Environment) -> tuple[LightGateway, GatewayClient, BffClient]:
    light = LightGateway(FakeClock())
    light.cases[CASE_ID] = case_detail_json(CASE_ID, "listo", "favorable")
    import bff_builders

    light.models["mv-9"] = bff_builders.model_version("mv-9", "lista_para_aprobacion")
    return (
        light,
        GatewayClient(environment, lambda: "tok-channel-simulator", TAG, transport=light),
        BffClient(environment, Session("cumplimiento-1", step_up=True), TAG, transport=light),
    )


def _public(cls: type) -> set[str]:
    return {
        n
        for n, m in inspect.getmembers(cls, inspect.isfunction)
        if not n.startswith("_") and m.__qualname__.startswith(cls.__name__) and n != "close"
    }


def test_every_public_method_of_gateway_and_bff_carries_the_header_and_the_prefix(
    dynamic_environment: guard.Environment,
) -> None:
    light, gateway, bff = _gateway_world(dynamic_environment)
    calls = {
        "submit_application": lambda: gateway.submit_application(APPLICATION, "k-0001"),
        "me": bff.me,
        "list_cases": bff.list_cases,
        "get_case": lambda: bff.get_case(CASE_ID),
        "record_explanation_view": lambda: bff.record_explanation_view(CASE_ID),
        "record_decision": lambda: bff.record_decision(
            CASE_ID,
            DecisionIn.model_validate_json(
                '{"decision":"sigue","final_outcome":"favorable","used_factors":["ninguno"],"justification":""}'
            ),
        ),
        "resolve_frozen": lambda: bff.resolve_frozen(
            "mv-1", FrozenResolutionIn(action="reactivar", justification="revisado"), "rt2"
        ),
        # U12-T03: las rutas de modelos del BFF
        "list_models": bff.list_models,
        "get_model": lambda: bff.get_model("mv-9"),
        "register_model": lambda: bff.register_model(
            ModelRegistration.model_validate(
                {
                    "artifact_uri": "s3://model-store/mv-10/predictor.json",
                    "artifact_format": "xgboost_json",
                    "artifact_sha256": "a" * 64,
                    "explainer_uri": "s3://model-store/mv-10/explainer.json",
                    "explainer_sha256": "b" * 64,
                    "manifest_uri": "s3://model-store/mv-10/manifest.json",
                    "manifest_sha256": "c" * 64,
                }
            )
        ),
        "start_validation": lambda: bff.start_validation("mv-9"),
        "approve_model": lambda: bff.approve_model("mv-9", ModelApprovalIn(decision="aprobado")),
    }
    # la prueba falla si aparece un metodo nuevo sin cubrir
    assert set(calls) == _public(GatewayClient) | _public(BffClient)
    trace_ids: list[str] = []
    for name, call in calls.items():
        before = len(light.requests)
        call()
        (request,) = light.requests[before:]
        assert (
            SCENARIO_PATTERN.fullmatch(request.headers["X-Test-Scenario"])
            and request.headers["X-Test-Scenario"] == "decisions.3fa9c2d1"
        ), name
        assert TRACEPARENT_PATTERN.fullmatch(request.headers["traceparent"]), name
        trace_ids.append(request.headers["traceparent"].split("-")[1])
        assert request.headers["Authorization"].startswith("Bearer tok-"), name
    assert all(t.startswith("3fa9c2d1") for t in trace_ids) and len(set(trace_ids)) == len(trace_ids)


def test_the_header_is_set_in_one_place_not_in_every_method() -> None:
    import vectra_verification.clients.bff as bff_module
    import vectra_verification.clients.gateway as gateway_module

    for module in (bff_module, gateway_module):
        assert "X-Test-Scenario" not in inspect.getsource(module) and "traceparent" not in inspect.getsource(
            module
        )


def test_errors_are_problems_with_status_code_and_reason_and_never_the_authorization(
    dynamic_environment: guard.Environment,
) -> None:
    light, _, bff = _gateway_world(dynamic_environment)
    light.conflict_ids.add(CASE_ID)
    decision = DecisionIn.model_validate_json(
        '{"decision":"sigue","final_outcome":"favorable","used_factors":["ninguno"],"justification":""}'
    )
    with pytest.raises(ApiError) as error:
        bff.record_decision(CASE_ID, decision)
    assert (error.value.status, error.value.code, error.value.reason) == (
        409,
        "conflict_state",
        "decision_already_recorded",
    )
    assert "tok-" not in str(error.value) and "Bearer" not in str(error.value)


def test_a_2xx_response_that_does_not_validate_is_an_error_not_data(
    dynamic_environment: guard.Environment,
) -> None:
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json={"case_id": CASE_ID, "state": "en_evaluacion", "extra": 1})
    )
    gateway = GatewayClient(dynamic_environment, lambda: "t", TAG, transport=transport)
    with pytest.raises(ApiError, match="invalid_response"):
        gateway.submit_application(APPLICATION, "k-1")


def test_resolve_frozen_outside_rt2_is_refused_with_zero_requests_and_needs_step_up(
    dynamic_environment: guard.Environment,
) -> None:
    light = LightGateway()
    bff = BffClient(dynamic_environment, Session("cumplimiento-1", step_up=True), TAG, transport=light)
    with pytest.raises(GuardError, match="reactivation_outside_rt2"):
        bff.resolve_frozen("mv-1", FrozenResolutionIn(action="reactivar", justification="x"), "decisions")
    plain = BffClient(dynamic_environment, Session("cumplimiento-1", step_up=False), TAG, transport=light)
    with pytest.raises(ApiError, match="step_up_required"):
        plain.resolve_frozen("mv-1", FrozenResolutionIn(action="reactivar", justification="x"), "rt2")
    assert light.requests == []


def test_a_production_host_sends_zero_requests() -> None:
    counting = CountingTransport()
    prod = guard.Environment(
        "kind", "vectra.banco.internal", "https://vectra.banco.internal/auth/realms/vectra"
    )
    with pytest.raises(GuardError, match="environment_not_allowed"):
        GatewayClient(prod, lambda: "t", TAG, transport=counting)
    with pytest.raises(GuardError):
        BffClient(prod, Session(), TAG, transport=counting)
    assert counting.count == 0


# ---- registro, prom, loki y port-forward ------------------------------------------------------------------------------------------------------


def test_the_registry_client_sends_the_verification_reader_token_and_only_parameters_of_the_openapi() -> None:
    double = RegistryReadDouble("tok-verification-reader", [metrics_item(i) for i in range(5)])
    client = RegistryClient("http://registry.test", lambda: "tok-verification-reader", transport=double)
    got = client.metrics(
        case_id=UUID(CASE_ID),
        entry_type="recommendation",
        recorded_from=datetime(2026, 11, 13, tzinfo=UTC),
        recorded_to=datetime(2026, 11, 14, tzinfo=UTC),
        limit=2,
    )
    assert [m.seq for m in got] == [0, 1, 2, 3, 4] and all(
        isinstance(m, MetricsProjection) for m in got
    )  # la paginacion se agota
    assert len(double.requests) == 3
    openapi_names = {p["name"] for p in REGISTRY_SPEC["paths"]["/v1/entries"]["get"]["parameters"]}
    assert openapi_names == ENTRIES_PARAMS
    for request in double.requests:
        assert (
            request.headers["Authorization"] == "Bearer tok-verification-reader"
            and set(request.url.params) <= openapi_names
        )
        assert request.url.params["projection"] == "metrics"


def test_projection_monitoring_freezes_returns_freeze_projections_and_a_bad_response_is_an_error() -> None:
    double = RegistryReadDouble("t", [freeze_item(1)])
    client = RegistryClient("http://registry.test", lambda: "t", transport=double)
    (freeze,) = client.freezes()
    assert (
        isinstance(freeze, FreezeProjection)
        and double.requests[0].url.params["projection"] == "monitoring_freezes"
    )
    double.corrupt = True
    with pytest.raises(ApiError, match="invalid_response"):
        client.freezes()


def test_registry_through_a_port_forward_that_falls_is_a_clear_error_without_silent_retries() -> None:
    kubectl = KubectlDouble([pod("registry-0"), pod("registry-1")], forwards=[None, None])
    with (
        pytest.raises(K8sError, match=r"vectra-app/pod/registry-1.*attempts=2"),
        RegistryClient.through_port_forward(K8sRead(kubectl), lambda: "t"),
    ):
        pass
    assert len(kubectl.forward_calls) == 2


def test_registry_through_a_port_forward_goes_to_a_pod_never_a_service_and_the_process_dies_on_exit() -> None:
    kubectl = KubectlDouble([pod("registry-0")])
    double = RegistryReadDouble("t", [metrics_item(1)])
    with RegistryClient.through_port_forward(K8sRead(kubectl), lambda: "t", transport=double) as client:
        assert client.forward is not None and client.forward.local_port == 41234
        client.metrics()
    (call,) = kubectl.forward_calls
    assert "pod/registry-0" in call and not any(a.startswith("svc/") for a in call) and "vectra-app" in call
    assert kubectl.processes[0].terminated


def test_prom_and_loki_return_the_query_and_the_window_and_an_error_status_is_an_error() -> None:
    start, end = datetime(2026, 11, 13, 10, tzinfo=UTC), datetime(2026, 11, 13, 11, tzinfo=UTC)
    obs = ObsDouble()
    prom = PromClient("http://prom.test", transport=obs)
    instant = prom.query("up", at=end)
    ranged = prom.query_range("rate(x[5m])", start, end, 60)
    assert (instant.query, instant.result_type) == ("up", "vector") and (
        ranged.query,
        ranged.start,
        ranged.end,
        ranged.step,
    ) == ("rate(x[5m])", start, end, 60)
    assert dict(obs.requests[1].url.params) | {
        "start": str(start.timestamp()),
        "end": str(end.timestamp()),
        "step": "60",
    } == dict(obs.requests[1].url.params)
    loki = LokiClient("http://loki.test", transport=obs).query_range('{app="x"}', start, end)
    assert (
        loki.query == '{app="x"}'
        and (loki.start, loki.end) == (start, end)
        and obs.requests[2].url.path == "/loki/api/v1/query_range"
    )
    with pytest.raises(ObsError, match="query_failed"):
        PromClient("http://prom.test", transport=ObsDouble(fail=True)).query("bad(")


# ---- CA-8: los dobles ligeros se parecen al contrato ------------------------------------------------------------------------------------------


def test_contract_every_route_and_method_the_light_double_serves_exists_in_the_openapi() -> None:
    light = LightGateway()
    for template, (method, _) in light._routes():  # noqa: SLF001
        assert method.lower() in BFF_SPEC["paths"][template], template
    assert "post" in CASE_SPEC["paths"]["/v1/intake/applications"] and INTAKE_GATEWAY.endswith(
        "/v1/intake/applications"
    )


def test_contract_openapi_a_served_201_for_the_intake_is_refused() -> None:
    """Rojo de CA-8: el contrato dice 200 para la ingesta."""
    with pytest.raises(ContractError, match="no declara 201"):
        check_served(
            CASE_SPEC,
            "POST",
            "/v1/intake/applications",
            201,
            b'{"case_id":"%s","state":"en_evaluacion"}' % CASE_ID.encode(),
            app_models.CaseRef,
        )
    check_served(
        CASE_SPEC,
        "POST",
        "/v1/intake/applications",
        200,
        b'{"case_id":"%s","state":"en_evaluacion"}' % CASE_ID.encode(),
        app_models.CaseRef,
    )


def test_contract_openapi_a_route_outside_the_contract_or_an_extra_field_fails() -> None:
    with pytest.raises(ContractError, match="fuera del contrato"):
        check_served(BFF_SPEC, "GET", "/api/console/inexistente", 200, b"{}", None)
    with pytest.raises(Exception, match="extra|Extra"):
        check_served(
            CASE_SPEC,
            "POST",
            "/v1/intake/applications",
            200,
            b'{"case_id":"%s","state":"en_evaluacion","de_mas":1}' % CASE_ID.encode(),
            app_models.CaseRef,
        )


def test_contract_openapi_every_served_error_is_a_valid_problem_and_every_2xx_body_validates(
    dynamic_environment: guard.Environment,
) -> None:
    light, gateway, bff = _gateway_world(dynamic_environment)
    light.conflict_ids.add(CASE_ID)
    light.intake_script.extend([(429, {"Retry-After": "1"}), (503, {})])
    for _ in range(2):
        with pytest.raises(ApiError):
            gateway.submit_application(APPLICATION, "k-9")
    assert gateway.submit_application(APPLICATION, "k-9").state.value == "en_evaluacion"
    detail = bff.get_case(CASE_ID)
    assert isinstance(detail, api_models.CaseDetail) and bff.me().mfa and bff.list_cases().items
    assert problem(409, "conflict_state", "decision_already_recorded")["status"] == 409


def test_the_model_writes_need_a_step_up_session_and_send_nothing_without_it(
    dynamic_environment: guard.Environment,
) -> None:
    """U12-T03: `register_model`, `start_validation` y `approve_model` exigen MFA reciente, como `resolve_frozen`; los tres leen sin ella."""
    light, _, _ = _gateway_world(dynamic_environment)
    plain = BffClient(dynamic_environment, Session("ingeniero-1", step_up=False), TAG, transport=light)
    registration = ModelRegistration.model_validate(
        {
            "artifact_uri": "s3://model-store/mv-10/predictor.json",
            "artifact_format": "xgboost_json",
            "artifact_sha256": "a" * 64,
            "explainer_uri": "s3://model-store/mv-10/explainer.json",
            "explainer_sha256": "b" * 64,
            "manifest_uri": "s3://model-store/mv-10/manifest.json",
            "manifest_sha256": "c" * 64,
        }
    )
    for call in (
        lambda: plain.register_model(registration),
        lambda: plain.start_validation("mv-9"),
        lambda: plain.approve_model("mv-9", ModelApprovalIn(decision="aprobado")),
    ):
        with pytest.raises(ApiError, match="step_up_required"):
            call()
    assert light.requests == []
    assert (
        plain.get_model("mv-9").state == "lista_para_aprobacion"
        and plain.list_models().items[0].model_version_id == "mv-9"
    )


def test_an_api_error_exposes_invalid_params_of_a_422() -> None:
    from vectra_verification.clients._api import error_of

    body = problem(422, "validation_error")
    body["invalid_params"] = [
        {"name": "package", "reason_code": "model_version_id_mismatch_inside:explainer.json"}
    ]
    error = error_of(httpx.Response(422, json=body))
    assert error.status == 422 and error.code == "validation_error"
    assert error.invalid_params == (("package", "model_version_id_mismatch_inside:explainer.json"),)
    assert error_of(httpx.Response(409, json=problem(409, "conflict_state"))).invalid_params is None
