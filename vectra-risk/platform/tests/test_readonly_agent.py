"""U01-T17: la identidad de solo lectura de los agentes del loop. Se prueba el manifiesto real; las mutaciones se aplican a una copia en memoria de el."""

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

PLATFORM = Path(__file__).resolve().parents[1]
GITOPS = PLATFORM.parent / "vectra-risk-gitops"
MANIFEST = PLATFORM / "rbac/readonly-agent/readonly-agent-kind.yaml"
READ_ONLY = ["get", "list", "watch"]
FORBIDDEN_RESOURCES = {"secrets", "pods/exec", "pods/portforward", "pods/attach", "pods/ephemeralcontainers", "serviceaccounts/token", "tokenreviews", "subjectaccessreviews"}
FORBIDDEN_VERBS = {"create", "update", "patch", "delete", "deletecollection", "impersonate", "escalate", "bind", "*"}
Doc = dict[str, Any]


def load() -> list[Doc]:
    return [d for d in yaml.safe_load_all(MANIFEST.read_text(encoding="utf-8")) if d]


def role_of(documents: list[Doc]) -> Doc:
    (role,) = [d for d in documents if d["kind"] == "ClusterRole"]
    return role


def problems_in(role: Doc) -> list[str]:
    """Lo que el ClusterRole no puede tener. Vacia si cumple."""
    found: list[str] = []
    for rule in role["rules"]:
        where = f"{rule['apiGroups']}/{rule['resources']}"
        if rule["verbs"] != READ_ONLY:
            found.append(f"{where}: verbos {rule['verbs']}")
        for field in ("verbs", "resources", "apiGroups", "nonResourceURLs", "resourceNames"):
            if any("*" in v for v in rule.get(field, [])):
                found.append(f"{where}: comodin en {field}")
        for resource in rule["resources"]:
            if resource.split("/")[0] == "secrets" or resource in FORBIDDEN_RESOURCES:
                found.append(f"{where}: recurso prohibido {resource}")
        if "nonResourceURLs" in rule:
            found.append(f"{where}: nonResourceURLs")
    return found


def test_readonly_agent_manifest_has_the_four_objects_and_the_binding_points_at_them():
    documents = load()
    kinds = sorted(d["kind"] for d in documents)
    assert kinds == ["ClusterRole", "ClusterRoleBinding", "Secret", "ServiceAccount"]
    service_account = next(d for d in documents if d["kind"] == "ServiceAccount")
    binding = next(d for d in documents if d["kind"] == "ClusterRoleBinding")
    token = next(d for d in documents if d["kind"] == "Secret")
    assert binding["roleRef"]["name"] == role_of(documents)["metadata"]["name"]
    assert binding["subjects"] == [{"kind": "ServiceAccount", "name": service_account["metadata"]["name"], "namespace": service_account["metadata"]["namespace"]}]
    assert token["type"] == "kubernetes.io/service-account-token"
    assert token["metadata"]["annotations"]["kubernetes.io/service-account.name"] == service_account["metadata"]["name"]
    assert "data" not in token and "stringData" not in token  # el valor no esta en Git


def test_readonly_agent_real_role_is_read_only_and_has_no_wildcards_nor_secrets():
    assert problems_in(role_of(load())) == []


def test_readonly_agent_every_rule_lists_only_get_list_watch():
    rules = role_of(load())["rules"]
    assert rules and all(rule["verbs"] == READ_ONLY for rule in rules)


def test_readonly_agent_never_mentions_secrets_or_the_pod_doors():
    resources = {r for rule in role_of(load())["rules"] for r in rule["resources"]}
    assert not resources & FORBIDDEN_RESOURCES
    assert not any(r.split("/")[0] == "secrets" or r.startswith("pods/") and r != "pods/log" for r in resources)  # `secretstores` no es `secrets`


