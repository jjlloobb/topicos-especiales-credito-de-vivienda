"""El perfil liviano de kind cabe en una maquina de 14 GiB, y conserva lo que los simulacros necesitan."""

from pathlib import Path

import integration
import yaml

PLATFORM = Path(__file__).resolve().parents[1]
#: Memoria pedida por todos los pods de kind, proxies incluidos. Es lo que el planificador reserva, no el uso real.
BUDGET_GIB = 5.0
PROXY_GIB = 20 / 1024
MESHED = {
    "vectra-edge", "vectra-app", "vectra-serving", "vectra-staging", "vectra-data", "vectra-identity", "vectra-mock",
    "vectra-observability", "vectra-restore-drill",
}  # fmt: skip
UNITS = {"Ki": 1 / 1024**2, "Mi": 1 / 1024, "Gi": 1}


def gib(value: object) -> float:
    text = str(value)
    for suffix, factor in UNITS.items():
        if text.endswith(suffix):
            return float(text.removesuffix(suffix)) * factor
    return float(text) / 1024**3 if text.isdigit() else 0.0


def pod_memory(spec: dict) -> float:
    return sum(gib(c.get("resources", {}).get("requests", {}).get("memory", 0)) for c in spec.get("containers", []))


def rendered() -> list[dict]:
    return [d for _, group in integration.render_env("kind") for d in group]


def hpa_minimums(documents: list[dict]) -> dict[tuple[str, str, str], int]:
    """(kind, name, namespace) del workload -> `minReplicas` de su HPA. Con HPA, el numero de pods no es `spec.replicas`."""
    return {
        (d["spec"]["scaleTargetRef"]["kind"], d["spec"]["scaleTargetRef"]["name"], d["metadata"].get("namespace", "")): d["spec"].get("minReplicas", 1)
        for d in documents
        if d["kind"] == "HorizontalPodAutoscaler"
    }


def replicas_of(document: dict, minimums: dict[tuple[str, str, str], int]) -> int:
    key = (document["kind"], document["metadata"]["name"], document["metadata"].get("namespace", ""))
    return max(document["spec"].get("replicas", 1), minimums.get(key, 1))


def envoy_proxy_gib(document: dict) -> float:
    """Los pods que el controlador crea para un EnvoyProxy: contenedor, `shutdown-manager` del parche y el proxy de Linkerd."""
    kubernetes = document["spec"]["provider"]["kubernetes"]
    deployment = kubernetes["envoyDeployment"]
    replicas = max(deployment.get("replicas", 1), kubernetes.get("envoyHpa", {}).get("minReplicas", 1))
    containers = [deployment["container"]]
    containers += deployment.get("patch", {}).get("value", {}).get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    memory = sum(gib(c.get("resources", {}).get("requests", {}).get("memory", 0)) for c in containers)
    proxy = PROXY_GIB if document["metadata"].get("namespace", "") in MESHED else 0.0
    return replicas * (memory + proxy)


def envoy_gateway_gib(values: dict) -> float:
    """El controlador y `envoy-ratelimit` (namespace `envoy-gateway-system`, sin malla) salen de los values del chart OCI `envoy-gateway`."""
    controller = values["deployment"]["replicas"] * gib(values["deployment"]["envoyGateway"]["resources"]["requests"]["memory"])
    limiter = values["config"]["envoyGateway"]["provider"]["kubernetes"]["rateLimitDeployment"]
    return controller + limiter["replicas"] * gib(limiter["container"]["resources"]["requests"]["memory"])


def requested_gib(documents: list[dict] | None = None, gateway_values: dict | None = None) -> float:
    documents = rendered() if documents is None else documents
    gateway_values = yaml.safe_load((PLATFORM / "operators/envoy-gateway.yaml").read_text(encoding="utf-8")) if gateway_values is None else gateway_values
    minimums = hpa_minimums(documents)
    total = envoy_gateway_gib(gateway_values)
    for document in documents:
        namespace = document["metadata"].get("namespace", "")
        proxy = PROXY_GIB if namespace in MESHED else 0.0
        kind = document["kind"]
        if kind in {"Deployment", "StatefulSet"}:
            total += replicas_of(document, minimums) * (pod_memory(document["spec"]["template"]["spec"]) + proxy)
        elif kind == "DaemonSet":
            total += 2 * (pod_memory(document["spec"]["template"]["spec"]) + proxy)  # dos nodos de trabajo
        elif kind == "Cluster":
            memory = gib(document["spec"]["resources"]["requests"]["memory"])
            total += document["spec"]["instances"] * (memory + proxy)
        elif kind in {"Prometheus", "Alertmanager"}:
            memory = gib(document["spec"]["resources"]["requests"]["memory"])
            total += document["spec"].get("replicas", 1) * (memory + proxy)
        elif kind == "EnvoyProxy":
            total += envoy_proxy_gib(document)
    return total


