"""CA-15 (U12-T03, P-6; leccion de la enmienda §8): los dobles de los escenarios se parecen al contrato.

Un oraculo que espera un campo, un estado o una serie que el servicio no produce solo se descubre en kind, y U12 es la ultima unidad: por eso cada ruta, parametro, estado, causa y nombre de serie que los escenarios usan se ata aqui a su
fuente (`contracts/openapi/`, `role-endpoint-matrix.md`, `projections.py`, los modelos de U0 y los archivos de las demas unidades), y cada doble se valida contra el esquema de su ruta.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from contract_world import BFF_SPEC, OPENAPI, ContractError, check_served, problem
from external_paths import ROOT
from registry_read_double import ENTRIES_PARAMS, REGISTRY_SPEC
from rt2_world import PROXY, REFERENCE, TAG, Rt2World, make_package
from rt5_world import active_job, completed_job, failed_job
from vectra_contracts.catalog import CaseState, FailClosedCause, LocalCause
from vectra_contracts.models import api as api_models
from vectra_contracts.models.governance import ModelVersion, ModelVersionDetail, ValidationRun
from vectra_contracts.models.registry import FreezeProjection, FrozenResolutionProjection, MetricsProjection
from vectra_registry.projections import FIELDS
from vectra_verification.guard import KIND
from vectra_verification.scenarios import rt2, rt3, rt5, sim_normal
from vectra_verification.scenarios.common import Sessions

SRC = Path(__file__).resolve().parents[2] / "src" / "vectra_verification"
MATRIX = (OPENAPI / "role-endpoint-matrix.md").read_text(encoding="utf-8")
MODEL_STATES = {
    "registrado",
    "en_validacion",
    "validacion_fallida",
    "lista_para_aprobacion",
    "aprobado",
    "rechazado",
    "activo",
    "inactivo",
    "congelado",
    "retirado",
}
CASE_STATES = {s.value for s in CaseState}
CAUSES = {c.value for c in FailClosedCause} | {c.value for c in LocalCause}


def matrix_rows() -> dict[tuple[str, str], dict[str, str]]:
    """`(metodo, ruta) -> {rol: x, mfa: si}` de las filas del `console-bff` de la matriz."""
    out: dict[tuple[str, str], dict[str, str]] = {}
    for line in MATRIX.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 8 and cells[0] == "console-bff":
            out[(cells[1], cells[2].strip("`"))] = {
                "analista": cells[3], "ingeniero_riesgo": cells[4], "cro": cells[5], "cumplimiento": cells[6], "mfa": cells[7],
            }  # fmt: skip
    return out


def bff_routes() -> list[tuple[str, str]]:
    """Las rutas que `BffClient` llama (leidas de su codigo): `_send("METODO", f"{BASE}/...")`."""
    text = (SRC / "clients" / "bff.py").read_text(encoding="utf-8")
    found = re.findall(r'_send\(\s*"([A-Z]+)",\s*f"\{BASE\}(/[^"]*)"', text)
    return [
        (method, "/api/console" + re.sub(r"\{(?:model_version_id|case_id)\}", "{id}", path))
        for method, path in found
    ]


def test_contract_every_route_the_bff_client_calls_exists_in_the_openapi_and_the_matrix_with_its_role_and_mfa() -> (
    None
):
    expected = {
        ("GET", "/api/console/cases/{id}"): ("analista", False),
        ("GET", "/api/console/models"): ("ingeniero_riesgo", False),
        ("GET", "/api/console/models/{id}"): ("ingeniero_riesgo", False),
        ("POST", "/api/console/models"): ("ingeniero_riesgo", True),
        ("POST", "/api/console/models/{id}/validations"): ("ingeniero_riesgo", True),
        ("POST", "/api/console/models/{id}/approval"): ("cro", True),
        ("POST", "/api/console/models/{id}/frozen-resolution"): ("cumplimiento", True),
    }
    rows, routes = matrix_rows(), set(bff_routes())
    assert set(expected) <= routes, f"el cliente no llama: {sorted(set(expected) - routes)}"
    for method, path in routes:
        assert method.lower() in BFF_SPEC["paths"][path], f"{method} {path} no esta en console-bff.yaml"
        assert (method, path) in rows, f"{method} {path} no esta en la matriz"
    for key, (role, mfa) in expected.items():
        assert rows[key][role] == "x", f"{key}: el rol {role} no puede"
        assert (rows[key]["mfa"] == "si") is mfa, f"{key}: MFA {rows[key]['mfa']!r}"
        assert BFF_SPEC["paths"][key[1]][key[0].lower()].get("x-vectra-mfa", False) is mfa


def test_contract_the_users_the_scenarios_use_have_the_role_of_each_route() -> None:
    """`ingeniero-1` registra y valida, `cro-1` aprueba, `cumplimiento-1` reactiva y lee modelos, `analista-1` lee casos."""
    rows = matrix_rows()
    for user_role, route in (
        ("ingeniero_riesgo", ("POST", "/api/console/models")),
        ("cro", ("POST", "/api/console/models/{id}/approval")),
        ("cumplimiento", ("GET", "/api/console/models/{id}")),
        ("cumplimiento", ("POST", "/api/console/models/{id}/frozen-resolution")),
        ("analista", ("GET", "/api/console/cases/{id}")),
    ):
        assert rows[route][user_role] == "x", (user_role, route)


def test_contract_the_registry_query_parameters_exist_and_entry_type_and_projection_are_allowed_for_the_scope() -> (
    None
):
    source = (SRC / "clients" / "registry.py").read_text(encoding="utf-8")
    used = set(re.findall(r'params\["(\w+)"\]', source)) | {"projection", "limit"}
    assert used <= ENTRIES_PARAMS, sorted(used - ENTRIES_PARAMS)
    assert "get" in REGISTRY_SPEC["paths"]["/v1/entries"]
    scenarios = "\n".join(p.read_text(encoding="utf-8") for p in (SRC / "scenarios").glob("*.py"))
    for entry_type in re.findall(r'entry_type="(\w+)"', scenarios):
        assert entry_type in FIELDS["metrics"], f"la proyeccion metrics no admite entry_type={entry_type}"
    assert {"freeze", "frozen_resolution"} == set(FIELDS["monitoring_freezes"])


def test_contract_red_a_fail_closed_entry_is_not_in_the_metrics_projection() -> None:
    """El caso rojo de la tarea: pedir `entry_type=fail_closed` con la proyeccion `metrics` no tiene sentido: `FIELDS` no lo admite."""
    assert "fail_closed" not in FIELDS["metrics"]


def literals_compared_with_state(path: Path) -> set[str]:
    """Las cadenas contra las que el codigo compara un `.state`, o que pasa como estado esperado (`wait_state`, `_state`)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and any(
            isinstance(n, ast.Attribute) and n.attr == "state" for n in ast.walk(node.left)
        ):
            for comparator in node.comparators:
                found |= {
                    c.value
                    for c in ast.walk(comparator)
                    if isinstance(c, ast.Constant) and isinstance(c.value, str)
                }
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "wait_state"
            and len(node.args) >= 2
        ):
            if isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                found.add(node.args[1].value)
    return found


