"""Comprueba que las piezas encajan entre si: charts, politicas, flujos, servicios, secretos y CRDs."""

import re
from collections import defaultdict
from pathlib import Path

import pytest
import yaml
from integration import REPO, ROOT, documents, pod_labels, pod_spec

PLATFORM = ROOT / "platform"
FLOWS = yaml.safe_load((PLATFORM / "network/flows.yaml").read_text(encoding="utf-8"))
VECTRA = set(FLOWS["meshed_namespaces"])
ENVS = ["kind", "prod"]
OPERATOR_PORTS = {"prometheus": {9090}, "alertmanager": {8080, 9093, 9094}}  # 8080 = reloader-web, F130


def in_vectra(env="prod"):
    return [d for d in documents(env) if d["metadata"].get("namespace") in VECTRA]


def workloads(env="prod"):
    return [d for d in in_vectra(env) if pod_spec(d) is not None]


def containers(spec):
    return [*spec.get("initContainers", []), *spec.get("containers", [])]


def names(document):
    return f"{document['kind']}/{document['metadata']['namespace']}/{document['metadata']['name']}"


# --- Imagenes (NFR-U1-25)


@pytest.mark.parametrize("env", ENVS)
def test_every_image_is_pinned_by_digest(env):
    bad = [(names(w), c["image"]) for w in workloads(env) for c in containers(pod_spec(w)) if not re.search(r"[^:]@sha256:[0-9a-f]{64}$", c["image"])]
    assert not bad, bad


def operator_resources():
    return [d for d in in_vectra() if d["kind"] in {"Prometheus", "Alertmanager"}]


def test_operator_managed_pods_are_pinned_and_bounded():
    resources = operator_resources()
    assert {d["kind"] for d in resources} == {"Prometheus", "Alertmanager"}
    for document in resources:
        spec = document["spec"]
        assert "@sha256:" in spec["image"], names(document)
        assert spec["priorityClassName"] == "vectra-normal"
        assert spec["resources"]["limits"] and spec["resources"]["requests"], names(document)
        zones = [c["topologyKey"] for c in spec.get("topologySpreadConstraints", [])]
        assert "topology.kubernetes.io/zone" in zones, names(document)


def test_config_reloader_is_pinned():
    operator = next(d for d in in_vectra() if d["kind"] == "Deployment" and d["metadata"]["name"].endswith("-operator"))
    arguments = " ".join(operator["spec"]["template"]["spec"]["containers"][0]["args"])
    assert re.search(r"--prometheus-config-reloader=\S+@sha256:", arguments)


def test_postgres_clusters_pin_their_image():
    for document in in_vectra():
        if document["kind"] == "Cluster":
            assert "@sha256:" in document["spec"]["imageName"], names(document)


# --- Pod Security `restricted` (lo que comprueba la admision de Kubernetes)


def restricted_violations(spec):
    found = []
    context = spec.get("securityContext") or {}
    if spec.get("hostNetwork") or spec.get("hostPID") or spec.get("hostIPC"):
        found.append("host namespaces")
    if any("hostPath" in v for v in spec.get("volumes") or []):
        found.append("hostPath")
    for container in containers(spec):
        security = container.get("securityContext") or {}
        name = container["name"]
        if security.get("privileged"):
            found.append(f"{name}: privileged")
        if security.get("allowPrivilegeEscalation") is not False:
            found.append(f"{name}: allowPrivilegeEscalation")
        if "ALL" not in (security.get("capabilities") or {}).get("drop", []):
            found.append(f"{name}: capabilities.drop")
        if set((security.get("capabilities") or {}).get("add") or []) - {"NET_BIND_SERVICE"}:
            found.append(f"{name}: capabilities.add")
        if not (security.get("runAsNonRoot") or context.get("runAsNonRoot")):
            found.append(f"{name}: runAsNonRoot")
        if 0 in (security.get("runAsUser"), context.get("runAsUser")):
            found.append(f"{name}: runAsUser 0")
        seccomp = security.get("seccompProfile") or context.get("seccompProfile") or {}
        if seccomp.get("type") not in {"RuntimeDefault", "Localhost"}:
            found.append(f"{name}: seccompProfile")
    return found