def test_the_profile_requests_fit_the_budget():
    assert requested_gib() <= BUDGET_GIB, requested_gib()


def test_kind_has_no_synchronous_replica_but_production_does():
    clusters = {e: [d for d in integration.render_env(e) for d in d[1] if d["kind"] == "Cluster"] for e in ("kind", "prod")}
    assert all(c["spec"]["instances"] == 1 and "minSyncReplicas" not in c["spec"] for c in clusters["kind"])
    assert all(c["spec"]["instances"] == 3 and c["spec"]["minSyncReplicas"] == 1 for c in clusters["prod"])


def test_minio_keeps_several_drives_for_object_lock():
    values = yaml.safe_load((PLATFORM / "data/minio/values-kind.yaml").read_text(encoding="utf-8"))
    assert values["replicas"] == 1 and values["drivesPerNode"] >= 4


def test_linkerd_loses_ha_only_in_kind():
    assert yaml.safe_load((PLATFORM / "mesh/linkerd-kind.yaml").read_text(encoding="utf-8"))["controllerReplicas"] == 1
    assert yaml.safe_load((PLATFORM / "mesh/linkerd-values.yaml").read_text(encoding="utf-8"))["controllerReplicas"] == 3


def _statefulset(replicas: int | None = None) -> dict:
    spec: dict = {"template": {"spec": {"containers": [{"resources": {"requests": {"memory": "512Mi"}}}]}}}
    if replicas is not None:
        spec["replicas"] = replicas
    return {"kind": "StatefulSet", "metadata": {"name": "k", "namespace": "vectra-identity"}, "spec": spec}


def _hpa(minimum: int) -> dict:
    target = {"kind": "StatefulSet", "name": "k"}
    return {"kind": "HorizontalPodAutoscaler", "metadata": {"name": "k", "namespace": "vectra-identity"}, "spec": {"scaleTargetRef": target, "minReplicas": minimum}}


GATEWAY_VALUES = {
    "deployment": {"replicas": 2, "envoyGateway": {"resources": {"requests": {"memory": "128Mi"}}}},
    "config": {"envoyGateway": {"provider": {"kubernetes": {"rateLimitDeployment": {"replicas": 2, "container": {"resources": {"requests": {"memory": "64Mi"}}}}}}}},
}


def test_a_workload_with_an_hpa_counts_its_minimum_replicas():
    """Keycloak no declara `replicas` y su HPA pide 2: corren 2 pods, no 1."""
    one = requested_gib([_statefulset()], {**GATEWAY_VALUES})
    two = requested_gib([_statefulset(), _hpa(2)], {**GATEWAY_VALUES})
    assert two - one == 0.5 + PROXY_GIB
    assert requested_gib([_statefulset(3), _hpa(2)], GATEWAY_VALUES) - one == 2 * (0.5 + PROXY_GIB)  # max(replicas, minReplicas)


def test_the_envoy_data_plane_comes_from_the_envoy_proxy():
    proxy = {
        "kind": "EnvoyProxy",
        "metadata": {"name": "api-gateway", "namespace": "vectra-edge"},
        "spec": {"provider": {"kubernetes": {
            "envoyDeployment": {"replicas": 2, "container": {"resources": {"requests": {"memory": "256Mi"}}},
                                "patch": {"value": {"spec": {"template": {"spec": {"containers": [{"name": "shutdown-manager", "resources": {"requests": {"memory": "32Mi"}}}]}}}}}},
            "envoyHpa": {"minReplicas": 3},
        }}},
    }
    base = requested_gib([], GATEWAY_VALUES)
    assert requested_gib([proxy], GATEWAY_VALUES) - base == 3 * (0.25 + 32 / 1024 + PROXY_GIB)  # el mayor de replicas y el minimo del HPA, con el proxy de la malla


def test_the_envoy_gateway_controller_and_ratelimit_come_from_its_values():
    assert requested_gib([], GATEWAY_VALUES) == 2 * 0.125 + 2 * 0.0625  # sin proxy: envoy-gateway-system no esta en la malla


def test_the_real_count_includes_what_the_old_count_left_out():
    """Los tres huecos de C-02: Keycloak a 2 pods, el data plane y el controlador con `envoy-ratelimit`."""
    documents = rendered()
    kinds = {d["kind"] for d in documents}
    assert {"EnvoyProxy", "HorizontalPodAutoscaler"} <= kinds
    assert requested_gib() > requested_gib([d for d in documents if d["kind"] not in {"EnvoyProxy", "HorizontalPodAutoscaler"}], GATEWAY_VALUES)
