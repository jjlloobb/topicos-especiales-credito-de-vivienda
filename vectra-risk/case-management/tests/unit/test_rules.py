"""Paso 21 (INF-U8-03; P-U8-06; US-603, US-112): la PrometheusRule `CoreWriteAttempt` y la prueba del nombre de las metricas que alimentan alertas de U1.

La regla vive en `chart/templates/prometheusrule.yaml`; `observability/rules/case-management.rules.yaml` es su `spec` renderizado, versionado. Los casos de `promtool`
estan en `observability/rules/tests/core-write-attempt.yaml` (uno con nombre por afirmacion de la aceptacion). Necesita `platform/install-tools.sh` (helm y promtool).
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import core_banking_mock.metrics as mock_metrics
import pytest
import vectra_case.metrics as case_metrics
import yaml
from prometheus_client.metrics import MetricWrapperBase

ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "case-management"
CHART = CASE / "chart"
GITOPS = ROOT / "vectra-risk-gitops"
BIN = ROOT / "platform" / ".tools" / "bin"
RULES = CASE / "observability" / "rules" / "case-management.rules.yaml"
TESTS = CASE / "observability" / "rules" / "tests" / "core-write-attempt.yaml"
RUNBOOK = CASE / "observability" / "runbooks" / "core-write-attempt.md"
TMP = ROOT / "platform" / ".tools" / "tmp"

# INF-U8-03, literal (sin `increase()` sobre la serie de Linkerd, que nace en 1).
INF_U8_03 = (
    'increase(vectra_core_write_attempts_total[5m]) > 0 or sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"})'
    ' - (sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"} offset 5m) or vector(0)) > 0'
)


def tool(name: str) -> str:
    path = BIN / name
    assert path.is_file(), f"falta {path}: corre platform/install-tools.sh"
    return str(path)


def spec(env: str) -> dict[str, Any]:
    """El `spec` de la PrometheusRule que renderiza el chart con los values que usa Argo CD en `env`."""
    generate = _generate()
    component = next(
        c
        for c in yaml.safe_load((GITOPS / "components.yaml").read_text(encoding="utf-8"))["components"]
        if c["name"] == "case-management"
    )
    command = [
        tool("helm"),
        "template",
        "case-management",
        str(CHART),
        "-n",
        "vectra-app",
        "-f",
        str(GITOPS / "envs" / env / "values.yaml"),
    ]
    for f in generate.value_files(component, env):
        command += ["-f", str(ROOT / f)]
    out = subprocess.run(command, check=True, capture_output=True, text=True).stdout  # noqa: S603
    rules = [d for d in yaml.safe_load_all(out) if d and d["kind"] == "PrometheusRule"]
    assert len(rules) <= 1
    return dict(rules[0]["spec"]) if rules else {}


def _generate() -> Any:
    import importlib.util

    loaded = importlib.util.spec_from_file_location("gitops_generate", GITOPS / "generate.py")
    assert loaded and loaded.loader
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module


def normalized(expr: str) -> str:
    return re.sub(r"\s+", " ", expr).strip()


def versioned() -> dict[str, Any]:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def the_rule() -> dict[str, Any]:
    rules = [r for g in versioned()["groups"] for r in g["rules"]]
    assert len(rules) == 1
    return rules[0]  # type: ignore[no-any-return]


def test_the_expression_is_the_one_of_inf_u8_03_literally() -> None:
    assert normalized(the_rule()["expr"]) == normalized(INF_U8_03)
    expr = the_rule()["expr"]
    assert "offset 5m" in expr and "or vector(0)" in expr
    assert not re.search(r"increase\(\s*inbound_http_authz_deny_total", expr), (
        "increase() sobre la serie de Linkerd nunca la ve nacer en 1"
    )
    assert expr.count('route_name="core-mock-catch-all"') == 2 and "for" not in the_rule()


def test_one_alert_and_no_recording_rule() -> None:
    rules = [r for g in versioned()["groups"] for r in g["rules"]]
    assert [r.get("alert", "RECORD") for r in rules] == ["CoreWriteAttempt"]


def test_severity_runbook_url_and_the_runbook_file_exist() -> None:
    rule = the_rule()
    assert rule["labels"]["severity"] == "SEV2"
    url = rule["annotations"]["runbook_url"]
    assert url == "case-management/observability/runbooks/core-write-attempt.md" and (ROOT / url).is_file()
    description = rule["annotations"][
        "description"
    ]  # distingue las dos series: la del mock indica ademas que Linkerd dejo pasar el POST
    assert (
        "vectra_core_write_attempts_total" in description
        and "inbound_http_authz_deny_total" in description
        and "Linkerd" in description
    )


def test_the_spec_is_the_same_in_kind_and_staging_and_is_the_versioned_file() -> None:
    kind, staging = spec("kind"), spec("staging")
    assert kind == staging != {}
    assert kind == versioned()


def test_prod_renders_no_prometheus_rule() -> None:
    assert spec("prod") == {}


def test_the_route_name_is_the_catch_all_of_flows_yaml() -> None:
    flows = yaml.safe_load((ROOT / "platform" / "network" / "flows.yaml").read_text(encoding="utf-8"))
    assert f'route_name="{flows["http_routes"]["core-banking-mock"]["_catch_all"]}"' in the_rule()["expr"]


def series(module: Any) -> set[str]:
    """Los nombres de serie que registra un modulo de metricas (importado): el de cada `Counter`, `Gauge` o `Histogram` que define."""
    names: set[str] = set()
    for value in vars(module).values():
        if isinstance(value, MetricWrapperBase):
            names |= {sample.name for metric in value.collect() for sample in metric.samples}
            names |= {metric.name for metric in value.collect()}
    return names


def metric_names(expr: str) -> set[str]:
    return {m for m in re.findall(r"[a-zA-Z_:][a-zA-Z0-9_:]*", expr) if m.startswith("vectra_")}


def test_names_failclosed_persistent_of_u1_is_a_series_of_vectra_case_metrics() -> None:
    """US-112: la regla `FailClosedPersistente` (U1, leida del archivo) lee una serie que `vectra_case.metrics` registra con ese nombre; renombrarla rompe la alerta."""
    platform = yaml.safe_load(
        (ROOT / "platform" / "observability" / "rules" / "platform-rules.yaml").read_text(encoding="utf-8")
    )
    alert = next(
        r for g in platform["groups"] for r in g["rules"] if r.get("alert") == "FailClosedPersistente"
    )
    names = metric_names(alert["expr"])
    assert names == {"vectra_cases_failclosed_persistent"}
    assert names <= series(case_metrics), f"vectra_case.metrics no registra {names - series(case_metrics)}"


def test_names_core_write_attempts_of_the_alert_is_a_series_of_the_mock_metrics() -> None:
    names = metric_names(the_rule()["expr"])
    assert names == {"vectra_core_write_attempts_total"}
    assert names <= series(mock_metrics), (
        f"core_banking_mock.metrics no registra {names - series(mock_metrics)}"
    )


def test_names_a_renamed_metric_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Renombrar la metrica en el codigo hace fallar la prueba del nombre (el rojo de CA-8, sin tocar `metrics.py`)."""
    from prometheus_client import CollectorRegistry, Counter, Gauge

    registry = CollectorRegistry()
    monkeypatch.setattr(
        case_metrics,
        "FAILCLOSED_PERSISTENT",
        Gauge("vectra_cases_failclosed_persistent_v2", "x", registry=registry),
    )
    monkeypatch.setattr(
        mock_metrics, "WRITE_ATTEMPTS", Counter("vectra_core_writes_total", "x", registry=registry)
    )
    assert "vectra_cases_failclosed_persistent" not in series(case_metrics)
    assert "vectra_core_write_attempts_total" not in series(mock_metrics)