def test_restricted_detects_a_bad_pod():
    bad = {"hostNetwork": True, "volumes": [{"hostPath": {}}], "containers": [{"name": "a"}]}
    assert len(restricted_violations(bad)) >= 5


@pytest.mark.parametrize("env", ENVS)
def test_every_pod_passes_restricted(env):
    bad = {names(w): v for w in workloads(env) if (v := restricted_violations(pod_spec(w)))}
    assert not bad, bad


def test_node_exporter_stays_off():
    assert not [w for w in workloads() if "node-exporter" in w["metadata"]["name"]], "no esta en el inventario"


# --- Flujos contra lo que de verdad corre


def selector_of(workload):
    if "labels" in workload:
        return workload["labels"]
    if "name" in workload:
        return {"app.kubernetes.io/name": workload["name"]}
    return None


def matches(labels, selector):
    return all(labels.get(k) == v for k, v in selector.items())


def chart_workloads():
    owned = {"prometheus", "alertmanager", "grafana", "loki", "tempo", "otel-collector", "alloy", "pushgateway", "kube-state-metrics", "minio", "minio-post-job", "prometheus-operator", "grafana-folder-permissions", "grafana-folder-check", "restore-drill"}
    return {name: w for name, w in FLOWS["workloads"].items() if name in owned}


def selected(workload):
    selector = selector_of(workload)
    found = [(d, pod_labels(d), pod_spec(d)) for d in workloads() if d["metadata"]["namespace"] == workload["ns"] and matches(pod_labels(d), selector)]
    operator = [d for d in in_vectra() if d["kind"] in {"Prometheus", "Alertmanager"} and d["metadata"]["namespace"] == workload["ns"] and selector == {"app.kubernetes.io/name": d["kind"].lower()}]
    return found, operator


@pytest.mark.parametrize("name", sorted(chart_workloads()))
def test_flow_selector_finds_pods_with_that_service_account(name):
    workload = chart_workloads()[name]
    found, operator = selected(workload)
    assert found or operator, f"{name}: {selector_of(workload)} no selecciona ningun pod"
    for _, _, spec in found:
        assert spec.get("serviceAccountName") == workload["sa"], name
    for document in operator:
        assert document["spec"]["serviceAccountName"] == workload["sa"], name


def declared_ports(name):
    workload = FLOWS["workloads"][name]
    found, operator = selected(workload)
    ports = {p["containerPort"] for _, _, spec in found for c in containers(spec) for p in c.get("ports", [])}
    for document in operator:
        ports |= OPERATOR_PORTS[document["kind"].lower()]
    return ports


def incoming():
    pairs = defaultdict(set)
    for flow in FLOWS["flows"]:
        ports = [flow["target_port"]] if "target_port" in flow else flow.get("ports") or [flow["port"]]
        for destination in flow["to"]:
            if destination in chart_workloads():
                pairs[destination].add((flow["id"], tuple(ports)))
    return pairs


FLOWS_THAT_DECLARE_SEVERAL_DESTINATIONS = {"F62", "F65"}


@pytest.mark.parametrize("name", sorted(incoming()))
def test_flow_ports_are_really_open(name):
    open_ports = declared_ports(name)
    for flow_id, ports in incoming()[name]:
        # F62 y F65 listan un puerto por destino: basta con que el destino exponga alguno.
        if flow_id in FLOWS_THAT_DECLARE_SEVERAL_DESTINATIONS:
            assert open_ports & set(ports), (name, flow_id, open_ports)
        else:
            assert set(ports) <= open_ports, (name, flow_id, ports, open_ports)


# --- URLs


URL = re.compile(r"(?:https?://)?\b([a-z0-9-]+)\.(vectra-[a-z-]+)\.svc(?:\.cluster\.local)?(?::(\d+))?")
HTTP_DEFAULT = 80


def source_texts():
    for folder in (PLATFORM / "observability", PLATFORM / "restore-drill", PLATFORM / "data/minio", PLATFORM / "operators"):
        for path in folder.rglob("*.yaml"):
            if "tests" not in path.parts:
                yield path, path.read_text(encoding="utf-8")


