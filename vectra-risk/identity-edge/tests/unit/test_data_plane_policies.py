"""El data plane contra las politicas de U1 (U02-T10, Y1 y Y2): el Deployment que Envoy Gateway v1.9.3 armaria, con `kyverno apply`.

`EnvoyProxy` no genera un Deployment en el render, asi que esta prueba arma el que `resource_provider.go` y `resource.go` de
v1.9.3 producirian con `generated/<env>/` y le aplica las politicas estaticas de U1 (`STATIC_POLICIES` del Makefile) mas
`require-spread-and-pdb`. Lo que modela, con su fuente en v1.9.3:
- etiquetas del Deployment: `EnvoyAppLabel` + las del owning gateway + `Gateway.spec.infrastructure.labels` (`getLabels`);
- etiquetas del pod: las anteriores + `pod.labels` del EnvoyProxy, que ganan (`getPodLabels`);
- `replicas` sin fijar con `envoyHpa` (el apiserver lo deja en 1);
- contenedor `envoy`: contexto de seguridad por defecto, mezclado con el del EnvoyProxy (`expectedEnvoySecurityContext`);
- sidecar `shutdown-manager`: requests 10m / 32Mi y sin limits (`DefaultShutdownManagerContainerResourceRequirements`), el mismo
  contexto, la imagen de `provider.kubernetes.shutdownManager.image` del controlador, y el `envoyDeployment.patch` mezclado por nombre.
"""

import copy
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import envoy_gateway_design as eg_design
import gateway_checks as gc
import pytest
import yaml

ROOT = gc.EDGE.parent
KYVERNO = gc.TOOLS_BIN / "kyverno"
POLICIES = ROOT / "platform" / "policies" / "kyverno"
MAKEFILE = (gc.EDGE / "Makefile").read_text(encoding="utf-8")
OK = re.compile(r"pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0")
OWNING_GATEWAY = "gateway.envoyproxy.io/owning-gateway-name"
ENV_IMAGES = {"kind": "kind", "staging": "prod", "prod": "prod"}


def static_policies() -> list[str]:
    found = re.search(r"^STATIC_POLICIES := (.+)$", MAKEFILE, re.MULTILINE)
    assert found, "identity-edge/Makefile sin STATIC_POLICIES"
    return found.group(1).split()


def deep_default_security() -> dict[str, Any]:
    """`resource.DefaultSecurityContext()` de v1.9.3, con la raiz escribible que el codigo de Envoy y del sidecar dejan en nil."""
    return {
        "allowPrivilegeEscalation": False,
        "capabilities": {"drop": ["ALL"]},
        "privileged": False,
        "runAsNonRoot": True,
        "runAsGroup": 65532,
        "runAsUser": 65532,
        "seccompProfile": {"type": "RuntimeDefault"},
    }


def merge_containers(containers: list[dict[str, Any]], patch: dict[str, Any]) -> list[dict[str, Any]]:
    """StrategicMerge de `spec.template.spec.containers` por nombre, lo unico que los patches de EnvoyProxy usan aqui."""
    merged = copy.deepcopy(containers)
    for change in patch["value"]["spec"]["template"]["spec"]["containers"]:
        (target,) = [c for c in merged if c["name"] == change["name"]]
        for key, value in change.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                target[key] = {**target[key], **value}
            else:
                target[key] = value
    return merged


def data_plane_deployment(docs: gc.Docs, env: str, with_patch: bool = True) -> dict[str, Any]:
    proxy = gc.find(docs, "EnvoyProxy", "api-gateway")["spec"]["provider"]["kubernetes"]
    gateway = gc.find(docs, "Gateway", "api-gateway")
    deployment = proxy["envoyDeployment"]
    labels = {
        "app.kubernetes.io/name": "envoy",
        "app.kubernetes.io/component": "proxy",
        "app.kubernetes.io/managed-by": "envoy-gateway",
        OWNING_GATEWAY: gateway["metadata"]["name"],
        "gateway.envoyproxy.io/owning-gateway-namespace": gateway["metadata"]["namespace"],
        **gateway["spec"].get("infrastructure", {}).get("labels", {}),
    }
    security = {**deep_default_security(), **deployment["container"]["securityContext"]}
    containers = [
        {"name": "envoy", "image": deployment["container"]["image"], "resources": deployment["container"]["resources"], "securityContext": security},
        {
            "name": "shutdown-manager",
            "image": eg_design.shutdown_manager_image(ENV_IMAGES[env]),
            "resources": {"requests": {"cpu": "10m", "memory": "32Mi"}},
            "securityContext": security,
        },
    ]
    if with_patch and "patch" in deployment:
        containers = merge_containers(containers, deployment["patch"])
    pod = deployment["pod"]
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "envoy-vectra-edge-api-gateway", "namespace": gateway["metadata"]["namespace"], "labels": labels},
        "spec": {
            "replicas": 1,  # con envoyHpa v1.9.3 no lo fija y el apiserver lo deja en 1
            "selector": {"matchLabels": {"app.kubernetes.io/name": "envoy"}},
            "template": {
                "metadata": {"labels": {**labels, **pod["labels"]}},
                "spec": {
                    "containers": containers,
                    "priorityClassName": pod["priorityClassName"],
                    "securityContext": pod["securityContext"],
                    "topologySpreadConstraints": pod["topologySpreadConstraints"],
                },
            },
        },
    }


