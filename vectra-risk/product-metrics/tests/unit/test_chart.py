"""Chart de U11 (Paso 11, acotado a la demo; INF-U11-01; INF-U11-02; INF-U11-03; INF-U11-04; BR-U11-09; BR-U11-12; BR-U11-13; NFR-U11-05; NFR-U11-13; NFR-U11-14; NFR-U11-20; NFR-U11-21; P-U11-06).

`helm template` de los tres entornos + `conftest` con `product-metrics/policies/conftest/` (por documento y con todo el render junto). Cada
`# regla: x` de las politicas tiene aqui un caso que falla (una mutacion del render por regla) y el chart sin tocar pasa. Ademas: la identidad y
las variables contra el codigo (CA-3), la paridad de los rangos de los parametros con `params.parse` (BR-U11-09), `flows.yaml`, la cuota, el `Server`
`metrics-8081` de U1 y `CODEOWNERS` (CA-6). Necesita `platform/install-tools.sh` (helm y conftest en `platform/.tools/bin`): si faltan, **fallan**.
"""

import copy
import hashlib
import importlib.util
import inspect
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from chart_render import CHART, ENVS, KIND_VALUES, POLICY_FILE, ROOT, Doc, env_values, render, tool
from vectra_common import deps, ops_server, service_token
from vectra_product import config, main, params

CONFTEST_POLICIES = ROOT / "product-metrics" / "policies" / "conftest"
NETWORK = ROOT / "platform" / "network"
PROCESS_MD = ROOT / "aidlc-docs" / "construction" / "product-metrics" / "code" / "process.md"
POLICY_KEY = "values-product-metrics-policy.yaml"


def conftest(docs: list[Doc], *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [tool("conftest"), "test", "--policy", str(CONFTEST_POLICIES), *extra, "-"],
        input=yaml.safe_dump_all(docs, sort_keys=False),
        capture_output=True,
        text=True,
        check=False,
    )


def failures(docs: list[Doc]) -> str:
    """Los mensajes de las dos pasadas: por documento (`main`) y con todos juntos (`chart_set`)."""
    single = conftest(docs)
    combined = conftest(docs, "--combine", "--namespace", "chart_set")
    return single.stdout + single.stderr + combined.stdout + combined.stderr


def of_kind(docs: list[Doc], kind: str, name: str | None = None) -> Doc:
    return next(d for d in docs if d["kind"] == kind and (name is None or d["metadata"]["name"] == name))


def deployment(docs: list[Doc]) -> Doc:
    return of_kind(docs, "Deployment", "product-metrics")


def pod(docs: list[Doc]) -> Doc:
    return deployment(docs)["spec"]["template"]["spec"]  # type: ignore[no-any-return]


def container(docs: list[Doc]) -> Doc:
    return pod(docs)["containers"][0]  # type: ignore[no-any-return]


def edit(docs: list[Doc], change: Callable[[list[Doc]], None]) -> list[Doc]:
    copied = copy.deepcopy(docs)
    change(copied)
    return copied


def env_map(c: Doc) -> dict[str, str]:
    return {e["name"]: e.get("value", "") for e in c["env"]}


# --- el chart sin tocar -------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
def test_the_chart_as_is_passes_both_conftest_passes_in_every_environment(env: str) -> None:
    docs = render(env)
    assert conftest(docs).returncode == 0, conftest(docs).stdout
    assert conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0
    assert sorted(d["kind"] for d in docs) == sorted(
        [
            "Deployment",
            "Service",
            "PodDisruptionBudget",
            "ServiceAccount",
            "ExternalSecret",
            "ServiceMonitor",
            "PrometheusRule",
            "ConfigMap",
            "ConfigMap",
        ]
    )


def test_the_deployment_follows_the_design() -> None:
    docs = render()
    spec = deployment(docs)["spec"]
    assert spec["replicas"] == 2 and spec["strategy"]["rollingUpdate"] == {"maxSurge": 1, "maxUnavailable": 0}
    assert spec["progressDeadlineSeconds"] == 4800 and pod(docs)["terminationGracePeriodSeconds"] == 10
    assert deployment(docs)["metadata"]["annotations"]["vectra.io/hpa-exempt"].strip()
    assert pod(docs)["priorityClassName"] == "vectra-normal"
    assert of_kind(docs, "PodDisruptionBudget")["spec"]["minAvailable"] == 1
    assert container(docs)["command"] == ["python", "-m", "vectra_product.main"]
    assert {t["topologyKey"] for t in pod(docs)["topologySpreadConstraints"]} == {
        "topology.kubernetes.io/zone"
    }
    assert "startupProbe" not in container(docs)
    assert not [
        d for d in docs if d["kind"] in {"Server", "AuthorizationPolicy", "HorizontalPodAutoscaler", "Secret"}
    ]


