"""Renderiza los charts upstream con nuestros values: una clave mal escrita aqui se ignora en silencio.

Si faltan los charts, la prueba falla: `make -C platform charts` los descarga.
"""

import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CHARTS = ROOT / "platform/.charts"
COMPONENTS = {c["name"]: c for c in yaml.safe_load((ROOT / "vectra-risk-gitops/components.yaml").read_text(encoding="utf-8"))["components"]}


def render(name, *extra):
    component = COMPONENTS[name]
    chart = CHARTS / name / component["chart"]
    assert chart.is_dir(), f"Falta {chart}: corre `make -C platform charts`"
    command = ["helm", "template", name, str(chart), "--namespace", component["namespace"], "--skip-tests"]
    for values in component.get("values", []):
        command += ["-f", str(ROOT / values)]
    command += extra
    result = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    return [d for d in yaml.safe_load_all(result) if d]


def of(documents, kind):
    return [d for d in documents if d["kind"] == kind]


def trust_anchor():
    return ["--set-string", "identityTrustAnchorsPEM=x"]


def test_linkerd_is_ha_with_cni_and_deny():
    documents = render("linkerd-control-plane", *trust_anchor())
    deployments = of(documents, "Deployment")
    assert deployments
    assert all(d["spec"]["replicas"] == 3 for d in deployments), [d["metadata"]["name"] for d in deployments]
    text = yaml.safe_dump(documents)
    assert "default-inbound-policy" in text or "LINKERD2_PROXY_INBOUND_DEFAULT_POLICY" in text
    assert "value: deny" in text or "deny" in text
    assert not [d for d in deployments for c in d["spec"]["template"]["spec"].get("initContainers", []) if c["name"] == "linkerd-init"], "con CNI no hay init"


def test_linkerd_trust_roots_come_from_outside_the_chart():
    names = {d["metadata"]["name"] for d in of(render("linkerd-control-plane", *trust_anchor()), "ConfigMap")}
    assert "linkerd-identity-trust-roots" not in names


def test_eso_chart_grants_no_cluster_wide_secrets():
    for role in of(render("external-secrets"), "ClusterRole"):
        assert not [r for r in role.get("rules", []) if "secrets" in r.get("resources", [])], role["metadata"]["name"]


def test_prometheus_and_alertmanager():
    documents = render("kube-prometheus-stack")
    prometheus = of(documents, "Prometheus")[0]["spec"]
    assert prometheus["replicas"] == 2 and prometheus["retention"] == "30d" and not prometheus.get("remoteWrite")
    assert of(documents, "Alertmanager")[0]["spec"]["replicas"] == 3
    assert not of(documents, "CustomResourceDefinition"), "los CRDs van en la wave 0"


def test_grafana_is_recreate_with_persistence_and_kube_state_metrics_labels():
    documents = render("kube-prometheus-stack")
    grafana = next(d for d in of(documents, "Deployment") if d["metadata"]["name"].endswith("grafana"))
    assert grafana["spec"]["replicas"] == 1 and grafana["spec"]["strategy"]["type"] == "Recreate"
    assert any("persistentVolumeClaim" in v for v in grafana["spec"]["template"]["spec"]["volumes"])
    metrics = next(d for d in of(documents, "Deployment") if "kube-state-metrics" in d["metadata"]["name"])
    assert "topology.kubernetes.io/zone" in " ".join(metrics["spec"]["template"]["spec"]["containers"][0]["args"])


def test_loki_keeps_retention_out_of_the_compactor():
    documents = render("loki")
    config = next(d for d in of(documents, "ConfigMap") if "config.yaml" in d.get("data", {}))["data"]["config.yaml"]
    parsed = yaml.safe_load(config)
    assert parsed["compactor"]["retention_enabled"] is False
    assert parsed["common"]["storage"]["s3"]["bucketnames"] == "loki"


def test_tempo_retention():
    documents = render("tempo")
    config = next(d for d in of(documents, "ConfigMap") if "tempo.yaml" in d.get("data", {}))["data"]["tempo.yaml"]
    parsed = yaml.safe_load(config)
    assert parsed["compactor"]["compaction"]["block_retention"] == "168h"
    assert parsed["storage"]["trace"]["backend"] == "s3"


def test_alloy_is_daemonset():
    assert of(render("alloy"), "DaemonSet")


def test_alloy_storage_is_writable_with_a_read_only_root():
    spec = of(render("alloy"), "DaemonSet")[0]["spec"]["template"]["spec"]
    alloy = next(c for c in spec["containers"] if c["name"] == "alloy")
    assert alloy["securityContext"]["readOnlyRootFilesystem"] is True
    assert {"name": "alloy-storage", "mountPath": "/tmp/alloy"} in alloy["volumeMounts"]  # noqa: S108
    assert {"name": "alloy-storage", "emptyDir": {"sizeLimit": "256Mi"}} in spec["volumes"]


def test_pushgateway_persists_without_admin_api():
    documents = render("pushgateway")
    assert of(documents, "PersistentVolumeClaim")[0]["spec"]["resources"]["requests"]["storage"] == "1Gi"
    deployment = of(documents, "Deployment")[0]
    assert deployment["spec"]["replicas"] == 1
    args = deployment["spec"]["template"]["spec"]["containers"][0]["args"]
    assert "--persistence.interval=1m" in args and any(a.startswith("--persistence.file=/data") for a in args)
    assert "--web.enable-admin-api" not in args


def test_otel_collector_replicas():
    assert of(render("otel-collector"), "Deployment")[0]["spec"]["replicas"] == 2


def test_minio_buckets_lock_and_lifecycle():
    documents = render("minio", "--set-string", "rootUser=x,rootPassword=y")
    assert of(documents, "StatefulSet")[0]["spec"]["replicas"] == 4
    data = next(d for d in of(documents, "ConfigMap") if "initialize" in d.get("data", {}))["data"]
    for bucket in ("model-store", "validation-datasets", "loki", "tempo"):
        assert bucket in data["initialize"]
    assert "retention set --default GOVERNANCE 90d myminio/loki" in data["custom-command"]
    assert "ilm rule add --expire-days 7 myminio/tempo" in data["custom-command"]


def test_minio_kind_has_worm_buckets():
    documents = render("minio", "-f", str(ROOT / "platform/data/minio/values-kind.yaml"), "--set-string", "rootUser=x,rootPassword=y")
    data = next(d for d in of(documents, "ConfigMap") if "initialize" in d.get("data", {}))["data"]
    assert "vectra-registry-checkpoints" in data["initialize"]
    assert "COMPLIANCE 3650d myminio/vectra-registry-checkpoints" in data["custom-command"]


@pytest.mark.parametrize(("name", "kind", "expected"), [("cloudnative-pg", "Deployment", 2), ("external-secrets", "Deployment", 2), ("cert-manager", "Deployment", 2), ("kyverno", "Deployment", 2)])
def test_operators_are_ha(name, kind, expected):
    replicas = [d["spec"]["replicas"] for d in of(render(name), kind)]
    assert replicas and min(replicas) >= expected, replicas


def test_kyverno_admission_has_three_replicas():
    deployment = next(d for d in of(render("kyverno"), "Deployment") if "admission" in d["metadata"]["name"])
    assert deployment["spec"]["replicas"] == 3


def test_vault_dev_only_in_kind():
    assert COMPONENTS["vault"]["envs"] == ["kind"]
    assert of(render("vault"), "StatefulSet")
