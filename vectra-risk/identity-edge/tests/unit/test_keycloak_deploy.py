"""Despliegue de Keycloak (U02-T07, Paso 5): NFR-U2-01, 02, 23, 26; P-U2-04; INF-U2-01, 05a, 05b, 06, 08.

Cada regla de identity-edge/keycloak/policy/ tiene su caso que falla sobre un render alterado, y los valores
que las pruebas esperan salen de los documentos de diseno (las pruebas `design`).
"""

import copy
from collections.abc import Callable
from typing import Any

import keycloak_deploy_checks as kd
import pytest
import yaml

Docs = list[dict[str, Any]]


def _sts(docs: Docs) -> dict[str, Any]:
    return kd.statefulset(docs)


def _pod(docs: Docs) -> dict[str, Any]:
    return _sts(docs)["spec"]["template"]["spec"]


def _container(docs: Docs) -> dict[str, Any]:
    return _pod(docs)["containers"][0]


def _env(docs: Docs, name: str) -> dict[str, Any]:
    (found,) = [e for e in _container(docs)["env"] if e["name"] == name]
    return found


def _drop(kind: str, name: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        docs.remove(kd.find(docs, kind, name))

    return mutate


def _set(kind: str, name: str, path: list[str | int], value: Any) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node: Any = kd.find(docs, kind, name)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


def _env_value(name: str, value: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _env(docs, name).pop("valueFrom", None)
        _env(docs, name)["value"] = value

    return mutate


def _env_drop(name: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _container(docs)["env"].remove(_env(docs, name))

    return mutate


def _env_add(name: str, value: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _container(docs)["env"].append({"name": name, "value": value})

    return mutate


def _sts_set(path: list[str | int], value: Any) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node: Any = _sts(docs)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


def _sts_del(path: list[str]) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node: Any = _sts(docs)
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return mutate


def _add_doc(doc: dict[str, Any]) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        docs.append(copy.deepcopy(doc))

    return mutate


def _other_container(docs: Docs) -> None:
    _pod(docs)["containers"].append({"name": "sidecar", "image": "x"})


def _spread_hostname(docs: Docs) -> None:
    _pod(docs)["topologySpreadConstraints"][0]["topologyKey"] = "kubernetes.io/hostname"


def _spread_soft(docs: Docs) -> None:
    _pod(docs)["topologySpreadConstraints"][0]["whenUnsatisfiable"] = "ScheduleAnyway"


def _es_dataFrom(docs: Docs) -> None:
    kd.find(docs, "ExternalSecret", "identity-ca")["spec"]["dataFrom"] = [{"extract": {"key": "identity"}}]


def _service_drop_port(docs: Docs) -> None:
    ports = kd.find(docs, "Service", "keycloak")["spec"]["ports"]
    ports[:] = [p for p in ports if p["port"] != 7800]


def _admin_extra_port(docs: Docs) -> None:
    kd.find(docs, "Service", "keycloak-admin")["spec"]["ports"].append({"name": "http", "port": 80, "targetPort": "http"})


def _probe_port(docs: Docs) -> None:
    _container(docs)["readinessProbe"]["httpGet"]["port"] = "http"


def _volume_drop(docs: Docs) -> None:
    volumes = _pod(docs)["volumes"]
    volumes[:] = [v for v in volumes if v.get("secret", {}).get("secretName") != "keycloak-tls"]


def _hpa_metric_memory(docs: Docs) -> None:
    kd.find(docs, "HorizontalPodAutoscaler", "keycloak")["spec"]["metrics"][0]["resource"]["name"] = "memory"


PLAIN_SECRET = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "keycloak-plain", "namespace": "vectra-identity"}, "data": {"password": "cGFzcw=="}}
ROUTE = {"apiVersion": "gateway.networking.k8s.io/v1", "kind": "HTTPRoute", "metadata": {"name": "keycloak-admin", "namespace": "vectra-identity"}, "spec": {}}
STRANGER = {"apiVersion": "external-secrets.io/v1", "kind": "ExternalSecret", "metadata": {"name": "other", "namespace": "vectra-identity"}, "spec": {}}
OTHER_CERT = {"apiVersion": "cert-manager.io/v1", "kind": "Certificate", "metadata": {"name": "other", "namespace": "vectra-identity"}, "spec": {}}
IMAGE = "registro.banco.internal/vectra/keycloak"

# (regla, caso, alteracion). Cada regla de la politica aparece al menos una vez; la prueba exige que la salida la nombre.
MUTATIONS: list[tuple[str, str, Callable[[Docs], None]]] = [
    ("statefulset-shape", "dos contenedores", _other_container),
    ("statefulset-shape", "otro namespace", _sts_set(["metadata", "namespace"], "vectra-app")),
    ("replicas", "1 replica", _sts_set(["spec", "replicas"], 1)),
    ("replicas", "3 replicas", _sts_set(["spec", "replicas"], 3)),
    ("hpa", "minimo 1", _set("HorizontalPodAutoscaler", "keycloak", ["spec", "minReplicas"], 1)),
    ("hpa", "maximo 5", _set("HorizontalPodAutoscaler", "keycloak", ["spec", "maxReplicas"], 5)),
    ("hpa", "maximo 3", _set("HorizontalPodAutoscaler", "keycloak", ["spec", "maxReplicas"], 3)),
    ("hpa", "metrica de memoria", _hpa_metric_memory),
    ("hpa", "apunta a un Deployment", _set("HorizontalPodAutoscaler", "keycloak", ["spec", "scaleTargetRef", "kind"], "Deployment")),
    ("zone-spread", "sin reparto", _sts_del(["spec", "template", "spec", "topologySpreadConstraints"])),
    ("zone-spread", "reparto por nodo", _spread_hostname),
    ("zone-spread", "reparto blando", _spread_soft),
    ("pdb", "maxUnavailable en vez de minAvailable", lambda d: kd.find(d, "PodDisruptionBudget", "keycloak")["spec"].update({"maxUnavailable": 1}) or kd.find(d, "PodDisruptionBudget", "keycloak")["spec"].pop("minAvailable")),
    ("pdb", "minAvailable 2", _set("PodDisruptionBudget", "keycloak", ["spec", "minAvailable"], 2)),
    ("start-optimized", "start sin --optimized", _sts_set(["spec", "template", "spec", "containers", 0, "args"], ["start"])),
    ("start-optimized", "start-dev", _sts_set(["spec", "template", "spec", "containers", 0, "args"], ["start-dev"])),
    ("start-optimized", "sin args", _sts_del(["spec", "template", "spec", "containers", 0, "args"])),
    ("start-optimized", "con command", _sts_set(["spec", "template", "spec", "containers", 0, "command"], ["sh"])),
    ("env-whitelist", "variable de mas", _env_add("KC_BOOTSTRAP_ADMIN_PASSWORD", "x")),
    ("env-whitelist", "falta una variable", _env_drop("KC_DB_POOL_MAX_SIZE")),
    ("env-whitelist", "pool distinto de 20", _env_value("KC_DB_POOL_MAX_SIZE", "100")),
    ("env-whitelist", "envFrom", _sts_set(["spec", "template", "spec", "containers", 0, "envFrom"], [{"secretRef": {"name": "x"}}])),
    ("env-whitelist", "variable repetida", _env_add("KC_DB", "postgres")),
    ("cache-stack", "kubernetes", _env_value("KC_CACHE_STACK", "kubernetes")),
    ("cache-stack", "sin cache-stack", _env_drop("KC_CACHE_STACK")),
    ("proxy-headers", "forwarded", _env_value("KC_PROXY_HEADERS", "forwarded")),
    ("proxy-headers", "sin proxy-headers", _env_drop("KC_PROXY_HEADERS")),
    ("hostname", "otro host", _env_value("KC_HOSTNAME", "https://otro.banco.internal/auth")),
    ("hostname", "sin /auth", _env_value("KC_HOSTNAME", "https://vectra.banco.internal")),
    ("hostname-admin", "admin publico", _env_value("KC_HOSTNAME_ADMIN", "https://vectra.banco.internal/auth")),
    ("hostname-admin", "otro admin", _env_value("KC_HOSTNAME_ADMIN", "https://admin.banco.internal/auth")),
    ("persistent-sessions", "features-disabled en args", _sts_set(["spec", "template", "spec", "containers", 0, "args"], ["start", "--optimized", "--features-disabled=persistent-user-sessions"])),
    ("persistent-sessions", "KC_FEATURES_DISABLED", _env_add("KC_FEATURES_DISABLED", "persistent-user-sessions")),
    ("probes", "readiness al 8080", _probe_port),
    ("probes", "sin liveness", lambda d: _container(d).pop("livenessProbe")),
    ("resources", "limite de CPU", _sts_set(["spec", "template", "spec", "containers", 0, "resources", "limits", "cpu"], "4")),
    ("resources", "request de memoria", _sts_set(["spec", "template", "spec", "containers", 0, "resources", "requests", "memory"], "512Mi")),
    ("priority", "otra prioridad", _sts_set(["spec", "template", "spec", "priorityClassName"], "vectra-normal")),
    ("priority", "sin prioridad", _sts_del(["spec", "template", "spec", "priorityClassName"])),
    ("criticality", "sin etiqueta", lambda d: _sts(d)["metadata"]["labels"].pop("vectra.io/criticality")),
    ("criticality", "otra criticidad", _sts_set(["metadata", "labels", "vectra.io/criticality"], "medium")),
    ("image", "sin digest", _sts_set(["spec", "template", "spec", "containers", 0, "image"], f"{IMAGE}:26.8.1")),
    ("image", "otro repositorio", _sts_set(["spec", "template", "spec", "containers", 0, "image"], "quay.io/keycloak/keycloak@sha256:" + "a" * 64)),
    ("image", "digest corto", _sts_set(["spec", "template", "spec", "containers", 0, "image"], f"{IMAGE}@sha256:abc")),
    ("db-credentials", "contrasena en claro", _env_value("KC_DB_PASSWORD", "secreto")),
    ("db-credentials", "otro Secret", lambda d: _env(d, "KC_DB_USERNAME")["valueFrom"]["secretKeyRef"].update({"name": "otro"})),
    ("tls-mount", "sin el volumen keycloak-tls", _volume_drop),
    ("no-plain-secret", "Secret con data", _add_doc(PLAIN_SECRET)),
    ("external-secret", "otra clave", _set("ExternalSecret", "identity-ca", ["spec", "data", 0, "remoteRef", "key"], "identity/otra")),
    ("external-secret", "otra propiedad", _set("ExternalSecret", "keycloak-reader-client", ["spec", "data", 0, "remoteRef", "property"], "jwks")),
    ("external-secret", "otro store", _set("ExternalSecret", "identity-ca", ["spec", "secretStoreRef", "name"], "otro")),
    ("external-secret", "dataFrom", _es_dataFrom),
    ("external-secret", "ExternalSecret ajeno", _add_doc(STRANGER)),
    ("keycloak-tls", "SAN de mas", _set("Certificate", "keycloak-tls", ["spec", "dnsNames"], ["keycloak.vectra-identity.svc", "x.svc"])),
    ("keycloak-tls", "otro SAN", _set("Certificate", "keycloak-tls", ["spec", "dnsNames"], ["keycloak.otro.svc"])),
    ("keycloak-tls", "duracion", _set("Certificate", "keycloak-tls", ["spec", "duration"], "8760h")),
    ("keycloak-tls", "renovacion", _set("Certificate", "keycloak-tls", ["spec", "renewBefore"], "360h")),
    ("keycloak-tls", "issuer vacio", _set("Certificate", "keycloak-tls", ["spec", "issuerRef", "name"], "")),
    ("keycloak-tls", "Issuer de namespace", _set("Certificate", "keycloak-tls", ["spec", "issuerRef", "kind"], "Issuer")),
    ("keycloak-tls", "otro secretName", _set("Certificate", "keycloak-tls", ["spec", "secretName"], "otro")),
    ("keycloak-tls", "Certificate ajeno", _add_doc(OTHER_CERT)),
    ("backend-tls-policy", "otro puerto", _set("BackendTLSPolicy", "keycloak", ["spec", "targetRefs", 0, "sectionName"], "jgroups")),
    ("backend-tls-policy", "otra CA", _set("BackendTLSPolicy", "keycloak", ["spec", "validation", "caCertificateRefs", 0, "name"], "otra")),
    ("backend-tls-policy", "CA como ConfigMap", _set("BackendTLSPolicy", "keycloak", ["spec", "validation", "caCertificateRefs", 0, "kind"], "ConfigMap")),
    ("backend-tls-policy", "otro hostname", _set("BackendTLSPolicy", "keycloak", ["spec", "validation", "hostname"], "keycloak.otro.svc")),
    ("service-ports", "sin 7800", _service_drop_port),
    ("service-ports", "admin con dos puertos", _admin_extra_port),
    ("no-gateway-route", "HTTPRoute del admin", _add_doc(ROUTE)),
    ("present", "sin StatefulSet", _drop("StatefulSet", "keycloak")),
    ("present", "sin HPA", _drop("HorizontalPodAutoscaler", "keycloak")),
    ("present", "sin PDB", _drop("PodDisruptionBudget", "keycloak")),
    ("present", "sin Service keycloak", _drop("Service", "keycloak")),
    ("present", "sin Service keycloak-admin", _drop("Service", "keycloak-admin")),
    ("present", "sin keycloak-tls", _drop("Certificate", "keycloak-tls")),
    ("present", "sin BackendTLSPolicy", _drop("BackendTLSPolicy", "keycloak")),
    ("present", "sin identity-ca", _drop("ExternalSecret", "identity-ca")),
    ("present", "sin credencial de config-cli", _drop("ExternalSecret", "keycloak-config-cli-client")),
    ("present", "sin credencial de reader", _drop("ExternalSecret", "keycloak-reader-client")),
    ("hpa-targets-statefulset", "sin StatefulSet", _drop("StatefulSet", "keycloak")),
]  # fmt: skip


@pytest.fixture(scope="module")
def prod() -> Docs:
    return kd.load("prod")


# --- lo renderizado cumple ----------------------------------------------------------------------

@pytest.mark.parametrize("env", kd.ENVS)
def test_rendered_keycloak_meets_the_policies(env):
    code, output = kd.conftest(kd.load(env))
    assert code == 0, output


@pytest.mark.parametrize("env", kd.ENVS)
def test_committed_render_matches_a_fresh_render(env):
    fresh = kd.render(env)
    assert fresh.returncode == 0, fresh.stderr
    assert (kd.RENDERED / env / "keycloak.yaml").read_text(encoding="utf-8") == fresh.stdout


# --- cada regla falla sobre un render alterado -------------------------------------------------

def test_every_rule_has_a_failing_case():
    assert {rule for rule, _, _ in MUTATIONS} == kd.policy_rules()


@pytest.mark.parametrize(("rule", "case", "mutate"), MUTATIONS, ids=[f"{r}-{c}" for r, c, _ in MUTATIONS])
def test_rule_fails_on_an_altered_render(rule, case, mutate, prod):
    docs = copy.deepcopy(prod)
    mutate(docs)
    code, output = kd.conftest(docs)
    assert code != 0, f"{rule}/{case}: conftest no fallo"
    assert f"{rule}: " in output, f"{rule}/{case}: la salida no nombra la regla\n{output}"


@pytest.mark.parametrize("env", ["kind", "staging"])
def test_a_rule_also_fails_in_other_environments(env):
    docs = kd.load(env)
    _env_value("KC_HOSTNAME_ADMIN", "https://vectra.banco.internal/auth")(docs)
    code, output = kd.conftest(docs)
    assert code != 0 and "hostname-admin: " in output


# --- los valores salen del diseno ---------------------------------------------------------------

def test_design_chart_version_is_the_downloaded_one():
    chart = yaml.safe_load((kd.CHART / "Chart.yaml").read_text(encoding="utf-8"))
    assert chart["version"] == kd.design_chart_version()


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_hostnames(env):
    public = kd.design_public_hostnames()[env]
    path = kd.design_hostname_path()
    envs = kd.container_env(kd.load(env))
    assert envs["KC_HOSTNAME"]["value"] == f"https://{public}{path}"
    admin = envs["KC_HOSTNAME_ADMIN"]["value"]
    assert admin.startswith(f"https://{kd.design_admin_hostname()}:") and admin.endswith(path)
    assert kd.find(kd.load(env), "Service", "keycloak-admin")["metadata"]["name"] == kd.design_admin_hostname().split(".")[0]


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_resources(env):
    docs = kd.load(env)
    assert _container(docs)["resources"] == kd.design_keycloak_resources()
    assert kd.container_env(docs)["JAVA_OPTS_APPEND"]["value"] == kd.design_max_ram_percentage()


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_replicas_hpa_and_pdb(env):
    docs = kd.load(env)
    low, high = kd.design_replicas()
    spec = kd.find(docs, "HorizontalPodAutoscaler", "keycloak")["spec"]
    assert (spec["minReplicas"], spec["maxReplicas"]) == (low, high)
    assert "replicas" not in _sts(docs)["spec"]
    assert kd.find(docs, "PodDisruptionBudget", "keycloak")["spec"]["minAvailable"] == kd.design_pdb_min_available()


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_image_repository_and_digest(env):
    image = _container(kd.load(env))["image"]
    repository, digest = image.split("@")
    assert repository == kd.design_image_repositories()[env]
    assert digest.startswith("sha256:")


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_vault_keys(env):
    docs = kd.load(env)
    read = {}
    for doc in docs:
        if doc["kind"] == "ExternalSecret":
            for item in doc["spec"]["data"]:
                read[item["remoteRef"]["key"]] = item["remoteRef"]["property"]
    assert read == kd.design_vault_entries()


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_certificate_and_backend_policy(env):
    docs = kd.load(env)
    cert = kd.design_certificate()
    spec = kd.find(docs, "Certificate", "keycloak-tls")["spec"]
    assert (spec["dnsNames"], spec["duration"], spec["renewBefore"]) == ([cert["san"]], cert["duration"], cert["renewBefore"])
    assert kd.find(docs, "BackendTLSPolicy", "keycloak")["spec"]["validation"]["hostname"] == cert["san"]


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_ports_match_flows(env):
    ports = kd.design_ports()
    service = kd.find(kd.load(env), "Service", "keycloak")
    assert sorted(p["port"] for p in service["spec"]["ports"]) == sorted(ports.values())


def test_design_issuer_in_kind_is_the_internal_ca():
    spec = kd.find(kd.load("kind"), "Certificate", "keycloak-tls")["spec"]
    assert spec["issuerRef"] == {"name": "vectra-internal-ca", "kind": "ClusterIssuer"}


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_render_fails_without_digest(env):
    result = kd.render(env, "--set", "image.digest=")
    assert result.returncode != 0
    assert "digest" in result.stderr


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_render_without_digest_key_fails(env):
    result = kd.render(env, "--set", "image.digest=null")
    assert result.returncode != 0
    assert "digest" in result.stderr


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_design_render_fails_without_issuer_ref(env):
    result = kd.render(env, "--set", "vectra.tls.issuerRef=null")
    assert result.returncode != 0
    assert "issuerRef" in result.stderr


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_design_render_fails_with_an_empty_issuer_name(env):
    result = kd.render(env, "--set", "vectra.tls.issuerRef.name=")
    assert result.returncode != 0
    assert "issuerRef" in result.stderr


def test_design_common_values_have_no_default_issuer_or_digest():
    common = yaml.safe_load((kd.VALUES / "common.yaml").read_text(encoding="utf-8"))
    assert not common.get("image", {}).get("digest")
    assert "issuerRef" not in common.get("vectra", {}).get("tls", {})


# --- politicas de U1 (Kyverno) ------------------------------------------------------------------

@pytest.mark.parametrize("env", kd.ENVS)
def test_rendered_keycloak_meets_the_u1_kyverno_policies(env):
    ok, output = kd.kyverno(kd.load(env))
    assert ok, output


U1_MUTATIONS: list[tuple[str, Callable[[Docs], None]]] = [
    ("sin prioridad", _sts_del(["spec", "template", "spec", "priorityClassName"])),
    ("raiz escribible", _sts_set(["spec", "template", "spec", "containers", 0, "securityContext", "readOnlyRootFilesystem"], False)),
    ("sin limites", _sts_del(["spec", "template", "spec", "containers", 0, "resources", "limits"])),
    ("pod como root", _sts_set(["spec", "template", "spec", "securityContext", "runAsNonRoot"], False)),
    ("sin digest", _sts_set(["spec", "template", "spec", "containers", 0, "image"], f"{IMAGE}:26.8.1")),
    ("registro ajeno", _sts_set(["spec", "template", "spec", "containers", 0, "image"], "quay.io/keycloak/keycloak@sha256:" + "a" * 64)),
    ("sin criticidad", lambda d: _sts(d)["metadata"]["labels"].pop("vectra.io/criticality")),
    ("Secret en claro", _add_doc(PLAIN_SECRET)),
]


@pytest.mark.parametrize(("case", "mutate"), U1_MUTATIONS, ids=[c for c, _ in U1_MUTATIONS])
def test_u1_kyverno_policies_fail_on_an_altered_render(case, mutate, prod):
    docs = copy.deepcopy(prod)
    mutate(docs)
    ok, output = kd.kyverno(docs)
    assert not ok, f"{case}: kyverno no fallo\n{output}"