def test_without_a_digest_it_does_not_render() -> None:
    result = subprocess.run(  # noqa: S603
        [tool("helm"), "template", "x", str(CHART), "-f", str(POLICY_FILE), "--set", "image.digest="],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "image.digest es obligatorio" in result.stderr


def test_without_the_policy_file_and_without_values_the_chart_does_not_render(tmp_path: Path) -> None:
    """Los ocho parametros salen solo de `values-product-metrics-policy.yaml`: sin el archivo del chart y sin esos values no hay render (INF-U11-02)."""
    bare = tmp_path / "chart"
    shutil.copytree(CHART, bare)
    (bare / POLICY_KEY).unlink()
    result = subprocess.run(  # noqa: S603
        [tool("helm"), "template", "x", str(bare)], capture_output=True, text=True, check=False
    )
    assert result.returncode != 0 and "es obligatorio (values-product-metrics-policy.yaml)" in result.stderr
    # `platform/tests/integration.py render_env` no pasa los values de la unidad: el chart sin tocar renderiza con un `helm template` simple
    plain = subprocess.run(
        [tool("helm"), "template", "x", str(CHART)], capture_output=True, text=True, check=False
    )  # noqa: S603
    assert plain.returncode == 0, plain.stderr


def test_none_of_the_eight_parameters_is_repeated_in_values_yaml() -> None:
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    policy = yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8"))
    assert set(values) & set(policy) == set()


# --- una mutacion del render por regla ----------------------------------------------------------------------------------------------------


def _dep(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
    return lambda docs: change(deployment(docs))


def _replace(docs: list[Doc], kind: str, change: Callable[[Doc], None]) -> None:
    change(of_kind(docs, kind))


def _append_doc(doc: Doc) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.append(doc)


def _drop_doc(kind: str, name: str | None = None) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.remove(of_kind(docs, kind, name))


POD = ["spec", "template", "spec"]
CONT = [*POD, "containers", 0]
TEMPLATE_META = ["spec", "template", "metadata"]


def at(doc: Doc, path: list[Any]) -> Any:
    node: Any = doc
    for key in path:
        node = node[key]
    return node


def set_at(path: list[Any], value: Any) -> Callable[[Doc], None]:
    return lambda doc: at(doc, path[:-1]).__setitem__(path[-1], value)


def drop_at(path: list[Any]) -> Callable[[Doc], None]:
    return lambda doc: at(doc, path[:-1]).pop(path[-1])


def set_env(name: str, value: str) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        for e in at(doc, CONT)["env"]:
            if e["name"] == name:
                e["value"] = value

    return change


def drop_env(name: str) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        at(doc, CONT)["env"] = [e for e in at(doc, CONT)["env"] if e["name"] != name]

    return change


def add_env(name: str, value: str) -> Callable[[Doc], None]:
    return lambda doc: at(doc, CONT)["env"].append({"name": name, "value": value})


def alert(name: str, nth: int = 0) -> Callable[[Doc], None]:
    """Un cambio sobre la `nth` regla de alerta llamada `name` de la PrometheusRule (`change` recibe la regla)."""

    def wrap(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
        def apply(docs: list[Doc]) -> None:
            rules = [
                r
                for g in of_kind(docs, "PrometheusRule")["spec"]["groups"]
                for r in g["rules"]
                if r.get("alert") == name
            ]
            change(rules[nth])

        return apply

    return wrap  # type: ignore[return-value]


SECRET = {
    "apiVersion": "v1",
    "kind": "Secret",
    "metadata": {"name": "product-key", "namespace": "vectra-app"},
    "stringData": {"k": "v"},
}
HPA = {
    "apiVersion": "autoscaling/v2",
    "kind": "HorizontalPodAutoscaler",
    "metadata": {"name": "product-metrics", "namespace": "vectra-app"},
    "spec": {
        "scaleTargetRef": {"kind": "Deployment", "name": "product-metrics"},
        "minReplicas": 2,
        "maxReplicas": 6,
    },
}
SERVER = {
    "apiVersion": "policy.linkerd.io/v1beta3",
    "kind": "Server",
    "metadata": {"name": "product-metrics-8081", "namespace": "vectra-app"},
    "spec": {"podSelector": {}, "port": 8081, "proxyProtocol": "unknown"},
}
AUTHZ = {
    "apiVersion": "policy.linkerd.io/v1alpha1",
    "kind": "AuthorizationPolicy",
    "metadata": {"name": "product-metrics-8081", "namespace": "vectra-app"},
    "spec": {"targetRef": {"group": "policy.linkerd.io", "kind": "Server", "name": "product-metrics-8081"}},
}


def mount_without_read_only(docs: list[Doc]) -> None:
    for m in container(docs)["volumeMounts"]:
        if m["name"] == "client-identity":
            m.pop("readOnly")


def policy_mount_with_subpath(docs: list[Doc]) -> None:
    for m in container(docs)["volumeMounts"]:
        if m["name"] == "product-metrics-policy":
            m["subPath"] = POLICY_KEY


def policy_mounted_elsewhere(docs: list[Doc]) -> None:
    for m in container(docs)["volumeMounts"]:
        if m["name"] == "product-metrics-policy":
            m["mountPath"] = "/etc/vectra/other"


def hostpath(docs: list[Doc]) -> None:
    pod(docs)["volumes"].append({"name": "h", "hostPath": {"path": "/"}})


def fix_checksum(docs: list[Doc]) -> None:
    deployment(docs)["spec"]["template"]["metadata"]["annotations"]["checksum/config"] = "0" * 64


def drop_checksum(docs: list[Doc]) -> None:
    deployment(docs)["spec"]["template"]["metadata"]["annotations"].pop("checksum/config")


def other_secret_key(docs: list[Doc]) -> None:
    of_kind(docs, "ExternalSecret")["spec"]["data"][0]["remoteRef"]["key"] = (
        "identity/clients/governance-service"
    )


def selector_of_pdb(docs: list[Doc]) -> None:
    of_kind(docs, "PodDisruptionBudget")["spec"]["selector"]["matchLabels"] = {
        "app.kubernetes.io/name": "otro"
    }


def drop_dashboard_label(docs: list[Doc]) -> None:
    of_kind(docs, "ConfigMap", "product-metrics-dashboard")["metadata"]["labels"].pop("vectra.io/dashboard")


def dashboard_other_folder(docs: list[Doc]) -> None:
    of_kind(docs, "ConfigMap", "product-metrics-dashboard")["metadata"]["annotations"]["grafana_folder"] = (
        "Vectra / Operación"
    )


def sustain_not_from_policy(docs: list[Doc]) -> None:
    for g in of_kind(docs, "PrometheusRule")["spec"]["groups"]:
        for r in g["rules"]:
            if r.get("alert") == "RuidoExplicacion":
                r["expr"] = "vectra:product_noise_days_below_floor:dedup >= 5"


def fifth_alert(docs: list[Doc]) -> None:
    of_kind(docs, "PrometheusRule")["spec"]["groups"][-1]["rules"].append(
        {
            "alert": "Quinta",
            "expr": "vector(1)",
            "labels": {"severity": "SEV3"},
            "annotations": {"runbook_url": "x"},
        }
    )


CASES: list[tuple[str, str, Callable[[list[Doc]], None]]] = [
    # --- el Deployment
    ("replicas 1", "replicas", _dep(set_at(["spec", "replicas"], 1))),
    ("replicas 3", "replicas", _dep(set_at(["spec", "replicas"], 3))),
    ("sin hpa-exempt", "replicas", _dep(drop_at(["metadata", "annotations", "vectra.io/hpa-exempt"]))),
    (
        "hpa-exempt sin justificacion",
        "replicas",
        _dep(set_at(["metadata", "annotations", "vectra.io/hpa-exempt"], " ")),
    ),
    ("un HPA en el render", "no-hpa", _append_doc(HPA)),
    ("maxSurge 2", "rollout", _dep(set_at(["spec", "strategy", "rollingUpdate", "maxSurge"], 2))),
    ("maxUnavailable 1", "rollout", _dep(set_at(["spec", "strategy", "rollingUpdate", "maxUnavailable"], 1))),
    ("estrategia Recreate", "rollout", _dep(set_at(["spec", "strategy"], {"type": "Recreate"}))),
    ("progressDeadlineSeconds 600", "deadlines", _dep(set_at(["spec", "progressDeadlineSeconds"], 600))),
    (
        "terminationGracePeriodSeconds 30",
        "deadlines",
        _dep(set_at([*POD, "terminationGracePeriodSeconds"], 30)),
    ),
    ("sin spread", "spread", _dep(drop_at([*POD, "topologySpreadConstraints"]))),
    ("vectra-high", "priority", _dep(set_at([*POD, "priorityClassName"], "vectra-high"))),
    ("sin criticality", "criticality", _dep(drop_at(["metadata", "labels", "vectra.io/criticality"]))),
    ("readiness /healthz", "probes", _dep(set_at([*CONT, "readinessProbe", "httpGet", "path"], "/healthz"))),
    ("liveness /livez", "probes", _dep(set_at([*CONT, "livenessProbe", "httpGet", "path"], "/livez"))),
    ("liveness en otro puerto", "probes", _dep(set_at([*CONT, "livenessProbe", "httpGet", "port"], 8080))),
    (
        "un startupProbe",
        "probes",
        _dep(set_at([*CONT, "startupProbe"], {"httpGet": {"path": "/healthz", "port": "metrics"}})),
    ),
    (
        "puerto 8080 en el contenedor",
        "ports",
        _dep(
            set_at(
                [*CONT, "ports"],
                [{"name": "metrics", "containerPort": 8081}, {"name": "http", "containerPort": 8080}],
            )
        ),
    ),
    (
        "command de otro modulo",
        "command",
        _dep(set_at([*CONT, "command"], ["python", "-m", "vectra_bias.app"])),
    ),
    ("constante como variable", "env", _dep(add_env("CYCLE_SECONDS", "300"))),
    ("plazo de la pasada como variable", "env", _dep(add_env("FULL_PASS_DEADLINE_SECONDS", "4500"))),
    ("falta VECTRA_TOKEN_URL", "env", _dep(drop_env("VECTRA_TOKEN_URL"))),
    ("falta VECTRA_REGISTRY_URL", "env", _dep(drop_env("VECTRA_REGISTRY_URL"))),
    ("clientId de otro cliente", "identity-doc", _dep(set_env("VECTRA_CLIENT_ID", "governance-service"))),
    ("cuenta de servicio de otro", "identity-doc", _dep(set_at([*POD, "serviceAccountName"], "default"))),
    # --- Service, PDB, ServiceMonitor
    (
        "Service renombrado",
        "service-doc",
        lambda d: _replace(d, "Service", set_at(["metadata", "name"], "product-metrics-svc")),
    ),
    (
        "Service con 8080",
        "service-doc",
        lambda d: _replace(
            d,
            "Service",
            set_at(
                ["spec", "ports"],
                [
                    {"name": "metrics", "port": 8081, "targetPort": "metrics"},
                    {"name": "http", "port": 8080, "targetPort": "metrics"},
                ],
            ),
        ),
    ),
    (
        "sin publishNotReadyAddresses",
        "service-doc",
        lambda d: _replace(d, "Service", set_at(["spec", "publishNotReadyAddresses"], False)),
    ),
    (
        "PDB minAvailable 0",
        "pdb-doc",
        lambda d: _replace(d, "PodDisruptionBudget", set_at(["spec", "minAvailable"], 0)),
    ),
    ("PDB con otro selector", "service-pdb", selector_of_pdb),
    (
        "ServiceMonitor a otro puerto",
        "servicemonitor-port",
        lambda d: _replace(d, "ServiceMonitor", set_at(["spec", "endpoints", 0, "port"], "http")),
    ),
    (
        "ServiceMonitor con jobLabel",
        "servicemonitor-port",
        lambda d: _replace(d, "ServiceMonitor", set_at(["spec", "jobLabel"], "app")),
    ),
    (
        "Service con otro targetPort",
        "service-port-names",
        lambda d: _replace(d, "Service", set_at(["spec", "ports", 0, "targetPort"], "nada")),
    ),
    # --- seguridad
    ("un Secret en el render", "no-plain-secret", _append_doc(SECRET)),
    (
        "credenciales en la URL",
        "no-plain-secret",
        _dep(set_env("VECTRA_REGISTRY_URL", "http://u:p@decision-registry-service:8080")),
    ),
    (
        "variable desde un Secret",
        "no-plain-secret",
        _dep(
            set_at(
                [*CONT, "env", 0],
                {"name": "VECTRA_REGISTRY_URL", "valueFrom": {"secretKeyRef": {"name": "s", "key": "k"}}},
            )
        ),
    ),
    ("un Server en el render", "no-linkerd-policy", _append_doc(SERVER)),
    ("una AuthorizationPolicy en el render", "no-linkerd-policy", _append_doc(AUTHZ)),
    ("pod como root", "hardening", _dep(set_at([*POD, "securityContext", "runAsNonRoot"], False))),
    ("runAsUser 0", "hardening", _dep(set_at([*POD, "securityContext", "runAsUser"], 0))),
    ("runAsGroup 0", "hardening", _dep(set_at([*POD, "securityContext", "runAsGroup"], 0))),
    ("sin seccomp", "hardening", _dep(drop_at([*POD, "securityContext", "seccompProfile"]))),
    (
        "raiz escribible",
        "hardening",
        _dep(set_at([*CONT, "securityContext", "readOnlyRootFilesystem"], False)),
    ),
    ("volumen hostPath", "hardening", hostpath),
    ("llave sin readOnly", "read-only-mounts", mount_without_read_only),
    ("ConfigMap con subPath", "no-subpath", policy_mount_with_subpath),
    ("token montado en el pod", "pod-token", _dep(set_at([*POD, "automountServiceAccountToken"], True))),
    (
        "token montado en la cuenta",
        "service-account-doc",
        lambda d: _replace(d, "ServiceAccount", set_at(["automountServiceAccountToken"], True)),
    ),
    (
        "secretos en la cuenta",
        "service-account-doc",
        lambda d: _replace(d, "ServiceAccount", set_at(["secrets"], [{"name": "s"}])),
    ),
    # --- recursos, imagen, namespace
    ("limit de memoria 1Gi", "resources", _dep(set_at([*CONT, "resources", "limits", "memory"], "1Gi"))),
    ("limit de CPU 1", "resources", _dep(set_at([*CONT, "resources", "limits", "cpu"], "1"))),
    ("request de CPU 250m", "resources", _dep(set_at([*CONT, "resources", "requests", "cpu"], "250m"))),
    (
        "request de memoria 64Mi",
        "resources",
        _dep(set_at([*CONT, "resources", "requests", "memory"], "64Mi")),
    ),
    (
        "imagen por etiqueta",
        "image",
        _dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/product-metrics:dev")),
    ),
    (
        "repositorio ajeno",
        "image",
        _dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/otra@sha256:" + "a" * 64)),
    ),
    (
        "digest corto",
        "image",
        _dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/product-metrics@sha256:abc")),
    ),
    (
        "namespace ajeno",
        "namespace",
        lambda d: _replace(d, "Service", set_at(["metadata", "namespace"], "default")),
    ),
    # --- el conjunto
    (
        "un documento de mas",
        "documents-exact",
        _append_doc(
            {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "otro", "namespace": "vectra-app"}}
        ),
    ),
    ("falta el PDB", "documents-exact", _drop_doc("PodDisruptionBudget")),
    ("falta el dashboard", "documents-exact", _drop_doc("ConfigMap", "product-metrics-dashboard")),
    ("checksum/config fijo", "checksum-config", fix_checksum),
    ("sin checksum/config", "checksum-config", drop_checksum),
    ("parametros montados en otra carpeta", "policy-mounted", policy_mounted_elsewhere),
    ("llave fuera del volumen", "identity", _dep(set_env("VECTRA_CLIENT_KEY_PATH", "/tmp/private-key"))),
    ("ExternalSecret de otro cliente", "identity", other_secret_key),
    ("cuenta de servicio ausente", "service-account-exists", _drop_doc("ServiceAccount")),
    ("una quinta alerta", "alerts-exact", fifth_alert),
    ("alerta sin SEV3", "alerts-exact", alert("RuidoExplicacion")(set_at(["labels", "severity"], "SEV1"))),
    (
        "alerta sin runbook_url",
        "alerts-exact",
        alert("ProductMetricsDegraded")(drop_at(["annotations", "runbook_url"])),
    ),
    (
        "job de la rama de ausencia distinto del Service",
        "alert-job",
        alert("ProductMetricsStale", 1)(set_at(["expr"], 'up{job="otro"} == 1')),
    ),
    ("S escrita en la plantilla", "noise-sustain", sustain_not_from_policy),
    ("dashboard sin etiqueta del sidecar", "dashboard-labels", drop_dashboard_label),
    ("dashboard en otra carpeta", "dashboard-labels", dashboard_other_folder),
]


@pytest.mark.parametrize(("name", "rule", "change"), CASES, ids=[c[0] for c in CASES])
def test_each_mutation_of_the_render_fails_its_rule(
    name: str, rule: str, change: Callable[[list[Doc]], None]
) -> None:
    output = failures(edit(render(), change))
    assert f"{rule}:" in output, f"{name}: ninguna regla {rule} fallo\n{output}"


def test_every_rule_of_the_policies_has_a_case_that_fails_it() -> None:
    declared = set()
    for rego in CONFTEST_POLICIES.glob("*.rego"):
        declared |= set(re.findall(r"^# regla: (\S+)", rego.read_text(encoding="utf-8"), flags=re.MULTILINE))
    covered = {c[1] for c in CASES} | {"policy-ranges"}
    assert declared - covered == set(), f"reglas sin caso: {sorted(declared - covered)}"
    assert covered - declared == set(), f"casos de reglas que no existen: {sorted(covered - declared)}"


# --- `values-product-metrics-policy.yaml`: rangos y paridad con `params.parse` (INF-U11-02; BR-U11-09) -------------------------------------------

POLICY_OK: dict[str, Any] = yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8"))


def render_with_policy(tmp_path: Path, **changes: Any) -> list[Doc]:
    path = tmp_path / POLICY_KEY
    path.write_text(yaml.safe_dump({**POLICY_OK, **changes}), encoding="utf-8")
    return render("kind", CHART, path)


def with_policy_text(text: str) -> list[Doc]:
    """El render con el `data` del ConfigMap de parametros reemplazado por `text`: lo que evalua la regla es ese `data` (no el archivo suelto)."""

    def change(docs: list[Doc]) -> None:
        of_kind(docs, "ConfigMap", "product-metrics-policy")["data"][POLICY_KEY] = text

    return edit(render(), change)


def rule_verdict(text: str) -> bool:
    """`True` si `conftest` acepta ese `data` en la regla de rangos (las demas reglas del chart no cambian)."""
    return "policy-ranges:" not in conftest(with_policy_text(text)).stdout


def code_verdict(text: str) -> bool:
    try:
        params.parse(yaml.safe_load(text))
    except params.ParamsError:
        return False
    return True


def dumped(**changes: Any) -> str:
    return yaml.safe_dump({**POLICY_OK, **changes}, sort_keys=False)


def without_key(key: str) -> str:
    return yaml.safe_dump({k: v for k, v in POLICY_OK.items() if k != key}, sort_keys=False)


# (nombre, texto del archivo, si debe pasar). Incluye tipos y no solo rangos (lecciones de U09-T04, F-01).
PARITY: list[tuple[str, str, bool]] = [
    ("el archivo actual", POLICY_FILE.read_text(encoding="utf-8"), True),
    ("F 0", dumped(noise_floor=0), False),
    ("F 1", dumped(noise_floor=1), False),
    ("F 0.01", dumped(noise_floor=0.01), True),
    ("F 0.99", dumped(noise_floor=0.99), True),
    ("F '0.6' (texto)", dumped(noise_floor="0.6"), False),
    ("F true", dumped(noise_floor=True), False),
    ("S 0", dumped(noise_sustain_days=0), False),
    ("S 1", dumped(noise_sustain_days=1), True),
    ("S 14", dumped(noise_sustain_days=14), True),
    ("S 15", dumped(noise_sustain_days=15), False),
    ("S 3.5", dumped(noise_sustain_days=3.5), False),
    ("S true", dumped(noise_sustain_days=True), False),
    ("S '3' (texto)", dumped(noise_sustain_days="3"), False),
    ("N 29", dumped(noise_min_decisions=29), False),
    ("N 30", dumped(noise_min_decisions=30), True),
    ("N '50' (texto)", dumped(noise_min_decisions="50"), False),
    ("N 50.5", dumped(noise_min_decisions=50.5), False),
    ("target de respuesta 1.1", dumped(target_complete_response=1.1), False),
    ("target de respuesta -0.1", dumped(target_complete_response=-0.1), False),
    ("target de respuesta 0", dumped(target_complete_response=0), True),
    ("horas 0", dumped(target_origination_hours=0), False),
    ("horas -1", dumped(target_origination_hours=-1), False),
    ("horas 0.25", dumped(target_origination_hours=0.25), True),
    ("horas 'x'", dumped(target_origination_hours="x"), False),
    ("razon de originacion 1.5", dumped(target_origination_ratio=1.5), False),
    ("sostenida del mes 6 igual a 2", dumped(target_sustained_ratio_month6=2), False),
    ("North Star 1.2", dumped(target_north_star=1.2), False),
    ("North Star 'x'", dumped(target_north_star="x"), False),
    ("North Star null", dumped(target_north_star=None), True),
    ("North Star 0.5", dumped(target_north_star=0.5), True),
    ("North Star true", dumped(target_north_star=True), False),
    ("una clave de menos", without_key("noise_floor"), False),
    ("sin North Star (clave ausente)", without_key("target_north_star"), False),
    ("una clave de mas", dumped(extra=1), False),
    ("una lista", "- 1\n- 2\n", False),
    ("un escalar", "3\n", False),
]


@pytest.mark.parametrize(("name", "text", "ok"), PARITY, ids=[c[0] for c in PARITY])
def test_policy_parity_conftest_and_params_parse_agree_on_every_row(name: str, text: str, ok: bool) -> None:
    code, rule = code_verdict(text), rule_verdict(text)
    assert code == ok, f"{name}: params.parse dio {code}, se esperaba {ok}"
    assert rule == code, f"{name}: la regla de conftest dio {rule} y params.parse {code} (BR-U11-09)"


def test_policy_the_ranges_of_the_rule_are_the_constants_of_config() -> None:
    """Mover una constante de rango en `config.py` hace fallar esta prueba si la regla no la sigue (candidata F-07 de U11-T01)."""
    text = (CONFTEST_POLICIES / "policy.rego").read_text(encoding="utf-8")
    found = dict(
        re.findall(r"^\w+ := (\S+) # ([A-Z_]+)$", text, flags=re.MULTILINE)[i][::-1]
        for i in range(len(re.findall(r"^\w+ := \S+ # [A-Z_]+$", text, flags=re.MULTILINE)))
    )
    constants = {n for n in dir(config) if n.startswith(("NOISE_", "TARGET_")) and n.isupper()}
    assert set(found) == constants, f"la regla sigue {sorted(found)} y config.py tiene {sorted(constants)}"
    for name, literal in found.items():
        assert float(literal) == float(getattr(config, name)), (
            f"{name}: la regla dice {literal} y config.py {getattr(config, name)}"
        )


OUT_OF_RANGE: list[tuple[str, dict[str, Any]]] = [
    ("S 15", {"noise_sustain_days": 15}),
    ("S 0", {"noise_sustain_days": 0}),
    ("F 1", {"noise_floor": 1}),
    ("N 29", {"noise_min_decisions": 29}),
    ("horas 0", {"target_origination_hours": 0}),
    ("North Star 1.2", {"target_north_star": 1.2}),
]


@pytest.mark.parametrize(("name", "changes"), OUT_OF_RANGE, ids=[c[0] for c in OUT_OF_RANGE])
def test_a_policy_file_out_of_range_fails_conftest_on_the_real_render_and_the_code_refuses_it(
    tmp_path: Path, name: str, changes: dict[str, Any]
) -> None:
    """Lo que Argo CD pasa con `-f`: el `data` renderizado fuera de rango no pasa `conftest`, y el proceso lo rechaza (CA-4 lo comprueba en el contenedor)."""
    docs = render_with_policy(tmp_path, **changes)
    assert "policy-ranges:" in failures(docs), name
    with pytest.raises(params.ParamsError):
        params.parse(yaml.safe_load(of_kind(docs, "ConfigMap", "product-metrics-policy")["data"][POLICY_KEY]))


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"noise_floor": 0.01},
        {"noise_sustain_days": 14},
        {"noise_min_decisions": 30},
        {"target_north_star": 0.5},
        {"noise_sustain_days": 3.0},
    ],
)
def test_the_current_values_and_the_edges_of_the_ranges_pass_on_the_real_render(
    tmp_path: Path, changes: dict[str, Any]
) -> None:
    docs = render_with_policy(tmp_path, **changes)
    assert conftest(docs).returncode == 0, conftest(docs).stdout
    params.parse(yaml.safe_load(of_kind(docs, "ConfigMap", "product-metrics-policy")["data"][POLICY_KEY]))


