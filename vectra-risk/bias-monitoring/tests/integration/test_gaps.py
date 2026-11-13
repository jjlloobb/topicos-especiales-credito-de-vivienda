"""Paso 10 (NFR-U9-50): ramas de `run`, `publish`, `freeze_client`, `registry_client` y `app` que las pruebas anteriores no recorrian."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC

import httpx
import pytest
from builders import batch_client, uniform
from scenario import NOW, POLICY, make_deps, seed
from service_support import write_policy
from vectra_bias import app as bias_app
from vectra_bias import run as run_module
from vectra_bias.freeze_client import FAILED, freeze
from vectra_bias.publish import list_groups
from vectra_bias.registry_client import RegistryError, query_daily
from vectra_bias.run import EXIT_FAILED, EXIT_PUSH, acquire_tokens, log_outcome, main, run_once
from vectra_contracts.models.monitoring import DayRange, MonitoringQuery, MonitoringRangeRequest
from world import ASSERTION_AUDIENCE, GOVERNANCE_URL, PRIVATE_KEY_PEM, PUSHGATEWAY_URL, REGISTRY_URL, World

TODAY = NOW.date()


def run(coro):
    return asyncio.run(coro)


class Fixed(httpx.AsyncBaseTransport):
    """Responde siempre lo mismo (o falla con un error de conexion)."""

    def __init__(self, status=200, content: bytes = b"{}", error: Exception | None = None) -> None:
        self.status, self.content, self.error = status, content, error

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self.error is not None:
            raise self.error
        return httpx.Response(self.status, content=self.content)


# --- run ---------------------------------------------------------------------------------------------------------------------


def test_a_service_without_token_source_is_skipped():
    run(acquire_tokens([None]))


def test_a_failure_of_the_library_fails_the_run_without_freezing(monkeypatch):
    world = World()
    seed(world, "v1", TODAY, days=1, model="high")

    def boom(*_args, **_kwargs):
        raise RuntimeError("libreria")

    monkeypatch.setattr(run_module, "evaluate", boom)
    outcome = run(run_once(make_deps(world, lambda: NOW)))
    assert not outcome.report.complete and outcome.report.failure_reason == "libreria"
    assert world.governance.calls == []


def test_a_window_without_the_totals_of_a_requested_range_is_an_incomplete_reading(monkeypatch):
    world = World()
    seed(world, "v1", TODAY, days=1, model="high")
    original = run_module.query_daily

    async def without_totals(client, query):
        window = await original(client, query)
        return window if query.include_versions else window.model_copy(update={"totals": []})

    monkeypatch.setattr(run_module, "query_daily", without_totals)
    outcome = run(run_once(make_deps(world, lambda: NOW)))
    assert outcome.report.failure_reason == "lectura" and world.governance.calls == []


def test_the_logs_of_a_complete_run_with_a_good_freeze_and_a_down_pushgateway():
    import io

    from vectra_common.logging import configure

    stream = io.StringIO()
    configure("bias-monitoring-job", stream)
    world = World()
    seed(world, "v1", TODAY, days=1, model="high")
    seed(world, "v2", TODAY, days=1, model="low")
    world.pushgateway.down = True
    outcome = run(run_once(make_deps(world, lambda: NOW)))
    assert outcome.report.complete and outcome.exit_code == EXIT_PUSH
    log_outcome(outcome, 7)
    lines = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    assert any(line.get("error_code") == "pushgateway" for line in lines)
    assert any(line.get("status") == "congelado" and "error_code" not in line for line in lines)
    assert lines[-1]["status"] == "completa" and "error_code" not in lines[-1]


def _job_env(tmp_path, **over):
    (tmp_path / "client.pem").write_text(PRIVATE_KEY_PEM, encoding="utf-8")
    write_policy(tmp_path / "policy.yaml", POLICY)
    dead = "http://127.0.0.1:1"  # nadie escucha: la conexion se rechaza al instante
    env = {
        "VECTRA_REGISTRY_URL": dead,
        "VECTRA_GOVERNANCE_URL": dead,
        "VECTRA_PUSHGATEWAY_URL": dead,
        "VECTRA_TOKEN_URL": dead + "/token",
        "VECTRA_ASSERTION_AUDIENCE": ASSERTION_AUDIENCE,
        "VECTRA_CLIENT_ID": "bias-monitoring-job",
        "VECTRA_CLIENT_KEY_PATH": str(tmp_path / "client.pem"),
        "VECTRA_POLICY_PATH": str(tmp_path / "policy.yaml"),
    }
    return {**env, **over}


def test_main_with_every_dependency_down_is_a_failed_run_and_a_push_failure(tmp_path, monkeypatch):
    env = _job_env(tmp_path)
    for name in ("VECTRA_CLIENT_ID", "VECTRA_TOKEN_URL", "VECTRA_ASSERTION_AUDIENCE", "VECTRA_CLIENT_KEY_PATH"):
        monkeypatch.setenv(name, env[name])  # `provider_from_env` lee el entorno del proceso
    assert (
        main(env) == EXIT_PUSH
    )  # sin token la corrida falla, y el Pushgateway tampoco acepta: prevalece el 2


def test_main_without_configuration_is_a_failed_run():
    assert main({}) == EXIT_FAILED


# --- freeze_client y registry_client --------------------------------------------------------------------------------------


def test_a_governance_that_does_not_answer_is_a_failed_freeze_after_the_retries():
    from builders import ensure_batch

    ensure_batch()
    world = World()
    client = batch_client("governance", GOVERNANCE_URL, Fixed(error=httpx.ConnectError("down")))
    outcome = run(freeze(client, "v1", _package(), world.clock.sleep))
    assert outcome.outcome == FAILED and outcome.reason == "unavailable" and outcome.attempts == 4


def _package():
    from datetime import date

    from vectra_bias.context import build_context_package, measure
    from vectra_bias.freeze_rule import attribute_limits, decide
    from vectra_contracts.models.monitoring import AffectedVolume

    counts = uniform(0.5, 100)
    after = measure(counts, 30, "modelo", "v1", date(2026, 10, 11), TODAY)
    return build_context_package(
        model_version_id="v1", computed_at=NOW, threshold_pp=POLICY.threshold_pp, n_min=30, window_days=30,
        schedule=POLICY.schedule, stale_after_s=3600, window_start=date(2026, 10, 11), before=None, after=after,
        last_7_days=None, decision=decide("modelo", POLICY.threshold_pp, attribute_limits(counts, 30)),
        affected_volume=AffectedVolume(total=1, favorable=1),
    )  # fmt: skip


def test_a_window_that_is_not_a_monitoring_window_is_a_registry_error():
    from builders import ensure_batch

    ensure_batch()
    client = batch_client("registry", REGISTRY_URL, Fixed(200, b'{"versions": 1}'))
    query = MonitoringQuery(
        ranges=[MonitoringRangeRequest(range_id="r", population="modelo", from_day=TODAY, to_day=TODAY)],
        include_versions=False,
        unattributable_range=DayRange(from_day=TODAY, to_day=TODAY),
    )
    with pytest.raises(RegistryError, match="window_invalid"):
        run(query_daily(client, query))


# --- publish: el listado de grupos y el borrado fallido --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "content", "expected"),
    [(200, b"no es json", "GET:groups:invalid_json"), (200, b'{"data": 5}', "GET:groups:invalid_response")],
)
def test_a_group_listing_that_is_not_json_or_has_another_shape_is_an_error_code(status, content, expected):
    from builders import ensure_batch

    ensure_batch()
    client = batch_client("pushgateway", PUSHGATEWAY_URL, Fixed(status, content))
    assert run(list_groups(client)) == expected


def test_a_stale_group_whose_delete_fails_is_reported_and_kept():
    from datetime import datetime as dt

    from builders import population_report
    from vectra_bias.publish import RunReport, VersionReport, publish

    world = World()
    world.pushgateway.put_group("bias-monitoring", "freeze-old")
    world.pushgateway.failing_paths = {"/metrics/job/bias-monitoring/group/freeze-old"}
    client = batch_client("pushgateway", PUSHGATEWAY_URL, world.pushgateway.transport())
    t = dt(2026, 11, 9, 12, tzinfo=UTC)
    low = uniform(0.5, 2000)
    version = VersionReport(
        "v1",
        population_report(low, "modelo", "v1"),
        population_report(uniform(0.5, 100), "humana", "v1"),
        None,
    )
    result = run(publish(client, RunReport(t, t, True, None, True, (version,), 0, 100)))
    assert result.deleted_stale == [] and any("freeze-old" in e or "DELETE" in e for e in result.errors)


# --- app: configuracion y arranque en proceso ---------------------------------------------------------------------------


def _service_env(tmp_path, **over):
    (tmp_path / "client.pem").write_text(PRIVATE_KEY_PEM, encoding="utf-8")
    write_policy(tmp_path / "policy.yaml", POLICY)
    env = {
        "VECTRA_REGISTRY_URL": "http://registry.test",
        "VECTRA_TOKEN_URL": "http://keycloak.test/token",
        "VECTRA_ASSERTION_AUDIENCE": ASSERTION_AUDIENCE,
        "VECTRA_CLIENT_ID": "bias-monitoring-service",
        "VECTRA_CLIENT_KEY_PATH": str(tmp_path / "client.pem"),
        "VECTRA_OIDC_ISSUER": "https://keycloak.test/auth/realms/vectra",
        "VECTRA_JWKS_URL": "http://keycloak.test/jwks",
        "VECTRA_POLICY_PATH": str(tmp_path / "policy.yaml"),
    }
    return {**env, **over}


def test_config_from_env_reads_only_the_environment_and_the_policy_file(tmp_path):
    cfg = bias_app.config_from_env(_service_env(tmp_path))
    assert cfg.registry_url == "http://registry.test" and cfg.policy == POLICY


def test_config_from_env_names_every_missing_variable(tmp_path):
    env = _service_env(tmp_path)
    del env["VECTRA_REGISTRY_URL"], env["VECTRA_JWKS_URL"]
    with pytest.raises(bias_app.ConfigError) as error:
        bias_app.config_from_env(env)
    assert "VECTRA_REGISTRY_URL" in str(error.value) and "VECTRA_JWKS_URL" in str(error.value)


def test_an_https_url_without_the_ca_bundle_stops_the_start(tmp_path):
    with pytest.raises(bias_app.ConfigError, match="VECTRA_CA_BUNDLE"):
        bias_app.config_from_env(_service_env(tmp_path, VECTRA_REGISTRY_URL="https://registry.test"))


def test_an_invalid_policy_stops_the_start_naming_the_variable(tmp_path):
    env = _service_env(tmp_path)
    (tmp_path / "policy.yaml").write_text("threshold_pp: 99\n", encoding="utf-8")
    with pytest.raises(bias_app.ConfigError, match="VECTRA_POLICY_PATH"):
        bias_app.config_from_env(env)


def test_build_app_builds_the_four_routes_from_the_environment(tmp_path, monkeypatch):
    for name, value in _service_env(tmp_path).items():
        monkeypatch.setenv(name, value)
    app = bias_app.build_app()
    assert {r.path for r in app.router.routes if hasattr(r, "methods")} >= {"/v1/disparity", "/v1/freezes"}


def test_build_app_with_an_unreadable_key_names_the_variable(tmp_path, monkeypatch):
    for name, value in _service_env(tmp_path, VECTRA_CLIENT_KEY_PATH=str(tmp_path / "no-hay.pem")).items():
        monkeypatch.setenv(name, value)
    with pytest.raises(bias_app.ConfigError, match="VECTRA_CLIENT_KEY_PATH"):
        bias_app.build_app()


def test_main_exits_with_code_2_and_the_message_when_the_configuration_is_wrong(monkeypatch, capsys):
    for name in bias_app.REQUIRED:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit) as stop:
        bias_app.main()
    assert stop.value.code == bias_app.EXIT_CONFIG
    assert "VECTRA_REGISTRY_URL" in capsys.readouterr().err


def test_main_serves_the_app_it_built(monkeypatch):
    served = []
    monkeypatch.setattr(bias_app, "build_app", lambda: "la-app")
    monkeypatch.setattr(bias_app, "run_service", served.append)
    bias_app.main()
    assert served == ["la-app"]
