"""Los planes de las unidades cargan las reglas que Kyverno aplica; `check-chart` renderiza lo que renderiza Argo CD."""

from pathlib import Path

import integration
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PLANS = ROOT / "aidlc-docs/construction/plans"
UNITS_WITH_CHARTS = [
    "identity-edge", "decision-registry", "model-serving", "scoring-explainability", "governance",
    "case-management", "bias-monitoring", "console", "product-metrics", "system-verification",
]  # fmt: skip


@pytest.mark.parametrize("unit", UNITS_WITH_CHARTS)
def test_plan_carries_the_admission_rules(unit):
    text = (PLANS / f"{unit}-code-generation-plan.md").read_text(encoding="utf-8")
    for needle in ("check-chart", "vectra.io/criticality", "readOnlyRootFilesystem", "restrict-registries"):
        assert needle in text, (unit, needle)


def test_chart_without_entry_renders_every_environment():
    renders = list(integration.chart_renders("nueva/chart", None, "vectra-app"))
    assert [(name, env, ns) for name, env, ns, _ in renders] == [
        ("chart", "kind", "vectra-app"),
        ("chart", "staging", "vectra-app"),
        ("chart", "prod", "vectra-app"),
    ]


def test_chart_with_entry_uses_the_values_of_argo():
    """`postgres`: en kind suma values-kind.yaml, y su namespace sale de components.yaml."""
    renders = {env: (ns, values) for _, env, ns, values in integration.chart_renders("platform/data/chart", None, "ignorado")}
    assert renders["prod"][0] == "vectra-data"
    assert [p.name for p in renders["kind"][1]] == ["values.yaml", "values-kind.yaml"]
    assert [p.name for p in renders["prod"][1]] == ["values.yaml"]


def test_only_env_limits_the_render():
    assert {env for _, env, _, _ in integration.chart_renders("platform/data/chart", "kind", "x")} == {"kind"}


def test_envoy_gateway_deploys_in_the_namespace_of_the_gateway():
    values = yaml.safe_load((ROOT / "platform/operators/envoy-gateway.yaml").read_text(encoding="utf-8"))
    assert values["config"]["envoyGateway"]["provider"]["kubernetes"]["deploy"]["type"] == "GatewayNamespace"


def test_u2_plan_sets_the_identity_flows_expects():
    flows = yaml.safe_load((ROOT / "platform/network/flows.yaml").read_text(encoding="utf-8"))
    gateway = flows["workloads"]["api-gateway"]
    owning = "gateway.envoyproxy.io/owning-gateway-name"
    assert (gateway["sa"], gateway["labels"]) == ("api-gateway", {owning: "api-gateway"})  # Z1: el data plane se selecciona por el Gateway que lo posee
    text = (PLANS / "identity-edge-code-generation-plan.md").read_text(encoding="utf-8")
    assert "envoyServiceAccount.name: api-gateway" in text and f"{owning}: api-gateway" in text