def test_the_configmap_is_the_policy_file_and_the_process_reads_it_as_valid() -> None:
    data = of_kind(render(), "ConfigMap", "product-metrics-policy")["data"][POLICY_KEY]
    assert yaml.safe_load(data) == POLICY_OK
    assert params.parse(yaml.safe_load(data)).noise_sustain_days == POLICY_OK["noise_sustain_days"]


def test_a_null_north_star_survives_the_values_merge(tmp_path: Path) -> None:
    """Helm descarta una clave nula de un values: el `target_north_star: null` del archivo del chart debe seguir en el ConfigMap (sin target acordado)."""
    docs = render_with_policy(tmp_path)
    assert (
        yaml.safe_load(of_kind(docs, "ConfigMap", "product-metrics-policy")["data"][POLICY_KEY])[
            "target_north_star"
        ]
        is None
    )


# --- CA-3: identidad, variables, sondas y checksum -------------------------------------------------------------------------------------


def names_read_by_the_code() -> set[str]:
    """Las variables que lee `main.py`, el proveedor de token de U0 y `deps` (con `https`): el codigo, no una copia."""
    token = set(
        re.findall(
            r"""os\.environ\[["'](VECTRA_\w+)["']\]""", inspect.getsource(service_token.provider_from_env)
        )
    )
    return {main.REGISTRY_URL_ENV, deps.CA_BUNDLE_ENV, *token}


