"""U01-T17: la identidad de solo lectura de los agentes del loop. Se prueba el manifiesto real; las mutaciones se aplican a una copia en memoria de el."""

import copy
import re
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
CHARTS = PLATFORM / ".charts"
#: Lo que no es CRD: grupo -> recursos que existen en Kubernetes. Un nombre que no este aqui ni en un CRD de `platform/.charts` es un error de escritura.
BUILTIN = {
    "": {"pods", "pods/log", "services", "endpoints", "configmaps", "events", "namespaces", "nodes", "persistentvolumeclaims", "persistentvolumes", "resourcequotas", "limitranges", "serviceaccounts", "replicationcontrollers"},
    "apps": {"deployments", "replicasets", "statefulsets", "daemonsets"},
    "batch": {"jobs", "cronjobs"},
    "autoscaling": {"horizontalpodautoscalers"},
    "policy": {"poddisruptionbudgets"},
    "networking.k8s.io": {"networkpolicies", "ingresses", "ingressclasses"},
    "discovery.k8s.io": {"endpointslices"},
    "events.k8s.io": {"events"},
    "storage.k8s.io": {"storageclasses"},
    "scheduling.k8s.io": {"priorityclasses"},
    "rbac.authorization.k8s.io": {"roles", "rolebindings", "clusterroles", "clusterrolebindings"},
    "apiextensions.k8s.io": {"customresourcedefinitions"},
    "admissionregistration.k8s.io": {"validatingwebhookconfigurations", "mutatingwebhookconfigurations", "validatingadmissionpolicies", "validatingadmissionpolicybindings"},
    "metrics.k8s.io": {"pods", "nodes"},
}  # fmt: skip
Doc = dict[str, Any]


def crd_names() -> set[str]:
    """`<plural>.<grupo>` de cada CRD que traen los charts de `platform/.charts` (CI y operador los tienen)."""
    pattern = re.compile(r'^\s*name:\s*"?([a-z0-9-]+\.[a-z0-9.-]+)"?\s*$', re.MULTILINE)
    found: set[str] = set()
    for path in CHARTS.rglob("*"):
        if path.is_file() and path.suffix in {".yaml", ".yml", ".tpl"}:
            found |= set(pattern.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return found

KNOWN_CRDS = crd_names()


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
            if "/" in resource and resource != "pods/log":
                found.append(f"{where}: subrecurso {resource} (solo se admite pods/log: proxy, exec, token y log de nodos abren caminos que `get` no cierra)")
            for group in rule["apiGroups"]:
                if resource not in BUILTIN.get(group, set()) and f"{resource}.{group}" not in KNOWN_CRDS:
                    found.append(f"{where}: {resource} no existe en el grupo {group!r} (error de escritura o CRD que ningun chart trae)")
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


@pytest.mark.parametrize("name", ["add-delete", "add-secrets", "wildcard-resources", "wildcard-verbs", "wildcard-groups", "add-exec", "add-impersonate", "add-secrets-subresource", "add-nodes-proxy", "add-services-proxy", "add-pods-proxy", "add-nodes-log", "add-sa-token", "typo-resource", "typo-group"])
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
    elif name in {"add-nodes-proxy", "add-services-proxy", "add-pods-proxy", "add-nodes-log", "add-sa-token"}:
        extra = {"add-nodes-proxy": "nodes/proxy", "add-services-proxy": "services/proxy", "add-pods-proxy": "pods/proxy", "add-nodes-log": "nodes/log", "add-sa-token": "serviceaccounts/token"}[name]
        role["rules"].append({"apiGroups": [""], "resources": [extra], "verbs": READ_ONLY})
    elif name == "typo-resource":
        role["rules"].append({"apiGroups": [""], "resources": ["podz"], "verbs": READ_ONLY})
    elif name == "typo-group":
        role["rules"].append({"apiGroups": ["argoproj.iox"], "resources": ["applications"], "verbs": READ_ONLY})
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


def test_readonly_agent_every_resource_pair_exists():
    """F-02: el validador comprueba cada (grupo, recurso) contra el nucleo y los CRD de los charts; con `.charts` ausente no hay nada que comparar y fallaria."""
    assert KNOWN_CRDS, "platform/.charts vacio: corre `make -C platform charts`"
    assert "applications.argoproj.io" in KNOWN_CRDS and "certificates.cert-manager.io" in KNOWN_CRDS
    assert problems_in(role_of(load())) == []