# U02-T11 (R1): `platform/operators/envoy-gateway.yaml` apunta a los Sentinel de `vectra-edge`, que da el chart de Valkey de U2. Todavia no es
# un componente de `components.yaml` (Paso 12 de U2), asi que sus Services se toman del render versionado de ese chart.
VALKEY_RENDERED = ROOT / "identity-edge/charts/valkey/rendered/prod/valkey.yaml"


def services():
    found = [d for d in in_vectra() if d["kind"] == "Service"]
    found += [d for d in yaml.safe_load_all(VALKEY_RENDERED.read_text(encoding="utf-8")) if d and d["kind"] == "Service"]
    return {(d["metadata"]["namespace"], d["metadata"]["name"]): {p["port"] for p in d["spec"]["ports"]} for d in found}


def test_every_internal_url_points_at_a_real_service_and_port():
    known = services()
    checked = 0
    for path, text in source_texts():
        for name, namespace, port in URL.findall(text):
            key = (namespace, name)
            assert key in known, (path.name, key)
            assert int(port or HTTP_DEFAULT) in known[key], (path.name, key, port, known[key])
            checked += 1
    assert checked >= 8


# --- Secretos


def referenced_secrets(document):
    spec = pod_spec(document)
    if spec is None:
        return set()
    found = set()
    for volume in spec.get("volumes") or []:
        if "secret" in volume:
            found.add((volume["secret"]["secretName"], volume["secret"].get("optional", False)))
    for container in containers(spec):
        for source in container.get("envFrom") or []:
            if "secretRef" in source:
                found.add((source["secretRef"]["name"], source["secretRef"].get("optional", False)))
        for item in container.get("env") or []:
            reference = (item.get("valueFrom") or {}).get("secretKeyRef")
            if reference:
                found.add((reference["name"], reference.get("optional", False)))
    return {name for name, optional in found if not optional}


def available_secrets(env="prod"):
    found = set()
    for document in documents(env):
        namespace = document["metadata"].get("namespace")
        if document["kind"] == "Secret":
            found.add((namespace, document["metadata"]["name"]))
        if document["kind"] == "ExternalSecret":
            found.add((namespace, (document["spec"].get("target") or {}).get("name") or document["metadata"]["name"]))
        if document["kind"] == "Certificate":
            found.add((namespace, document["spec"]["secretName"]))
    return found


def test_every_secret_a_pod_needs_has_a_source():
    available = available_secrets()
    bad = [(names(w), s) for w in workloads() for s in referenced_secrets(w) if (w["metadata"]["namespace"], s) not in available]
    assert not bad, bad


def test_minio_and_backups_have_their_secrets():
    available = available_secrets()
    for key in [("vectra-data", "minio-root"), ("vectra-data", "minio-kserve"), ("vectra-data", "minio-validation"), ("vectra-data", "minio-loki"), ("vectra-data", "minio-tempo"), ("vectra-data", "postgres-backup-credentials"), ("vectra-serving", "minio-kserve"), ("vectra-staging", "minio-validation"), ("vectra-observability", "loki-s3"), ("vectra-observability", "tempo-s3"), ("vectra-observability", "alertmanager-config"), ("vectra-observability", "grafana-admin")]:
        assert key in available, key


def test_alertmanager_config_comes_from_the_vault():
    manager = next(d for d in in_vectra() if d["kind"] == "Alertmanager")
    assert manager["spec"]["configSecret"] == "alertmanager-config"
    source = next(d for d in in_vectra() if d["kind"] == "ExternalSecret" and d["metadata"]["name"] == "alertmanager-config")
    config = yaml.safe_load(source["spec"]["target"]["template"]["data"]["alertmanager.yaml"])
    assert config["receivers"][0]["webhook_configs"][0]["url"] == "{{ .url }}"
    assert next(r for r in config["route"]["routes"] if "Watchdog" in r["matchers"][0])["repeat_interval"] == "5m"


def test_loki_and_tempo_load_their_s3_credentials():
    for document in workloads():
        name = document["metadata"]["name"]
        if name.startswith("loki-") or name.startswith("tempo-"):
            expected = "loki-s3" if name.startswith("loki-") else "tempo-s3"
            assert expected in referenced_secrets(document), name