def names_in_process_md() -> set[str]:
    return set(
        re.findall(
            r"`(VECTRA_[A-Z_]+)`", PROCESS_MD.read_text(encoding="utf-8").split("## Entorno y arranque", 1)[1]
        )
    )


@pytest.mark.parametrize("env", ENVS)
def test_env_the_variables_of_the_container_are_the_ones_of_process_md_and_the_code(env: str) -> None:
    names = set(env_map(container(render(env))))
    assert names == names_read_by_the_code(), (
        f"el chart pone {names} y el codigo lee {names_read_by_the_code()}"
    )
    assert names <= names_in_process_md()
    assert main.POLICY_PATH_ENV not in names, (
        "VECTRA_POLICY_PATH es opcional: el ConfigMap se monta en params.POLICY_PATH"
    )


def test_env_no_constant_of_config_is_an_environment_variable() -> None:
    # `CLIENT_ID` es la unica constante que el chart **repite** como variable (`VECTRA_CLIENT_ID`, que `provider_from_env` exige): su valor lo compara otra prueba.
    constants = {n for n in dir(config) if n.isupper()} - {"CLIENT_ID"}
    names = set(env_map(container(render())))
    assert not {n for n in names if n in constants or n.removeprefix("VECTRA_") in constants}


@pytest.mark.parametrize("env", ENVS)
def test_identity_the_client_id_the_key_and_the_service_account(env: str) -> None:
    docs = render(env)
    c = container(docs)
    env_ = env_map(c)
    assert env_["VECTRA_CLIENT_ID"] == config.CLIENT_ID == pod(docs)["serviceAccountName"]
    secret = of_kind(docs, "ExternalSecret")
    assert secret["spec"]["data"] == [
        {
            "secretKey": "private-key",
            "remoteRef": {"key": f"identity/clients/{config.CLIENT_ID}", "property": "private-key"},
        }
    ]
    volume = next(
        v
        for v in pod(docs)["volumes"]
        if v.get("secret", {}).get("secretName") == secret["spec"]["target"]["name"]
    )
    mount = next(m for m in c["volumeMounts"] if m["name"] == volume["name"])
    assert mount["readOnly"] is True and env_["VECTRA_CLIENT_KEY_PATH"] == f"{mount['mountPath']}/private-key"
    assert not [d for d in docs if d["kind"] == "Secret"]
    assert pod(docs)["automountServiceAccountToken"] is False
    assert of_kind(docs, "ServiceAccount")["automountServiceAccountToken"] is False


