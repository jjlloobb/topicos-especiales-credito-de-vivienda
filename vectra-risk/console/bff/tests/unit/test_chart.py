"""Los dos charts de U10 (Paso 18; INF-U10-01, INF-U10-03, INF-U10-04, INF-U10-06; NFR-U10-10, NFR-U10-12, NFR-U10-20, NFR-U10-22; BR-U10-02; P-1 a P-6 de U10-T05).

`helm template` de los dos charts en los tres entornos, con lo que usa Argo CD (`components.yaml`) y `conftest` con `console/policies/conftest/` (por documento y con todo el
render junto, con los datos del realm por `--data`). Cada `# regla: x` de las politicas tiene aqui un caso que falla (una mutacion del render por regla) y el chart sin
tocar pasa. Ademas, el **mundo cerrado** (CA-3): `config.json` contra el realm y el gateway de U2, las variables del BFF contra el codigo y contra `flows.yaml`, y los nombres
contra `flows.yaml` y `routes.yaml`; la cuota recalculada; `forbidden.yaml` y los `Server` generados. Necesita `platform/install-tools.sh` (helm y conftest en
`platform/.tools/bin`): si faltan, **fallan**.
"""

import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import chart_data
import pytest
import yaml
from vectra_common import telemetry
from vectra_common.ops_server import create_ops_app

from console_bff import app as bff_app
from console_bff import config as bff_config

ROOT = Path(__file__).resolve().parents[4]
CHARTS = {
    "console-bff": ROOT / "console" / "chart" / "bff",
    "console-spa": ROOT / "console" / "chart" / "spa",
}
POLICIES = ROOT / "console" / "policies" / "conftest"
BIN = ROOT / "platform" / ".tools" / "bin"
ENVS = ("kind", "staging", "prod")
NGINX_CONF = ROOT / "console" / "spa" / "nginx.conf"
Doc = dict[str, Any]


def tool(name: str) -> str:
    path = BIN / name
    assert path.is_file(), f"falta {path}: corre platform/install-tools.sh"
    return str(path)


