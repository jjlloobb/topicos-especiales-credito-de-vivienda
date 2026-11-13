"""`tools/gen_rules.py` y la `PrometheusRule` (Paso 12; BR-U11-06; BR-U11-14; P-U11-05; P-U11-06; NFR-U11-06; NFR-U11-08; NFR-U11-32; NFR-U11-42).

Las reglas generadas salen de datos del codigo (la categoria `desincronia` del catalogo de U0 y `collector.PRODUCT_SERIES`); la `PrometheusRule` del chart tiene
exactamente cuatro `alertname`; el `spec` renderizado es identico en los tres entornos y es el archivo versionado contra el que corre `promtool`.
Necesita `platform/install-tools.sh` (helm y promtool en `platform/.tools/bin`): si faltan, las pruebas **fallan**.
"""

import importlib.util
import re
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from chart_render import ENVS, ROOT, render, tool
from vectra_contracts.catalog import FAIL_CLOSED_CAUSES_BY_CATEGORY
from vectra_product import collector

TOOL = ROOT / "product-metrics" / "tools" / "gen_rules.py"
RULES_TESTS = ROOT / "product-metrics" / "observability" / "rules" / "tests"


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_rules", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = load_tool()


def versioned() -> dict[str, Any]:
    return yaml.safe_load(GEN.GENERATED.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def spec_rules() -> list[dict[str, Any]]:
    spec = yaml.safe_load(GEN.SPEC.read_text(encoding="utf-8"))
    return [r for g in spec["groups"] for r in g["rules"]]


def test_the_versioned_generated_file_is_what_the_tool_generates() -> None:
    assert GEN.GENERATED.read_text(encoding="utf-8") == GEN.dump(GEN.generated_rules(), GEN.GENERATED_HEADER)
    assert GEN.run(["--check"]) == 0


def test_the_desync_rule_uses_the_causes_of_the_category_in_order() -> None:
    expected = sorted(str(c) for c in FAIL_CLOSED_CAUSES_BY_CATEGORY["desincronia"])
    assert expected == ["feature_dictionary_incomplete", "version_mismatch"]
    (rule,) = [
        r
        for g in versioned()["groups"]
        for r in g["rules"]
        if r["record"] == "vectra:product_desync_failclosed:rate1h"
    ]
    assert rule["expr"] == f'sum(rate(vectra_scoring_failclosed_total{{cause=~"{"|".join(expected)}"}}[1h]))'


def test_with_one_more_cause_in_the_category_check_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    grown = {
        **FAIL_CLOSED_CAUSES_BY_CATEGORY,
        "desincronia": frozenset({*map(str, FAIL_CLOSED_CAUSES_BY_CATEGORY["desincronia"]), "otra_causa"}),
    }
    monkeypatch.setattr(GEN, "FAIL_CLOSED_CAUSES_BY_CATEGORY", grown)
    before = GEN.GENERATED.read_bytes()
    assert GEN.run(["--check"]) == 1
    assert "difiere" in capsys.readouterr().out
    assert GEN.GENERATED.read_bytes() == before, "--check no escribe"


def test_one_dedup_per_key_of_product_series_and_none_for_operation_series() -> None:
    rules = [r for g in versioned()["groups"] for r in g["rules"] if r["record"].endswith(":dedup")]
    by_name = {r["record"]: r["expr"] for r in rules}
    assert len(rules) == len(by_name) == len(collector.PRODUCT_SERIES)
    for series in collector.PRODUCT_SERIES:
        name = f"vectra:{series.removeprefix('vectra_')}:dedup"
        assert by_name[name] == f"max without (instance, pod) ({series})"
    for series in collector.OPERATION_SERIES:
        assert not [n for n in by_name if series.removeprefix("vectra_") in n], (
            f"{series}: las series de operacion no llevan :dedup"
        )
        assert not [e for e in by_name.values() if series in e]


def test_the_output_is_deterministic(tmp_path: Path) -> None:
    first = GEN.dump(GEN.generated_rules(), GEN.GENERATED_HEADER)
    assert first == GEN.dump(GEN.generated_rules(), GEN.GENERATED_HEADER)
    runs = [
        subprocess.run(
            ["uv", "run", "python", str(TOOL), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        for _ in range(2)
    ]  # noqa: S607
    assert [r.returncode for r in runs] == [0, 0]


def test_a_hand_edited_versioned_file_makes_check_exit_1_and_nothing_is_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    edited = tmp_path / "generated-rules.yaml"
    edited.write_text(
        GEN.GENERATED.read_text(encoding="utf-8").replace("max without", "sum without", 1), encoding="utf-8"
    )
    monkeypatch.setattr(GEN, "GENERATED", edited)
    before = edited.read_bytes()
    assert GEN.run(["--check"]) == 1
    assert edited.read_bytes() == before
    assert GEN.run([]) == 0, "sin --check, el tool regenera el archivo"
    assert edited.read_text(encoding="utf-8") == GEN.dump(GEN.generated_rules(), GEN.GENERATED_HEADER)


def test_a_dedup_removed_from_the_generated_file_makes_check_exit_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document = versioned()
    group = next(g for g in document["groups"] if g["name"] == "vectra-product-dedup")
    group["rules"] = [r for r in group["rules"] if r["record"] != "vectra:product_north_star_ratio:dedup"]
    edited = tmp_path / "generated-rules.yaml"
    edited.write_text(GEN.dump(document, GEN.GENERATED_HEADER), encoding="utf-8")
    monkeypatch.setattr(GEN, "GENERATED", edited)
    assert GEN.run(["--check"]) == 1


# --- el spec renderizado (P-4 = a) -----------------------------------------------------------------------------------------------------------


def rendered_spec(env: str) -> dict[str, Any]:
    (rule,) = [d for d in render(env) if d["kind"] == "PrometheusRule"]
    return rule["spec"]  # type: ignore[no-any-return]


def test_the_spec_is_identical_in_the_three_environments_and_is_the_versioned_file() -> None:
    specs = {env: rendered_spec(env) for env in ENVS}
    assert specs["kind"] == specs["staging"] == specs["prod"]
    assert specs["kind"] == yaml.safe_load(GEN.SPEC.read_text(encoding="utf-8"))
    assert GEN.run(["--spec", "--check"]) == 0


def test_the_rendered_spec_contains_the_generated_groups_verbatim() -> None:
    generated = versioned()["groups"]
    rendered = rendered_spec("prod")["groups"]
    assert rendered[: len(generated)] == generated


def test_a_stale_versioned_spec_makes_spec_check_exit_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stale = tmp_path / "product-metrics.rules.yaml"
    stale.write_text(GEN.SPEC.read_text(encoding="utf-8").replace("for: 26h", "for: 25h"), encoding="utf-8")
    monkeypatch.setattr(GEN, "SPEC", stale)
    assert GEN.run(["--spec", "--check"]) == 1


# --- las alertas (CA-8) -----------------------------------------------------------------------------------------------------------------------

RECORDS_WITH_RAW_SOURCE = {f"vectra:{s.removeprefix('vectra_')}:dedup" for s in collector.PRODUCT_SERIES}
PER_REPLICA_ALERTS = {"ProductMetricsStale", "ProductMetricsFullRecomputeMissing"}


def test_alert_the_prometheusrule_has_exactly_four_alertnames_and_six_alert_rules() -> None:
    alerts = [r for r in spec_rules() if "alert" in r]
    assert sorted({r["alert"] for r in alerts}) == [
        "ProductMetricsDegraded",
        "ProductMetricsFullRecomputeMissing",
        "ProductMetricsStale",
        "RuidoExplicacion",
    ]
    assert len(alerts) == 6
    for env in ENVS:
        names = {r["alert"] for g in rendered_spec(env)["groups"] for r in g["rules"] if "alert" in r}
        assert len(names) == 4


def test_alert_every_alert_has_severity_sev3_and_a_runbook_url_to_an_existing_file() -> None:
    for rule in (r for r in spec_rules() if "alert" in r):
        assert rule["labels"]["severity"] == "SEV3", rule["alert"]
        assert (ROOT / rule["annotations"]["runbook_url"]).is_file(), rule["alert"]


def test_alert_the_two_branches_of_each_per_replica_alert_differ_in_their_for_and_label() -> None:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for rule in (r for r in spec_rules() if "alert" in r):
        by_name.setdefault(rule["alert"], []).append(rule)
    assert {n for n, rules in by_name.items() if len(rules) == 2} == PER_REPLICA_ALERTS
    stale = {r["labels"]["branch"]: r for r in by_name["ProductMetricsStale"]}
    full = {r["labels"]["branch"]: r for r in by_name["ProductMetricsFullRecomputeMissing"]}
    assert (stale["edad"]["for"], stale["ausencia"]["for"]) == ("0m", "30m")
    assert (full["edad"]["for"], full["ausencia"]["for"]) == ("0m", "26h")
    assert "> 1800" in stale["edad"]["expr"] and "> 93600" in full["edad"]["expr"]
    for rule in (*stale.values(), *full.values()):
        assert rule["expr"].endswith("unless on (pod) (vectra_product_full_pass_in_progress == 1)"), (
            "la pasada en curso no dispara ninguna rama"
        )
    for rule in (stale["ausencia"], full["ausencia"]):
        assert (
            'up{job="product-metrics"} == 1 unless on (pod)' in rule["expr"] and "absent(" not in rule["expr"]
        )


def test_alert_raw_vectra_product_series_only_in_the_two_per_replica_alerts_and_as_the_source_of_a_dedup() -> (
    None
):
    """P-U11-05: el dashboard y las alertas de producto usan solo `:dedup`; las crudas, solo en `ProductMetricsStale` y `ProductMetricsFullRecomputeMissing`."""
    for rule in spec_rules():
        raw = re.findall(r"\bvectra_product_[a-z0-9_]+", rule["expr"])
        if not raw:
            continue
        if "record" in rule:
            assert rule["record"] in RECORDS_WITH_RAW_SOURCE and len(raw) == 1, rule["record"]
        else:
            assert rule["alert"] in PER_REPLICA_ALERTS, f"{rule['alert']} lee una serie cruda: {raw}"


def test_alert_ruido_explicacion_and_degraded_read_dedup_series_only() -> None:
    rules = {
        r["alert"]: r
        for r in spec_rules()
        if r.get("alert") in {"RuidoExplicacion", "ProductMetricsDegraded"}
    }
    assert rules["RuidoExplicacion"]["expr"].startswith("vectra:product_noise_days_below_floor:dedup >= ")
    assert rules["RuidoExplicacion"]["for"] == "0m"
    assert rules["ProductMetricsDegraded"]["expr"] == "vectra:product_metrics_degraded:dedup == 1"
    assert rules["ProductMetricsDegraded"]["for"] == "1h"


def test_alert_br_u11_06_the_complete_response_rules_exclude_only_fail_closed() -> None:
    by_name = {r["record"]: r["expr"] for r in spec_rules() if "record" in r}
    for window in ("1h", "1d"):
        expr = by_name[f"vectra:product_complete_response_ratio:{window}"]
        assert (
            f'sum(rate(vectra_recommendations_total{{outcome!="fail_closed"}}[{window}])) / sum(rate(vectra_recommendations_total[{window}]))'
            == expr
        )


# --- los casos de promtool (CA-8) --------------------------------------------------------------------------------------------------------------

PLAN_BULLETS = {
    "cada alerta a los dos lados del umbral": [
        "ruido-a-los-dos-lados-del-umbral-S",
        "degraded-a-los-dos-lados-de-1-hora",
        "stale-edad-no-dispara-en-el-umbral",
        "full-recompute-edad-a-los-dos-lados-de-las-26-horas",
    ],
    "una replica sin la serie y la otra con ella: Stale solo para la primera": [
        "stale-una-replica-sin-la-serie-y-la-otra-con-ella"
    ],
    "la pasada en curso: ninguna rama": [
        "stale-la-pasada-en-curso-no-dispara-ninguna-rama",
        "full-recompute-la-pasada-en-curso-no-dispara-ninguna-rama",
    ],
    "la rama de edad dispara sin esperar un for; la de ausencia solo tras su for": [
        "stale-edad-dispara-al-superar-el-umbral-sin-esperar-un-for",
        "stale-ausencia-dispara-solo-tras-su-for",
    ],
    "replica recien arrancada con U3 caido: FullRecomputeMissing a las 26 h": [
        "full-recompute-replica-recien-arrancada-con-u3-caido"
    ],
    "dos replicas identicas: una sola RuidoExplicacion": ["ruido-dos-replicas-identicas-una-sola-alerta"],
    "respuesta completa 98 + 2 fail_closed = 0,98": ["respuesta-completa-98-de-100-es-0-98"],
    "Degraded: dos replicas, una sola alerta": ["degraded-dos-replicas-una-sola-alerta"],
    "las dos replicas sin la serie: Stale para las dos": ["stale-las-dos-replicas-sin-la-serie"],
    "dos replicas identicas: cada :dedup vale lo que una": ["dedup-dos-replicas-identicas-valen-lo-que-una"],
    "desincronia cuenta version_mismatch y feature_dictionary_incomplete y no otra categoria": [
        "desincronia-cuenta-version-mismatch-y-feature-dictionary-incomplete-y-no-otra-categoria"
    ],
}


def promtool_case_names() -> set[str]:
    names: set[str] = set()
    for path in sorted(RULES_TESTS.glob("*.yaml")):
        names |= {t["name"] for t in yaml.safe_load(path.read_text(encoding="utf-8"))["tests"]}
    return names


@pytest.mark.parametrize("bullet", sorted(PLAN_BULLETS))
def test_promtool_each_bullet_of_the_plan_has_a_named_case(bullet: str) -> None:
    assert set(PLAN_BULLETS[bullet]) <= promtool_case_names(), bullet


def test_promtool_every_case_file_points_at_the_versioned_rules_file() -> None:
    for path in sorted(RULES_TESTS.glob("*.yaml")):
        files = yaml.safe_load(path.read_text(encoding="utf-8"))["rule_files"]
        assert [(path.parent / f).resolve() for f in files] == [GEN.SPEC.resolve()]


def test_promtool_the_cases_pass() -> None:
    result = subprocess.run(  # noqa: S603
        [tool("promtool"), "test", "rules", *map(str, sorted(RULES_TESTS.glob("*.yaml")))],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("SUCCESS") == len(list(RULES_TESTS.glob("*.yaml")))


def test_promtool_check_rules_accepts_the_versioned_spec() -> None:
    result = subprocess.run(
        [tool("promtool"), "check", "rules", str(GEN.SPEC)], capture_output=True, text=True, check=False
    )  # noqa: S603
    assert result.returncode == 0, result.stdout + result.stderr