def apply_policies(resources: list[dict[str, Any]], extra: tuple[str, ...] = ("require-spread-and-pdb.yaml",)) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        policies = Path(tmp) / "policies"
        policies.mkdir()
        for name in [*static_policies(), *extra]:
            shutil.copy(POLICIES / name, policies / name)
        target = Path(tmp) / "resources.yaml"
        target.write_text(yaml.safe_dump_all(resources, sort_keys=False), encoding="utf-8")
        run = subprocess.run([str(KYVERNO), "apply", str(policies), "--resource", str(target)], capture_output=True, text=True, check=False)  # noqa: S603 - herramienta fija de platform/.tools
    output = run.stdout + run.stderr
    return (0 if run.returncode == 0 and OK.search(output) else 1), output


def service(docs: gc.Docs) -> dict[str, Any]:
    kube = gc.find(docs, "EnvoyProxy", "api-gateway")["spec"]["provider"]["kubernetes"]["envoyService"]
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": "envoy-vectra-edge-api-gateway", "namespace": "vectra-edge", "labels": kube["labels"]},
        "spec": {"type": kube["type"], "externalTrafficPolicy": kube["externalTrafficPolicy"]},
    }


@pytest.mark.parametrize("env", gc.ENVS)
def test_the_data_plane_deployment_passes_the_static_policies_and_the_spread_policy(env):
    docs = gc.load_env(env)
    code, output = apply_policies([data_plane_deployment(docs, env), service(docs)])
    assert code == 0, output


def test_the_simulation_sees_the_sidecar_without_limits():
    """Y1: sin el patch, el shutdown-manager de v1.9.3 no tiene limits y `require-resources` lo rechaza."""
    docs = gc.load_env("prod")
    code, output = apply_policies([data_plane_deployment(docs, "prod", with_patch=False)])
    assert code != 0 and "require-resources" in output, output


def test_the_simulation_sees_a_writable_root():
    docs = copy.deepcopy(gc.load_env("prod"))
    gc.find(docs, "EnvoyProxy", "api-gateway")["spec"]["provider"]["kubernetes"]["envoyDeployment"]["container"]["securityContext"].pop("readOnlyRootFilesystem")
    code, output = apply_policies([data_plane_deployment(docs, "prod")])
    assert code != 0 and "require-ro-rootfs" in output, output


def test_the_simulation_sees_the_missing_criticality_label_of_the_deployment():
    """X3: `require-criticality-label` valida el Deployment, que toma sus etiquetas de `Gateway.spec.infrastructure.labels`."""
    docs = copy.deepcopy(gc.load_env("prod"))
    gc.find(docs, "Gateway", "api-gateway")["spec"].pop("infrastructure")
    code, output = apply_policies([data_plane_deployment(docs, "prod")])
    assert code != 0 and "require-criticality-label" in output, output


def test_the_replicas_rule_exempts_only_the_deployments_of_the_gateway():
    """Y2: sin la etiqueta del owning gateway, un Deployment de una replica sigue rechazado."""
    docs = gc.load_env("prod")
    deployment = data_plane_deployment(docs, "prod")
    deployment["metadata"]["labels"].pop(OWNING_GATEWAY)
    code, output = apply_policies([deployment])
    assert code != 0 and "require-spread-and-pdb" in output, output


def test_the_spread_rule_still_applies_to_the_data_plane():
    docs = gc.load_env("prod")
    deployment = data_plane_deployment(docs, "prod")
    deployment["spec"]["template"]["spec"].pop("topologySpreadConstraints")
    code, output = apply_policies([deployment])
    assert code != 0 and "require-spread-gateway" in output, output


def test_the_simulation_sees_a_registry_that_is_not_allowed():
    docs = copy.deepcopy(gc.load_env("prod"))
    gc.find(docs, "EnvoyProxy", "api-gateway")["spec"]["provider"]["kubernetes"]["envoyDeployment"]["container"]["image"] = "docker.io/envoyproxy/envoy@sha256:" + "0" * 64
    code, output = apply_policies([data_plane_deployment(docs, "prod")])
    assert code != 0 and "restrict-registries" in output, output


def test_the_simulation_sees_a_service_without_the_gateway_label():
    docs = copy.deepcopy(gc.load_env("prod"))
    gc.find(docs, "EnvoyProxy", "api-gateway")["spec"]["provider"]["kubernetes"]["envoyService"]["labels"] = {"app.kubernetes.io/name": "envoy"}
    code, output = apply_policies([service(docs)])
    assert code != 0 and "restrict-loadbalancer" in output, output
