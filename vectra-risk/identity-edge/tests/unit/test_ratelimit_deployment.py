"""`envoy-ratelimit` (U02-T11, Paso 9; CA-2): el Deployment, el HPA y el PDB que Envoy Gateway v1.9.3 crearia, y las reglas de conftest.

El controlador crea el Deployment en tiempo de ejecucion, asi que no aparece en el render del chart. Esta prueba lo arma como lo harian
`resource_provider.go` y `resource.go` de v1.9.3 (`internal/infrastructure/kubernetes/ratelimit`), con su env de base,
`ExpectedContainerEnv`, los volumenes y los puertos, a partir de los values del controlador (`platform/operators/envoy-gateway.yaml` y,
en kind, `envoy-gateway-kind.yaml`), y comprueba sobre eso lo que el diseno fija (INF-U2-03, 06; R1, R2 y R5). Fuentes del modelo:
- `rateLimitLabels()`: etiquetas del template y del selector (`resource.GetSelector`), del PDB y del reparto;
- `Deployment()`: `replicas` sin fijar con HPA (el apiserver lo deja en 1), el patch `StrategicMerge` encima, etiquetas del Deployment
  solo las de `rateLimitLabels()`, las del pod con `pod.labels` encima;
- `expectedRateLimitContainerEnv()`: env de base, `REDIS_SOCKET_TYPE=tcp` y `REDIS_URL`, y `container.env` que reemplaza o agrega por nombre.
"""

import copy
import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import valkey_design as design
import yaml

ROOT = Path(__file__).resolve().parents[3]
EDGE = ROOT / "identity-edge"
RATELIMIT = EDGE / "ratelimit"
POLICY = RATELIMIT / "policy"
EXTERNAL_SECRET = RATELIMIT / "external-secret.yaml"
HELM = ROOT / "platform" / ".tools" / "bin" / "helm"
CONFTEST = ROOT / "platform" / ".tools" / "bin" / "conftest"
KYVERNO = ROOT / "platform" / ".tools" / "bin" / "kyverno"
CHART = ROOT / "platform" / ".charts" / "envoy-gateway" / "gateway-helm"
VALUES = ROOT / "platform" / "operators" / "envoy-gateway.yaml"
KIND_VALUES = ROOT / "platform" / "operators" / "envoy-gateway-kind.yaml"
KYVERNO_POLICIES = ROOT / "platform" / "policies" / "kyverno"
MAKEFILE = (EDGE / "Makefile").read_text(encoding="utf-8")
ENVS = ("kind", "staging", "prod")
NAMESPACE = "envoy-gateway-system"
SECRET = "envoy-ratelimit-valkey"  # noqa: S105 - nombre del Secret, no una credencial
OK = re.compile(r"pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0")

Docs = list[dict[str, Any]]

# Constantes de `resource.go` de v1.9.3. Los puertos no se configuran; el diseno (INF-U2-03) los repite y se compara con estas.
INFRA_NAME = "envoy-ratelimit"
INFRA_GRPC_PORT = 8081
READINESS_PORT = 8080
PROMETHEUS_PORT = 19001
XDS_PORT = 18001


# --- el controlador: values -> EnvoyGateway ---------------------------------------------------------------------


def render(env: str, *extra: str) -> Docs:
    files = [VALUES] + ([KIND_VALUES] if env == "kind" else [])
    args = [str(HELM), "template", "envoy-gateway", str(CHART), "-n", NAMESPACE, "--skip-crds", *(a for f in files for a in ("-f", str(f))), *extra]
    run = subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603 - helm fijo de platform/.tools
    assert run.returncode == 0, run.stderr
    return [d for d in yaml.safe_load_all(run.stdout) if d]


def config_map(docs: Docs) -> dict[str, Any]:
    (found,) = [d for d in docs if d["kind"] == "ConfigMap" and d["metadata"]["name"] == "envoy-gateway-config"]
    return found


def controller_config(docs: Docs) -> dict[str, Any]:
    return yaml.safe_load(config_map(docs)["data"]["envoy-gateway.yaml"])


def with_config(docs: Docs, change: Callable[[dict[str, Any]], None]) -> Docs:
    """Copia de `docs` con `change` aplicado al `EnvoyGateway` del ConfigMap del controlador."""
    out = copy.deepcopy(docs)
    cfg = controller_config(out)
    change(cfg)
    config_map(out)["data"]["envoy-gateway.yaml"] = yaml.safe_dump(cfg, sort_keys=False)
    return out


@pytest.fixture(scope="module", params=ENVS)
def case(request: pytest.FixtureRequest) -> tuple[str, Docs]:
    return request.param, render(request.param)


# --- el modelo de v1.9.3 -----------------------------------------------------------------------------------


def ratelimit_labels() -> dict[str, str]:
    """`rateLimitLabels()`."""
    return {"app.kubernetes.io/name": INFRA_NAME, "app.kubernetes.io/component": "ratelimit", "app.kubernetes.io/managed-by": "envoy-gateway"}


def selects(selector: dict[str, str], labels: dict[str, str]) -> bool:
    return bool(selector) and all(labels.get(k) == v for k, v in selector.items())


