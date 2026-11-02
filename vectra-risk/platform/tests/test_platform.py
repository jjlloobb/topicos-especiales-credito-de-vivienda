"""Verificaciones estaticas que no necesitan kyverno, conftest ni promtool."""

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml
from forbidden_steps import dockerfile_violations, workflow_violations
from pg_hba_rules import assert_postgres_requires_tls
from rollback_note import has_rollback_note
from test_runbooks import template_sections

PLATFORM = Path(__file__).resolve().parents[1]
ROOT = PLATFORM.parent
REPO = ROOT.parent
GITOPS = ROOT / "vectra-risk-gitops"
INVENTORY = ROOT / "aidlc-docs/inception/application-design/component-dependency.md"
RULES = yaml.safe_load((PLATFORM / "observability/rules/platform-rules.yaml").read_text(encoding="utf-8"))
ALERTS = [r for g in RULES["groups"] for r in g["rules"] if "alert" in r]
RUNBOOK_SECTIONS = template_sections()


def helm(chart, *args):
    return list(yaml.safe_load_all(subprocess.run(["helm", "template", "x", str(chart), *args], check=True, capture_output=True, text=True).stdout))


def docs_of(path):
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def test_kind_config():
    config = docs_of(PLATFORM / "kind/cluster.yaml")[0]
    workers = [n for n in config["nodes"] if n["role"] == "worker"]
    zones = sorted(n["labels"]["topology.kubernetes.io/zone"] for n in workers)
    assert zones == ["zone-a", "zone-b"]
    ha = docs_of(PLATFORM / "kind/cluster-ha.yaml")[0]
    zones = sorted(n["labels"]["topology.kubernetes.io/zone"] for n in ha["nodes"] if n["role"] == "worker")
    assert zones == ["zone-a", "zone-a", "zone-b", "zone-b"]
    assert config["networking"]["disableDefaultCNI"] is True
    plane = next(n for n in config["nodes"] if n["role"] == "control-plane")
    assert "encryption-provider-config" in plane["kubeadmConfigPatches"][0]


def test_mesh_and_certificates():
    values = yaml.safe_load((PLATFORM / "mesh/linkerd-values.yaml").read_text(encoding="utf-8"))
    assert values["controllerReplicas"] == 3 and values["cniEnabled"] and values["proxy"]["defaultInboundPolicy"] == "deny"
    certs = {d["metadata"]["name"]: d for d in docs_of(PLATFORM / "mesh/certificates.yaml") if d["kind"] == "Certificate"}
    assert certs["linkerd-trust-anchor"]["spec"]["duration"] == "8760h"
    assert certs["linkerd-identity-issuer"]["spec"]["duration"] == "48h"
    assert certs["postgres-server"]["spec"]["duration"] == "2160h" and certs["postgres-server"]["spec"]["renewBefore"] == "720h"


def test_namespaces_mesh_label_and_annotation_together():
    expected = {"vectra-edge", "vectra-app", "vectra-serving", "vectra-staging", "vectra-data", "vectra-identity", "vectra-mock", "vectra-observability", "vectra-restore-drill"}
    rendered = [d for d in helm(PLATFORM / "namespaces") if d]
    assert {d["metadata"]["name"] for d in rendered} == expected
    for ns in rendered:
        assert ns["metadata"]["labels"]["vectra.io/mesh"] == "enabled" and ns["metadata"]["annotations"]["linkerd.io/inject"] == "enabled"
        assert ns["metadata"]["labels"]["pod-security.kubernetes.io/enforce"] == "restricted"


def test_namespaces_without_mock_in_prod():
    assert "vectra-mock" not in {d["metadata"]["name"] for d in helm(PLATFORM / "namespaces", "--set", "mockEnabled=false") if d}


def test_policies_present():
    names = {p.stem for p in (PLATFORM / "policies/kyverno").glob("*.yaml")} - {"kyverno-test"}
    assert names >= {"verify-images", "disallow-latest", "require-run-as-non-root", "disallow-privileged", "disallow-host-path", "require-ro-rootfs", "require-resources", "require-priority-class", "require-spread-and-pdb", "require-hpa-bounds", "restrict-loadbalancer", "disallow-plain-secrets", "disallow-argocd-auto-sync", "require-criticality-label", "disallow-rbac-wildcards", "add-native-sidecar-to-jobs"}
    assert "restrict-manual-jobs" not in names