CASES = {
    "linkerd-series-born-at-1-fires",  # la serie de Linkerd nace en 1 y dispara
    "linkerd-denial-with-another-route-name-does-not-fire",  # una denegacion con otro route_name no dispara
    "mock-counter-from-0-to-1-fires",  # el contador del mock de 0 a 1 dispara
    "mock-counter-stays-at-0-and-no-linkerd-series-does-not-fire",  # el otro lado del umbral
    "linkerd-series-at-1-for-more-than-5-minutes-stops-firing",  # sin eventos nuevos deja de disparar
    "d3-linkerd-born-at-1-and-mock-counter-still-0-fires",  # el caso de D3
}


def test_the_promtool_file_has_one_named_case_per_claim() -> None:
    document = yaml.safe_load(TESTS.read_text(encoding="utf-8"))
    assert {t["name"] for t in document["tests"]} == CASES
    for t in document["tests"]:  # cada caso pone series en los dos lados del umbral
        assert any(a["exp_alerts"] for a in t["alert_rule_test"]) or "does-not-fire" in t["name"]


def promtool_test(rules: str) -> subprocess.CompletedProcess[str]:
    """Corre los casos contra un `rules` distinto (en un directorio temporal dentro del repositorio: `/tmp` es un tmpfs casi lleno)."""
    TMP.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(dir=TMP))
    try:
        (folder / "tests").mkdir()
        (folder / "case-management.rules.yaml").write_text(rules, encoding="utf-8")
        shutil.copy(TESTS, folder / "tests" / "core-write-attempt.yaml")
        return subprocess.run(  # noqa: S603
            [tool("promtool"), "test", "rules", str(folder / "tests" / "core-write-attempt.yaml")],
            capture_output=True,
            text=True,
            check=False,
            env={"TMPDIR": str(TMP), "PATH": "/usr/bin:/bin"},
        )
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_promtool_the_versioned_rule_passes_every_case() -> None:
    result = promtool_test(RULES.read_text(encoding="utf-8"))
    assert result.returncode == 0 and "SUCCESS" in result.stdout + result.stderr, (
        result.stdout + result.stderr
    )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda e: e.replace(
                "sum(inbound_http_authz_deny_total{", "sum(increase(inbound_http_authz_deny_total{", 1
            ).replace('"core-mock-catch-all"})\n', '"core-mock-catch-all"}[5m]))\n', 1),
            "linkerd-series-born-at-1-fires",
        ),
        (
            lambda e: e.replace(', route_name="core-mock-catch-all"', ""),
            "linkerd-denial-with-another-route-name-does-not-fire",
        ),
        (
            lambda e: e.replace("increase(vectra_core_write_attempts_total[5m]) > 0", "vector(0) > 1"),
            "mock-counter-from-0-to-1-fires",
        ),
        (lambda e: e.replace(" offset 5m", ""), "linkerd-series-at-1-for-more-than-5-minutes-stops-firing"),
    ],
    ids=["increase-over-linkerd", "no-route-name-filter", "no-mock-counter", "no-offset"],
)
def test_promtool_a_mutated_expression_fails_the_case_that_guards_it(mutation: Any, expected: str) -> None:
    document = versioned()
    document["groups"][0]["rules"][0]["expr"] = mutation(document["groups"][0]["rules"][0]["expr"])
    result = promtool_test(yaml.safe_dump(document, sort_keys=False))
    assert result.returncode != 0, "la mutacion no rompio ningun caso"
    assert expected in result.stdout + result.stderr, result.stdout + result.stderr