def test_loki_and_tempo_have_a_minio_user_with_a_scoped_policy():
    values = yaml.safe_load((PLATFORM / "data/minio/values.yaml").read_text(encoding="utf-8"))
    users = {u["accessKey"]: u for u in values["users"]}
    policies = {p["name"]: p for p in values["policies"]}
    for user, bucket in (("loki-writer", "loki"), ("tempo-writer", "tempo")):
        resources = policies[users[user]["policy"]]["statements"][0]["resources"]
        assert resources == [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"]


# --- Certificados y malla


def test_every_issuer_reference_exists():
    all_documents = documents()
    issuers = {d["metadata"]["name"] for d in all_documents if d["kind"] == "ClusterIssuer"}
    references = [d["spec"]["issuerRef"]["name"] for d in all_documents if d["kind"] == "Certificate" and d["spec"]["issuerRef"]["kind"] == "ClusterIssuer"]
    assert references and set(references) <= issuers, set(references) - issuers


def test_ca_issuers_read_a_secret_that_a_certificate_creates():
    all_documents = documents()
    secrets = {d["spec"]["secretName"] for d in all_documents if d["kind"] == "Certificate"}
    for document in all_documents:
        if document["kind"] == "ClusterIssuer" and "ca" in document["spec"]:
            assert document["spec"]["ca"]["secretName"] in secrets, document["metadata"]["name"]


def test_trust_roots_are_published_for_linkerd():
    bundle = next(d for d in documents() if d["kind"] == "Bundle")
    assert bundle["metadata"]["name"] == "linkerd-identity-trust-roots"
    assert bundle["spec"]["target"]["configMap"]["key"] == "ca-bundle.crt"
    assert bundle["spec"]["target"]["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"] == "linkerd"
    assert bundle["spec"]["sources"][0]["secret"]["name"] == "linkerd-trust-anchor"


# --- Imagenes propias


def own_images():
    found = set()
    for workload in workloads():
        for container in containers(pod_spec(workload)):
            if container["image"].startswith("registro.vectra.internal/"):
                found.add(container["image"].split("/")[1].split("@")[0].split(":")[0])
    return found


DOCKERFILES = {"restore-drill": "restore-drill/Dockerfile", "grafana-folder-permissions": "observability/grafana/Dockerfile", "minio": "data/minio/Dockerfile", "mc": "data/minio/Dockerfile"}


def test_placeholder_digests_are_only_on_images_we_build():
    placeholder = "@sha256:" + "0" * 64
    bad = [c["image"] for w in workloads() for c in containers(pod_spec(w)) if c["image"].endswith(placeholder) and not c["image"].startswith("registro.vectra.internal/")]
    assert not bad, bad


def test_every_own_image_has_a_dockerfile():
    assert own_images() == set(DOCKERFILES)


@pytest.mark.parametrize("path", sorted(DOCKERFILES.values()))
def test_dockerfiles_are_pinned_and_not_root(path):
    text = (PLATFORM / path).read_text(encoding="utf-8")
    for image in re.findall(r"^FROM\s+(\S+)", text, flags=re.M):
        assert "@sha256:" in image, image
    assert re.findall(r"^USER\s+(\S+)", text, flags=re.M)[-1] == "65532"


def test_restore_script_exists_and_pins_its_image():
    assert "restore-cluster.sh" in (PLATFORM / "restore-drill/drill.py").read_text(encoding="utf-8")
    script = (PLATFORM / "restore-drill/restore-cluster.sh").read_text(encoding="utf-8")
    assert "RESTORE_IMAGE" in script and "restore-cluster.sh" in (PLATFORM / "restore-drill/Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"RESTORE_IMAGE.*@sha256:[0-9a-f]{64}", (PLATFORM / "restore-drill/cronjob.yaml").read_text(encoding="utf-8"))


# --- Esquemas: un campo mal escrito en un recurso propio se pierde en silencio


def crd_schemas():
    schemas = {}
    for document in documents("kind"):
        if document["kind"] == "CustomResourceDefinition":
            group, kind = document["spec"]["group"], document["spec"]["names"]["kind"]
            for version in document["spec"]["versions"]:
                schema = (version.get("schema") or {}).get("openAPIV3Schema")
                if schema:
                    schemas[(f"{group}/{version['name']}", kind)] = schema
    return schemas


def schema_errors(value, schema, path=""):
    errors = []
    if schema.get("x-kubernetes-preserve-unknown-fields") or schema.get("x-kubernetes-int-or-string"):
        return errors
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties")
        for key, item in value.items():
            if key in properties:
                errors += schema_errors(item, properties[key], f"{path}.{key}")
            elif isinstance(extra, dict):
                errors += schema_errors(item, extra, f"{path}.{key}")
            elif properties and path != "" and extra is not True:
                errors.append(f"{path}.{key}: campo desconocido")
            elif properties and path == "" and key not in {"apiVersion", "kind", "metadata"}:
                errors.append(f"{key}: campo desconocido")
        errors += [f"{path}.{key}: obligatorio" for key in schema.get("required", []) if key not in value]
    elif isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                errors += schema_errors(item, items, f"{path}[{index}]")
    elif "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} fuera de {schema['enum']}")
    return errors


def test_schema_check_detects_unknown_required_and_enum():
    schema = {"properties": {"spec": {"required": ["a"], "properties": {"a": {"enum": ["x"]}}}}}
    assert schema_errors({"spec": {"a": "y", "b": 1}}, schema)
    assert schema_errors({"spec": {}}, schema) == [".spec.a: obligatorio"]


OWN_KINDS = {"Cluster", "ScheduledBackup", "ExternalSecret", "ClusterSecretStore", "Certificate", "ClusterIssuer", "Bundle", "ClusterPolicy", "PrometheusRule", "Server", "HTTPRoute", "AuthorizationPolicy", "MeshTLSAuthentication", "NetworkAuthentication", "Application", "AppProject"}


def own_documents(env):
    for document in documents(env):
        if document["kind"] in OWN_KINDS:
            yield document
    for path in (ROOT / f"vectra-risk-gitops/apps/{env}").glob("*.yaml"):
        yield from yaml.safe_load_all(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("env", ["kind"])
def test_own_custom_resources_match_the_real_crds(env):
    schemas = crd_schemas()
    errors, checked = [], 0
    for document in own_documents(env):
        schema = schemas.get((document["apiVersion"], document["kind"]))
        assert schema, f"Sin CRD para {document['apiVersion']} {document['kind']}"
        checked += 1
        errors += [f"{document['kind']}/{document['metadata']['name']}{e}" for e in schema_errors(document, schema)]
    assert checked > 100
    assert not errors, errors[:20]


# --- Capacidad


def quantity(value):
    text = str(value)
    units = {"m": 0.001, "Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40, "k": 1000, "M": 10**6, "G": 10**9}
    for suffix, factor in units.items():
        if text.endswith(suffix):
            return float(text[: -len(suffix)]) * factor
    return float(text)


def replicas_of(document):
    return document["spec"].get("replicas", 1) if document["kind"] in {"Deployment", "StatefulSet"} else 1


#: El proxy de Linkerd que se inyecta en cada pod (NFR-U1-13).
PROXY = {"requests": {"cpu": "100m", "memory": "20Mi"}, "limits": {"cpu": "500m", "memory": "128Mi"}}
QUOTA_INPUT = yaml.safe_load((PLATFORM / "policies/quotas/quotas.yaml").read_text(encoding="utf-8"))
#: config-reloader no declara recursos en el chart: los toma de los valores por omision del LimitRange.
CONFIG_RELOADER = {
    "requests": {"cpu": QUOTA_INPUT["limit_range"]["request_cpu"], "memory": QUOTA_INPUT["limit_range"]["request_memory"]},
    "limits": {"cpu": QUOTA_INPUT["limit_range"]["default_cpu"], "memory": QUOTA_INPUT["limit_range"]["default_memory"]},
}
DAEMONSET_PODS = 8  # zonas de produccion: 2 x (4 general + 2 data) + plano de control
SECTIONS = ("requests", "limits")
RESOURCE_KEYS = ("cpu", "memory")


def is_meshed(annotations):
    return (annotations or {}).get("linkerd.io/inject") != "disabled"


def pods_of(document):
    """(pods, recursos de cada contenedor, si lleva proxy), o None si el documento no corre pods de larga duracion."""
    spec = document.get("spec") or {}
    kind = document["kind"]
    if kind == "Cluster":
        annotations = (spec.get("inheritedMetadata") or {}).get("annotations")
        return spec["instances"], [spec["resources"]], is_meshed(annotations)
    if kind in {"Prometheus", "Alertmanager"}:
        annotations = (spec.get("podMetadata") or {}).get("annotations")
        return spec.get("replicas", 1), [spec["resources"], CONFIG_RELOADER], is_meshed(annotations)
    if kind in {"Deployment", "StatefulSet", "DaemonSet"}:
        count = DAEMONSET_PODS if kind == "DaemonSet" else replicas_of(document)
        template = spec["template"]
        resources = [c.get("resources") or {} for c in template["spec"].get("containers", [])]
        return count, resources, is_meshed((template.get("metadata") or {}).get("annotations"))
    return None


def undeclared_resources(documents_):
    return [
        (names(d), section, key)
        for d in documents_
        if (pods := pods_of(d))
        for resources in pods[1]
        for section in SECTIONS
        for key in RESOURCE_KEYS
        if key not in (resources.get(section) or {})
    ]


def usage_by_namespace(documents_):
    totals = defaultdict(lambda: defaultdict(float))
    for document in documents_:
        pods = pods_of(document)
        if pods is None:
            continue
        count, resources, meshed = pods
        for item in [*resources, PROXY] if meshed else resources:
            for section in SECTIONS:
                for key in RESOURCE_KEYS:
                    if key in (item.get(section) or {}):
                        totals[document["metadata"]["namespace"]][f"{section}.{key}"] += quantity(item[section][key]) * count
    return totals


def test_usage_counts_cnpg_operator_pods_and_proxies():
    resources = {"requests": {"cpu": "1", "memory": "1Gi"}, "limits": {"cpu": "2", "memory": "2Gi"}}
    usage = usage_by_namespace(
        [
            {"kind": "Cluster", "metadata": {"namespace": "a"}, "spec": {"instances": 3, "resources": resources}},
            {"kind": "Prometheus", "metadata": {"namespace": "b"}, "spec": {"replicas": 2, "resources": resources}},
            {"kind": "Alertmanager", "metadata": {"namespace": "c"}, "spec": {"resources": resources}},
        ]
    )
    assert usage["a"]["requests.cpu"] == pytest.approx(3 * (1 + 0.1))
    assert usage["a"]["limits.memory"] == pytest.approx(3 * (2 * 2**30 + 128 * 2**20))
    assert usage["b"]["requests.cpu"] == pytest.approx(2 * (1 + 0.1 + quantity(QUOTA_INPUT["limit_range"]["request_cpu"])))
    assert usage["c"]["limits.cpu"] == pytest.approx(2 + 0.5 + quantity(QUOTA_INPUT["limit_range"]["default_cpu"]))


def test_usage_skips_the_proxy_when_the_pod_is_not_meshed():
    resources = {"requests": {"cpu": "1", "memory": "1Gi"}, "limits": {"cpu": "2", "memory": "2Gi"}}
    template = {"metadata": {"annotations": {"linkerd.io/inject": "disabled"}}, "spec": {"containers": [{"resources": resources}]}}
    usage = usage_by_namespace([{"kind": "Deployment", "metadata": {"namespace": "a"}, "spec": {"replicas": 2, "template": template}}])
    assert usage["a"]["requests.cpu"] == pytest.approx(2)


def test_every_workload_declares_requests_and_limits_and_fits_the_quota():
    quotas = {d["metadata"]["namespace"]: d["spec"]["hard"] for d in yaml.safe_load_all((PLATFORM / "policies/quotas/generated.yaml").read_text(encoding="utf-8")) if d and d["kind"] == "ResourceQuota"}
    running = in_vectra()
    assert {"Cluster", "Prometheus", "Alertmanager"} <= {d["kind"] for d in running}
    assert not undeclared_resources(running), undeclared_resources(running)
    shortfalls = [
        f"{namespace} {key}: usa {value:.2f}, cuota {quotas[namespace][key]} ({quantity(quotas[namespace][key]):.2f})"
        for namespace, usage in usage_by_namespace(running).items()
        for key, value in usage.items()
        if value > quantity(quotas[namespace][key])
    ]
    assert not shortfalls, shortfalls


def test_repo_root_is_the_monorepo():
    assert Path(REPO / ".github").is_dir()