def test_readonly_agent_covers_what_the_read_only_scripts_read():
    covered = {(g, r) for rule in role_of(load())["rules"] for g in rule["apiGroups"] for r in rule["resources"]}
    needed = {
        ("", "pods"), ("", "pods/log"), ("", "nodes"), ("", "namespaces"), ("apps", "deployments"), ("batch", "jobs"), ("networking.k8s.io", "networkpolicies"),
        ("argoproj.io", "applications"), ("external-secrets.io", "externalsecrets"), ("serving.kserve.io", "inferenceservices"),
        ("policy.linkerd.io", "servers"), ("policy.linkerd.io", "authorizationpolicies"), ("policy.linkerd.io", "meshtlsauthentications"),
        ("metrics.k8s.io", "pods"), ("postgresql.cnpg.io", "clusters"), ("kyverno.io", "clusterpolicies"), ("gateway.networking.k8s.io", "gateways"),
        ("gateway.envoyproxy.io", "envoyproxies"), ("monitoring.coreos.com", "servicemonitors"), ("monitoring.coreos.com", "prometheusrules"),
        ("autoscaling", "horizontalpodautoscalers"), ("policy", "poddisruptionbudgets"), ("external-secrets.io", "secretstores"),
    }
    assert needed <= covered, sorted(needed - covered)


@pytest.mark.parametrize("name", ["add-delete", "add-secrets", "wildcard-resources", "wildcard-verbs", "wildcard-groups", "add-exec", "add-impersonate", "add-secrets-subresource"])
def test_readonly_agent_mutations_of_the_real_role_are_rejected(name: str):
    role = copy.deepcopy(role_of(load()))
    first = role["rules"][0]
    if name == "add-delete":
        first["verbs"] = [*first["verbs"], "delete"]
    elif name == "add-secrets":
        first["resources"] = [*first["resources"], "secrets"]
    elif name == "wildcard-resources":
        first["resources"] = ["*"]
    elif name == "wildcard-verbs":
        first["verbs"] = ["*"]
    elif name == "wildcard-groups":
        first["apiGroups"] = ["*"]
    elif name == "add-exec":
        first["resources"] = [*first["resources"], "pods/exec"]
    elif name == "add-impersonate":
        role["rules"].append({"apiGroups": [""], "resources": ["users"], "verbs": ["impersonate"]})
    elif name == "add-secrets-subresource":
        first["resources"] = [*first["resources"], "secrets/status"]
    assert problems_in(role), name


def test_readonly_agent_application_exists_only_in_kind():
    assert [p.name for p in (GITOPS / "apps/kind").glob("*readonly*")] == ["readonly-agent-rbac-kind.yaml"]
    for env in ("staging", "prod"):
        assert not list((GITOPS / f"apps/{env}").glob("*readonly*"))
        assert "readonly-agent" not in "".join(p.read_text(encoding="utf-8") for p in (GITOPS / f"apps/{env}").glob("*.yaml"))
    application = yaml.safe_load((GITOPS / "apps/kind/readonly-agent-rbac-kind.yaml").read_text(encoding="utf-8"))
    assert application["spec"]["source"]["path"] == "vectra-risk/platform/rbac/readonly-agent"
    assert application["spec"]["source"]["directory"] == {"include": "readonly-agent-kind.yaml"}
    assert application["spec"]["destination"]["namespace"] == "argocd"
    assert application["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "1"


def test_readonly_agent_kyverno_fixture_is_the_real_cluster_role():
    fixtures = [d for d in yaml.safe_load_all((PLATFORM / "policies/kyverno/fixtures/resources.yaml").read_text(encoding="utf-8")) if d]
    copy_in_fixture = next(d for d in fixtures if d["kind"] == "ClusterRole" and d["metadata"]["name"] == "vectra-readonly-agent")
    assert copy_in_fixture == role_of(load())
    cases = yaml.safe_load((PLATFORM / "policies/kyverno/kyverno-test.yaml").read_text(encoding="utf-8"))["results"]
    assert {"policy": "disallow-rbac-wildcards", "rule": "disallow-rbac-wildcards", "resources": ["vectra-readonly-agent"], "kind": "ClusterRole", "result": "pass"} in cases