def test_identity_the_client_exists_in_the_vault_and_the_realm() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "platform" / "kind"))
    import vault_paths  # type: ignore[import-not-found]

    assert config.CLIENT_ID in vault_paths.service_account_clients()
    realm = (ROOT / "identity-edge" / "keycloak" / "realm" / "realm.kind.yaml").read_text(encoding="utf-8")
    assert re.search(rf"clientId: {config.CLIENT_ID}$", realm, flags=re.MULTILINE)


@pytest.mark.parametrize("env", ENVS)
def test_env_the_registry_url_is_the_service_and_port_of_flow_f28(env: str) -> None:
    flow = next(f for f in FLOWS["flows"] if f["id"] == "F28")
    (target,) = flow["to"]
    service = FLOWS["workloads"][target]["name"]
    url = env_map(container(render(env)))["VECTRA_REGISTRY_URL"]
    assert (
        url == f"http://{service}.vectra-app.svc.cluster.local:{flow['port']}"
        and config.REGISTRY_SERVICE == service
    )


@pytest.mark.parametrize("env", ENVS)
def test_params_the_policy_is_mounted_where_params_py_reads_it_without_subpath(env: str) -> None:
    docs = render(env)
    c = container(docs)
    volume = next(
        v for v in pod(docs)["volumes"] if v.get("configMap", {}).get("name") == "product-metrics-policy"
    )
    mount = next(m for m in c["volumeMounts"] if m["name"] == volume["name"])
    assert f"{mount['mountPath'].rstrip('/')}/{POLICY_KEY}" == str(params.POLICY_PATH)
    assert "subPath" not in mount and mount["readOnly"] is True
    assert list(of_kind(docs, "ConfigMap", "product-metrics-policy")["data"]) == [params.POLICY_PATH.name]