def base_env(rate_limit: dict[str, Any]) -> list[dict[str, Any]]:
    """`expectedRateLimitContainerEnv()` antes de `ExpectedContainerEnv`: base, Redis, Prometheus y tracing."""
    plain = {
        "RUNTIME_ROOT": "/data", "RUNTIME_SUBDIRECTORY": "ratelimit", "RUNTIME_IGNOREDOTFILES": "true", "RUNTIME_WATCH_ROOT": "false",
        "LOG_LEVEL": "info", "USE_STATSD": "false", "CONFIG_TYPE": "GRPC_XDS_SOTW",
        "CONFIG_GRPC_XDS_SERVER_URL": f"envoy-gateway:{XDS_PORT}", "CONFIG_GRPC_XDS_NODE_ID": INFRA_NAME,
        "GRPC_SERVER_USE_TLS": "true", "GRPC_SERVER_TLS_CERT": "/certs/tls.crt", "GRPC_SERVER_TLS_KEY": "/certs/tls.key",
        "GRPC_SERVER_TLS_CA_CERT": "/certs/ca.crt", "CONFIG_GRPC_XDS_SERVER_USE_TLS": "true",
        "CONFIG_GRPC_XDS_CLIENT_TLS_CERT": "/certs/tls.crt", "CONFIG_GRPC_XDS_CLIENT_TLS_KEY": "/certs/tls.key",
        "CONFIG_GRPC_XDS_SERVER_TLS_CACERT": "/certs/ca.crt", "FORCE_START_WITHOUT_INITIAL_CONFIG": "true",
    }  # fmt: skip
    env: list[dict[str, Any]] = [{"name": k, "value": v} for k, v in plain.items()]
    redis = rate_limit.get("backend", {}).get("redis")
    if redis:
        env += [{"name": "REDIS_SOCKET_TYPE", "value": "tcp"}, {"name": "REDIS_URL", "value": redis["url"]}]
    metrics = rate_limit.get("telemetry", {}).get("metrics", {}).get("prometheus", {})
    if not metrics.get("disable"):
        env += [{"name": "USE_PROMETHEUS", "value": "true"}, {"name": "PROMETHEUS_ADDR", "value": f":{PROMETHEUS_PORT}"}]
        env += [{"name": "PROMETHEUS_MAPPER_YAML", "value": "/etc/statsd-exporter/conf.yaml"}]
    tracing = rate_limit.get("telemetry", {}).get("tracing", {})
    if tracing.get("provider", {}).get("url"):
        url = tracing["provider"]["url"]
        rate = tracing.get("samplingRate")
        env += [
            {"name": "TRACING_ENABLED", "value": "true"},
            {"name": "TRACING_SERVICE_NAME", "value": INFRA_NAME},
            {"name": "TRACING_SERVICE_NAMESPACE", "value": NAMESPACE},
            {"name": "TRACING_SERVICE_INSTANCE_ID", "valueFrom": {"fieldRef": {"apiVersion": "v1", "fieldPath": "metadata.name"}}},
            {"name": "TRACING_SAMPLING_RATE", "value": f"{(1.0 if rate is None else rate / 100.0):.1f}"},
            {"name": "OTEL_EXPORTER_OTLP_ENDPOINT", "value": url if url.startswith("http://") else f"http://{url}"},
        ]  # fmt: skip
    return env