def test_spread_policy_scope_excludes_observability():
    policy = docs_of(PLATFORM / "policies/kyverno/require-spread-and-pdb.yaml")[0]
    scope = policy["spec"]["rules"][0]["match"]["any"][0]["resources"]["namespaces"]
    assert set(scope) == {"vectra-app", "vectra-edge", "vectra-identity", "vectra-serving", "vectra-mock"}


def test_priority_classes():
    values = {d["metadata"]["name"]: d["value"] for d in docs_of(PLATFORM / "policies/priority-classes.yaml")}
    assert values == {"vectra-critical": 1000000, "vectra-high": 100000, "vectra-normal": 10000, "vectra-low": 100}


def test_quotas_cover_every_namespace_and_add_up():
    generated = docs_of(PLATFORM / "policies/quotas/generated.yaml")
    with_quota = {d["metadata"]["namespace"] for d in generated if d["kind"] == "ResourceQuota"}
    with_limits = {d["metadata"]["namespace"] for d in generated if d["kind"] == "LimitRange"}
    flows = yaml.safe_load((PLATFORM / "network/flows.yaml").read_text(encoding="utf-8"))
    assert set(flows["meshed_namespaces"]) == with_quota == with_limits
    source = yaml.safe_load((PLATFORM / "policies/quotas/quotas.yaml").read_text(encoding="utf-8"))["namespaces"]
    for quota in (d for d in generated if d["kind"] == "ResourceQuota"):
        parts = source[quota["metadata"]["namespace"]]["contributions"].values()
        hard = quota["spec"]["hard"]
        assert float(hard["requests.cpu"]) == pytest.approx(sum(p["requests"][0] for p in parts))
        assert float(hard["requests.memory"].removesuffix("Gi")) == pytest.approx(sum(p["requests"][1] for p in parts))
        assert float(hard["limits.cpu"]) == pytest.approx(sum(p["limits"][0] for p in parts))
        assert float(hard["limits.memory"].removesuffix("Gi")) == pytest.approx(sum(p["limits"][1] for p in parts))


def inventory_roles():
    roles = {}
    for db, role in re.findall(r"^\| `([a-z]+-db)` \| `([a-z_]+)` \|", INVENTORY.read_text(encoding="utf-8"), flags=re.M):
        roles.setdefault(db, set()).add(role)
    return roles


def clusters():
    return {d["metadata"]["name"]: d for d in helm(PLATFORM / "data/chart") if d and d["kind"] == "Cluster"}


def test_postgres_clusters():
    found = clusters()
    assert set(found) == {"registry-db", "case-db", "governance-db", "keycloak-db"}
    for cluster in found.values():
        spec = cluster["spec"]
        assert spec["instances"] == 3 and spec["minSyncReplicas"] == 1 and spec["maxSyncReplicas"] == 2
        assert spec["postgresql"]["parameters"]["archive_timeout"] == "60s"
        assert spec["postgresql"]["syncReplicaElectionConstraint"]["nodeLabelsAntiAffinity"] == ["topology.kubernetes.io/zone"]
        assert spec["backup"]["retentionPolicy"] == "30d" and spec["walStorage"]["size"]
        assert spec["priorityClassName"] == "vectra-critical" and spec["affinity"]["podAntiAffinityType"] == "required"
        assert spec["affinity"]["tolerations"][0]["value"] == "data"
        assert spec["inheritedMetadata"]["annotations"]["config.linkerd.io/skip-inbound-ports"] == "8000"


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_postgres_requires_tls(env):
    """NFR-U1-22: sin `host` en texto plano; lee el YAML renderizado, no los values."""
    extra = ["-f", str(PLATFORM / "data/chart/values-kind.yaml")] if env == "kind" else []
    rendered = helm(PLATFORM / "data/chart", "-f", str(GITOPS / f"envs/{env}/values.yaml"), *extra)
    found = {d["metadata"]["name"]: d for d in rendered if d and d["kind"] == "Cluster"}
    assert len(found) == 4
    for name, cluster in found.items():
        assert_postgres_requires_tls(cluster, name)
        parameters = cluster["spec"]["postgresql"]
        assert parameters["parameters"]["ssl_min_protocol_version"] == "TLSv1.2"