@pytest.mark.parametrize("env", ENVS)
def test_checksum_is_the_sha256_of_the_data_of_the_policy_configmap(env: str, tmp_path: Path) -> None:
    docs = render(env)
    data = of_kind(docs, "ConfigMap", "product-metrics-policy")["data"][POLICY_KEY]
    annotation = deployment(docs)["spec"]["template"]["metadata"]["annotations"]["checksum/config"]
    assert annotation == hashlib.sha256(data.encode()).hexdigest()
    # un cambio de parametros cambia el checksum (reinicia las replicas)
    other = render_with_policy(tmp_path, noise_floor=0.7)
    assert deployment(other)["spec"]["template"]["metadata"]["annotations"]["checksum/config"] != annotation


def test_probes_the_paths_are_routes_that_ops_server_serves() -> None:
    """INF-U11-01: `/healthz` y `/readyz` en 8081, las rutas que sirve `vectra_common.ops_server` (importado, no copiado)."""
    routes = {r.path for r in ops_server.create_ops_app(init_process=False).routes}  # type: ignore[attr-defined]
    assert {"/healthz", "/readyz", "/metrics"} <= routes and "/livez" not in routes
    for env in ENVS:
        c = container(render(env))
        assert (
            c["livenessProbe"]["httpGet"]["path"] == "/healthz"
            and c["readinessProbe"]["httpGet"]["path"] == "/readyz"
        )
        for probe in ("livenessProbe", "readinessProbe"):
            assert c[probe]["httpGet"]["path"] in routes
            assert c[probe]["httpGet"]["port"] == "metrics"
        assert {p["name"]: p["containerPort"] for p in c["ports"]} == {"metrics": ops_server.OPS_PORT}