def test_contract_the_states_and_causes_the_oracles_name_are_members_of_the_catalog() -> None:
    assert (
        set(rt3.FAIL_CLOSED_STATES) | set(sim_normal.OK_STATES) | set(sim_normal.FAIL_CLOSED_STATES)
        <= CASE_STATES
    )
    assert set(rt3.F22_CAUSES) | set(rt3.RT3B_CAUSES) <= {c.value for c in FailClosedCause}
    assert set(rt3.CATALOG_CAUSES) == CAUSES
    for module in ("rt2.py", "rt3.py", "rt5.py", "sim_normal.py"):
        found = literals_compared_with_state(SRC / "scenarios" / module)
        assert found <= MODEL_STATES | CASE_STATES, (
            f"{module}: estados fuera del catalogo: {sorted(found - MODEL_STATES - CASE_STATES)}"
        )
    assert {"activo", "inactivo", "congelado", "aprobado"} <= literals_compared_with_state(
        SRC / "scenarios" / "rt2.py"
    ) | {rt2.FROZEN}


def test_contract_red_an_unknown_state_like_sincronizando_is_caught(tmp_path: Path) -> None:
    sample = tmp_path / "x.py"
    sample.write_text('def f(case):\n    return case.state == "sincronizando"\n', encoding="utf-8")
    assert (
        literals_compared_with_state(sample) == {"sincronizando"}
        and not {"sincronizando"} <= MODEL_STATES | CASE_STATES
    )


# --- los dobles, contra el esquema de su ruta ---------------------------------------------------------------------------------------------