def test_every_inventory_role_is_managed():
    found = clusters()
    for database, roles in inventory_roles().items():
        managed = {r["name"] for r in found[database]["spec"]["managed"]["roles"]}
        assert managed == roles, database


def test_no_plain_secret_in_gitops_or_platform():
    for folder in (GITOPS, PLATFORM / "data", PLATFORM / "secrets", PLATFORM / "restore-drill"):
        for path in folder.rglob("*.yaml"):
            assert not re.search(r"^kind:\s*Secret\s*$", path.read_text(encoding="utf-8"), flags=re.M), path


def test_minio():
    values = yaml.safe_load((PLATFORM / "data/minio/values.yaml").read_text(encoding="utf-8"))
    assert values["replicas"] == 4 and values["mode"] == "distributed"
    assert {b["name"] for b in values["buckets"]} == {"model-store", "validation-datasets", "loki", "tempo"}


def test_eso_rbac_without_wildcards():
    for name in ("eso-rbac-k11.yaml", "eso-rbac-cluster.yaml"):
        for doc in docs_of(PLATFORM / "secrets" / name):
            for rule in doc.get("rules", []):
                assert "*" not in rule["verbs"] + rule["resources"], (name, doc["metadata"]["name"])


def test_eso_cluster_roles_do_not_touch_secrets():
    for doc in docs_of(PLATFORM / "secrets/eso-rbac-cluster.yaml"):
        if doc["kind"] == "ClusterRole":
            assert not [r for r in doc["rules"] if "secrets" in r["resources"]], doc["metadata"]["name"]


def test_k16_only_allowed_verbs_and_group_subject():
    allowed = {"get", "list", "watch", "create"}
    for doc in docs_of(PLATFORM / "rbac/verification-operator/k16.yaml"):
        for rule in doc.get("rules", []):
            assert set(rule["verbs"]) <= allowed
            if "create" in rule["verbs"]:
                assert rule["resources"] == ["pods/portforward"]
            assert "pods/exec" not in rule["resources"] and "*" not in rule["resources"]
        for subject in doc.get("subjects", []):
            assert subject["kind"] == "Group" and subject["name"] == "vectra-verification-operators"


def test_k16_not_enabled_in_prod():
    assert yaml.safe_load((GITOPS / "envs/prod/values.yaml").read_text(encoding="utf-8"))["verificationOperator"] is False


def test_expected_alerts_and_severity():
    names = {a["alert"] for a in ALERTS}
    assert names >= {"WalArchiveStale", "BackupFailed", "RestoreDrillFailed", "RestoreDrillMissing", "RestoreDrillRetentionViolation", "RegistryDbWritesBlocked", "KyvernoUnavailable", "LinkerdControlPlaneDown", "SingleZoneOperation", "MinioWriteQuorumLost", "PostgresReplicaLag", "CertificateExpiringSoon", "RecommendationSLOBurnFast", "RecommendationSLOBurnSlow", "FailClosedPersistente", "PostgresConnectionsHigh", "PostgresVolumeUsageHigh", "HPAMaxedOut", "PushgatewayDown", "GrafanaFolderPermissionsDrift", "Watchdog"}
    assert "AuthDeniedBurst" not in names, "es de U2"
    for alert in ALERTS:
        assert alert["labels"]["severity"] in {"SEV1", "SEV2", "SEV3", "none"}


def test_failclosed_uses_u8_gauge_not_sli():
    alert = next(a for a in ALERTS if a["alert"] == "FailClosedPersistente")
    assert alert["expr"] == "max(vectra_cases_failclosed_persistent) > 0" and alert["for"] == "1m"


def test_volume_absence_rule_per_cluster():
    rules = {a["labels"]["cluster"]: a["expr"] for a in ALERTS if a["alert"] == "PostgresVolumeUsageHigh" and "cluster" in a["labels"]}
    assert set(rules) == {"registry-db", "case-db", "governance-db", "keycloak-db"}
    for cluster, expr in rules.items():
        assert f'"{cluster}-[0-9]+(-wal)?"' in expr and "or vector(0)) < 6" in expr