# --- recursos: el unico ajuste de kind es el request de memoria (P-1 = b) ------------------------------------------------------------------


def memory_mib(quantity: str) -> int:
    return int(quantity.removesuffix("Mi"))


def test_kind_requests_128mi_and_staging_and_prod_keep_inf_u11_01() -> None:
    """NFR-U11-13: 100m / 256 MiB de request y 500m / 512 MiB de limit en staging y prod; kind baja solo el request de memoria a 128 MiB."""
    for env in ("staging", "prod"):
        assert container(render(env))["resources"] == {
            "requests": {"cpu": "100m", "memory": "256Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi"},
        }
    kind = container(render("kind"))["resources"]
    assert kind == {
        "requests": {"cpu": "100m", "memory": "128Mi"},
        "limits": {"cpu": "500m", "memory": "512Mi"},
    }


def test_kind_values_hold_only_the_memory_request() -> None:
    assert yaml.safe_load(KIND_VALUES.read_text(encoding="utf-8")) == {
        "deployment": {"resources": {"requests": {"memory": "128Mi"}}}
    }
    for env in ("kind", "staging", "prod"):
        assert deployment(render(env))["spec"]["replicas"] == 2  # DD-3 b: sin 1 replica en kind


def test_staging_and_prod_do_not_receive_the_kind_values() -> None:
    components = yaml.safe_load(
        (ROOT / "vectra-risk-gitops" / "components.yaml").read_text(encoding="utf-8")
    )["components"]
    (entry,) = [c for c in components if c["name"] == "product-metrics"]
    assert entry["kind_values"] == [
        "product-metrics/chart/values-kind.yaml"
    ] and "values-kind.yaml" not in str(entry.get("values"))


# --- CA-6: cuota, flujos, metrics-8081 y CODEOWNERS ------------------------------------------------------------------------------------------

FLOWS: dict[str, Any] = yaml.safe_load((NETWORK / "flows.yaml").read_text(encoding="utf-8"))
FORBIDDEN: list[dict[str, Any]] = yaml.safe_load((NETWORK / "forbidden.yaml").read_text(encoding="utf-8"))[
    "forbidden"
]
QUOTAS: dict[str, Any] = yaml.safe_load(
    (ROOT / "platform" / "policies" / "quotas" / "quotas.yaml").read_text(encoding="utf-8")
)


def to_cores(quantity: str) -> float:
    return int(quantity.removesuffix("m")) / 1000 if quantity.endswith("m") else float(quantity)


def to_gib(quantity: str) -> float:
    if quantity.endswith("Mi"):
        return int(quantity.removesuffix("Mi")) / 1024
    return float(quantity.removesuffix("Gi"))


def test_quota_the_u11_contribution_is_recomputed_from_the_prod_render() -> None:
    """NFR-U11-14: (replicas + maxSurge) pods x (contenedor + proxy de Linkerd 100m/20Mi y 500m/128Mi) x 1,3, contra la linea de `quotas.yaml`."""
    docs = render("prod")
    spec = deployment(docs)["spec"]
    pods = spec["replicas"] + spec["strategy"]["rollingUpdate"]["maxSurge"]
    r, lim = container(docs)["resources"]["requests"], container(docs)["resources"]["limits"]
    computed = {
        "requests": [
            round(pods * (to_cores(r["cpu"]) + 0.1) * 1.3, 2),
            round(pods * (to_gib(r["memory"]) + 20 / 1024) * 1.3, 2),
        ],
        "limits": [
            round(pods * (to_cores(lim["cpu"]) + 0.5) * 1.3, 2),
            round(pods * (to_gib(lim["memory"]) + 128 / 1024) * 1.3, 2),
        ],
    }
    assert computed == QUOTAS["namespaces"]["vectra-app"]["contributions"]["U11"]


