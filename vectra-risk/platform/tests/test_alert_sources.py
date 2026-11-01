"""Una alerta sin fuente de metricas no avisa nunca, o avisa siempre (revision del 2026-11-01)."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PLATFORM = ROOT / "platform"
RULES = yaml.safe_load((PLATFORM / "observability/rules/platform-rules.yaml").read_text(encoding="utf-8"))
MONITORS = [d for d in yaml.safe_load_all((PLATFORM / "observability/monitors/monitors.yaml").read_text(encoding="utf-8")) if d]
FLOWS = yaml.safe_load((PLATFORM / "network/flows.yaml").read_text(encoding="utf-8"))
#: Quien produce cada familia de metricas, y el puerto que Prometheus necesita alcanzar.
SOURCES = {
    "cnpg_": ("postgres", 9187),
    "certmanager_": ("cert-manager", 9402),
    "minio_": ("minio", 9000),
}
JOBS = {"kyverno": 8000, "linkerd-controller": 9996, "pushgateway": 9091}
#: Las emiten las unidades o los charts con su propio ServiceMonitor.
OWN = re.compile(r"^(vectra[_:]|kube_|kubelet_|push_time_seconds)")


def expressions() -> list[str]:
    return [rule["expr"] for group in RULES["groups"] for rule in group["rules"]]


def metric_names(expr: str) -> set[str]:
    without_labels = re.sub(r"\{[^}]*\}", "", expr)
    words = set(re.findall(r"\b[a-z][a-z0-9_:]*_[a-z0-9_:]+\b", without_labels))
    return {w for w in words if not w.startswith("label_")} - {"group_left"}


def monitor_jobs() -> set[str]:
    return {r["replacement"] for m in MONITORS for e in m["spec"]["podMetricsEndpoints"] for r in e["relabelings"] if r["targetLabel"] == "job"}


def prometheus_ports() -> set[int]:
    found: set[int] = set()
    for flow in FLOWS["flows"]:
        if "prometheus" in flow["from"]:
            found |= set(flow.get("ports", [flow.get("port")]))
    return found


def test_every_metric_family_has_a_known_source():
    unknown = set()
    for expr in expressions():
        for name in metric_names(expr):
            if not OWN.match(name) and not any(name.startswith(prefix) for prefix in SOURCES):
                unknown.add(name)
    assert not unknown


@pytest.mark.parametrize(("prefix", "source"), SOURCES.items())
def test_families_used_by_rules_are_reachable(prefix, source):
    assert any(prefix in expr for expr in expressions()), prefix
    _, port = source
    assert port in prometheus_ports()


def test_jobs_used_by_rules_have_a_monitor_and_a_flow():
    used = set(re.findall(r'up\{job="([^"]+)"\}', " ".join(expressions())))
    assert used == set(JOBS)
    assert used - {"pushgateway"} <= monitor_jobs()
    assert set(JOBS.values()) <= prometheus_ports()


def test_monitors_select_what_the_charts_label():
    selectors = {m["metadata"]["name"]: m["spec"]["selector"]["matchLabels"] for m in MONITORS}
    assert selectors["kyverno"]["app.kubernetes.io/part-of"] == "kyverno"
    assert selectors["minio"] == {"app": "minio"}


def test_cnpg_pod_monitor_labels_the_cluster():
    """`RegistryDbWritesBlocked` y `PostgresConnectionsHigh` filtran o agrupan por `cluster`."""
    text = (PLATFORM / "data/chart/templates/clusters.yaml").read_text(encoding="utf-8")
    assert "kind: PodMonitor" in text and "cnpg.io/cluster" in text and "targetLabel: cluster" in text
    assert any('cluster="registry-db"' in expr or "by (cluster)" in expr for expr in expressions())