class ValidatingTransport(httpx.BaseTransport):
    """Cada respuesta del BFF real pasa por `check_served` con el modelo que el OpenAPI nombra para su ruta."""

    MODELS: dict[tuple[str, str], type[Any] | None] = {
        ("GET", "/api/console/models"): api_models.Page[ModelVersion],
        ("POST", "/api/console/models"): ModelVersion,
        ("GET", "/api/console/models/{id}"): ModelVersionDetail,
        ("POST", "/api/console/models/{id}/validations"): ValidationRun,
        ("POST", "/api/console/models/{id}/approval"): None,
        ("POST", "/api/console/models/{id}/frozen-resolution"): None,
        ("GET", "/api/console/cases/{id}"): api_models.CaseDetail,
    }

    def __init__(self, inner: httpx.BaseTransport) -> None:
        self.inner, self.checked = inner, 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.inner.handle_request(request)
        response.read()
        for (method, template), model in self.MODELS.items():
            if method == request.method and re.fullmatch(template.replace("{id}", "[^/]+"), request.url.path):
                check_served(BFF_SPEC, method, template, response.status_code, response.content, model)
                self.checked += 1
                return response
        raise ContractError(f"ruta sin modelo en la prueba: {request.method} {request.url.path}")


@pytest.fixture
def world() -> Iterator[Rt2World]:
    built = Rt2World()
    built.add_model(REFERENCE, "activo", registered_by="otro", approved_by="otro-cro")
    yield built
    built.close()


def test_contract_every_correct_and_error_response_of_the_bff_double_validates_against_its_route(
    world: Rt2World, tmp_path: Path
) -> None:
    validating = ValidatingTransport(world.bff.transport)
    world.sessions = Sessions(KIND, world.oidc, world.clock, TAG, transport=validating, verify=False)
    version = rt2.ProxyVersion(1, PROXY, make_package(tmp_path, PROXY))
    assert rt2.rt2_setup(KIND, world.sessions, world.clock, [version]).result == "pasa"
    world.new_case("probe")
    case_id = next(iter(world.cases))
    world.clock.advance(60.0)
    world.sessions.reader("analista-1").get_case(case_id)
    # los errores: 409 al registrar dos veces, 404 de un caso o modelo desconocido y el 422 de U4 con `invalid_params`
    from vectra_verification.clients._api import ApiError
    from vectra_verification.scenarios.common import registration_body

    for call in (
        lambda c: c.register_model(registration_body(version.package_dir)),
        lambda c: c.get_model("mv-no-existe"),
        lambda c: c.get_case("3fa85f64-5717-4562-b3fc-2c963f66afa6"),
    ):  # type: ignore[arg-type]
        with pytest.raises(ApiError):
            call(world.sessions.writer("ingeniero-1"))
    world.register_overrides["rt3-a"] = rt3_reject("RT3-a")
    with pytest.raises(ApiError) as caught:
        world.sessions.writer("ingeniero-1").register_model(
            registration_body(make_package(tmp_path, "otro-pkg"), "rt3-a")
        )
    assert caught.value.status == 422 and caught.value.invalid_params
    assert validating.checked >= 10


def rt3_reject(case_id: str) -> Any:
    def respond(call: Any) -> tuple[int, Any]:
        body = problem(422, "validation_error")
        body["invalid_params"] = [{"name": "package", "reason_code": rt3.EXPECTED_REASON[case_id]}]
        return 422, body

    return respond


def test_contract_every_correct_response_of_the_registry_double_validates_and_the_list_page_is_a_page(
    world: Rt2World,
) -> None:
    world.add_model(PROXY, "aprobado", registered_by="ingeniero-1", approved_by="cro-1")
    world.simulator.run("stratified", 30, 1, section="rt2")
    world.freeze()
    world.reactivate()
    registry = world.registry
    metrics = registry.metrics(entry_type="recommendation")
    freezes = registry.freezes()
    assert metrics and all(isinstance(m, MetricsProjection) for m in metrics)
    assert any(isinstance(f, FreezeProjection) for f in freezes) and any(
        isinstance(f, FrozenResolutionProjection) for f in freezes
    )
    raw = registry.freezes_raw()
    assert {i["model_version_id"] for i in raw} == {PROXY}
    assert (
        "get" in REGISTRY_SPEC["paths"]["/v1/entries"]
        and "200" in REGISTRY_SPEC["paths"]["/v1/entries"]["get"]["responses"]
    )


def key_paths(value: Any, prefix: str = "") -> set[str]:
    if isinstance(value, dict):
        out = {prefix} if prefix else set()
        for key, inner in value.items():
            out |= key_paths(inner, f"{prefix}.{key}" if prefix else str(key))
        return out
    return {prefix}