def test_every_alert_has_existing_runbook():
    for alert in ALERTS:
        path = ROOT / alert["annotations"]["runbook_url"]
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert all(section in text for section in RUNBOOK_SECTIONS), path


@pytest.mark.parametrize("name", ["install", "zone-failover", "site-restore", "trust-anchor-rotation"])
def test_operational_runbooks(name):
    text = (PLATFORM / f"runbooks/{name}.md").read_text(encoding="utf-8")
    assert all(section in text for section in RUNBOOK_SECTIONS)
    verification = text.split("## Verificación")[1]
    assert "`" in verification, "cada verificacion nombra un comando"


def test_install_runbook_explains_wait_and_k16():
    text = (PLATFORM / "runbooks/install.md").read_text(encoding="utf-8")
    assert "vectra_product_full_pass_in_progress" in text and "vectra-verification-operators" in text


def recording_rules():
    return {r["record"] for g in RULES["groups"] for r in g["rules"] if "record" in r}


@pytest.mark.parametrize("path", sorted((PLATFORM / "observability/dashboards").glob("*.json")), ids=lambda p: p.stem)
def test_dashboards(path):
    board = json.loads(path.read_text(encoding="utf-8"))
    assert board["uid"] and board["panels"]
    for panel in board["panels"]:
        assert panel["datasource"]["uid"] == "prometheus"
        for target in panel["targets"]:
            for name in re.findall(r"vectra:[a-z_:0-9]+", target["expr"]):
                assert name in recording_rules(), name


def test_restore_drill_manifest():
    documents = docs_of(PLATFORM / "restore-drill/cronjob.yaml")
    cron = next(d for d in documents if d["kind"] == "CronJob")
    template = cron["spec"]["jobTemplate"]["spec"]["template"]
    assert template["metadata"]["annotations"]["config.alpha.linkerd.io/proxy-enable-native-sidecar"] == "true"
    assert template["spec"]["priorityClassName"] == "vectra-low"
    role = next(d for d in documents if d["kind"] == "Role")
    assert all("*" not in r["verbs"] + r["resources"] for r in role["rules"])
    secret = next(d for d in documents if d["kind"] == "ExternalSecret")
    assert "restore-readonly" in secret["spec"]["data"][0]["remoteRef"]["key"]


def test_f75_bucket_policy_is_read_only_and_scoped():
    policy = json.loads((PLATFORM / "restore-drill/bucket-policy-f75.json").read_text(encoding="utf-8"))
    actions = {action for statement in policy["Statement"] for action in statement["Action"]}
    assert actions == {"s3:GetObject", "s3:ListBucket"}
    objects = [r for s in policy["Statement"] if "s3:GetObject" in s["Action"] for r in s["Resource"]]
    assert objects and not [r for r in objects if not re.search(r"(registry-db|case-db)/\*$|vectra-registry-checkpoints/checkpoints/\*$", r)]


COMPONENTS = yaml.safe_load((GITOPS / "components.yaml").read_text(encoding="utf-8"))
# P-U1-12: cada componente en su wave.
EXPECTED_WAVES = {
    0: {"cert-manager", "trust-manager", "cloudnative-pg", "external-secrets-rbac", "external-secrets-rbac-kind", "external-secrets", "kyverno", "linkerd-crds", "linkerd-cni", "prometheus-operator-crds", "envoy-gateway", "kserve-crd", "kserve", "argo-cd", "vault"},
    1: {"mesh-certificates", "linkerd-control-plane", "kyverno-context-rbac", "kyverno-policies", "priority-classes", "namespaces", "quotas", "network", "secret-store", "secret-store-env", "verification-operator", "verify-images"},
    2: {"postgres", "minio"},
    3: {"grafana-secrets"},
    4: {"observability-monitors", "kube-prometheus-stack", "loki", "tempo", "alloy", "pushgateway", "otel-collector", "observability-rules", "grafana-config", "grafana-dashboards"},
    5: {"restore-drill"},
}
WAVES = {name: wave for wave, names in EXPECTED_WAVES.items() for name in names}