def expected_container_env(container: dict[str, Any], env: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`ExpectedContainerEnv`: lo de `container.env` reemplaza por nombre o se agrega al final."""
    out = copy.deepcopy(env)
    for var in container.get("env", []):
        for index, existing in enumerate(out):
            if existing["name"] == var["name"]:
                out[index] = copy.deepcopy(var)
                break
        else:
            out.append(copy.deepcopy(var))
    return out


def merge_patch(target: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """StrategicMerge: los mapas se mezclan y las listas de objetos con `name` (los `containers`) se mezclan por nombre."""
    out = copy.deepcopy(target)
    for key, value in patch.items():
        current = out.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            out[key] = merge_patch(current, value)
        elif isinstance(value, list) and isinstance(current, list) and all(isinstance(v, dict) and "name" in v for v in value + current):
            merged = {item["name"]: item for item in current}
            for item in value:
                merged[item["name"]] = merge_patch(merged[item["name"]], item) if item["name"] in merged else copy.deepcopy(item)
            out[key] = list(merged.values())
        else:
            out[key] = copy.deepcopy(value)
    return out


def ratelimit_deployment(cfg: dict[str, Any]) -> dict[str, Any]:
    """`Deployment()`: lo que el controlador crea en su namespace a partir de `rateLimit` y `provider.kubernetes.rateLimitDeployment`."""
    kube = cfg["provider"]["kubernetes"]
    spec = kube["rateLimitDeployment"]
    container, pod = spec["container"], spec.get("pod", {})
    ports = [{"name": "grpc", "containerPort": INFRA_GRPC_PORT, "protocol": "TCP"}, {"name": "metrics", "containerPort": PROMETHEUS_PORT, "protocol": "TCP"}]
    probe = {"httpGet": {"path": "/healthcheck", "port": READINESS_PORT, "scheme": "HTTP"}}
    pod_labels = {**ratelimit_labels(), **pod.get("labels", {}), **ratelimit_labels()}
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": INFRA_NAME, "namespace": NAMESPACE, "labels": ratelimit_labels()},
        "spec": {
            "replicas": 1 if "rateLimitHpa" in kube else spec.get("replicas", 1),  # con HPA el controlador no lo fija y el apiserver lo deja en 1
            "selector": {"matchLabels": ratelimit_labels()},
            "template": {
                "metadata": {"labels": pod_labels, "annotations": {"prometheus.io/path": "/metrics", "prometheus.io/port": str(PROMETHEUS_PORT), "prometheus.io/scrape": "true"}},
                "spec": {
                    "containers": [
                        {
                            "name": INFRA_NAME,
                            "image": container["image"],
                            "command": ["/bin/ratelimit"],
                            "env": expected_container_env(container, base_env(cfg["rateLimit"])),
                            "ports": ports,
                            "resources": container["resources"],
                            "securityContext": container["securityContext"],
                            "volumeMounts": [{"name": "certs", "mountPath": "/certs", "readOnly": True}, {"name": "statsd-exporter-config", "mountPath": "/etc/statsd-exporter", "readOnly": True}],
                            "startupProbe": probe,
                            "readinessProbe": probe,
                            "livenessProbe": probe,
                        }
                    ],
                    "serviceAccountName": INFRA_NAME,
                    "automountServiceAccountToken": False,
                    "securityContext": pod.get("securityContext"),
                    "volumes": [
                        {"name": "certs", "secret": {"secretName": "envoy-rate-limit", "defaultMode": 420}},
                        {"name": "statsd-exporter-config", "configMap": {"name": "statsd-exporter-config", "optional": True, "defaultMode": 420}},
                    ],
                    "topologySpreadConstraints": pod.get("topologySpreadConstraints"),
                    "priorityClassName": pod.get("priorityClassName", ""),
                },
            },
        },
    }
    if spec.get("patch"):
        assert spec["patch"]["type"] == "StrategicMerge", "el modelo solo aplica StrategicMerge"
        deployment = merge_patch(deployment, spec["patch"]["value"])
    return deployment


def ratelimit_hpa(cfg: dict[str, Any]) -> dict[str, Any]:
    hpa = cfg["provider"]["kubernetes"]["rateLimitHpa"]
    return {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": INFRA_NAME, "namespace": NAMESPACE, "labels": ratelimit_labels()},
        "spec": {"scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": INFRA_NAME}, "minReplicas": hpa["minReplicas"], "maxReplicas": hpa["maxReplicas"], "metrics": hpa["metrics"]},
    }


def ratelimit_pdb(cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "policy/v1",
        "kind": "PodDisruptionBudget",
        "metadata": {"name": INFRA_NAME, "namespace": NAMESPACE},
        "spec": {"minAvailable": cfg["provider"]["kubernetes"]["rateLimitPDB"]["minAvailable"], "selector": {"matchLabels": ratelimit_labels()}},
    }


def main_container(deployment: dict[str, Any]) -> dict[str, Any]:
    (found,) = deployment["spec"]["template"]["spec"]["containers"]
    return found


def env_by_name(container: dict[str, Any]) -> dict[str, dict[str, Any]]:
    names = [e["name"] for e in container["env"]]
    assert len(names) == len(set(names)), "variables repetidas"
    return {e["name"]: e for e in container["env"]}


# --- lo que el diseno fija sobre el modelo ----------------------------------------------------------------


def problems(docs: Docs, env: str, secret: dict[str, Any] | None = None) -> list[str]:
    """Diferencias entre el modelo del Deployment y el diseno. Vacio si coinciden."""
    found: list[str] = []
    cfg = controller_config(docs)
    deployment, hpa, pdb = ratelimit_deployment(cfg), ratelimit_hpa(cfg), ratelimit_pdb(cfg)
    container = main_container(deployment)
    pod = deployment["spec"]["template"]["spec"]
    template = deployment["spec"]["template"]["metadata"]["labels"]
    ports = design.ratelimit_ports()
    if {p["name"]: p["containerPort"] for p in container["ports"]} != {"grpc": ports["grpc"], "metrics": ports["metrics"]}:
        found.append("puertos")
    if {p["httpGet"]["port"] for k, p in container.items() if k.endswith("Probe")} != {ports["health"]}:
        found.append("health")
    if (INFRA_GRPC_PORT, READINESS_PORT, PROMETHEUS_PORT, XDS_PORT) != (ports["grpc"], ports["health"], ports["metrics"], ports["xds"]):
        found.append("constantes del modelo")
    envs = env_by_name(container)
    want_auth = {"secretKeyRef": {"name": SECRET, "key": ""}}
    if envs.get("REDIS_TYPE", {}).get("value") != "SENTINEL":
        found.append("REDIS_TYPE")
    if envs.get("REDIS_SOCKET_TYPE", {}).get("value") != "tcp":
        found.append("REDIS_SOCKET_TYPE")
    if envs.get("REDIS_URL", {}).get("value") != design.ratelimit_url():
        found.append("REDIS_URL")
    for name in ("REDIS_AUTH", "REDIS_SENTINEL_AUTH"):
        want = {"secretKeyRef": {**want_auth["secretKeyRef"], "key": name}}
        if envs.get(name, {}).get("valueFrom") != want or "value" in envs.get(name, {}):
            found.append(name)
    trace_url, trace_rate = design.ratelimit_tracing()
    if envs.get("OTEL_EXPORTER_OTLP_ENDPOINT", {}).get("value") != f"http://{trace_url}" or envs.get("TRACING_SAMPLING_RATE", {}).get("value") != f"{trace_rate / 100:.1f}":
        found.append("tracing")
    if envs.get("TRACING_EXPORTER_PROTOCOL", {}) != {"name": "TRACING_EXPORTER_PROTOCOL", "value": design.ratelimit_tracing_protocol()}:
        found.append("protocolo del tracing")
    if envs.get("PROMETHEUS_ADDR", {}).get("value") != f":{ports['metrics']}":
        found.append("metricas")
    image = f"{design.ratelimit_registries()[env]}@{design.ratelimit_digest()}"
    if container["image"] != image:
        found.append("imagen")
    if container["resources"] != design.ratelimit_resources():
        found.append("recursos")
    if pod["priorityClassName"] != "vectra-high":
        found.append("prioridad")
    if template.get("vectra.io/criticality") != "high" or deployment["metadata"]["labels"].get("vectra.io/criticality") != "high":
        found.append("criticidad")
    if not selects(deployment["spec"]["selector"]["matchLabels"], template):
        found.append("selector del Deployment")
    if not selects(pdb["spec"]["selector"]["matchLabels"], template):
        found.append("selector del PDB")
    constraints = pod["topologySpreadConstraints"] or []
    if not constraints or not all(c["topologyKey"] == "topology.kubernetes.io/zone" and selects(c["labelSelector"]["matchLabels"], template) for c in constraints):
        found.append("reparto")
    low, high, cpu = design.ratelimit_hpa()
    if (hpa["spec"]["minReplicas"], hpa["spec"]["maxReplicas"]) != (low, high) or hpa["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"] != cpu:
        found.append("HPA")
    if hpa["spec"]["scaleTargetRef"]["name"] != deployment["metadata"]["name"]:
        found.append("destino del HPA")
    if pdb["spec"]["minAvailable"] != design.ratelimit_pdb():
        found.append("PDB")
    if cfg["provider"]["kubernetes"]["rateLimitDeployment"].get("replicas") != design.ratelimit_replicas():
        found.append("replicas")
    if cfg["rateLimit"].get("failClosed", False) != design.ratelimit_failclosed():
        found.append("failClosed")
    return found


def test_the_model_matches_the_design(case: tuple[str, Docs]) -> None:
    env, docs = case
    assert problems(docs, env) == []


def test_the_ports_are_the_ones_v1_9_3_fixes() -> None:
    assert design.ratelimit_ports() == {"grpc": 8081, "health": 8080, "metrics": 19001, "xds": 18001}
    cfg = controller_config(render("prod"))
    container = main_container(ratelimit_deployment(cfg))
    assert [p["containerPort"] for p in container["ports"]] == [8081, 19001]
    assert env_by_name(container)["PROMETHEUS_ADDR"]["value"] == ":19001"
    assert container["readinessProbe"]["httpGet"]["port"] == 8080


def test_the_final_env_has_sentinel_and_both_credentials_from_the_secret(case: tuple[str, Docs]) -> None:
    _, docs = case
    envs = env_by_name(main_container(ratelimit_deployment(controller_config(docs))))
    assert envs["REDIS_TYPE"] == {"name": "REDIS_TYPE", "value": "SENTINEL"}
    assert envs["REDIS_SOCKET_TYPE"] == {"name": "REDIS_SOCKET_TYPE", "value": "tcp"}
    assert envs["REDIS_URL"]["value"] == design.ratelimit_url()
    assert envs["REDIS_URL"]["value"].split(",")[0] == design.master_name()
    for name in ("REDIS_AUTH", "REDIS_SENTINEL_AUTH"):
        assert envs[name] == {"name": name, "valueFrom": {"secretKeyRef": {"name": SECRET, "key": name}}}


def test_the_secret_keys_are_the_ones_the_external_secret_materializes() -> None:
    (doc,) = [d for d in yaml.safe_load_all(EXTERNAL_SECRET.read_text(encoding="utf-8")) if d]
    assert doc["metadata"] == {"name": SECRET, "namespace": NAMESPACE, "labels": doc["metadata"]["labels"]}
    assert doc["spec"]["target"]["name"] == SECRET
    assert set(doc["spec"]["target"]["template"]["data"]) == {"REDIS_AUTH", "REDIS_SENTINEL_AUTH"}
    assert doc["spec"]["target"]["template"]["data"] == {"REDIS_AUTH": "ratelimit:{{ .ratelimit }}", "REDIS_SENTINEL_AUTH": "ratelimit:{{ .sentinelRatelimit }}"}
    assert [(d["remoteRef"]["key"], d["remoteRef"]["property"]) for d in doc["spec"]["data"]] == [("edge/valkey", "ratelimit"), ("edge/valkey", "sentinel-ratelimit")]
    assert {p for p in design.vault_properties()} >= {d["remoteRef"]["property"] for d in doc["spec"]["data"]}
    assert design.vault_key() == "edge/valkey"


def test_the_design_values_are_read_from_the_documents() -> None:
    assert design.ratelimit_url() == (
        "ratelimit,sentinel-a-0.sentinel-a.vectra-edge.svc.cluster.local:26379,"
        "sentinel-b-0.sentinel-b.vectra-edge.svc.cluster.local:26379,sentinel-b-1.sentinel-b.vectra-edge.svc.cluster.local:26379"
    )
    assert (design.ratelimit_replicas(), design.ratelimit_hpa(), design.ratelimit_pdb(), design.ratelimit_failclosed()) == (2, (2, 4, 70), 1, False)
    assert design.ratelimit_tracing() == ("otel-collector.vectra-observability.svc:4317", 100)
    assert design.ratelimit_tracing_protocol() == "grpc"
    assert design.ratelimit_registries()["kind"] == "kind-registry:5000/vectra/ratelimit"


@pytest.mark.parametrize(
    ("name", "change"),
    [
        ("REDIS_TYPE", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["container"]["env"].pop(0)),
        ("REDIS_URL", lambda c: c["rateLimit"]["backend"]["redis"].update(url="ratelimit,sentinel-a-0.sentinel-a.vectra-edge.svc.cluster.local:26379")),
        ("REDIS_AUTH", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["container"]["env"].__setitem__(1, {"name": "REDIS_AUTH", "value": "ratelimit:x"})),
        ("REDIS_SENTINEL_AUTH", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["container"]["env"].pop(2)),
        ("tracing", lambda c: c["rateLimit"]["telemetry"]["tracing"].update(samplingRate=10)),
        ("protocolo del tracing", lambda c: _container(c).update(env=[e for e in _container(c)["env"] if e["name"] != "TRACING_EXPORTER_PROTOCOL"])),
        ("protocolo del tracing", lambda c: _container(c).update(env=[{"name": e["name"], "value": "http"} if e["name"] == "TRACING_EXPORTER_PROTOCOL" else e for e in _container(c)["env"]])),
        ("metricas", lambda c: c["rateLimit"].setdefault("telemetry", {}).setdefault("metrics", {}).update(prometheus={"disable": True})),
        ("imagen", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["container"].update(image="docker.io/envoyproxy/ratelimit:5ae0682e")),
        ("recursos", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["container"]["resources"]["limits"].update(cpu="1")),
        ("prioridad", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["pod"].update(priorityClassName="vectra-low")),
        ("criticidad", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"].pop("patch")),
        ("criticidad", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["pod"]["labels"].clear()),
        ("reparto", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["pod"].pop("topologySpreadConstraints")),
        ("reparto", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["pod"]["topologySpreadConstraints"][0]["labelSelector"]["matchLabels"].update({"app.kubernetes.io/name": "envoy"})),
        ("reparto", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["pod"]["topologySpreadConstraints"][0].update(topologyKey="kubernetes.io/hostname")),
        ("HPA", lambda c: c["provider"]["kubernetes"]["rateLimitHpa"].update(maxReplicas=6)),
        ("PDB", lambda c: c["provider"]["kubernetes"]["rateLimitPDB"].update(minAvailable=2)),
        ("replicas", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"].update(replicas=3)),
        ("failClosed", lambda c: c["rateLimit"].update(failClosed=True)),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_each_model_check_fails_on_an_altered_config(name: str, change: Callable[[dict[str, Any]], None]) -> None:
    docs = render("prod")
    assert name in problems(with_config(docs, change), "prod")


def test_a_pod_label_cannot_override_the_selector_labels() -> None:
    """F-12 de U02-T10: `Deployment()` copia `pod.labels` y vuelve a poner `rateLimitLabels()`; el selector sigue seleccionando el template."""
    docs = with_config(render("prod"), lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["pod"]["labels"].update({"app.kubernetes.io/name": "otro"}))
    deployment = ratelimit_deployment(controller_config(docs))
    assert selects(deployment["spec"]["selector"]["matchLabels"], deployment["spec"]["template"]["metadata"]["labels"])


def test_the_selector_check_sees_a_selector_that_selects_nothing() -> None:
    assert not selects({}, ratelimit_labels())
    assert not selects({"app.kubernetes.io/name": "envoy"}, ratelimit_labels())


# --- Kyverno de U1 sobre el modelo ---------------------------------------------------------------------------


def static_policies() -> list[str]:
    found = re.search(r"^STATIC_POLICIES := (.+)$", MAKEFILE, re.MULTILINE)
    assert found, "identity-edge/Makefile sin STATIC_POLICIES"
    return found.group(1).split()


def widen(node: Any) -> None:
    """Agrega `envoy-gateway-system` a cada lista `namespaces` que ya incluye `vectra-edge`: Kyverno de U1 no alcanza ese namespace."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "namespaces" and isinstance(value, list) and "vectra-edge" in value:
                value.append(NAMESPACE)
            else:
                widen(value)
    elif isinstance(node, list):
        for item in node:
            widen(item)


def kyverno(resources: list[dict[str, Any]], widened: bool = True) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        policies = Path(tmp) / "policies"
        policies.mkdir()
        for name in static_policies():
            policy = yaml.safe_load((KYVERNO_POLICIES / name).read_text(encoding="utf-8"))
            if widened:
                widen(policy)
            (policies / name).write_text(yaml.safe_dump(policy), encoding="utf-8")
        target = Path(tmp) / "resources.yaml"
        target.write_text(yaml.safe_dump_all(resources, sort_keys=False), encoding="utf-8")
        run = subprocess.run([str(KYVERNO), "apply", str(policies), "--resource", str(target)], capture_output=True, text=True, check=False)  # noqa: S603 - herramienta fija
    output = run.stdout + run.stderr
    return run.returncode == 0 and OK.search(output) is not None, output


def test_the_deployment_passes_the_static_policies_widened_to_the_namespace(case: tuple[str, Docs]) -> None:
    _, docs = case
    deployment = ratelimit_deployment(controller_config(docs))
    ok, output = kyverno([deployment])
    assert ok, output


def test_the_policies_do_not_reach_the_namespace_without_the_widening(case: tuple[str, Docs]) -> None:
    """Sin ampliar el `match`, ninguna regla ve el Deployment: por eso R2 pone las reglas en conftest."""
    _, docs = case
    ok, output = kyverno([ratelimit_deployment(controller_config(docs))], widened=False)
    assert not ok, output


def _container(c: dict[str, Any]) -> dict[str, Any]:
    return c["provider"]["kubernetes"]["rateLimitDeployment"]["container"]


KYVERNO_CASES: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = [
    ("disallow-latest", "sin digest", lambda c: _container(c).update(image="registro.banco.internal/vectra/ratelimit:latest")),
    ("restrict-registries", "registro ajeno", lambda c: _container(c).update(image="docker.io/envoyproxy/ratelimit@sha256:" + "0" * 64)),
    ("require-ro-rootfs", "raiz escribible", lambda c: _container(c)["securityContext"].update(readOnlyRootFilesystem=False)),
    ("require-run-as-non-root", "pod como root", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["pod"]["securityContext"].update(runAsNonRoot=False)),
    ("disallow-privileged", "privilegiado", lambda c: _container(c)["securityContext"].update(privileged=True)),
    ("require-resources", "sin limits", lambda c: _container(c)["resources"].pop("limits")),
    ("require-priority-class", "sin prioridad", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"]["pod"].pop("priorityClassName")),
    ("require-criticality-label", "sin etiqueta", lambda c: c["provider"]["kubernetes"]["rateLimitDeployment"].pop("patch")),
]


@pytest.mark.parametrize(("rule", "label", "change"), KYVERNO_CASES, ids=[f"{r}-{c}" for r, c, _ in KYVERNO_CASES])
def test_the_simulation_sees_what_the_static_policies_reject(rule: str, label: str, change: Callable[[dict[str, Any]], None]) -> None:
    docs = with_config(render("prod"), change)
    ok, output = kyverno([ratelimit_deployment(controller_config(docs))])
    assert not ok and rule in output, f"{rule}/{label}\n{output}"


# --- reglas de conftest -------------------------------------------------------------------------------------


def conftest(renders: dict[str, Docs], with_secret: dict[str, Any] | None = None) -> tuple[int, str]:
    """Las dos pasadas de `make policy-ratelimit` sobre `renders` (`bank` y `kind`), mas el ExternalSecret."""
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for env, docs in renders.items():
            (Path(tmp) / env).mkdir()
            path = Path(tmp) / env / "render.yaml"
            path.write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")
            files.append(str(path))
        external = Path(tmp) / "external-secret.yaml"
        external.write_text(yaml.safe_dump(with_secret) if with_secret else EXTERNAL_SECRET.read_text(encoding="utf-8"), encoding="utf-8")
        first = subprocess.run([str(CONFTEST), "test", "--policy", str(POLICY), *files, str(external)], capture_output=True, text=True, check=False)  # noqa: S603
        second = subprocess.run(  # noqa: S603
            [str(CONFTEST), "test", "--combine", "--namespace", "ratelimit_set", "--policy", str(POLICY), *files],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
    return max(first.returncode, second.returncode), first.stdout + first.stderr + second.stdout + second.stderr


def policy_rules() -> set[str]:
    rules = set()
    for path in sorted(POLICY.glob("*.rego")):
        rules |= set(re.findall(r"^# regla: ([\w-]+)$", path.read_text(encoding="utf-8"), re.MULTILINE))
    return rules


def _rl(c: dict[str, Any]) -> dict[str, Any]:
    return c["provider"]["kubernetes"]["rateLimitDeployment"]


def _kube(c: dict[str, Any]) -> dict[str, Any]:
    return c["provider"]["kubernetes"]


def _drop_env(name: str) -> Callable[[dict[str, Any]], None]:
    def change(c: dict[str, Any]) -> None:
        _container(c)["env"] = [e for e in _container(c)["env"] if e["name"] != name]

    return change


def _set_env(name: str, entry: dict[str, Any]) -> Callable[[dict[str, Any]], None]:
    def change(c: dict[str, Any]) -> None:
        _container(c)["env"] = [entry if e["name"] == name else e for e in _container(c)["env"]]

    return change


def _secret_change(change: Callable[[dict[str, Any]], None]) -> Callable[[dict[str, Any]], None]:
    return change


CONFIG_MUTATIONS: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = [
    ("backend", "otro tipo", lambda c: c["rateLimit"]["backend"].update(type="Memory")),
    ("backend", "URL sin los tres Sentinel", lambda c: c["rateLimit"]["backend"]["redis"].update(url="ratelimit,sentinel-a-0.sentinel-a.vectra-edge.svc.cluster.local:26379")),
    ("backend", "otro nombre de master", lambda c: c["rateLimit"]["backend"]["redis"].update(url=c["rateLimit"]["backend"]["redis"]["url"].replace("ratelimit,", "mymaster,", 1))),
    ("backend", "failClosed", lambda c: c["rateLimit"].update(failClosed=True)),
    ("telemetry", "otro proveedor", lambda c: c["rateLimit"]["telemetry"]["tracing"]["provider"].update(type="Zipkin")),
    ("telemetry", "otro collector", lambda c: c["rateLimit"]["telemetry"]["tracing"]["provider"].update(url="otel.example:4317")),
    ("telemetry", "muestreo 10", lambda c: c["rateLimit"]["telemetry"]["tracing"].update(samplingRate=10)),
    ("telemetry", "sin tracing", lambda c: c["rateLimit"]["telemetry"].pop("tracing")),
    ("telemetry", "sin TRACING_EXPORTER_PROTOCOL", _drop_env("TRACING_EXPORTER_PROTOCOL")),
    ("telemetry", "TRACING_EXPORTER_PROTOCOL http", _set_env("TRACING_EXPORTER_PROTOCOL", {"name": "TRACING_EXPORTER_PROTOCOL", "value": "http"})),
    ("telemetry", "Prometheus deshabilitado", lambda c: c["rateLimit"]["telemetry"].setdefault("metrics", {}).update(prometheus={"disable": True})),
    ("sentinel-env", "sin REDIS_TYPE", _drop_env("REDIS_TYPE")),
    ("sentinel-env", "REDIS_TYPE cluster", _set_env("REDIS_TYPE", {"name": "REDIS_TYPE", "value": "CLUSTER"})),
    ("sentinel-env", "REDIS_AUTH en claro", _set_env("REDIS_AUTH", {"name": "REDIS_AUTH", "value": "ratelimit:secreto"})),
    ("sentinel-env", "sin REDIS_SENTINEL_AUTH", _drop_env("REDIS_SENTINEL_AUTH")),
    ("sentinel-env", "otro Secret", _set_env("REDIS_AUTH", {"name": "REDIS_AUTH", "valueFrom": {"secretKeyRef": {"name": "otro", "key": "REDIS_AUTH"}}})),
    ("sentinel-env", "otra clave", _set_env("REDIS_SENTINEL_AUTH", {"name": "REDIS_SENTINEL_AUTH", "valueFrom": {"secretKeyRef": {"name": SECRET, "key": "REDIS_AUTH"}}})),
    ("sentinel-env", "variable ajena", lambda c: _container(c)["env"].append({"name": "REDIS_URL", "value": "x"})),
    ("image", "sin digest", lambda c: _container(c).update(image="registro.banco.internal/vectra/ratelimit:5ae0682e")),
    ("image", "registro ajeno", lambda c: _container(c).update(image="docker.io/envoyproxy/ratelimit@sha256:b95206e32b1a5f824fb06062fbb85bbdfb7f5de54135e92afe8462f22c979681")),
    ("image", "otro digest", lambda c: _container(c).update(image="registro.banco.internal/vectra/ratelimit@sha256:" + "0" * 64)),
    ("replicas", "una replica", lambda c: _rl(c).update(replicas=1)),
    ("replicas", "sin HPA de 2", lambda c: _kube(c)["rateLimitHpa"].update(minReplicas=1)),
    ("replicas", "HPA hasta 8", lambda c: _kube(c)["rateLimitHpa"].update(maxReplicas=8)),
    ("replicas", "HPA al 90 %", lambda c: _kube(c)["rateLimitHpa"]["metrics"][0]["resource"]["target"].update(averageUtilization=90)),
    ("replicas", "HPA por memoria", lambda c: _kube(c)["rateLimitHpa"]["metrics"][0]["resource"].update(name="memory")),
    ("replicas", "sin HPA", lambda c: _kube(c).pop("rateLimitHpa")),
    ("replicas", "PDB en 2", lambda c: _kube(c)["rateLimitPDB"].update(minAvailable=2)),
    ("replicas", "sin PDB", lambda c: _kube(c).pop("rateLimitPDB")),
    ("resources", "CPU ampliada", lambda c: _container(c)["resources"]["limits"].update(cpu="1")),
    ("resources", "sin requests", lambda c: _container(c)["resources"].pop("requests")),
    ("hardening", "sin prioridad", lambda c: _rl(c)["pod"].pop("priorityClassName")),
    ("hardening", "sin criticidad en el pod", lambda c: _rl(c)["pod"]["labels"].clear()),
    ("hardening", "sin criticidad en el Deployment", lambda c: _rl(c)["patch"]["value"]["metadata"]["labels"].clear()),
    ("hardening", "sin patch", lambda c: _rl(c).pop("patch")),
    ("hardening", "patch de otro tipo", lambda c: _rl(c)["patch"].update(type="JSONMerge")),
    ("hardening", "contenedor como root", lambda c: _container(c)["securityContext"].update(runAsNonRoot=False)),
    ("hardening", "escalada de privilegios", lambda c: _container(c)["securityContext"].update(allowPrivilegeEscalation=True)),
    ("hardening", "privilegiado", lambda c: _container(c)["securityContext"].update(privileged=True)),
    ("hardening", "raiz escribible", lambda c: _container(c)["securityContext"].update(readOnlyRootFilesystem=False)),
    ("hardening", "capabilities", lambda c: _container(c)["securityContext"].update(capabilities={"drop": ["NET_RAW"]})),
    ("hardening", "contenedor sin seccomp", lambda c: _container(c)["securityContext"].pop("seccompProfile")),
    ("hardening", "pod como root", lambda c: _rl(c)["pod"]["securityContext"].update(runAsNonRoot=False)),
    ("hardening", "pod sin seccomp", lambda c: _rl(c)["pod"]["securityContext"].pop("seccompProfile")),
    ("hardening", "sin securityContext del contenedor", lambda c: _container(c).pop("securityContext")),
    ("spread", "sin reparto", lambda c: _rl(c)["pod"].pop("topologySpreadConstraints")),
    ("spread", "reparto por nodo", lambda c: _rl(c)["pod"]["topologySpreadConstraints"][0].update(topologyKey="kubernetes.io/hostname")),
    ("spread", "ScheduleAnyway", lambda c: _rl(c)["pod"]["topologySpreadConstraints"][0].update(whenUnsatisfiable="ScheduleAnyway")),
    ("spread", "selector de otro", lambda c: _rl(c)["pod"]["topologySpreadConstraints"][0]["labelSelector"]["matchLabels"].update({"app.kubernetes.io/name": "envoy"})),
    ("spread", "selector vacio", lambda c: _rl(c)["pod"]["topologySpreadConstraints"][0]["labelSelector"].update(matchLabels={})),
    ("spread", "dos restricciones", lambda c: _rl(c)["pod"]["topologySpreadConstraints"].append(copy.deepcopy(_rl(c)["pod"]["topologySpreadConstraints"][0]))),
    ("spread", "matchExpressions", lambda c: _rl(c)["pod"]["topologySpreadConstraints"][0]["labelSelector"].update(matchExpressions=[{"key": "x", "operator": "Exists"}])),
]


@pytest.mark.parametrize(("rule", "label", "change"), CONFIG_MUTATIONS, ids=[f"{r}-{c}" for r, c, _ in CONFIG_MUTATIONS])
def test_each_conftest_rule_fails_on_an_altered_config(rule: str, label: str, change: Callable[[dict[str, Any]], None]) -> None:
    bank, kind = render("prod"), render("kind")
    code, output = conftest({"bank": with_config(bank, change), "kind": kind})
    assert code != 0, f"{rule}/{label}: conftest no fallo"
    assert f"{rule}: " in output, f"{rule}/{label}: la salida no nombra la regla\n{output}"


def secret_doc() -> dict[str, Any]:
    return yaml.safe_load(EXTERNAL_SECRET.read_text(encoding="utf-8"))


def _template(doc: dict[str, Any]) -> None:
    doc["spec"]["target"]["template"]["data"]["REDIS_AUTH"] = "{{ .ratelimit }}"


SECRET_MUTATIONS: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = [
    ("external-secret", "otro namespace", lambda d: d["metadata"].update(namespace="vectra-edge")),
    ("external-secret", "otro almacen", lambda d: d["spec"]["secretStoreRef"].update(name="otro")),
    ("external-secret", "otro Secret destino", lambda d: d["spec"]["target"].update(name="otro")),
    ("external-secret", "plantilla sin el usuario", _template),
    ("external-secret", "otra propiedad", lambda d: d["spec"]["data"][1]["remoteRef"].update(property="sentinel")),
    ("external-secret", "otra clave de boveda", lambda d: d["spec"]["data"][0]["remoteRef"].update(key="edge/otra")),
    ("no-plain-secret", "Secret en claro", lambda d: d.update(kind="Secret", data={"REDIS_AUTH": "eA=="})),
]


@pytest.mark.parametrize(("rule", "label", "change"), SECRET_MUTATIONS, ids=[f"{r}-{c}" for r, c, _ in SECRET_MUTATIONS])
def test_each_conftest_rule_fails_on_an_altered_external_secret(rule: str, label: str, change: Callable[[dict[str, Any]], None]) -> None:
    doc = secret_doc()
    change(doc)
    code, output = conftest({"bank": render("prod"), "kind": render("kind")}, with_secret=doc)
    assert code != 0, f"{rule}/{label}: conftest no fallo"
    assert f"{rule}: " in output, f"{rule}/{label}: la salida no nombra la regla\n{output}"


SET_MUTATIONS: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
    ("kind con el registro del banco", lambda c: _container(c).update(image=f"registro.banco.internal/vectra/ratelimit@{design.ratelimit_digest()}"), "kind"),
    ("el banco con el registro de kind", lambda c: _container(c).update(image=f"kind-registry:5000/vectra/ratelimit@{design.ratelimit_digest()}"), "bank"),
]


@pytest.mark.parametrize(("label", "change", "which"), SET_MUTATIONS, ids=[m[0] for m in SET_MUTATIONS])
def test_registry_per_env_fails_when_the_registry_is_the_other_one(label: str, change: Callable[[dict[str, Any]], None], which: str) -> None:
    renders = {"bank": render("prod"), "kind": render("kind")}
    renders[which] = with_config(renders[which], change)
    code, output = conftest(renders)
    assert code != 0 and "registry-per-env: " in output, f"{label}\n{output}"


def test_registry_per_env_fails_without_one_of_the_renders() -> None:
    code, output = conftest({"bank": render("prod")})
    assert code != 0 and "registry-per-env: " in output, output


def test_every_conftest_rule_has_a_failing_case() -> None:
    covered = {r for r, _, _ in CONFIG_MUTATIONS} | {r for r, _, _ in SECRET_MUTATIONS} | {"registry-per-env"}
    assert covered == policy_rules()


def test_the_unaltered_render_passes_both_conftest_passes() -> None:
    code, output = conftest({"bank": render("prod"), "kind": render("kind")})
    assert code == 0, output


def test_make_check_includes_the_ratelimit_policy() -> None:
    check = re.search(r"^check:(.+)$", MAKEFILE, re.MULTILINE)
    assert check and "policy-ratelimit" in check.group(1).split()
