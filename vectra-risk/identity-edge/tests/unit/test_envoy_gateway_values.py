"""Values del controlador de Envoy Gateway (U02-T10, Paso 8; U02-T11, Paso 9): NFR-U2-03; INF-U2-02, 03, 06; P-U2-01; K14; R1 y R2."""

import subprocess
from pathlib import Path
from typing import Any

import envoy_gateway_design as design
import pytest
import valkey_design as rl
import yaml

ROOT = Path(__file__).resolve().parents[3]
HELM = ROOT / "platform" / ".tools" / "bin" / "helm"
CHART = ROOT / "platform" / ".charts" / "envoy-gateway" / "gateway-helm"
VALUES = ROOT / "platform" / "operators" / "envoy-gateway.yaml"
ADR = ROOT / "identity-edge" / "docs" / "adr-envoy-gateway.md"
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


def ratelimit_problems(cfg: dict[str, Any], env: str) -> list[str]:
    """R1 y R2 (INF-U2-03): lo que los values fijan de `envoy-ratelimit`, leido del diseno. Las `rateLimit*` completas las exige conftest."""
    found = []
    rate_limit = cfg.get("rateLimit", {})
    kube = cfg.get("provider", {}).get("kubernetes", {})
    deployment = kube.get("rateLimitDeployment", {})
    if rate_limit.get("backend", {}).get("type") != "Redis":
        found.append("rateLimit.backend.type")
    if rate_limit.get("backend", {}).get("redis", {}).get("url") != rl.ratelimit_url():
        found.append("rateLimit.backend.redis.url")
    if rate_limit.get("failClosed", False) != rl.ratelimit_failclosed():
        found.append("rateLimit.failClosed")
    tracing = rate_limit.get("telemetry", {}).get("tracing", {})
    if (tracing.get("provider", {}).get("type"), tracing.get("provider", {}).get("url"), tracing.get("samplingRate")) != ("OpenTelemetry", *rl.ratelimit_tracing()):
        found.append("rateLimit.telemetry.tracing")
    if deployment.get("replicas") != rl.ratelimit_replicas():
        found.append("rateLimitDeployment.replicas")
    container = deployment.get("container", {})
    if container.get("image") != f"{rl.ratelimit_registries()[env]}@{rl.ratelimit_digest()}":
        found.append("rateLimitDeployment.image")
    if container.get("resources") != rl.ratelimit_resources():
        found.append("rateLimitDeployment.resources")
    if deployment.get("pod", {}).get("priorityClassName") != design.controller_priority():
        found.append("rateLimitDeployment.priorityClassName")
    hpa = kube.get("rateLimitHpa", {})
    low, high, cpu = rl.ratelimit_hpa()
    if (hpa.get("minReplicas"), hpa.get("maxReplicas")) != (low, high) or hpa.get("metrics", [{}])[0].get("resource", {}).get("target", {}).get("averageUtilization") != cpu:
        found.append("rateLimitHpa")
    if kube.get("rateLimitPDB", {}).get("minAvailable") != rl.ratelimit_pdb():
        found.append("rateLimitPDB")
    return found


def problems(docs: Docs, env: str = "prod") -> list[str]:
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
    if shutdown != design.shutdown_manager_image("kind" if env == "kind" else "prod"):
        found.append("shutdownManager.image")
    found += ratelimit_problems(cfg, env)
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
        (("--set", "config.envoyGateway.rateLimit.backend.type=Memory"), "rateLimit.backend.type"),
        (("--set", "config.envoyGateway.rateLimit.backend.redis.url=ratelimit"), "rateLimit.backend.redis.url"),
        (("--set", "config.envoyGateway.rateLimit.failClosed=true"), "rateLimit.failClosed"),
        (("--set", "config.envoyGateway.rateLimit.telemetry.tracing.samplingRate=10"), "rateLimit.telemetry.tracing"),
        (("--set", "config.envoyGateway.provider.kubernetes.rateLimitDeployment.replicas=1"), "rateLimitDeployment.replicas"),
        (("--set", "config.envoyGateway.provider.kubernetes.rateLimitDeployment.container.image=docker.io/envoyproxy/ratelimit:5ae0682e"), "rateLimitDeployment.image"),
        (("--set", "config.envoyGateway.provider.kubernetes.rateLimitDeployment.container.resources.limits.cpu=2"), "rateLimitDeployment.resources"),
        (("--set", "config.envoyGateway.provider.kubernetes.rateLimitDeployment.pod.priorityClassName=vectra-low"), "rateLimitDeployment.priorityClassName"),
        (("--set", "config.envoyGateway.provider.kubernetes.rateLimitHpa.maxReplicas=8"), "rateLimitHpa"),
        (("--set", "config.envoyGateway.provider.kubernetes.rateLimitPDB.minAvailable=2"), "rateLimitPDB"),
        (("--set", "config.envoyGateway.provider.kubernetes.shutdownManager.image=docker.io/envoyproxy/gateway:v1.9.3"), "shutdownManager.image"),
        (("--set", "config.envoyGateway.provider.kubernetes.leaderElection.disable=true"), "leaderElection"),
    ],
)
def test_each_controller_check_fails_on_an_altered_render(args: tuple[str, ...], name: str) -> None:
    assert name in problems(render(*args))