def test_contract_every_incorrect_response_differs_from_the_correct_one_only_in_what_its_name_says(
    world: Rt2World,
) -> None:
    from registry_read_double import freeze_item

    def package(variant: Any) -> set[str]:
        world.package_variant = variant
        world.freeze_entries.clear()
        world.freeze()
        return key_paths(world.freeze_entries[0])

    world.add_model(PROXY, "aprobado")
    correct = package(None)
    for name in (*rt2.PACKAGE_FIELDS, "data_sources", "computed_at"):
        removed = correct - package(lambda item, n=name: item["context_package"].pop(n))
        assert {path for path in removed if path.startswith(f"context_package.{name}")} and all(
            p.startswith(f"context_package.{name}") for p in removed
        ), (name, removed)
    # `initial_disparity` vacia: las mismas claves, solo cambia el valor de `attributes` (la lista queda vacia)
    assert (
        package(lambda item: item["context_package"].update(initial_disparity={"attributes": []})) == correct
    )
    assert world.freeze_entries[0]["context_package"]["initial_disparity"] == {"attributes": []}
    assert key_paths(freeze_item(1)) >= {"context_package.data_sources", "context_package.initial_disparity"}
    # el 422 de U4 solo agrega `invalid_params` al `Problem` corriente; el Job fallido y el activo solo cambian su `status`
    plain, with_params = (
        problem(422, "validation_error"),
        problem(422, "validation_error") | {"invalid_params": [{"name": "package", "reason_code": "x"}]},
    )
    assert key_paths(with_params) - key_paths(plain) == {"invalid_params"} and key_paths(plain) <= key_paths(
        with_params
    )
    import json
    from datetime import UTC, datetime

    t = datetime(2026, 11, 13, 10, 0, tzinfo=UTC)
    done, failed, active = (
        key_paths(json.loads(j)) for j in (completed_job(t, t), failed_job(t), active_job(t))
    )
    assert all(p.startswith("status") for p in done ^ failed) and all(
        p.startswith("status") for p in done ^ active
    )


def test_contract_the_job_json_of_the_kubectl_double_has_the_batch_v1_fields_the_oracle_reads() -> None:
    import json
    from datetime import UTC, datetime

    t = datetime(2026, 11, 13, 10, 0, tzinfo=UTC)
    document = json.loads(completed_job(t, t))
    assert document["apiVersion"] == "batch/v1" and document["kind"] == "Job"
    assert {"startTime", "completionTime", "succeeded", "failed", "conditions"} <= set(document["status"])
    assert rt5.parse_job(completed_job(t, t)).completion == t and rt5.parse_job(failed_job(t)).failed == 1


def test_contract_the_series_and_alert_names_the_oracles_query_appear_as_they_are_in_their_source() -> None:
    def text(relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    rule = text("case-management/chart/templates/prometheusrule.yaml")
    assert (
        "alert: CoreWriteAttempt" in rule
        and "inbound_http_authz_deny_total" in rule
        and 'route_name="core-mock-catch-all"' in rule
        and 'namespace="vectra-mock"' in rule
    )
    assert "vectra_core_write_attempts_total" in text(
        "case-management/core_banking_mock/src/core_banking_mock/metrics.py"
    )
    assert "vectra_cases_failclosed_persistent" in text("case-management/src/vectra_case/metrics.py")
    platform = text("platform/observability/rules/platform-rules.yaml")
    assert "alert: FailClosedPersistente" in platform and "vectra_cases_failclosed_persistent" in platform
    assert "core-mock-catch-all" in text("platform/network/flows.yaml")
    publish = text("bias-monitoring/src/vectra_bias/publish.py")
    for series in (
        "vectra_bias_last_run_timestamp",
        "vectra_bias_last_run_ok",
        "vectra_bias_last_run_failure",
    ):
        assert series in publish
    assert rt3.ALERT.startswith("ALERTS{") and 'alertname="FailClosedPersistente"' in rt3.ALERT
    assert rt5.ALERT.startswith("ALERTS{") and "CoreWriteAttempt" in rt5.ALERT
    for constant, name in (
        (rt2.BIAS_TS, "vectra_bias_last_run_timestamp"),
        (rt2.BIAS_OK, "vectra_bias_last_run_ok"),
        (rt2.BIAS_FAILURE, "vectra_bias_last_run_failure"),
        (rt5.COUNTER, "vectra_core_write_attempts_total"),
        (rt3.GAUGE, "vectra_cases_failclosed_persistent"),
    ):
        assert name in constant
    assert "retention: 3d" in text("platform/observability/values/kube-prometheus-stack-kind.yaml")


def test_contract_the_template_of_the_job_is_the_one_the_oracle_reads() -> None:
    template = (ROOT / "case-management" / "chart" / "templates" / "rt5-demo-job.yaml").read_text(
        encoding="utf-8"
    )
    assert 'name: {{ printf "rt5-demo-%s" $runId }}' in template and "l5d-proxy-error" in template
    assert rt5.JOB_PREFIX == "rt5-demo-" and rt5.NAMESPACE == "vectra-app"