def load(path: str) -> Any:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def gitops() -> Any:
    spec = importlib.util.spec_from_file_location(
        "gitops_generate", ROOT / "vectra-risk-gitops" / "generate.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPONENTS = {c["name"]: c for c in load("vectra-risk-gitops/components.yaml")["components"]}
FLOWS = load("platform/network/flows.yaml")
ROUTES = load("identity-edge/gateway/routes.yaml")


def values_files(name: str, env: str) -> list[Path]:
    """Los values que Argo CD pasa a cada Application: los del entorno y `generate.value_files` (kind_values y `values/<env>/<nombre>.yaml`)."""
    component = COMPONENTS[name]
    assert component["path"] == CHARTS[name].relative_to(ROOT).as_posix()
    return [
        ROOT / "vectra-risk-gitops" / "envs" / env / "values.yaml",
        *(ROOT / f for f in gitops().value_files(component, env)),
    ]


def helm_template(name: str, files: list[Path], *extra: str) -> list[Doc]:
    command = [tool("helm"), "template", name, str(CHARTS[name])]
    for path in files:
        command += ["-f", str(path)]
    out = subprocess.run([*command, *extra], check=True, capture_output=True, text=True).stdout
    return [d for d in yaml.safe_load_all(out) if d]


def render(name: str, env: str, *extra: str) -> list[Doc]:
    return helm_template(name, values_files(name, env), *extra)


def of_kind(docs: list[Doc], kind: str, name: str | None = None) -> Doc:
    return next(d for d in docs if d["kind"] == kind and (name is None or d["metadata"]["name"] == name))


def deployment(docs: list[Doc]) -> Doc:
    return of_kind(docs, "Deployment")


def pod(docs: list[Doc]) -> Doc:
    return deployment(docs)["spec"]["template"]["spec"]  # type: ignore[no-any-return]


def container(docs: list[Doc]) -> Doc:
    return pod(docs)["containers"][0]  # type: ignore[no-any-return]


def config_json_text(spa: list[Doc]) -> str:
    return of_kind(spa, "ConfigMap", "console-spa-config")["data"]["config.json"]  # type: ignore[no-any-return]


def config_json(spa: list[Doc]) -> Doc:
    return json.loads(config_json_text(spa))  # type: ignore[no-any-return]


def bff_env(bff: list[Doc]) -> dict[str, str]:
    return of_kind(bff, "ConfigMap", "console-bff-config")["data"]  # type: ignore[no-any-return]


def edit(docs: list[Doc], change: Callable[[list[Doc]], None]) -> list[Doc]:
    copied = copy.deepcopy(docs)
    change(copied)
    return copied


# --- conftest ----------------------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def data_files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Los datos que `console/bff/tools/chart_data.py` genera para el target `policy-chart`: el entorno y el cliente publico del realm."""
    folder = tmp_path_factory.mktemp("chart-data")
    files = {}
    for env in ENVS:
        files[env] = folder / f"{env}.json"
        files[env].write_text(json.dumps(chart_data.realm_data(env)), encoding="utf-8")
    return files


def conftest(docs: list[Doc], data: Path | None, *extra: str) -> subprocess.CompletedProcess[str]:
    command = [tool("conftest"), "test", "--policy", str(POLICIES), *extra]
    if data is not None:
        command += ["--data", str(data)]
    return subprocess.run(
        [*command, "-"],
        input=yaml.safe_dump_all(docs, sort_keys=False),
        capture_output=True,
        text=True,
        check=False,
    )


def failures(docs: list[Doc], data: Path | None) -> str:
    """Los mensajes de las dos pasadas: por documento (`main`) y con todos juntos (`console_set`)."""
    single = conftest(docs, data)
    combined = conftest(docs, data, "--combine", "--namespace", "console_set")
    return single.stdout + single.stderr + combined.stdout + combined.stderr


@pytest.mark.parametrize("env", ENVS)
@pytest.mark.parametrize("name", CHARTS)
def test_the_charts_as_is_pass_both_conftest_passes_in_every_environment(
    name: str, env: str, data_files: dict[str, Path]
) -> None:
    docs = render(name, env)
    single = conftest(docs, data_files[env])
    assert single.returncode == 0, single.stdout
    combined = conftest(docs, data_files[env], "--combine", "--namespace", "console_set")
    assert combined.returncode == 0, combined.stdout
    kinds = sorted(d["kind"] for d in docs)
    if name == "console-bff":
        assert kinds == sorted(
            [
                "ConfigMap",
                "Deployment",
                "HorizontalPodAutoscaler",
                "PodDisruptionBudget",
                "Service",
                "ServiceAccount",
                "ServiceMonitor",
            ]
        )
    else:
        assert kinds == sorted(
            ["ConfigMap", "Deployment", "PodDisruptionBudget", "Service", "ServiceAccount"]
        )


def test_without_the_data_files_the_environment_rules_fail() -> None:
    docs = render("console-bff", "prod")
    assert "data-env:" in failures(docs, None)


@pytest.mark.parametrize("name", CHARTS)
def test_without_a_digest_it_does_not_render(name: str) -> None:
    result = subprocess.run(
        [tool("helm"), "template", "x", str(CHARTS[name]), "--set", "image.digest="],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "image.digest es obligatorio" in result.stderr


def test_the_spa_without_a_hostname_does_not_render() -> None:
    result = subprocess.run(
        [tool("helm"), "template", "x", str(CHARTS["console-spa"]), "--set", "hostname="],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "hostname es obligatorio" in result.stderr


# --- una mutacion del render por regla ---------------------------------------------------------------------------------------------------


def at(doc: Any, path: list[Any]) -> Any:
    node = doc
    for key in path:
        node = node[key]
    return node


def set_at(kind: str, path: list[Any], value: Any) -> Callable[[list[Doc]], None]:
    return lambda docs: at(of_kind(docs, kind), path[:-1]).__setitem__(path[-1], value)


def drop_at(kind: str, path: list[Any]) -> Callable[[list[Doc]], None]:
    return lambda docs: at(of_kind(docs, kind), path[:-1]).pop(path[-1])


def drop_doc(kind: str) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.remove(of_kind(docs, kind))


def add_doc(doc: Doc) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.append(doc)


def edit_config_json(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
    def apply(docs: list[Doc]) -> None:
        cm = of_kind(docs, "ConfigMap", "console-spa-config")
        value = json.loads(cm["data"]["config.json"])
        change(value)
        cm["data"]["config.json"] = json.dumps(value, indent=2, sort_keys=True)
        # el checksum sigue al `config.json` mutado: se prueba la regla del contenido, no la del hash
        deployment(docs)["spec"]["template"]["metadata"]["annotations"]["checksum/config"] = hashlib.sha256(
            cm["data"]["config.json"].encode()
        ).hexdigest()

    return apply


def edit_env(name: str, value: str | None) -> Callable[[list[Doc]], None]:
    def apply(docs: list[Doc]) -> None:
        data = of_kind(docs, "ConfigMap", "console-bff-config")["data"]
        if value is None:
            data.pop(name)
        else:
            data[name] = value

    return apply


def first_volume_mount(docs: list[Doc], name: str) -> Doc:
    return next(m for m in container(docs)["volumeMounts"] if m["name"] == name)


def spa_config_with_subpath(docs: list[Doc]) -> None:
    first_volume_mount(docs, "config")["subPath"] = "config.json"


def spa_config_on_nginx_root(docs: list[Doc]) -> None:
    first_volume_mount(docs, "config")["mountPath"] = "/usr/share/nginx/html"


def spa_without_tmp_empty_dir(docs: list[Doc]) -> None:
    pod(docs)["volumes"] = [v for v in pod(docs)["volumes"] if v["name"] != "tmp"]
    container(docs)["volumeMounts"] = [m for m in container(docs)["volumeMounts"] if m["name"] != "tmp"]


def spa_tmp_not_empty_dir(docs: list[Doc]) -> None:
    for v in pod(docs)["volumes"]:
        if v["name"] == "tmp":
            v.pop("emptyDir")
            v["configMap"] = {"name": "otro"}


def spa_extra_volume(docs: list[Doc]) -> None:
    pod(docs)["volumes"].append({"name": "extra", "emptyDir": {}})


def config_not_read_only(docs: list[Doc]) -> None:
    first_volume_mount(docs, "config").pop("readOnly")


def config_volume_of_another_map(docs: list[Doc]) -> None:
    for v in pod(docs)["volumes"]:
        if v["name"] == "config":
            v["configMap"]["name"] = "otro"


def spa_config_unmounted(docs: list[Doc]) -> None:
    container(docs)["volumeMounts"] = [m for m in container(docs)["volumeMounts"] if m["name"] != "config"]


def bff_ca_from_another_map(docs: list[Doc]) -> None:
    pod(docs)["volumes"][0]["configMap"]["name"] = "otro"


def bff_env_inline(docs: list[Doc]) -> None:
    container(docs)["env"] = [{"name": "VECTRA_CASE_URL", "value": "http://x"}]


def bff_env_from_nowhere(docs: list[Doc]) -> None:
    container(docs)["envFrom"] = [{"configMapRef": {"name": "otro"}}]


def pdb_other_selector(docs: list[Doc]) -> None:
    of_kind(docs, "PodDisruptionBudget")["spec"]["selector"]["matchLabels"] = {
        "app.kubernetes.io/name": "otro"
    }


def spread_by_node(docs: list[Doc]) -> None:
    for t in pod(docs)["topologySpreadConstraints"]:
        t["topologyKey"] = "kubernetes.io/hostname"


def host_path(docs: list[Doc]) -> None:
    pod(docs)["volumes"].append({"name": "h", "hostPath": {"path": "/"}})


def spa_exempt_blank(docs: list[Doc]) -> None:
    deployment(docs)["metadata"]["annotations"]["vectra.io/hpa-exempt"] = "  "


def bff_exempt(docs: list[Doc]) -> None:
    deployment(docs)["metadata"].setdefault("annotations", {})["vectra.io/hpa-exempt"] = "no"


def hpa_with(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
    return lambda docs: change(of_kind(docs, "HorizontalPodAutoscaler")["spec"])


def service_port_added(docs: list[Doc]) -> None:
    of_kind(docs, "Service")["spec"]["ports"].append({"name": "otro", "port": 9090, "targetPort": 9090})


def service_loses_metrics(docs: list[Doc]) -> None:
    of_kind(docs, "Service")["spec"]["ports"] = [
        p for p in of_kind(docs, "Service")["spec"]["ports"] if p["name"] == "http"
    ]


def service_with_affinity(docs: list[Doc]) -> None:
    of_kind(docs, "Service")["spec"]["sessionAffinity"] = "ClientIP"


def other_namespace(kind: str) -> Callable[[list[Doc]], None]:
    return lambda docs: of_kind(docs, kind)["metadata"].__setitem__("namespace", "vectra-data")


def other_image_repository(docs: list[Doc]) -> None:
    container(docs)["image"] = "kind-registry:5000/vectra/otra@sha256:" + "1" * 64


def edit_resources(name: str, value: str) -> Callable[[list[Doc]], None]:
    def apply(docs: list[Doc]) -> None:
        group, key = name.split(".")
        container(docs)["resources"][group][key] = value

    return apply


def probe(kind: str, path: str) -> Callable[[list[Doc]], None]:
    return lambda docs: container(docs)[kind]["httpGet"].__setitem__("path", path)


def probe_port(kind: str, port: str) -> Callable[[list[Doc]], None]:
    return lambda docs: container(docs)[kind]["httpGet"].__setitem__("port", port)


def startup_probe(docs: list[Doc]) -> None:
    container(docs)["startupProbe"] = {"httpGet": {"path": "/healthz", "port": "http"}}


def sa_automount(docs: list[Doc]) -> None:
    of_kind(docs, "ServiceAccount")["automountServiceAccountToken"] = True


def no_pod_labels_sa(docs: list[Doc]) -> None:
    pod(docs)["serviceAccountName"] = "default"


def servicemonitor_endpoint(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
    return lambda docs: change(of_kind(docs, "ServiceMonitor")["spec"]["endpoints"][0])


def secret_doc(namespace: str) -> Doc:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "x", "namespace": namespace},
        "stringData": {"k": "v"},
    }


def foreign(kind: str, group: str, namespace: str) -> Doc:
    return {"apiVersion": group, "kind": kind, "metadata": {"name": "x", "namespace": namespace}, "spec": {}}


def rule(kind: str, group: str, namespace: str) -> Callable[[list[Doc]], None]:
    return add_doc(foreign(kind, group, namespace))


def configmap_extra_key(docs: list[Doc]) -> None:
    of_kind(docs, "ConfigMap")["data"]["otra.json"] = "{}"


# (chart, env, regla que debe fallar, mutacion). El render sin tocar pasa (`test_the_charts_as_is_...`).
CASES: list[tuple[str, str, str, Callable[[list[Doc]], None]]] = [
    # --- BFF: replicas, HPA y estrategia (NFR-U10-10; INF-U10-06)
    ("console-bff", "prod", "replicas", set_at("Deployment", ["spec", "replicas"], 1)),
    ("console-bff", "prod", "replicas", set_at("Deployment", ["spec", "replicas"], 3)),
    ("console-bff", "prod", "hpa-presence", drop_doc("HorizontalPodAutoscaler")),
    ("console-bff", "kind", "hpa-presence", drop_doc("HorizontalPodAutoscaler")),
    ("console-bff", "prod", "hpa-bff", hpa_with(lambda s: s.__setitem__("minReplicas", 1))),
    ("console-bff", "prod", "hpa-bff", hpa_with(lambda s: s.__setitem__("maxReplicas", 5))),
    ("console-bff", "staging", "hpa-bff", hpa_with(lambda s: s.__setitem__("maxReplicas", 2))),
    ("console-bff", "kind", "hpa-bff", hpa_with(lambda s: s.__setitem__("maxReplicas", 6))),
    ("console-bff", "kind", "hpa-bff", hpa_with(lambda s: s.__setitem__("minReplicas", 1))),
    (
        "console-bff",
        "prod",
        "hpa-bff",
        hpa_with(lambda s: s["metrics"][0]["resource"]["target"].__setitem__("averageUtilization", 80)),
    ),
    (
        "console-bff",
        "prod",
        "hpa-bff",
        hpa_with(lambda s: s["behavior"]["scaleUp"].__setitem__("stabilizationWindowSeconds", 30)),
    ),
    (
        "console-bff",
        "prod",
        "hpa-bff",
        hpa_with(lambda s: s["behavior"]["scaleDown"].__setitem__("stabilizationWindowSeconds", 60)),
    ),
    ("console-bff", "prod", "hpa-bff", hpa_with(lambda s: s["scaleTargetRef"].__setitem__("name", "otro"))),
    ("console-bff", "prod", "exempt", bff_exempt),
    (
        "console-bff",
        "prod",
        "rollout",
        set_at("Deployment", ["spec", "strategy", "rollingUpdate", "maxUnavailable"], 1),
    ),
    (
        "console-bff",
        "prod",
        "rollout",
        set_at("Deployment", ["spec", "strategy", "rollingUpdate", "maxSurge"], 2),
    ),
    # --- SPA: replicas fijas con la exencion (NFR-U10-12)
    ("console-spa", "prod", "replicas", set_at("Deployment", ["spec", "replicas"], 1)),
    ("console-spa", "kind", "replicas", set_at("Deployment", ["spec", "replicas"], 3)),
    (
        "console-spa",
        "prod",
        "exempt",
        drop_at("Deployment", ["metadata", "annotations", "vectra.io/hpa-exempt"]),
    ),
    ("console-spa", "prod", "exempt", spa_exempt_blank),
    (
        "console-spa",
        "prod",
        "hpa-presence",
        add_doc(
            {
                "apiVersion": "autoscaling/v2",
                "kind": "HorizontalPodAutoscaler",
                "metadata": {"name": "console-spa", "namespace": "vectra-edge"},
                "spec": {},
            }
        ),
    ),
    (
        "console-spa",
        "prod",
        "rollout",
        set_at("Deployment", ["spec", "strategy", "rollingUpdate", "maxSurge"], 1),
    ),
    (
        "console-spa",
        "prod",
        "rollout",
        set_at("Deployment", ["spec", "strategy", "rollingUpdate", "maxUnavailable"], 1),
    ),
    # --- SPA: config.json y volumenes
    ("console-spa", "prod", "no-subpath", spa_config_with_subpath),
    ("console-spa", "prod", "spa-volumes", spa_config_on_nginx_root),
    ("console-spa", "prod", "spa-volumes", spa_without_tmp_empty_dir),
    ("console-spa", "prod", "spa-volumes", spa_tmp_not_empty_dir),
    ("console-spa", "prod", "spa-volumes", spa_extra_volume),
    ("console-spa", "prod", "read-only-mounts", config_not_read_only),
    ("console-spa", "prod", "config-mounted", config_volume_of_another_map),
    ("console-spa", "prod", "config-mounted", spa_config_unmounted),
    (
        "console-spa",
        "prod",
        "checksum-present",
        drop_at("Deployment", ["spec", "template", "metadata", "annotations", "checksum/config"]),
    ),
    (
        "console-spa",
        "prod",
        "checksum-spa",
        set_at("Deployment", ["spec", "template", "metadata", "annotations", "checksum/config"], "0" * 64),
    ),
    (
        "console-spa",
        "prod",
        "config-json-keys",
        edit_config_json(lambda c: c.__setitem__("version_poll_seconds", 60)),
    ),
    ("console-spa", "prod", "config-json-keys", edit_config_json(lambda c: c.pop("grafana"))),
    (
        "console-spa",
        "prod",
        "config-json-keys",
        edit_config_json(lambda c: c["oidc"].__setitem__("scope", "openid")),
    ),
    (
        "console-spa",
        "prod",
        "config-json-keys",
        edit_config_json(lambda c: c["grafana"].__setitem__("other", "x")),
    ),
    ("console-spa", "prod", "config-json-keys", configmap_extra_key),
    (
        "console-spa",
        "prod",
        "config-json-no-secrets",
        edit_config_json(lambda c: c["oidc"].__setitem__("client_secret", "x")),
    ),
    (
        "console-spa",
        "prod",
        "config-json-no-secrets",
        edit_config_json(lambda c: c["oidc"].__setitem__("api_key", "x")),
    ),
    (
        "console-spa",
        "prod",
        "config-json-no-secrets",
        edit_config_json(
            lambda c: c["grafana"].__setitem__("bias_dashboard_uid", "-----BEGIN PRIVATE KEY-----")
        ),
    ),
    (
        "console-spa",
        "prod",
        "config-json-no-secrets",
        edit_config_json(
            lambda c: c["grafana"].__setitem__(
                "bias_dashboard_uid", "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ4In0.c2ln"
            )
        ),
    ),
    (
        "console-spa",
        "prod",
        "config-json-realm",
        edit_config_json(lambda c: c["oidc"].__setitem__("client_id", "console")),
    ),
    (
        "console-spa",
        "prod",
        "config-json-realm",
        edit_config_json(
            lambda c: c.__setitem__("redirect_uri", "https://vectra.banco.internal/auth/callback")
        ),
    ),
    (
        "console-spa",
        "prod",
        "config-json-realm",
        edit_config_json(
            lambda c: c.__setitem__("stepup_redirect_uri", "https://vectra.banco.internal/stepup")
        ),
    ),
    (
        "console-spa",
        "kind",
        "config-json-realm",
        edit_config_json(
            lambda c: c.__setitem__("redirect_uri", "https://vectra.staging.banco.internal/callback")
        ),
    ),
    # --- BFF: variables, CA y sondas
    ("console-bff", "prod", "bff-env", edit_env("VECTRA_BIAS_URL", None)),
    (
        "console-bff",
        "prod",
        "bff-env",
        edit_env("VECTRA_CASE_URL", "http://case-service.vectra-app.svc.cluster.local:8081"),
    ),
    ("console-bff", "prod", "bff-env", edit_env("CASE_READ_TIMEOUT_SECONDS", "9")),
    (
        "console-bff",
        "prod",
        "bff-env",
        edit_env("VECTRA_OIDC_ISSUER", "http://vectra.banco.internal/auth/realms/vectra"),
    ),
    (
        "console-bff",
        "prod",
        "bff-env",
        edit_env("VECTRA_JWKS_URL", "http://keycloak.vectra-identity.svc:8443/certs"),
    ),
    ("console-bff", "prod", "bff-env", edit_env("VECTRA_CA_BUNDLE", None)),
    ("console-bff", "prod", "bff-ca", bff_ca_from_another_map),
    ("console-bff", "prod", "bff-ca", bff_env_from_nowhere),
    ("console-bff", "prod", "no-inline-env", bff_env_inline),
    ("console-bff", "prod", "probes", probe("livenessProbe", "/livez")),
    ("console-bff", "prod", "probes", probe("readinessProbe", "/ready")),
    ("console-bff", "prod", "probes", probe_port("livenessProbe", "http")),
    ("console-spa", "prod", "probes", probe("readinessProbe", "/")),
    ("console-spa", "prod", "probes", probe_port("livenessProbe", "metrics")),
    ("console-bff", "prod", "probes", startup_probe),
    (
        "console-bff",
        "prod",
        "shutdown",
        set_at("Deployment", ["spec", "template", "spec", "terminationGracePeriodSeconds"], 10),
    ),
    ("console-bff", "prod", "shutdown", lambda docs: container(docs).pop("lifecycle")),
    (
        "console-bff",
        "prod",
        "shutdown",
        lambda docs: container(docs)["lifecycle"]["preStop"]["sleep"].__setitem__("seconds", 1),
    ),
    # --- las dos: prioridad, criticidad, PDB, spread y recursos
    (
        "console-bff",
        "prod",
        "priority",
        set_at("Deployment", ["spec", "template", "spec", "priorityClassName"], "vectra-normal"),
    ),
    (
        "console-spa",
        "prod",
        "priority",
        set_at("Deployment", ["spec", "template", "spec", "priorityClassName"], "vectra-high"),
    ),
    (
        "console-bff",
        "prod",
        "priority",
        drop_at("Deployment", ["spec", "template", "spec", "priorityClassName"]),
    ),
    (
        "console-bff",
        "prod",
        "criticality",
        drop_at("Deployment", ["metadata", "labels", "vectra.io/criticality"]),
    ),
    (
        "console-spa",
        "prod",
        "criticality",
        set_at("Deployment", ["metadata", "labels", "vectra.io/criticality"], "high"),
    ),
    ("console-bff", "prod", "pdb", drop_at("PodDisruptionBudget", ["spec", "minAvailable"])),
    ("console-spa", "prod", "pdb", set_at("PodDisruptionBudget", ["spec", "minAvailable"], 2)),
    ("console-spa", "prod", "pdb", pdb_other_selector),
    ("console-bff", "prod", "inventory", drop_doc("PodDisruptionBudget")),
    ("console-spa", "prod", "inventory", drop_doc("PodDisruptionBudget")),
    ("console-bff", "prod", "spread", spread_by_node),
    (
        "console-spa",
        "prod",
        "spread",
        drop_at("Deployment", ["spec", "template", "spec", "topologySpreadConstraints"]),
    ),
    ("console-bff", "prod", "resources-bff", edit_resources("requests.cpu", "100m")),
    ("console-bff", "prod", "resources-bff", edit_resources("limits.memory", "1Gi")),
    ("console-bff", "prod", "resources-bff", edit_resources("limits.cpu", "2")),
    ("console-bff", "staging", "resources-bff", edit_resources("requests.memory", "128Mi")),
    ("console-bff", "prod", "resources-bff", edit_resources("requests.memory", "512Mi")),
    ("console-bff", "kind", "resources-bff", edit_resources("requests.memory", "256Mi")),
    ("console-bff", "kind", "resources-bff", edit_resources("requests.memory", "64Mi")),
    ("console-spa", "prod", "resources-spa", edit_resources("requests.memory", "64Mi")),
    ("console-spa", "prod", "resources-spa", edit_resources("limits.cpu", "1")),
    ("console-spa", "kind", "resources-spa", edit_resources("requests.memory", "16Mi")),
    # --- imagen, usuario y endurecimiento
    (
        "console-bff",
        "prod",
        "image",
        set_at(
            "Deployment",
            ["spec", "template", "spec", "containers", 0, "image"],
            "kind-registry:5000/vectra/console-bff:dev",
        ),
    ),
    (
        "console-spa",
        "prod",
        "image",
        set_at(
            "Deployment",
            ["spec", "template", "spec", "containers", 0, "image"],
            "kind-registry:5000/vectra/console-spa@sha256:abc",
        ),
    ),
    ("console-spa", "prod", "image", other_image_repository),
    (
        "console-bff",
        "prod",
        "hardening",
        drop_at("Deployment", ["spec", "template", "spec", "securityContext", "runAsNonRoot"]),
    ),
    (
        "console-bff",
        "prod",
        "hardening",
        set_at("Deployment", ["spec", "template", "spec", "securityContext", "runAsUser"], 0),
    ),
    (
        "console-spa",
        "prod",
        "hardening",
        set_at("Deployment", ["spec", "template", "spec", "securityContext", "runAsUser"], 65532),
    ),
    (
        "console-spa",
        "prod",
        "hardening",
        set_at("Deployment", ["spec", "template", "spec", "securityContext", "runAsGroup"], 0),
    ),
    (
        "console-bff",
        "prod",
        "hardening",
        drop_at("Deployment", ["spec", "template", "spec", "securityContext", "seccompProfile"]),
    ),
    (
        "console-bff",
        "prod",
        "hardening",
        set_at(
            "Deployment",
            ["spec", "template", "spec", "containers", 0, "securityContext", "readOnlyRootFilesystem"],
            False,
        ),
    ),
    (
        "console-spa",
        "prod",
        "hardening",
        set_at(
            "Deployment",
            ["spec", "template", "spec", "containers", 0, "securityContext", "readOnlyRootFilesystem"],
            False,
        ),
    ),
    (
        "console-spa",
        "prod",
        "hardening",
        set_at(
            "Deployment",
            ["spec", "template", "spec", "containers", 0, "securityContext", "allowPrivilegeEscalation"],
            True,
        ),
    ),
    ("console-bff", "prod", "hardening", host_path),
    (
        "console-bff",
        "prod",
        "pod-token",
        set_at("Deployment", ["spec", "template", "spec", "automountServiceAccountToken"], True),
    ),
    ("console-spa", "prod", "pod-token", sa_automount),
    ("console-bff", "prod", "service-account-name", no_pod_labels_sa),
    ("console-bff", "prod", "namespace", other_namespace("Deployment")),
    ("console-spa", "prod", "namespace", other_namespace("Service")),
    ("console-spa", "prod", "namespace", other_namespace("ConfigMap")),
    # --- Service y ServiceMonitor
    ("console-bff", "prod", "service-ports", service_loses_metrics),
    ("console-bff", "prod", "service-ports", set_at("Service", ["spec", "ports", 0, "port"], 80)),
    ("console-spa", "prod", "service-ports", service_port_added),
    ("console-bff", "prod", "service-ports", service_with_affinity),
    ("console-bff", "prod", "service-ports", set_at("Service", ["spec", "selector"], {"app": "console-bff"})),
    ("console-bff", "prod", "monitor", servicemonitor_endpoint(lambda e: e.__setitem__("port", "http"))),
    ("console-bff", "prod", "monitor", servicemonitor_endpoint(lambda e: e.pop("honorLabels"))),
    # --- lo que no se declara en ninguno de los dos charts
    ("console-bff", "prod", "forbidden-kinds", add_doc(secret_doc("vectra-app"))),
    ("console-spa", "prod", "forbidden-kinds", add_doc(secret_doc("vectra-edge"))),
    (
        "console-bff",
        "prod",
        "forbidden-kinds",
        rule("ExternalSecret", "external-secrets.io/v1", "vectra-app"),
    ),
    (
        "console-bff",
        "prod",
        "forbidden-kinds",
        rule("PrometheusRule", "monitoring.coreos.com/v1", "vectra-app"),
    ),
    ("console-spa", "prod", "forbidden-kinds", rule("Server", "policy.linkerd.io/v1beta3", "vectra-edge")),
    (
        "console-spa",
        "prod",
        "forbidden-kinds",
        rule("HTTPRoute", "gateway.networking.k8s.io/v1", "vectra-edge"),
    ),
    (
        "console-bff",
        "prod",
        "forbidden-kinds",
        rule("AuthorizationPolicy", "policy.linkerd.io/v1alpha1", "vectra-app"),
    ),
    ("console-bff", "prod", "forbidden-kinds", rule("NetworkPolicy", "networking.k8s.io/v1", "vectra-app")),
]


@pytest.mark.parametrize(
    ("name", "env", "rule_name", "mutation"),
    CASES,
    ids=[f"{n}-{e}-{r}-{i}" for i, (n, e, r, _) in enumerate(CASES)],
)
def test_each_rule_fails_with_a_mutation_of_the_render(
    name: str, env: str, rule_name: str, mutation: Callable[[list[Doc]], None], data_files: dict[str, Path]
) -> None:
    docs = render(name, env)
    assert failures(docs, data_files[env]).count(f"{rule_name}:") == 0, "el render sin tocar debe pasar"
    mutated = edit(docs, mutation)
    assert f"{rule_name}:" in failures(mutated, data_files[env]), f"la mutacion no hizo fallar {rule_name}"


def test_every_rule_of_the_policies_has_a_case() -> None:
    declared = {
        m
        for p in sorted(POLICIES.glob("*.rego"))
        for m in re.findall(r"^# regla: ([a-z-]+)$", p.read_text(encoding="utf-8"), flags=re.M)
    }
    covered = {rule_name for _, _, rule_name, _ in CASES}
    assert declared and declared - {"data-env"} <= covered, sorted(declared - covered)
    # y cada mensaje de `deny` empieza por una regla declarada
    messages = {
        m
        for p in sorted(POLICIES.glob("*.rego"))
        for m in re.findall(r'msg := (?:sprintf\()?"([a-z-]+):', p.read_text(encoding="utf-8"))
    }
    assert messages <= declared | {"data-env"}, sorted(messages - declared)


# --- el mundo cerrado: chart -> SPA -> realm de U2 -> gateway de U2 (CA-3) ---------------------------------------------------------------


def gateway_hostname(env: str) -> str:
    return load(f"identity-edge/gateway/values/{env}.yaml")["hostname"]  # type: ignore[no-any-return]


def keycloak_hostname(env: str) -> str:
    return load(f"identity-edge/keycloak/values/{env}.yaml")["vectra"]["publicHostname"]  # type: ignore[no-any-return]


def realm_public_client(env: str) -> Doc:
    clients = [
        c
        for c in load(f"identity-edge/keycloak/realm/realm.{env}.yaml")["clients"]
        if c["clientId"] == "vectra-console"
    ]
    assert len(clients) == 1 and clients[0]["publicClient"] is True
    return clients[0]  # type: ignore[no-any-return]


def backend(route: str) -> Doc:
    return next(r for r in ROUTES["routes"] if r["name"] == route)["backend"]  # type: ignore[no-any-return]


def host_of(url: str) -> str:
    return re.match(r"https?://([^/:]+)", url).group(1)  # type: ignore[union-attr]


def origin_of(url: str) -> str:
    return re.match(r"(https?://[^/]+)", url).group(1)  # type: ignore[union-attr]


def world_problems(env: str, spa: list[Doc], bff: list[Doc]) -> list[str]:
    """Todo lo que no cierra entre el chart, la SPA, el realm y el gateway. Vacia en el render sin tocar; cada defecto del plan la llena."""
    problems: list[str] = []
    cfg = config_json(spa)
    if set(cfg) != {"oidc", "redirect_uri", "stepup_redirect_uri", "grafana"}:
        problems.append(f"claves de config.json: {sorted(cfg)}")
    if set(cfg.get("oidc", {})) != {"authority", "client_id"} or set(cfg.get("grafana", {})) != {
        "bias_dashboard_uid"
    }:
        problems.append("claves anidadas de config.json")
    realm = realm_public_client(env)
    hostname = gateway_hostname(env)
    if keycloak_hostname(env) != hostname:
        problems.append("el hostname del gateway y el de Keycloak difieren")  # no es del chart: U2 se rompio
    if cfg["oidc"]["client_id"] != realm["clientId"]:
        problems.append(f"client_id {cfg['oidc']['client_id']} != {realm['clientId']}")
    registered = {u.replace("$(env:PUBLIC_HOSTNAME)", keycloak_hostname(env)) for u in realm["redirectUris"]}
    if {cfg["redirect_uri"], cfg["stepup_redirect_uri"]} != registered:
        problems.append("los redirect_uri no son los del realm")
    authority = f"https://{hostname}{ROUTES['jwt']['issuer_path']}"
    if cfg["oidc"]["authority"] != authority:
        problems.append(f"authority {cfg['oidc']['authority']} != {authority}")
    origins = {
        origin_of(u) for u in (cfg["oidc"]["authority"], cfg["redirect_uri"], cfg["stepup_redirect_uri"])
    }
    if origins != {f"https://{hostname}"}:
        problems.append(f"origenes distintos: {sorted(origins)}")
    env_vars = bff_env(bff)
    if env_vars["VECTRA_OIDC_ISSUER"] != cfg["oidc"]["authority"]:
        problems.append("VECTRA_OIDC_ISSUER != authority de la SPA")
    if env_vars["VECTRA_JWKS_URL"] != ROUTES["jwt"]["jwks_uri"]:
        problems.append("VECTRA_JWKS_URL != jwt.jwks_uri de routes.yaml")
    if set(env_vars) != {*bff_app.REQUIRED, *bff_app.OPTIONAL, telemetry.ENDPOINT_ENV}:
        problems.append(f"variables del BFF: {sorted(env_vars)}")
    constants = {n for n in dir(bff_config) if n.isupper()}
    if {n for n in env_vars if n in constants or n.removeprefix("VECTRA_") in constants}:
        problems.append("una constante de config.py es una variable")
    targets = flows_targets()
    for key, flow_id in URL_FLOWS.items():
        service, port = targets[flow_id]
        namespace = FLOWS["workloads"][service]["ns"]
        if env_vars.get(key) != f"http://{service}.{namespace}.svc.cluster.local:{port}":
            problems.append(f"{key} = {env_vars.get(key)}")
    return problems


URL_FLOWS = {
    "VECTRA_CASE_URL": "F10",
    "VECTRA_GOVERNANCE_URL": "F11",
    "VECTRA_EXPLAINABILITY_URL": "F12",
    "VECTRA_REGISTRY_URL": "F13",
    "VECTRA_BIAS_URL": "F14",
}


def flows_targets() -> dict[str, tuple[str, int]]:
    """F10 a F14: `(workload, puerto)` leidos de `flows.yaml`."""
    out: dict[str, tuple[str, int]] = {}
    for flow_id in URL_FLOWS.values():
        (flow,) = [f for f in FLOWS["flows"] if f["id"] == flow_id]
        assert flow["from"] == ["console-bff"] and len(flow["to"]) == 1
        out[flow_id] = (flow["to"][0], flow["port"])
    return out


@pytest.mark.parametrize("env", ENVS)
def test_the_closed_world_holds_in_every_environment(env: str) -> None:
    assert world_problems(env, render("console-spa", env), render("console-bff", env)) == []


@pytest.mark.parametrize("env", ENVS)
def test_config_json_has_exactly_the_keys_of_the_spa_schema_and_the_realm_values(env: str) -> None:
    cfg = config_json(render("console-spa", env))
    realm = realm_public_client(env)
    hostname = gateway_hostname(env)
    assert cfg == {
        "oidc": {"authority": f"https://{hostname}/auth/realms/vectra", "client_id": "vectra-console"},
        "redirect_uri": f"https://{hostname}/callback",
        "stepup_redirect_uri": f"https://{hostname}/stepup-callback",
        "grafana": {"bias_dashboard_uid": "vectra-bias"},
    }
    assert realm["clientId"] == cfg["oidc"]["client_id"]
    assert ":" not in hostname  # kind publica el 443 (`platform/kind/cluster.yaml`): sin puerto


def test_the_realm_data_of_conftest_is_what_the_realm_files_say() -> None:
    for env in ENVS:
        data = chart_data.realm_data(env)
        realm = realm_public_client(env)
        assert data["realm"]["client_id"] == realm["clientId"]
        assert sorted(data["realm"]["redirect_uris"]) == sorted(
            u.replace("$(env:PUBLIC_HOSTNAME)", keycloak_hostname(env)) for u in realm["redirectUris"]
        )


def test_the_bff_has_no_client_in_the_realm_it_uses_the_users_token() -> None:
    assert "clientId: console-bff" not in (ROOT / "identity-edge/keycloak/realm/realm.kind.yaml").read_text(
        encoding="utf-8"
    )


def test_the_chart_audience_is_not_a_variable() -> None:
    """El plan dice «ConfigMap de URLs y audiencias», pero el BFF no lee ninguna variable de audiencia: U0 valida `aud = console-bff` (el nombre del servicio)."""
    names = set(bff_env(render("console-bff", "prod")))
    assert not {n for n in names if "AUD" in n}


def _world_with(
    env: str, change_spa: Callable[[list[Doc]], None] | None, change_bff: Callable[[list[Doc]], None] | None
) -> list[str]:
    spa, bff = render("console-spa", env), render("console-bff", env)
    if change_spa:
        change_spa(spa)
    if change_bff:
        change_bff(bff)
    return world_problems(env, spa, bff)


WORLD_CASES: list[tuple[str, Callable[[list[Doc]], None] | None, Callable[[list[Doc]], None] | None]] = [
    (
        "version_poll_seconds de mas",
        edit_config_json(lambda c: c.__setitem__("version_poll_seconds", 60)),
        None,
    ),
    ("sin grafana", edit_config_json(lambda c: c.pop("grafana")), None),
    ("client_id console", edit_config_json(lambda c: c["oidc"].__setitem__("client_id", "console")), None),
    (
        "redirect_uri con /auth/callback",
        edit_config_json(
            lambda c: c.__setitem__("redirect_uri", c["redirect_uri"].replace("/callback", "/auth/callback"))
        ),
        None,
    ),
    (
        "authority sin issuer_path",
        edit_config_json(
            lambda c: c["oidc"].__setitem__(
                "authority", c["oidc"]["authority"].replace("/auth/realms/vectra", "")
            )
        ),
        None,
    ),
    (
        "issuer keycloak-admin",
        None,
        edit_env(
            "VECTRA_OIDC_ISSUER",
            "https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra",
        ),
    ),
    ("sin VECTRA_BIAS_URL", None, edit_env("VECTRA_BIAS_URL", None)),
    (
        "VECTRA_CASE_URL al 8081",
        None,
        edit_env("VECTRA_CASE_URL", "http://case-service.vectra-app.svc.cluster.local:8081"),
    ),
    (
        "VECTRA_CASE_URL a otro servicio",
        None,
        edit_env("VECTRA_CASE_URL", "http://case-worker.vectra-app.svc.cluster.local:8080"),
    ),
    ("CASE_READ_TIMEOUT_SECONDS como variable", None, edit_env("CASE_READ_TIMEOUT_SECONDS", "9")),
    (
        "JWKS distinto de routes.yaml",
        None,
        edit_env("VECTRA_JWKS_URL", "https://keycloak-admin.vectra-identity.svc.cluster.local:8443/certs"),
    ),
]


@pytest.mark.parametrize(("label", "change_spa", "change_bff"), WORLD_CASES, ids=[c[0] for c in WORLD_CASES])
def test_the_closed_world_breaks_with_each_defect_of_the_plan(
    label: str, change_spa: Callable[[list[Doc]], None] | None, change_bff: Callable[[list[Doc]], None] | None
) -> None:
    assert _world_with("prod", change_spa, change_bff), label


def test_the_closed_world_breaks_with_the_hostname_of_staging_in_the_kind_values() -> None:
    """El hostname de `values/staging/console-spa.yaml` en lugar del de kind: el `authority`, los URI y el host del gateway ya no cierran."""
    staging = ROOT / "vectra-risk-gitops" / "values" / "staging" / "console-spa.yaml"
    files = [f for f in values_files("console-spa", "kind") if f.name != "console-spa.yaml"] + [staging]
    spa = helm_template("console-spa", files)
    assert world_problems("kind", spa, render("console-bff", "kind"))


def test_the_bff_issuer_of_every_environment_is_the_public_one_and_the_jwks_the_internal_one() -> None:
    for env in ENVS:
        env_vars = bff_env(render("console-bff", env))
        assert env_vars["VECTRA_OIDC_ISSUER"] == f"https://{gateway_hostname(env)}/auth/realms/vectra"
        assert env_vars["VECTRA_JWKS_URL"] == ROUTES["jwt"]["jwks_uri"]
        assert host_of(env_vars["VECTRA_JWKS_URL"]) == "keycloak.vectra-identity.svc"
        assert "keycloak-admin" not in env_vars["VECTRA_OIDC_ISSUER"]


@pytest.mark.parametrize("env", ENVS)
def test_the_ca_bundle_is_a_file_of_the_read_only_volume_of_vectra_internal_ca(env: str) -> None:
    bff = render("console-bff", env)
    path = Path(bff_env(bff)["VECTRA_CA_BUNDLE"])
    mounts = [m for m in container(bff)["volumeMounts"] if m["mountPath"] == str(path.parent)]
    assert len(mounts) == 1 and mounts[0]["readOnly"] is True
    volume = next(v for v in pod(bff)["volumes"] if v["name"] == mounts[0]["name"])
    assert volume["configMap"]["name"] == "vectra-internal-ca"
    assert [i["path"] for i in volume["configMap"]["items"]] == [path.name]
    assert any(url.startswith("https://") for url in (bff_env(bff)["VECTRA_JWKS_URL"],))


def test_no_constants_of_config_py_is_an_environment_variable() -> None:
    constants = {n for n in dir(bff_config) if n.isupper()}
    assert {
        "CASE_READ_TIMEOUT_SECONDS",
        "BREAKER_WINDOW_SIZE",
        "REPLICAS",
        "CONNECTIONS_PER_REPLICA",
    } <= constants
    for env in ENVS:
        names = set(bff_env(render("console-bff", env)))
        assert not names & constants and not {n.removeprefix("VECTRA_") for n in names} & constants
        assert not container(render("console-bff", env)).get("env")


def test_the_env_variables_are_exactly_required_optional_and_the_telemetry_one() -> None:
    names = set(bff_env(render("console-bff", "prod")))
    assert (
        names == {*bff_app.REQUIRED, *bff_app.OPTIONAL, telemetry.ENDPOINT_ENV}
        and telemetry.ENDPOINT_ENV == "VECTRA_OTLP_ENDPOINT"
    )


def test_the_probes_paths_are_routes_that_ops_server_serves() -> None:
    served = {r.path for r in create_ops_app().routes}  # type: ignore[attr-defined]
    bff = render("console-bff", "prod")
    assert {container(bff)[p]["httpGet"]["path"] for p in ("readinessProbe", "livenessProbe")} == {
        "/readyz",
        "/healthz",
    }
    assert {"/readyz", "/healthz", "/metrics"} <= served
    ports = {p["name"]: p["containerPort"] for p in container(bff)["ports"]}
    assert (
        ports == {"http": 8080, "metrics": 8081}
        and container(bff)["livenessProbe"]["httpGet"]["port"] == "metrics"
    )


# --- nombres, flujos y rutas (INF-U10-04) --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "route", "flow"),
    [("console-spa", "spa", "F02"), ("console-bff", "console", "F03")],
    ids=["spa", "bff"],
)
def test_names_namespaces_labels_and_ports_are_the_ones_of_flows_and_routes(
    name: str, route: str, flow: str
) -> None:
    workload = FLOWS["workloads"][name]
    gateway = backend(route)
    docs = render(name, "prod")
    assert workload == {"ns": gateway["namespace"], "sa": name, "name": name} and gateway["service"] == name
    (declared,) = [f for f in FLOWS["flows"] if f["id"] == flow]
    assert declared["to"] == [name] and declared["port"] == gateway["port"] == 8080
    for kind in ("Deployment", "Service", "ServiceAccount", "PodDisruptionBudget"):
        doc = of_kind(docs, kind)
        assert doc["metadata"]["name"] == name and doc["metadata"]["namespace"] == workload["ns"]
        assert doc["metadata"]["labels"]["app.kubernetes.io/name"] == name
    assert (
        pod(docs)["serviceAccountName"]
        == workload["sa"]
        == of_kind(docs, "ServiceAccount")["metadata"]["name"]
    )
    assert deployment(docs)["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/name"] == name
    ports = {p["port"] for p in of_kind(docs, "Service")["spec"]["ports"]}
    assert gateway["port"] in ports and ports == ({8080, 8081} if name == "console-bff" else {8080})
    assert deployment(docs)["spec"]["selector"]["matchLabels"] == {"app.kubernetes.io/name": name}
    assert COMPONENTS[name]["namespace"] == workload["ns"] and COMPONENTS[name]["wave"] == 5


def test_names_the_spa_config_mount_is_the_directory_that_nginx_uses_for_config_json() -> None:
    mount = first_volume_mount(render("console-spa", "prod"), "config")
    nginx = NGINX_CONF.read_text(encoding="utf-8")
    (alias,) = re.findall(r"location = /config\.json \{[^}]*alias ([^;]+);", nginx)
    assert alias == f"{mount['mountPath']}/config.json" and "subPath" not in mount
    assert not mount["mountPath"].startswith("/usr/share/nginx/html") and mount["readOnly"] is True
    tmp = next(m for m in container(render("console-spa", "prod"))["volumeMounts"] if m["name"] == "tmp")
    assert tmp["mountPath"] == "/tmp" and re.search(r"^pid /tmp/", nginx, flags=re.M)


def test_flows_f10_to_f14_are_the_five_urls_of_the_bff_and_f02_f03_f50_f60_f61_exist() -> None:
    targets = flows_targets()
    assert [t[0] for t in targets.values()] == [
        "case-service",
        "governance-service",
        "explainability-service",
        "decision-registry-service",
        "bias-monitoring-service",
    ]
    assert {port for _, port in targets.values()} == {8080}
    ids = {f["id"] for f in FLOWS["flows"]}
    assert {"F02", "F03", "F10", "F11", "F12", "F13", "F14", "F50", "F60", "F61"} <= ids
    f50 = next(f for f in FLOWS["flows"] if f["id"] == "F50")
    assert "console-bff" in f50["from"] and f50["port"] == 8443
    f60 = [f for f in FLOWS["flows"] if f["id"] == "F60" and f["port"] == 8081]
    assert any({"ns:vectra-app", "ns:vectra-edge"} <= set(f["to"]) for f in f60)
    f61 = next(f for f in FLOWS["flows"] if f["id"] == "F61")
    assert {"ns:vectra-app", "ns:vectra-edge"} <= set(f61["from"])
    for env in ENVS:
        url = bff_env(render("console-bff", env))["VECTRA_OTLP_ENDPOINT"]
        assert url == "http://otel-collector.vectra-observability.svc.cluster.local:4317"


def test_flows_the_gateway_routes_f02_and_f03_name_the_two_services() -> None:
    by_name = {r["name"]: r for r in ROUTES["routes"]}
    assert by_name["spa"]["flow"] == "F02" and by_name["console"]["flow"] == "F03"
    assert by_name["spa"]["affinity"]["cookie"] == "vectra-spa-route"
    assert by_name["console"]["auth"]["claims"][0] == {"name": "azp", "values": ["vectra-console"]}


def test_forbidden_cases_of_inf_u10_04_are_in_the_network_suite() -> None:
    cases = {
        (f["from"], f["to"], f["port"])
        for f in load("platform/network/forbidden.yaml")["forbidden"]
        if f["id"] == "U10"
    }
    assert cases == {
        ("console-spa", "case-service", 8080),
        ("console-spa", "console-bff", 8080),
        ("console-bff", "case-db", 5432),
        ("console-bff", "predictor", 80),
    }
    x09 = {
        (f["from"], f["to"]) for f in load("platform/network/forbidden.yaml")["forbidden"] if f["id"] == "X09"
    }
    assert ("external:banco", "console-bff") in x09
    # SPA -> un servicio de vectra-app, BFF -> vectra-data, BFF -> vectra-serving
    assert (
        FLOWS["workloads"]["case-service"]["ns"] == "vectra-app"
        and FLOWS["workloads"]["case-db"]["ns"] == "vectra-data"
    )
    assert FLOWS["workloads"]["predictor"]["ns"] == "vectra-serving"


def test_flows_the_generated_servers_select_the_pods_of_the_charts() -> None:
    for name, namespace, generated in (
        ("console-spa", "vectra-edge", "vectra-edge.yaml"),
        ("console-bff", "vectra-app", "vectra-app.yaml"),
    ):
        docs = list(
            yaml.safe_load_all(
                (ROOT / "platform/network/generated/kind" / generated).read_text(encoding="utf-8")
            )
        )
        (server,) = [
            d for d in docs if d and d["kind"] == "Server" and d["metadata"]["name"] == f"{name}-8080"
        ]
        assert server["metadata"]["namespace"] == namespace and server["spec"]["port"] == 8080
        labels = deployment(render(name, "kind"))["spec"]["template"]["metadata"]["labels"]
        assert server["spec"]["podSelector"]["matchLabels"].items() <= labels.items()


def test_flows_the_bff_service_has_no_session_affinity_and_no_persistent_volume() -> None:
    """BR-U10-02: el BFF no tiene estado. Sin volumen persistente ni afinidad de sesion en su `Service`; la afinidad de la SPA es la cookie `vectra-spa-route` del gateway."""
    bff = render("console-bff", "prod")
    assert "sessionAffinity" not in of_kind(bff, "Service")["spec"]
    for doc in bff:
        assert doc["kind"] not in {"PersistentVolumeClaim", "StatefulSet"}
    assert not [v for v in pod(bff)["volumes"] if "persistentVolumeClaim" in v]
    assert not [v for v in pod(bff)["volumes"] if "emptyDir" in v]


# --- cuota (INF-U10-01; P-6) --------------------------------------------------------------------------------------------------------------


def parse_cpu(value: str) -> float:
    return float(value.removesuffix("m")) / 1000 if value.endswith("m") else float(value)


def parse_gib(value: str) -> float:
    return float(value.removesuffix("Mi")) / 1024 if value.endswith("Mi") else float(value.removesuffix("Gi"))


PROXY = {"requests": ("100m", "20Mi"), "limits": ("500m", "128Mi")}
MARGIN = 1.3


def contribution(name: str, pods: int) -> dict[str, tuple[float, float]]:
    """Requests y limits del aporte de una pieza: `pods` por (contenedor + proxy), mas el 30 % (NFR-U1-13)."""
    resources = container(render(name, "prod"))["resources"]
    out = {}
    for group in ("requests", "limits"):
        cpu = pods * (parse_cpu(resources[group]["cpu"]) + parse_cpu(PROXY[group][0]))
        mem = pods * (parse_gib(resources[group]["memory"]) + parse_gib(PROXY[group][1]))
        out[group] = (cpu * MARGIN, mem * MARGIN)
    return out


def test_quota_the_contribution_of_u10_recomputed_from_the_prod_render_matches_quotas_yaml() -> None:
    quotas = load("platform/policies/quotas/quotas.yaml")["namespaces"]
    bff, spa = render("console-bff", "prod"), render("console-spa", "prod")
    hpa = of_kind(bff, "HorizontalPodAutoscaler")["spec"]
    surge = deployment(bff)["spec"]["strategy"]["rollingUpdate"]["maxSurge"]
    bff_pods = hpa["maxReplicas"] + surge  # el HPA al maximo mas 1 de `maxSurge`
    assert bff_pods == 7
    spa_replicas = deployment(spa)["spec"]["replicas"]
    assert deployment(spa)["spec"]["strategy"]["rollingUpdate"]["maxSurge"] == "100%"
    spa_pods = spa_replicas * 2  # 2 mas el 100 %
    assert spa_pods == 4
    for namespace, name, pods in (
        ("vectra-app", "console-bff", bff_pods),
        ("vectra-edge", "console-spa", spa_pods),
    ):
        declared = quotas[namespace]["contributions"]["U10"]
        computed = contribution(name, pods)
        for group in ("requests", "limits"):
            for got, want in zip(computed[group], declared[group], strict=True):
                # P-6 (a): `quotas.yaml` redondea como INF-U10-01; el request de memoria del BFF queda 0,05 GiB por encima (2,4527 frente a 2,4)
                assert abs(got - want) < 0.06, (namespace, group, got, want)
    assert round(contribution("console-bff", 7)["requests"][1], 4) == 2.4527


def test_quota_the_rendered_requests_are_what_the_design_says_in_staging_and_prod() -> None:
    for env in ("staging", "prod"):
        assert container(render("console-bff", env))["resources"] == {
            "requests": {"cpu": "250m", "memory": "256Mi"},
            "limits": {"cpu": "1", "memory": "512Mi"},
        }
        hpa = of_kind(render("console-bff", env), "HorizontalPodAutoscaler")["spec"]
        assert (hpa["minReplicas"], hpa["maxReplicas"]) == (2, 6)


# --- values por entorno (P-1 a P-3) -------------------------------------------------------------------------------------------------------


def test_values_kind_only_sets_the_hpa_maximum_and_the_memory_request_of_the_bff() -> None:
    kind_values = yaml.safe_load((CHARTS["console-bff"] / "values-kind.yaml").read_text(encoding="utf-8"))
    assert kind_values == {
        "hpa": {"maxReplicas": 2},
        "deployment": {"resources": {"requests": {"memory": "128Mi"}}},
    }
    assert not (CHARTS["console-spa"] / "values-kind.yaml").exists()
    assert not list((ROOT / "console" / "chart").rglob("values-kind-demo.yaml"))
    assert COMPONENTS["console-bff"]["kind_values"] == ["console/chart/bff/values-kind.yaml"]
    assert "kind_values" not in COMPONENTS["console-spa"]


def test_values_p1_kind_requests_128_mib_and_staging_and_prod_keep_the_design_256_mib() -> None:
    sizes = {env: container(render("console-bff", env))["resources"]["requests"]["memory"] for env in ENVS}
    assert sizes == {"kind": "128Mi", "staging": "256Mi", "prod": "256Mi"}
    kind = render("console-bff", "kind")
    prod = render("console-bff", "prod")
    # replicas, limits, PDB y estrategia no cambian
    assert deployment(kind)["spec"] == {
        **deployment(prod)["spec"],
        "template": deployment(kind)["spec"]["template"],
    }
    assert container(kind)["resources"]["limits"] == container(prod)["resources"]["limits"]
    assert of_kind(kind, "PodDisruptionBudget") == of_kind(prod, "PodDisruptionBudget")
    assert of_kind(kind, "HorizontalPodAutoscaler")["spec"]["maxReplicas"] == 2
    assert of_kind(prod, "HorizontalPodAutoscaler")["spec"]["maxReplicas"] == 6


def test_values_every_environment_has_its_two_files_and_the_defaults_are_production() -> None:
    for env in ENVS:
        for name in CHARTS:
            assert (ROOT / "vectra-risk-gitops" / "values" / env / f"{name}.yaml").stat().st_size > 0
    prod_spa = helm_template("console-spa", [])
    assert config_json(prod_spa)["redirect_uri"] == "https://vectra.banco.internal/callback"
    assert helm_template("console-bff", [])[0]["kind"]  # sin ningun values de entorno tambien renderiza
    assert gateway_hostname("prod") == "vectra.banco.internal"
    assert (
        yaml.safe_load((CHARTS["console-spa"] / "values.yaml").read_text(encoding="utf-8"))["hostname"]
        == "vectra.banco.internal"
    )


def test_values_the_example_digests_are_new_and_distinct_from_the_other_charts() -> None:
    mine = {
        yaml.safe_load((CHARTS[name] / "values.yaml").read_text(encoding="utf-8"))["image"]["digest"]
        for name in CHARTS
    }
    assert mine == {"sha256:" + "0" * 63 + "8", "sha256:" + "0" * 63 + "9"}
    others: set[str] = set()
    for path in ROOT.glob("*/chart/values*.yaml"):
        if path.parts[-3] != "console":
            others |= set(re.findall(r"sha256:[0-9a-f]{64}", path.read_text(encoding="utf-8")))
    assert not mine & others


def test_values_the_kind_render_of_platform_tests_sees_the_same_deployments_as_the_chart_render() -> None:
    """P-3 y C-9: `integration.render_env("kind")` (lo que usan `test_kind_profile.py` y `test_integration.py`) pasa `kind_values` pero no `values/<env>/<nombre>.yaml`."""
    spec = importlib.util.spec_from_file_location(
        "platform_integration", ROOT / "platform" / "tests" / "integration.py"
    )
    assert spec and spec.loader
    integration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(integration)
    seen = {
        d["metadata"]["name"]: d
        for d in integration.documents("kind")
        if d["kind"] == "Deployment" and d["metadata"]["name"] in CHARTS
    }
    assert set(seen) == set(CHARTS)
    for name, namespace in (("console-bff", "vectra-app"), ("console-spa", "vectra-edge")):
        own = deployment(render(name, "kind"))
        assert seen[name]["metadata"]["namespace"] == own["metadata"]["namespace"] == namespace
        assert seen[name]["spec"]["replicas"] == own["spec"]["replicas"] == 2
        mine = own["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"]["memory"]
        assert (
            seen[name]["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"]["memory"] == mine
        )


# --- secretos y checksum ------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", CHARTS)
def test_secrets_neither_chart_creates_one(name: str) -> None:
    for env in ENVS:
        kinds = {d["kind"] for d in render(name, env)}
        assert not kinds & {
            "Secret",
            "ExternalSecret",
            "PrometheusRule",
            "Server",
            "HTTPRoute",
            "AuthorizationPolicy",
            "NetworkPolicy",
        }
    text = "".join(p.read_text(encoding="utf-8") for p in CHARTS[name].rglob("*") if p.is_file())
    assert (
        not re.search(r"kind: (Secret|ExternalSecret|PrometheusRule)", text) and "grafana_folder" not in text
    )


def test_secrets_a_config_json_with_a_secret_key_or_a_key_shaped_value_fails_conftest(
    data_files: dict[str, Path],
) -> None:
    docs = render("console-spa", "prod")
    for change in (
        edit_config_json(lambda c: c.__setitem__("client_secret", "x")),
        edit_config_json(
            lambda c: c["grafana"].__setitem__("bias_dashboard_uid", "-----BEGIN PRIVATE KEY-----")
        ),
        edit_config_json(
            lambda c: c["grafana"].__setitem__(
                "bias_dashboard_uid", "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ4In0.c2ln"
            )
        ),
    ):
        assert conftest(edit(docs, change), data_files["prod"]).returncode != 0


def test_checksum_the_spa_one_is_the_sha256_of_the_rendered_config_json_and_follows_the_hostname() -> None:
    kind = render("console-spa", "kind")
    annotation = deployment(kind)["spec"]["template"]["metadata"]["annotations"]["checksum/config"]
    assert annotation == hashlib.sha256(config_json_text(kind).encode()).hexdigest()
    staging_host = ["--set", "hostname=vectra.otro.banco.internal"]
    other = render("console-spa", "kind", *staging_host)
    assert config_json_text(other) != config_json_text(kind)
    assert deployment(other)["spec"]["template"]["metadata"]["annotations"]["checksum/config"] != annotation
    assert (
        deployment(other)["spec"]["template"]["metadata"]["annotations"]["checksum/config"]
        == hashlib.sha256(config_json_text(other).encode()).hexdigest()
    )
    # un cambio en los values de un entorno distinto (por `values/<env>/console-spa.yaml`) tambien cambia el hash
    assert (
        deployment(render("console-spa", "staging"))["spec"]["template"]["metadata"]["annotations"][
            "checksum/config"
        ]
        != annotation
    )


def test_checksum_the_bff_one_changes_with_a_url_and_so_does_its_configmap() -> None:
    base = render("console-bff", "prod")
    other = render(
        "console-bff", "prod", "--set", "peers.caseUrl=http://case-service.vectra-app.svc.cluster.local:9999"
    )
    assert bff_env(other)["VECTRA_CASE_URL"] != bff_env(base)["VECTRA_CASE_URL"]
    first = deployment(base)["spec"]["template"]["metadata"]["annotations"]["checksum/config"]
    second = deployment(other)["spec"]["template"]["metadata"]["annotations"]["checksum/config"]
    assert re.fullmatch(r"[0-9a-f]{64}", first) and first != second
    assert deployment(base)["spec"]["template"]["metadata"]["annotations"]["checksum/config"] == first


def test_the_charts_render_nothing_with_a_namespace_other_than_the_application_one() -> None:
    for name, namespace in (("console-bff", "vectra-app"), ("console-spa", "vectra-edge")):
        assert {d["metadata"]["namespace"] for d in render(name, "prod")} == {namespace}


# --- las herramientas de la maquina -------------------------------------------------------------------------------------------------------


def test_the_tools_the_target_needs_are_there() -> None:
    for name in ("helm", "kubeconform", "conftest", "kyverno", "hadolint"):
        assert Path(tool(name)).is_file()
    assert shutil.which("docker") is not None, (
        "Docker no esta disponible: las pruebas de la imagen fallan, no se saltan"
    )