def selector(endpoint: str) -> dict[str, str]:
    """El selector de pods que `generate.py` usa para el extremo (la misma funcion, no una copia)."""
    spec = importlib.util.spec_from_file_location("network_generate", NETWORK / "generate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.labels_of(FLOWS["workloads"][endpoint])  # type: ignore[no-any-return]


def matches(docs: list[Doc]) -> bool:
    workload = FLOWS["workloads"]["product-metrics"]
    want = selector("product-metrics")
    labels = deployment(docs)["spec"]["template"]["metadata"]["labels"]
    return (
        pod(docs)["serviceAccountName"] == workload["sa"]
        and deployment(docs)["metadata"]["namespace"] == workload["ns"]
        and all(labels.get(k) == v for k, v in want.items())
    )


@pytest.mark.parametrize("env", ENVS)
def test_flows_the_labels_and_service_account_of_the_render_are_the_selector_of_the_flows(env: str) -> None:
    docs = render(env)
    assert matches(docs), "el render no es product-metrics para flows.yaml"
    f28 = next(f for f in FLOWS["flows"] if f["id"] == "F28")
    assert (
        f28["from"] == ["product-metrics"]
        and f28["to"] == ["decision-registry-service"]
        and f28["port"] == 8080
    )
    assert any(f["id"] == "F50" and "product-metrics" in f["from"] for f in FLOWS["flows"])
    assert any(
        f["id"] == "F60" and f["from"] == ["prometheus"] and f.get("port") == 8081 for f in FLOWS["flows"]
    )
    assert sum(1 for f in FORBIDDEN if f["id"] == "U11") == 3
    assert {(f["from"], f["to"], f["port"]) for f in FORBIDDEN if f["id"] == "U11"} == {
        ("product-metrics", "case-service", 8080),
        ("product-metrics", "governance-service", 8080),
        ("case-service", "product-metrics", 8081),
    }


def test_flows_a_changed_label_or_account_is_no_longer_the_selector() -> None:
    assert not matches(edit(render(), _dep(set_at([*POD, "serviceAccountName"], "otra"))))
    assert not matches(
        edit(render(), _dep(set_at([*TEMPLATE_META, "labels", "app.kubernetes.io/name"], "otro")))
    )


def test_flows_no_new_flows_were_added_for_u11() -> None:
    """INF-U11-04: sin flujos nuevos; los de U11 son exactamente F28, F50 y F60 (F60 es de Prometheus hacia el namespace)."""
    mentioning = {f["id"] for f in FLOWS["flows"] if "product-metrics" in (set(f["from"]) | set(f["to"]))}
    assert mentioning == {"F28", "F50"}


@pytest.mark.parametrize("env", ENVS)
def test_metrics_8081_u1_covers_the_port_and_only_prometheus_is_admitted(env: str) -> None:
    """P-3 = (a): el chart no declara `Server` ni `AuthorizationPolicy`; 8081 lo cubre el `Server` de U1 y solo admite la identidad de Prometheus."""
    docs = list(
        yaml.safe_load_all((NETWORK / "generated" / env / "vectra-app.yaml").read_text(encoding="utf-8"))
    )
    server = next(d for d in docs if d and d["kind"] == "Server" and d["metadata"]["name"] == "metrics-8081")
    assert server["spec"]["port"] == 8081 and server["spec"]["podSelector"] == {}, (
        "cubre todos los pods de vectra-app, tambien product-metrics"
    )
    policies = [
        d
        for d in docs
        if d and d["kind"] == "AuthorizationPolicy" and d["spec"]["targetRef"]["name"] == "metrics-8081"
    ]
    assert policies
    for policy in policies:
        for ref in policy["spec"]["requiredAuthenticationRefs"]:
            auth = next(
                d for d in docs if d and d["kind"] == ref["kind"] and d["metadata"]["name"] == ref["name"]
            )
            assert auth["spec"]["identities"] == [
                "prometheus.vectra-observability.serviceaccount.identity.linkerd.cluster.local"
            ]


CODEOWNERS = ROOT.parent / ".github" / "CODEOWNERS"
POLICY_PATH = "vectra-risk/product-metrics/chart/values-product-metrics-policy.yaml"


def codeowners_for(path: str, text: str) -> list[str] | None:
    """Los duenos de la ultima regla que cubre la ruta (GitHub: gana la ultima). Cubre `**/`, `*` y rutas con prefijo."""
    owners: list[str] | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        pattern, *who = line.split()
        anchored = pattern.startswith("/")
        pattern = pattern.lstrip("/")
        regex = (
            re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        )
        if pattern.endswith("/"):
            regex += ".*"
        prefix = "" if anchored or "/" in pattern.rstrip("/") else "(?:.*/)?"
        if re.fullmatch(prefix + regex, path):
            owners = who
    return owners


def test_codeowners_a_rule_covers_the_policy_file() -> None:
    """INF-U11-02, BR-U11-09: la regla `**/values-product-metrics-policy.yaml` cubre la ruta: cambiar los parametros exige a producto y riesgo."""
    owners = codeowners_for(POLICY_PATH, CODEOWNERS.read_text(encoding="utf-8"))
    assert owners and {"@jjlloobb", "@joseluisjedi"} <= set(owners), (
        f"ninguna regla de CODEOWNERS cubre {POLICY_PATH}"
    )
    assert (ROOT / POLICY_PATH.removeprefix("vectra-risk/")).is_file()


def test_codeowners_without_the_rule_the_path_is_not_covered() -> None:
    text = "\n".join(
        line
        for line in CODEOWNERS.read_text(encoding="utf-8").splitlines()
        if "values-product-metrics-policy" not in line
    )
    assert codeowners_for(POLICY_PATH, text) is None
    assert (
        codeowners_for(
            "vectra-risk/product-metrics/chart/values.yaml", CODEOWNERS.read_text(encoding="utf-8")
        )
        is None
    )


# --- Service y alertas: el `job` de las ramas de ausencia es el nombre del Service ---------------------------------------------------------


def test_the_job_of_the_alerts_is_the_name_of_the_service() -> None:
    """El ServiceMonitor no fija `jobLabel`: `job` es el nombre del Service. Un Service renombrado deja las ramas de ausencia ciegas (P-U11-06)."""
    docs = render()
    service = of_kind(docs, "Service")["metadata"]["name"]
    jobs = set()
    for g in of_kind(docs, "PrometheusRule")["spec"]["groups"]:
        for r in g["rules"]:
            jobs |= set(re.findall(r'up\{job="([^"]+)"\}', r.get("expr", "")))
    assert jobs == {service}
    assert "jobLabel" not in of_kind(docs, "ServiceMonitor")["spec"]


def test_s_of_ruido_explicacion_is_noise_sustain_days_of_the_rendered_configmap(tmp_path: Path) -> None:
    for sustain in (3, 5, 14):
        docs = render_with_policy(tmp_path, noise_sustain_days=sustain)
        (rule,) = [
            r
            for g in of_kind(docs, "PrometheusRule")["spec"]["groups"]
            for r in g["rules"]
            if r.get("alert") == "RuidoExplicacion"
        ]
        assert rule["expr"].endswith(f">= {sustain}")
        assert (
            yaml.safe_load(of_kind(docs, "ConfigMap", "product-metrics-policy")["data"][POLICY_KEY])[
                "noise_sustain_days"
            ]
            == sustain
        )


def test_the_env_values_of_every_environment_exist() -> None:
    for env in ENVS:
        assert env_values(env).is_file()