KIND_VALUES = ROOT / "platform" / "operators" / "envoy-gateway-kind.yaml"


def test_kind_values_set_the_kind_registry_for_the_sidecar_and_for_ratelimit() -> None:
    """Y3 y R2: el `kind_values` de la entrada `envoy-gateway` cambia solo las imagenes del shutdown-manager y de envoy-ratelimit."""
    cfg = controller_config(render("-f", str(KIND_VALUES)))
    assert cfg["provider"]["kubernetes"]["shutdownManager"]["image"] == design.shutdown_manager_image("kind")
    assert design.shutdown_manager_image("kind") != design.shutdown_manager_image("prod")
    assert problems(render("-f", str(KIND_VALUES)), "kind") == []
    # sin decir que es kind, el unico desvio contra el banco son las dos imagenes que el espejo de kind cambia
    assert problems(render("-f", str(KIND_VALUES))) == ["shutdownManager.image", "rateLimitDeployment.image"]
    assert cfg["provider"]["kubernetes"]["rateLimitDeployment"]["container"]["image"] == f"{rl.ratelimit_registries()['kind']}@{rl.ratelimit_digest()}"
    components = yaml.safe_load((ROOT / "vectra-risk-gitops" / "components.yaml").read_text(encoding="utf-8"))["components"]
    (entry,) = [c for c in components if c["name"] == "envoy-gateway"]
    assert entry["kind_values"] == ["platform/operators/envoy-gateway-kind.yaml"]


def test_the_design_values_of_ratelimit_are_read_from_the_documents() -> None:
    assert rl.ratelimit_digest() == "sha256:b95206e32b1a5f824fb06062fbb85bbdfb7f5de54135e92afe8462f22c979681"
    assert rl.ratelimit_resources() == {"requests": {"cpu": "100m", "memory": "64Mi"}, "limits": {"cpu": "500m", "memory": "128Mi"}}
    assert rl.ratelimit_registries() == {"kind": "kind-registry:5000/vectra/ratelimit", "staging": "registro.banco.internal/vectra/ratelimit", "prod": "registro.banco.internal/vectra/ratelimit"}
    assert rl.master_name() == "ratelimit" and rl.ratelimit_url().startswith("ratelimit,sentinel-a-0.")


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_the_bank_environments_share_the_ratelimit_values(env: str) -> None:
    """Staging y prod usan los mismos values: el banco."""
    assert problems(render(), env) == []


def test_the_design_values_are_read_from_the_documents() -> None:
    assert (design.controller_replicas(), design.controller_priority()) == (2, "vectra-high")
    assert design.shutdown_manager_image() == "registro.banco.internal/vectra/envoy-gateway@sha256:192fc9bdadb6d2462e8cf7bd702ce3dd9648f3310c6038787448a1f509b7cd9f"
    assert design.controller_resources() == {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}


# --- K14 (X2): el RBAC exacto del chart ------------------------------------------------------------


def rbac_lines(docs: Docs) -> list[str]:
    """Una linea por regla y por ambito (Y4: tambien el ServiceAccount de `certgen`; F-04: sin juntar verbos ni ambitos)."""
    roles = {(d["kind"], d["metadata"]["name"]): d for d in docs if d["kind"] in ("Role", "ClusterRole")}
    lines = []
    for binding in (d for d in docs if d["kind"] in ("RoleBinding", "ClusterRoleBinding")):
        role = roles[(binding["roleRef"]["kind"], binding["roleRef"]["name"])]
        scope = "cluster" if binding["kind"] == "ClusterRoleBinding" else binding["metadata"]["namespace"]
        for subject in binding["subjects"]:
            for rule in role["rules"]:
                resources = ", ".join(f"{group or 'core'}/{resource}" for group in sorted(rule["apiGroups"]) for resource in sorted(rule["resources"]))
                names = f" [{', '.join(sorted(rule['resourceNames']))}]" if rule.get("resourceNames") else ""
                lines.append(f"- `{subject['name']}` ({scope}): {resources}: {', '.join(sorted(rule['verbs']))}{names}")
    return sorted(set(lines))


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


def test_the_k14_comparison_sees_a_verb_that_moves_to_a_cluster_wide_role() -> None:
    """F-04: un verbo que pasa de un Role a un ClusterRole cambia las lineas."""
    docs = render()
    namespaced = find(docs, "Role", "envoy-gateway-gateway-helm-leader-election-role")
    cluster = find(docs, "ClusterRole", "envoy-gateway-gateway-helm-envoy-gateway-role")
    moved = namespaced["rules"][0]
    namespaced["rules"].remove(moved)
    cluster["rules"].append(moved)
    assert rbac_lines(docs) != adr_rbac_lines()


def test_k14_includes_the_certgen_service_account() -> None:
    assert any(line.startswith("- `envoy-gateway-gateway-helm-certgen`") for line in rbac_lines(render()))
    assert any(line.startswith("- `envoy-gateway-gateway-helm-certgen`") for line in adr_rbac_lines())


def test_the_k14_comparison_sees_a_wider_verb() -> None:
    docs = render()
    role = find(docs, "ClusterRole", "envoy-gateway-gateway-helm-envoy-gateway-role")
    role["rules"][0]["verbs"].append("delete")
    assert rbac_lines(docs) != adr_rbac_lines()