def test_every_component_is_in_its_wave():
    assert {c["name"]: c["wave"] for c in COMPONENTS["components"]} == WAVES


def test_gitops_manifests_match_components():
    subprocess.run(["python", str(GITOPS / "generate.py"), "--check"], check=True)


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_directory_applications_point_at_real_manifests(env):
    """Una Application de directorio solo ve YAML de Kubernetes: ni values, ni casos de prueba."""
    for path in (GITOPS / f"apps/{env}").glob("*.yaml"):
        document = docs_of(path)[0]
        source = document["spec"].get("source")
        if document["kind"] != "Application" or path.stem == "root" or not source:
            continue
        assert source["path"].startswith("vectra-risk/"), path
        folder = REPO / source["path"]
        assert folder.is_dir(), folder
        if (folder / "Chart.yaml").exists() or (folder / "kustomization.yaml").exists():
            continue
        selected = [p for p in folder.iterdir() if p.is_file() and p.suffix in {".yaml", ".yml", ".json"}]
        directory = source.get("directory", {})
        if "include" in directory:
            allowed = set(directory["include"].strip("{}").split(","))
            selected = [p for p in selected if p.name in allowed]
            assert {p.name for p in selected} == allowed, path
        if "exclude" in directory:
            excluded = set(directory["exclude"].strip("{}").split(","))
            selected = [p for p in selected if p.name not in excluded]
        assert selected, path
        for candidate in selected:
            for manifest in docs_of(candidate):
                assert "apiVersion" in manifest and "kind" in manifest, candidate


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_project_allows_every_source_and_destination(env):
    project = docs_of(GITOPS / f"apps/{env}/project.yaml")[0]["spec"]
    namespaces = {d["namespace"] for d in project["destinations"]}
    for path in (GITOPS / f"apps/{env}").glob("*.yaml"):
        document = docs_of(path)[0]
        if document["kind"] != "Application":
            continue
        assert document["spec"]["destination"]["namespace"] in namespaces, path
        sources = document["spec"].get("sources") or [document["spec"]["source"]]
        for source in sources:
            assert source["repoURL"] in project["sourceRepos"], path


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_gitops_applications(env):
    folder = GITOPS / f"apps/{env}"
    assert (folder / "root.yaml").is_file()
    for path in folder.glob("*.yaml"):
        document = docs_of(path)[0]
        if document["kind"] != "Application":
            continue
        assert "automated" not in document["spec"].get("syncPolicy", {}), path
        assert document["spec"]["project"] == f"vectra-{env}"
        assert "argocd.argoproj.io/sync-wave" in document["metadata"]["annotations"]
        if path.stem in WAVES:
            assert int(document["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]) == WAVES[path.stem]


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_app_project_without_wildcards(env):
    project = docs_of(GITOPS / f"apps/{env}/project.yaml")[0]
    assert "*" not in project["spec"]["sourceRepos"]
    assert all("*" not in d["namespace"] for d in project["spec"]["destinations"])
    assert all("*" not in r["kind"] for r in project["spec"]["clusterResourceWhitelist"])


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_admission_policies_are_allowed_only_by_name(env):
    project = docs_of(GITOPS / f"apps/{env}/project.yaml")[0]
    policies = [r for r in project["spec"]["clusterResourceWhitelist"] if "AdmissionPolicy" in r["kind"]]
    assert {r["kind"] for r in policies} == {"ValidatingAdmissionPolicy", "ValidatingAdmissionPolicyBinding"}
    assert all(r["name"] == "safe-upgrades.gateway.networking.k8s.io" for r in policies)


def test_cluster_wide_secret_read_exists_only_in_kind():
    docs = docs_of(PLATFORM / "secrets/eso-rbac-secrets-read-kind.yaml")
    role = next(d for d in docs if d["kind"] == "ClusterRole")
    assert role["rules"] == [{"apiGroups": [""], "resources": ["secrets"], "verbs": ["list", "watch"]}]
    assert (GITOPS / "apps/kind/external-secrets-rbac-kind.yaml").exists()
    for env in ("staging", "prod"):
        assert not (GITOPS / f"apps/{env}/external-secrets-rbac-kind.yaml").exists()
        assert "eso-rbac-secrets-read-kind" not in "".join(p.read_text(encoding="utf-8") for p in (GITOPS / f"apps/{env}").glob("*.yaml"))


def test_trivy_skips_only_the_kind_secret_read():
    workflow = (REPO / ".github/workflows/supply-chain.yml").read_text(encoding="utf-8")
    assert re.findall(r"skip-files: (.+)", workflow) == ["vectra-risk/platform/secrets/eso-rbac-secrets-read-kind.yaml"]


def test_forbidden_steps_fixture(tmp_path):
    (tmp_path / "bad.yml").write_text("jobs:\n  a:\n    steps:\n      - run: kubectl apply -f x\n", encoding="utf-8")
    (tmp_path / "good.yml").write_text("jobs:\n  a:\n    steps:\n      - run: kubectl diff -f x\n", encoding="utf-8")
    problems = workflow_violations(tmp_path)
    assert len(problems) == 1 and "bad.yml" in problems[0]


def test_real_workflows_have_no_forbidden_steps():
    assert workflow_violations(REPO / ".github/workflows") == []


def test_real_composite_actions_have_no_forbidden_steps():
    assert workflow_violations(REPO / ".github/actions") == []


@pytest.mark.parametrize(("line", "bad"), [("FROM python:latest", True), ("FROM python", True), ("FROM python:3.12", False), ("FROM r/p:latest@sha256:abc", False)])
def test_dockerfile_latest_fixture(tmp_path, line, bad):
    (tmp_path / "Dockerfile").write_text(line + "\n", encoding="utf-8")
    assert bool(dockerfile_violations(tmp_path)) is bad


def test_pr_template_has_rollback():
    assert "## Rollback" in (REPO / ".github/pull_request_template.md").read_text(encoding="utf-8")


def test_no_migrations_nor_frontend():
    assert not (PLATFORM / "migrations").exists() and not (PLATFORM / "frontend").exists()


@pytest.mark.parametrize("folder", [PLATFORM, GITOPS, REPO / ".github"], ids=["platform", "gitops", "github"])
def test_every_yaml_file_parses(folder):
    for path in folder.rglob("*.y*ml"):
        if {"templates", ".charts", ".tools", "node_modules"} & set(path.parts):
            continue
        list(yaml.safe_load_all(path.read_text(encoding="utf-8")))


def test_role_passwords_reach_vectra_data_and_each_consumer():
    rendered = [d for d in helm(PLATFORM / "data/chart") if d and d["kind"] == "ExternalSecret"]
    found = {(d["metadata"]["namespace"], d["metadata"]["name"]) for d in rendered}
    consumers = yaml.safe_load((PLATFORM / "data/chart/values.yaml").read_text(encoding="utf-8"))["roleConsumers"]
    flows = yaml.safe_load((PLATFORM / "network/flows.yaml").read_text(encoding="utf-8"))
    assert set(consumers) == {r for roles in inventory_roles().values() for r in roles}
    for role, namespaces in consumers.items():
        secret = f"pg-role-{role.replace('_', '-')}"
        assert namespaces and ("vectra-data", secret) in found
        for namespace in namespaces:
            assert namespace in flows["meshed_namespaces"] and (namespace, secret) in found


def test_rendered_prod_has_no_k16():
    for path in (PLATFORM / "rendered/prod").glob("*.yaml"):
        assert "vectra-verification-operator" not in path.read_text(encoding="utf-8"), path


def test_rendered_uses_the_storage_class_of_the_environment():
    assert "storageClass: standard" in (PLATFORM / "rendered/kind/data.yaml").read_text(encoding="utf-8")
    assert "storageClass: vectra-encrypted" in (PLATFORM / "rendered/prod/data.yaml").read_text(encoding="utf-8")


def test_grafana_jobs():
    documents = docs_of(PLATFORM / "observability/grafana/manifests.yaml")
    job = next(d for d in documents if d["kind"] == "Job")
    assert job["metadata"]["annotations"]["argocd.argoproj.io/hook"] == "PostSync"
    cron = next(d for d in documents if d["kind"] == "CronJob")
    pod = cron["spec"]["jobTemplate"]["spec"]["template"]
    assert pod["metadata"]["annotations"]["config.alpha.linkerd.io/proxy-enable-native-sidecar"] == "true"


def test_dashboards_are_published_as_configmaps():
    config = yaml.safe_load((PLATFORM / "observability/dashboards/kustomization.yaml").read_text(encoding="utf-8"))
    files = {f for entry in config["configMapGenerator"] for f in entry["files"]}
    assert files == {p.name for p in (PLATFORM / "observability/dashboards").glob("*.json")}


def test_untouched_template_fails_rollback_note():
    assert not has_rollback_note((REPO / ".github/pull_request_template.md").read_text(encoding="utf-8"))


def test_filled_template_passes_rollback_note():
    assert has_rollback_note("## Qué cambia\nx\n\n## Rollback\nRevert y sync manual.\n")


def test_kyverno_test_names_only_existing_policies_and_fixtures():
    test = yaml.safe_load((PLATFORM / "policies/kyverno/kyverno-test.yaml").read_text(encoding="utf-8"))
    policies = {yaml.safe_load((PLATFORM / "policies/kyverno" / p).read_text(encoding="utf-8"))["metadata"]["name"]: yaml.safe_load((PLATFORM / "policies/kyverno" / p).read_text(encoding="utf-8")) for p in test["policies"]}
    resources = {d["metadata"]["name"] for r in test["resources"] for d in docs_of(PLATFORM / "policies/kyverno" / r)}
    for result in test["results"]:
        rules = {r["name"] for r in policies[result["policy"]]["spec"]["rules"]}
        assert result["rule"] in rules, result
        assert set(result["resources"]) <= resources, result


def test_every_alert_fires_and_has_a_quiet_case_in_promtool():
    tests = yaml.safe_load((PLATFORM / "observability/rules/tests/platform-rules-test.yaml").read_text(encoding="utf-8"))["tests"]
    cases = [case for test in tests for case in test["alert_rule_test"]]
    fired = {case["alertname"] for case in cases if case.get("exp_alerts")}
    assert {a["alert"] for a in ALERTS} == fired
    assert len([c for c in cases if not c.get("exp_alerts")]) >= 15


def test_every_validation_rule_except_signatures_has_a_pass_and_a_fail_case():
    """Por regla: dos reglas de una politica no se cubren entre si."""
    test = yaml.safe_load((PLATFORM / "policies/kyverno/kyverno-test.yaml").read_text(encoding="utf-8"))
    results: dict[tuple[str, str], set[str]] = {}
    for result in test["results"]:
        results.setdefault((result["policy"], result["rule"]), set()).add(result["result"])
    policies = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in (PLATFORM / "policies/kyverno").glob("*.yaml") if p.name != "kyverno-test.yaml"]
    validation_rules = [(d["metadata"]["name"], rule["name"]) for d in policies for rule in d["spec"]["rules"] if "validate" in rule]
    assert validation_rules
    missing = {rule: results.get(rule, set()) for rule in validation_rules if not {"pass", "fail"} <= results.get(rule, set())}
    assert not missing, missing
    assert {d["metadata"]["name"] for d in policies} - {policy for policy, _ in results} == {"verify-images"}


def test_deny_rules_do_not_block_deletes():
    """Una regla deny sin `operations` tambien se evalua al borrar, y ahi request.object esta vacio."""
    for path in (PLATFORM / "policies/kyverno").glob("*.yaml"):
        if path.name == "kyverno-test.yaml":
            continue
        for rule in docs_of(path)[0]["spec"]["rules"]:
            if "deny" in rule.get("validate", {}):
                for block in rule["match"]["any"]:
                    assert block["resources"]["operations"] == ["CREATE", "UPDATE"], (path.name, rule["name"])


def test_kyverno_can_read_what_its_policies_query():
    role = docs_of(PLATFORM / "policies/rbac/kyverno-context.yaml")[0]
    assert role["metadata"]["labels"]["rbac.kyverno.io/aggregate-to-admission-controller"] == "true"
    allowed = {resource for rule in role["rules"] for resource in rule["resources"]}
    for path in (PLATFORM / "policies/kyverno").glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        for resource in re.findall(r"urlPath: .*/namespaces/\{\{ request.namespace \}\}/([a-z]+)", text):
            assert resource in allowed, path.name
