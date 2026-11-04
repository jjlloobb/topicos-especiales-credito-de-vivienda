"""Values del controlador de Envoy Gateway (U02-T10, Paso 8): NFR-U2-03; INF-U2-02, 06; P-U2-01; K14."""

import collections
import subprocess
from pathlib import Path
from typing import Any

import envoy_gateway_design as design
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
HELM = ROOT / "platform" / ".tools" / "bin" / "helm"
CHART = ROOT / "platform" / ".charts" / "envoy-gateway" / "gateway-helm"
VALUES = ROOT / "platform" / "operators" / "envoy-gateway.yaml"
ADR = ROOT / "identity-edge" / "docs" / "adr-envoy-gateway.md"
SA = ("envoy-gateway", "envoy-gateway-system")
GATEWAY_GROUPS = ("gateway.networking.k8s.io", "gateway.envoyproxy.io")
READ = {"get", "list", "watch"}
MANAGE = {"create", "get", "list", "watch", "patch", "update", "delete", "deletecollection"}
DATA_PLANE = (("apps", "deployments"), ("", "services"), ("", "configmaps"))

Docs = list[dict[str, Any]]


def render(*extra: str) -> Docs:
    run = subprocess.run(  # noqa: S603 - helm fijo de platform/.tools
        [str(HELM), "template", "envoy-gateway", str(CHART), "-n", "envoy-gateway-system", "--skip-crds", "-f", str(VALUES), *extra],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert run.returncode == 0, run.stderr
    return [d for d in yaml.safe_load_all(run.stdout) if d]


def find(docs: Docs, kind: str, name: str) -> dict[str, Any]:
    (found,) = [d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name]
    return found


def controller_config(docs: Docs) -> dict[str, Any]:
    return yaml.safe_load(find(docs, "ConfigMap", "envoy-gateway-config")["data"]["envoy-gateway.yaml"])


def problems(docs: Docs) -> list[str]:
    found = []
    dep = find(docs, "Deployment", "envoy-gateway")
    pod = dep["spec"]["template"]["spec"]
    cfg = controller_config(docs)
    if dep["spec"].get("replicas") != design.controller_replicas():
        found.append("replicas")
    if pod.get("priorityClassName") != design.controller_priority():
        found.append("priorityClassName")
    (container,) = [c for c in pod["containers"] if c["name"] == "envoy-gateway"]
    if container["resources"] != design.controller_resources():
        found.append("resources")
    if cfg["provider"]["kubernetes"]["deploy"]["type"] != design.deploy_type():
        found.append("deploy.type")
    if cfg.get("extensionApis", {}).get(design.patch_policy_key()) is not True:
        found.append("extensionApis")
    shutdown = cfg.get("provider", {}).get("kubernetes", {}).get("shutdownManager", {}).get("image")
    if shutdown != design.shutdown_manager_image():
        found.append("shutdownManager.image")
    if "rateLimit" in cfg:
        found.append("rateLimit")
    if cfg.get("provider", {}).get("kubernetes", {}).get("leaderElection", {}).get("disable"):
        found.append("leaderElection")
    return found


def test_the_controller_render_follows_the_design() -> None:
    assert problems(render()) == []


@pytest.mark.parametrize(
    ("args", "name"),
    [
        (("--set", "deployment.replicas=1"), "replicas"),
        (("--set", "deployment.priorityClassName=null"), "priorityClassName"),
        (("--set", "deployment.envoyGateway.resources.limits.cpu=2"), "resources"),
        (("--set", "config.envoyGateway.provider.kubernetes.deploy.type=ControllerNamespace"), "deploy.type"),
        (("--set", "config.envoyGateway.extensionApis.enableEnvoyPatchPolicy=false"), "extensionApis"),
        (("--set", "config.envoyGateway.rateLimit.backend.type=Redis"), "rateLimit"),
        (("--set", "config.envoyGateway.provider.kubernetes.shutdownManager.image=docker.io/envoyproxy/gateway:v1.9.3"), "shutdownManager.image"),
        (("--set", "config.envoyGateway.provider.kubernetes.leaderElection.disable=true"), "leaderElection"),
    ],
)
def test_each_controller_check_fails_on_an_altered_render(args: tuple[str, ...], name: str) -> None:
    assert name in problems(render(*args))


def test_the_design_values_are_read_from_the_documents() -> None:
    assert (design.controller_replicas(), design.controller_priority()) == (2, "vectra-high")
    assert design.shutdown_manager_image() == "registro.banco.internal/vectra/envoy-gateway@sha256:192fc9bdadb6d2462e8cf7bd702ce3dd9648f3310c6038787448a1f509b7cd9f"
    assert design.controller_resources() == {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}


# --- K14 (X2): el RBAC exacto del chart ------------------------------------------------------------


def grants(docs: Docs) -> dict[tuple[str, str], tuple[set[str], set[str]]]:
    roles = {(d["kind"], d["metadata"]["name"]): d for d in docs if d["kind"] in ("Role", "ClusterRole")}
    out: dict[tuple[str, str], tuple[set[str], set[str]]] = collections.defaultdict(lambda: (set(), set()))
    for binding in (d for d in docs if d["kind"] in ("RoleBinding", "ClusterRoleBinding")):
        if SA not in [(s["name"], s.get("namespace")) for s in binding["subjects"]]:
            continue
        role = roles[(binding["roleRef"]["kind"], binding["roleRef"]["name"])]
        scope = "cluster" if binding["kind"] == "ClusterRoleBinding" else binding["metadata"]["namespace"]
        for rule in role["rules"]:
            for group in rule["apiGroups"]:
                for resource in rule["resources"]:
                    verbs, scopes = out[(group, resource)]
                    verbs.update(rule["verbs"])
                    scopes.add(scope)
    return dict(out)


def rbac_lines(docs: Docs) -> list[str]:
    return [
        f"- `{group or 'core'}/{resource}`: {', '.join(sorted(verbs))} ({', '.join(sorted(scopes))})"
        for (group, resource), (verbs, scopes) in sorted(grants(docs).items())
    ]


def adr_rbac_lines() -> list[str]:
    text = ADR.read_text(encoding="utf-8")
    body = text[text.index(RBAC_HEADING) + len(RBAC_HEADING) :]
    end = [i for i in (body.find("\n## "), body.find("\n### ")) if i != -1]
    body = body[: min(end)] if end else body
    return [line for line in body.splitlines() if line.startswith("- `")]


RBAC_HEADING = "### Reglas del RBAC del chart (K14)"


def test_k14_is_exactly_the_rbac_of_the_chart() -> None:
    """X2: K14 es el RBAC del chart `gateway-helm` v1.9.3 listado en el ADR §5; si el chart cambia, la prueba falla."""
    assert "listado en `identity-edge/docs/adr-envoy-gateway.md` §5" in design.k14_row()
    assert rbac_lines(render()) == adr_rbac_lines()


def test_the_k14_comparison_sees_a_changed_grant() -> None:
    docs = render()
    role = find(docs, "ClusterRole", "envoy-gateway-gateway-helm-envoy-gateway-role")
    role["rules"].append({"apiGroups": ["rbac.authorization.k8s.io"], "resources": ["clusterroles"], "verbs": ["escalate"]})
    assert rbac_lines(docs) != adr_rbac_lines()


def test_the_k14_comparison_sees_a_dropped_grant() -> None:
    docs = render()
    role = find(docs, "ClusterRole", "envoy-gateway-gateway-helm-envoy-gateway-role")
    role["rules"].pop()
    assert rbac_lines(docs) != adr_rbac_lines()


def test_the_k14_comparison_sees_a_wider_verb() -> None:
    docs = render()
    role = find(docs, "ClusterRole", "envoy-gateway-gateway-helm-envoy-gateway-role")
    role["rules"][0]["verbs"].append("delete")
    assert rbac_lines(docs) != adr_rbac_lines()
