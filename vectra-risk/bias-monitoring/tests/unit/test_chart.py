"""Chart de U9 (Paso 12 acotado a la demo; INF-U9-01 a 04; BR-U9-13; P-U9-05; NFR-U9-10 a 13, 30, 34).

`helm template` de los tres entornos + `conftest` con `bias-monitoring/policies/conftest/` (por documento y con todo el render junto). Cada
`# regla: x` de las politicas tiene aqui un caso que falla (una mutacion del render por regla) y el chart sin tocar pasa. Ademas:
la identidad y las variables de los dos procesos contra el codigo (CA-3), `flows.yaml` (CA-6) y `CODEOWNERS` (P-1 = a).
Necesita `platform/install-tools.sh` (helm y conftest en `platform/.tools/bin`): si faltan, las pruebas **fallan**.
"""

import copy
import inspect
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from vectra_bias import app, config, run
from chart_render import CHART, ENVS, POLICY_FILE, ROOT, Doc, render, tool
from vectra_common import service_token

CONFTEST_POLICIES = ROOT / "bias-monitoring" / "policies" / "conftest"
NETWORK = ROOT / "platform" / "network"


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


def service(docs: list[Doc]) -> Doc:
    return of_kind(docs, "Deployment", "bias-monitoring-service")


def cronjob(docs: list[Doc]) -> Doc:
    return of_kind(docs, "CronJob")


def service_pod(docs: list[Doc]) -> Doc:
    return service(docs)["spec"]["template"]["spec"]  # type: ignore[no-any-return]


def service_container(docs: list[Doc]) -> Doc:
    return service_pod(docs)["containers"][0]  # type: ignore[no-any-return]


def job_pod(docs: list[Doc]) -> Doc:
    return cronjob(docs)["spec"]["jobTemplate"]["spec"]["template"]["spec"]  # type: ignore[no-any-return]


def job_container(docs: list[Doc]) -> Doc:
    return job_pod(docs)["containers"][0]  # type: ignore[no-any-return]


def edit(docs: list[Doc], change: Callable[[list[Doc]], None]) -> list[Doc]:
    copied = copy.deepcopy(docs)
    change(copied)
    return copied


def env_map(container: Doc) -> dict[str, str]:
    return {e["name"]: e.get("value", "") for e in container["env"]}


# --- el chart sin tocar -------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
def test_the_chart_as_is_passes_both_conftest_passes_in_every_environment(env: str) -> None:
    docs = render(env)
    assert conftest(docs).returncode == 0, conftest(docs).stdout
    assert conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0
    assert len(docs) == 10


def test_the_service_and_the_cronjob_follow_the_design() -> None:
    docs = render()
    spec = service(docs)["spec"]
    assert spec["replicas"] == 2 and spec["strategy"]["rollingUpdate"] == {"maxSurge": 1, "maxUnavailable": 0}
    assert "vectra.io/hpa-exempt" in service(docs)["metadata"]["annotations"]
    assert service_pod(docs)["priorityClassName"] == "vectra-normal"
    assert service_container(docs)["lifecycle"]["preStop"]["sleep"]["seconds"] == 5
    assert of_kind(docs, "PodDisruptionBudget")["spec"]["minAvailable"] == 1
    cron = cronjob(docs)["spec"]
    assert cron["concurrencyPolicy"] == "Forbid" and cron["timeZone"] == "Etc/UTC"
    assert cron["startingDeadlineSeconds"] == 300 and cron["jobTemplate"]["spec"]["backoffLimit"] == 0
    assert (cron["successfulJobsHistoryLimit"], cron["failedJobsHistoryLimit"]) == (3, 3)
    assert job_pod(docs)["priorityClassName"] == "vectra-high"
    assert job_container(docs)["command"] == ["python", "-m", "vectra_bias.run"]
    assert service_container(docs)["command"] == ["python", "-m", "vectra_bias.app"]


def test_without_a_digest_it_does_not_render() -> None:
    result = subprocess.run(  # noqa: S603
        [tool("helm"), "template", "x", str(CHART), "-f", str(POLICY_FILE), "--set", "image.digest="],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "image.digest es obligatorio" in result.stderr


def test_without_values_monitoring_policy_the_chart_does_not_render(tmp_path: Path) -> None:
    """Los cinco parametros salen solo de `values-monitoring-policy.yaml`: sin el archivo del chart y sin esos values no hay render (INF-U9-03)."""
    bare = tmp_path / "chart"
    shutil.copytree(CHART, bare)
    (bare / "values-monitoring-policy.yaml").unlink()
    result = subprocess.run(  # noqa: S603
        [tool("helm"), "template", "x", str(bare)], capture_output=True, text=True, check=False
    )
    assert result.returncode != 0 and "es obligatorio (values-monitoring-policy.yaml)" in result.stderr
    # y el chart sin tocar renderiza con un `helm template` simple (lo que hace `platform/tests/integration.py render_env`)
    plain = subprocess.run(
        [tool("helm"), "template", "x", str(CHART)], capture_output=True, text=True, check=False
    )  # noqa: S603
    assert plain.returncode == 0, plain.stderr


def test_the_configmap_is_values_monitoring_policy_and_the_app_reads_it_as_valid() -> None:
    docs = render()
    data = of_kind(docs, "ConfigMap")["data"]["values-monitoring-policy.yaml"]
    assert yaml.safe_load(data) == yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8"))
    assert config.parse_policy(yaml.safe_load(data)).schedule == yaml.safe_load(data)["schedule"]


# --- una mutacion del render por regla ----------------------------------------------------------------------------------------------------


def _service(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
    return lambda docs: change(service(docs))


def _cron(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
    return lambda docs: change(cronjob(docs))


def _replace(docs: list[Doc], kind: str, change: Callable[[Doc], None]) -> None:
    change(of_kind(docs, kind))


def _append_doc(doc: Doc) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.append(doc)


def _drop_doc(kind: str, name: str | None = None) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.remove(of_kind(docs, kind, name))


S_POD = ["spec", "template", "spec"]
S_CONT = [*S_POD, "containers", 0]
J_JOB = ["spec", "jobTemplate", "spec"]
J_POD = [*J_JOB, "template", "spec"]


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
        for e in at(doc, S_CONT if doc["kind"] == "Deployment" else [*J_POD, "containers", 0])["env"]:
            if e["name"] == name:
                e["value"] = value

    return change


def drop_env(name: str) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        container = at(doc, S_CONT if doc["kind"] == "Deployment" else [*J_POD, "containers", 0])
        container["env"] = [e for e in container["env"] if e["name"] != name]

    return change


def add_env(name: str, value: str) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        container = at(doc, S_CONT if doc["kind"] == "Deployment" else [*J_POD, "containers", 0])
        container["env"].append({"name": name, "value": value})

    return change


SECRET = {
    "apiVersion": "v1",
    "kind": "Secret",
    "metadata": {"name": "bias-key", "namespace": "vectra-app"},
    "stringData": {"k": "v"},
}
PROBE = {
    "apiVersion": "batch/v1",
    "kind": "Job",
    "metadata": {"name": "x04-probe-20261110-1200", "namespace": "vectra-app"},
    "spec": {"template": {"spec": {"containers": [{"name": "p", "image": "x"}], "restartPolicy": "Never"}}},
}
HPA = {
    "apiVersion": "autoscaling/v2",
    "kind": "HorizontalPodAutoscaler",
    "metadata": {"name": "bias-monitoring-service", "namespace": "vectra-app"},
    "spec": {
        "scaleTargetRef": {"kind": "Deployment", "name": "bias-monitoring-service"},
        "minReplicas": 2,
        "maxReplicas": 6,
    },
}


def mount_without_read_only(docs: list[Doc]) -> None:
    job_container(docs)["volumeMounts"][1].pop("readOnly")  # el montaje de la llave del CronJob


def wrong_key_mount(docs: list[Doc]) -> None:
    job_pod(docs)["volumes"][0]["secret"]["secretName"] = "bias-monitoring-service-client"


CASES: list[tuple[str, str, Callable[[list[Doc]], None]]] = [
    # --- servicio
    ("replicas 1", "service-replicas", _service(set_at(["spec", "replicas"], 1))),
    ("replicas 3", "service-replicas", _service(set_at(["spec", "replicas"], 3))),
    (
        "sin hpa-exempt",
        "service-replicas",
        _service(drop_at(["metadata", "annotations", "vectra.io/hpa-exempt"])),
    ),
    ("maxSurge 2", "service-rollout", _service(set_at(["spec", "strategy", "rollingUpdate", "maxSurge"], 2))),
    (
        "maxUnavailable 1",
        "service-rollout",
        _service(set_at(["spec", "strategy", "rollingUpdate", "maxUnavailable"], 1)),
    ),
    ("sin spread", "service-spread", _service(drop_at([*S_POD, "topologySpreadConstraints"]))),
    (
        "vectra-high en el servicio",
        "service-priority",
        _service(set_at([*S_POD, "priorityClassName"], "vectra-high")),
    ),
    (
        "sin criticality",
        "service-criticality",
        _service(drop_at(["metadata", "labels", "vectra.io/criticality"])),
    ),
    (
        "preStop 3 s",
        "service-prestop",
        _service(set_at([*S_CONT, "lifecycle", "preStop", "sleep", "seconds"], 3)),
    ),
    ("sin lifecycle", "service-prestop", _service(drop_at([*S_CONT, "lifecycle"]))),
    (
        "readiness /healthz",
        "service-probes",
        _service(set_at([*S_CONT, "readinessProbe", "httpGet", "path"], "/healthz")),
    ),
    (
        "liveness /readyz",
        "service-probes",
        _service(set_at([*S_CONT, "livenessProbe", "httpGet", "path"], "/readyz")),
    ),
    (
        "readiness en 8080",
        "service-probes",
        _service(set_at([*S_CONT, "readinessProbe", "httpGet", "port"], "http")),
    ),
    (
        "puertos",
        "service-ports",
        _service(set_at([*S_CONT, "ports"], [{"name": "http", "containerPort": 8080}])),
    ),
    (
        "command del CronJob en el servicio",
        "service-command",
        _service(set_at([*S_CONT, "command"], ["python", "-m", "vectra_bias.run"])),
    ),
    ("constante como variable", "service-env", _service(add_env("CACHE_TTL_SECONDS", "900"))),
    (
        "variable del CronJob en el servicio",
        "service-env",
        _service(add_env("VECTRA_GOVERNANCE_URL", "http://g")),
    ),
    ("falta REGISTRY_URL", "service-env", _service(drop_env("VECTRA_REGISTRY_URL"))),
    ("falta JWKS", "service-env", _service(drop_env("VECTRA_JWKS_URL"))),
    (
        "clientId del servicio",
        "service-identity",
        _service(set_env("VECTRA_CLIENT_ID", "bias-monitoring-job")),
    ),
    (
        "cuenta de servicio del servicio",
        "service-identity",
        _service(set_at([*S_POD, "serviceAccountName"], "bias-monitoring-job")),
    ),
    (
        "Service renombrado",
        "service-doc",
        lambda d: _replace(d, "Service", set_at(["metadata", "name"], "bias-monitoring")),
    ),
    (
        "Service sin 8081",
        "service-doc",
        lambda d: _replace(
            d, "Service", set_at(["spec", "ports"], [{"name": "http", "port": 8080, "targetPort": "http"}])
        ),
    ),
    (
        "PDB 0",
        "service-pdb-doc",
        lambda d: _replace(d, "PodDisruptionBudget", set_at(["spec", "minAvailable"], 0)),
    ),
    ("sin PDB", "service-pdb", _drop_doc("PodDisruptionBudget")),
    (
        "PDB de otro nombre",
        "service-pdb",
        lambda d: _replace(
            d,
            "PodDisruptionBudget",
            set_at(["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro"),
        ),
    ),
    ("con HPA", "service-pdb", _append_doc(HPA)),
    (
        "ServiceMonitor al puerto http",
        "servicemonitor-port",
        lambda d: _replace(d, "ServiceMonitor", set_at(["spec", "endpoints", 0, "port"], "http")),
    ),
    (
        "targetPort inexistente",
        "service-port-names",
        lambda d: _replace(d, "Service", set_at(["spec", "ports", 1, "targetPort"], "ops")),
    ),
    # --- CronJob
    ("otro nombre de CronJob", "cronjob-shape", _cron(set_at(["metadata", "name"], "otro"))),
    ("restartPolicy OnFailure", "cronjob-shape", _cron(set_at([*J_POD, "restartPolicy"], "OnFailure"))),
    (
        "command del servicio en el CronJob",
        "cronjob-shape",
        _cron(set_at([*J_POD, "containers", 0, "command"], ["python", "-m", "vectra_bias.app"])),
    ),
    ("concurrencyPolicy Allow", "concurrency", _cron(set_at(["spec", "concurrencyPolicy"], "Allow"))),
    ("sin timeZone", "timezone", _cron(drop_at(["spec", "timeZone"]))),
    ("startingDeadline 301", "deadlines", _cron(set_at(["spec", "startingDeadlineSeconds"], 301))),
    ("activeDeadline 601", "deadlines", _cron(set_at([*J_JOB, "activeDeadlineSeconds"], 601))),
    ("activeDeadline 599", "deadlines", _cron(set_at([*J_JOB, "activeDeadlineSeconds"], 599))),
    ("backoffLimit 1", "deadlines", _cron(set_at([*J_JOB, "backoffLimit"], 1))),
    ("historial exitosos 1", "history", _cron(set_at(["spec", "successfulJobsHistoryLimit"], 1))),
    ("historial fallidos 1", "history", _cron(set_at(["spec", "failedJobsHistoryLimit"], 1))),
    (
        "vectra-normal en el CronJob",
        "cronjob-priority",
        _cron(set_at([*J_POD, "priorityClassName"], "vectra-normal")),
    ),
    ("sin sidecar nativo", "native-sidecar", _cron(drop_at([*J_JOB, "template", "metadata", "annotations"]))),
    (
        "sin etiqueta de workload",
        "workload-label",
        _cron(drop_at([*J_JOB, "template", "metadata", "labels", "vectra.io/workload"])),
    ),
    (
        "clientId del CronJob",
        "cronjob-identity",
        _cron(set_env("VECTRA_CLIENT_ID", "bias-monitoring-service")),
    ),
    (
        "cuenta de servicio del CronJob",
        "cronjob-identity",
        _cron(set_at([*J_POD, "serviceAccountName"], "bias-monitoring-service")),
    ),
    ("constante como variable del CronJob", "cronjob-env", _cron(add_env("FREEZE_TIMEOUT_S", "10"))),
    ("falta GOVERNANCE_URL", "cronjob-env", _cron(drop_env("VECTRA_GOVERNANCE_URL"))),
    ("falta PUSHGATEWAY_URL", "cronjob-env", _cron(drop_env("VECTRA_PUSHGATEWAY_URL"))),
    (
        "CronJob sin criticality",
        "cronjob-criticality",
        _cron(set_at(["metadata", "labels", "vectra.io/criticality"], "medium")),
    ),
    (
        "horario escrito en la plantilla",
        "schedule-from-policy",
        _cron(set_at(["spec", "schedule"], "*/5 * * * *")),
    ),
    (
        "horario invalido en el CronJob",
        "schedule-vs-deadline",
        _cron(set_at(["spec", "schedule"], "*/5 * * * *")),
    ),
    (
        "5 min con activeDeadline 600",
        "schedule-vs-deadline",
        _cron(set_at(["spec", "schedule"], "2,7,12,17,22,27,32,37,42,47,52,57 * * * *")),
    ),
    # --- compartido
    ("un Secret", "no-plain-secret", _append_doc(SECRET)),
    (
        "credencial en la URL",
        "no-plain-secret",
        _service(set_env("VECTRA_REGISTRY_URL", "http://u:p@registry")),
    ),
    (
        "variable desde un Secret",
        "no-plain-secret",
        _service(
            lambda d: at(d, S_CONT)["env"].append(
                {"name": "X", "valueFrom": {"secretKeyRef": {"name": "s", "key": "k"}}}
            )
        ),
    ),
    ("un Job x04-probe", "no-probe", _append_doc(PROBE)),
    (
        "un documento de mas",
        "documents-exact",
        _append_doc(
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": "otro", "namespace": "vectra-app"},
                "data": {},
            }
        ),
    ),
    ("sin ServiceAccount del job", "documents-exact", _drop_doc("ServiceAccount", "bias-monitoring-job")),
    ("runAsNonRoot false", "hardening", _service(set_at([*S_POD, "securityContext", "runAsNonRoot"], False))),
    ("runAsUser 0", "hardening", _service(set_at([*S_POD, "securityContext", "runAsUser"], 1000))),
    (
        "raiz escribible",
        "hardening",
        _service(set_at([*S_CONT, "securityContext", "readOnlyRootFilesystem"], False)),
    ),
    ("sin seccomp", "hardening", _cron(drop_at([*J_POD, "securityContext", "seccompProfile"]))),
    ("montaje sin readOnly", "read-only-mounts", mount_without_read_only),
    ("limits 1 CPU", "resources", _service(set_at([*S_CONT, "resources", "limits", "cpu"], "1"))),
    (
        "requests 256Mi",
        "resources",
        _cron(set_at([*J_POD, "containers", 0, "resources", "requests", "memory"], "256Mi")),
    ),
    (
        "imagen por etiqueta",
        "image",
        _service(set_at([*S_CONT, "image"], "kind-registry:5000/vectra/bias-monitoring:dev")),
    ),
    (
        "imagen de otro",
        "image",
        _cron(
            set_at([*J_POD, "containers", 0, "image"], "kind-registry:5000/vectra/otra@sha256:" + "0" * 64)
        ),
    ),
    (
        "digest corto",
        "image",
        _service(set_at([*S_CONT, "image"], "kind-registry:5000/vectra/bias-monitoring@sha256:abc")),
    ),
    ("namespace", "namespace", _service(set_at(["metadata", "namespace"], "vectra-edge"))),
    (
        "ServiceAccount con secretos",
        "service-account-doc",
        lambda d: _replace(d, "ServiceAccount", set_at(["secrets"], [{"name": "s"}])),
    ),
    (
        "sin cuenta de servicio en el render",
        "service-account-exists",
        _drop_doc("ServiceAccount", "bias-monitoring-service"),
    ),
    # --- identidad y politica entre documentos
    (
        "VECTRA_POLICY_PATH apunta a otro",
        "policy-mounted",
        _service(set_env("VECTRA_POLICY_PATH", "/etc/otro/values-monitoring-policy.yaml")),
    ),
    ("el job monta la llave del servicio", "identity", wrong_key_mount),
    (
        "llave de otro cliente",
        "identity",
        lambda d: of_kind(d, "ExternalSecret", "bias-monitoring-job-client")["spec"]["data"][0][
            "remoteRef"
        ].__setitem__("key", "identity/clients/bias-monitoring-service"),
    ),
    (
        "propiedad de la llave",
        "identity",
        lambda d: of_kind(d, "ExternalSecret", "bias-monitoring-service-client")["spec"]["data"][0][
            "remoteRef"
        ].__setitem__("property", "public-key"),
    ),
    (
        "KEY_PATH fuera del volumen",
        "identity",
        _service(set_env("VECTRA_CLIENT_KEY_PATH", "/tmp/private-key")),
    ),
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
    covered = {c[1] for c in CASES} | {"policy-ranges", "policy-stale", "policy-schedule"}
    assert declared - covered == set(), f"reglas sin caso: {sorted(declared - covered)}"
    assert covered - declared == set(), f"casos de reglas que no existen: {sorted(covered - declared)}"


# --- `values-monitoring-policy.yaml` fuera de rango (INF-U9-03; BR-U9-13) -------------------------------------------------------------------

POLICY_OK: dict[str, Any] = yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8"))


def render_with_policy(tmp_path: Path, **changes: Any) -> list[Doc]:
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump({**POLICY_OK, **changes}), encoding="utf-8")
    return render("kind", CHART, path)


FIVE_MIN = "2,7,12,17,22,27,32,37,42,47,52,57 * * * *"
OUT_OF_RANGE: list[tuple[str, dict[str, Any], str]] = [
    ("umbral 0", {"threshold_pp": 0}, "policy-ranges"),
    ("umbral 21", {"threshold_pp": 21}, "policy-ranges"),
    ("n_min 29", {"n_min": 29}, "policy-ranges"),
    ("ventana 6", {"window_days": 6}, "policy-ranges"),
    ("ventana 91", {"window_days": 91}, "policy-ranges"),
    ("W de 20 min", {"stale_after": "20m"}, "policy-stale"),
    ("W menor que 4 x el intervalo", {"stale_after": "45m"}, "policy-stale"),
    ("W 1h30m (no es una duracion)", {"stale_after": "1h30m"}, "policy-stale"),
    ("W 90 (sin unidad)", {"stale_after": "90"}, "policy-stale"),
    ("W abc", {"stale_after": "abc"}, "policy-stale"),
    ("n_min abc", {"n_min": "abc"}, "policy-ranges"),
    ("n_min 30.5", {"n_min": 30.5}, "policy-ranges"),
    ("umbral abc", {"threshold_pp": "abc"}, "policy-ranges"),
    ("ventana abc", {"window_days": "abc"}, "policy-ranges"),
    ("intervalo de 6 min", {"schedule": "3,9,15,21,27,33,39,45,51,57 * * * *"}, "policy-schedule"),
    ("intervalo de 12 min", {"schedule": "2,14,26,38,50 * * * *"}, "policy-schedule"),
    ("desfase 0", {"schedule": "0,15,30,45 * * * *"}, "policy-schedule"),
    ("5 min con activeDeadlineSeconds 600", {"schedule": FIVE_MIN}, "schedule-vs-deadline"),
]


@pytest.mark.parametrize(("name", "changes", "rule"), OUT_OF_RANGE, ids=[c[0] for c in OUT_OF_RANGE])
def test_a_policy_out_of_range_fails_conftest_and_the_code_refuses_it_too(
    tmp_path: Path, name: str, changes: dict[str, Any], rule: str
) -> None:
    docs = render_with_policy(tmp_path, **changes)
    assert f"{rule}:" in failures(docs), name
    if (
        rule != "schedule-vs-deadline"
    ):  # un horario de 5 min es valido para el codigo; lo que falla es su cruce con el deadline del chart
        with pytest.raises(config.PolicyError):
            config.parse_policy({**POLICY_OK, **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"threshold_pp": 1},
        {"threshold_pp": 20},
        {"n_min": 30},
        {"window_days": 7},
        {"window_days": 90},
        {"stale_after": "1h"},
        {"schedule": "3,13,23,33,43,53 * * * *"},
        {"schedule": "1,16,31,46 * * * *"},
        {"schedule": "4,19,34,49 * * * *", "stale_after": "60m"},
    ],
)
def test_the_current_values_and_the_edges_of_the_ranges_pass(tmp_path: Path, changes: dict[str, Any]) -> None:
    docs = render_with_policy(tmp_path, **changes)
    assert conftest(docs).returncode == 0, conftest(docs).stdout
    assert conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0
    config.parse_policy({**POLICY_OK, **changes})


def test_the_schedule_of_the_cronjob_follows_values_monitoring_policy(tmp_path: Path) -> None:
    docs = render_with_policy(tmp_path, schedule="3,13,23,33,43,53 * * * *")
    assert cronjob(docs)["spec"]["schedule"] == "3,13,23,33,43,53 * * * *"
    assert "2,17,32,47" not in (CHART / "templates" / "cronjob.yaml").read_text(encoding="utf-8")


def test_a_schedule_written_in_the_template_fails_schedule_from_policy(tmp_path: Path) -> None:
    mutated = tmp_path / "chart"
    shutil.copytree(CHART, mutated)
    path = mutated / "templates" / "cronjob.yaml"
    text = path.read_text(encoding="utf-8")
    needle = "{{ $policy.schedule | quote }}"
    assert needle in text
    path.write_text(text.replace(needle, '"2,17,32,47 * * * *"'), encoding="utf-8")
    other = tmp_path / "policy.yaml"
    other.write_text(yaml.safe_dump({**POLICY_OK, "schedule": "3,13,23,33,43,53 * * * *"}), encoding="utf-8")
    assert "schedule-from-policy:" in failures(render("kind", mutated, other))


def test_no_x04_probe_appears_with_any_values(tmp_path: Path) -> None:
    """T5: el Job x04-probe esta diferido; ni `probes.runId` lo hace aparecer."""
    for env in ENVS:
        for extra in ([], ["--set", "probes.runId=20261110-1200"]):
            docs = render(env, CHART, POLICY_FILE, *extra)
            assert not [d for d in docs if d["kind"] == "Job" or "x04" in d["metadata"]["name"]]


# --- CA-3: identidad y variables de los dos procesos (leccion de U04-T08) -----------------------------------------------------------------


def names_read_by_the_cronjob() -> set[str]:
    """Las variables que lee `run.build_deps` y el proveedor de token de U0: el codigo, no una copia."""
    source = inspect.getsource(run.build_deps) + inspect.getsource(service_token.provider_from_env)
    return set(re.findall(r"""(?:env|os\.environ)\[["'](VECTRA_\w+)["']\]""", source)) | {
        "VECTRA_POLICY_PATH"
    }


def env_problems(docs: list[Doc]) -> list[str]:
    problems = []
    service_env = set(env_map(service_container(docs)))
    if not set(app.REQUIRED) <= service_env:
        problems.append(f"el servicio no tiene {set(app.REQUIRED) - service_env}")
    job_env = set(env_map(job_container(docs)))
    if not names_read_by_the_cronjob() <= job_env:
        problems.append(f"el CronJob no tiene {names_read_by_the_cronjob() - job_env}")
    return problems


def identity_problems(docs: list[Doc]) -> list[str]:
    problems = []
    for client, pod, container, secret in (
        (
            "bias-monitoring-service",
            service_pod(docs),
            service_container(docs),
            "bias-monitoring-service-client",
        ),
        ("bias-monitoring-job", job_pod(docs), job_container(docs), "bias-monitoring-job-client"),
    ):
        env = env_map(container)
        if env.get("VECTRA_CLIENT_ID") != client:
            problems.append(f"VECTRA_CLIENT_ID de {client} es {env.get('VECTRA_CLIENT_ID')}")
        volume = next((v for v in pod["volumes"] if v.get("secret", {}).get("secretName") == secret), None)
        mount = next((m for m in container["volumeMounts"] if volume and m["name"] == volume["name"]), None)
        if mount is None or mount.get("readOnly") is not True:
            problems.append(f"{client}: la llave no se monta de solo lectura desde {secret}")
        elif env.get("VECTRA_CLIENT_KEY_PATH") != f"{mount['mountPath']}/private-key":
            problems.append(
                f"{client}: VECTRA_CLIENT_KEY_PATH {env.get('VECTRA_CLIENT_KEY_PATH')} fuera del volumen"
            )
        es = of_kind(docs, "ExternalSecret", secret)
        if es["spec"]["data"] != [
            {
                "secretKey": "private-key",
                "remoteRef": {"key": f"identity/clients/{client}", "property": "private-key"},
            }
        ]:
            problems.append(f"el ExternalSecret {secret} no lee identity/clients/{client} (private-key)")
        if pod["serviceAccountName"] != client:
            problems.append(f"{client}: la cuenta de servicio es {pod['serviceAccountName']}")
    policy_cm = of_kind(docs, "ConfigMap")["metadata"]["name"]
    for container, pod in (
        (service_container(docs), service_pod(docs)),
        (job_container(docs), job_pod(docs)),
    ):
        volume = next(v for v in pod["volumes"] if v.get("configMap", {}).get("name") == policy_cm)
        mount = next(m for m in container["volumeMounts"] if m["name"] == volume["name"])
        if env_map(container)["VECTRA_POLICY_PATH"] != f"{mount['mountPath']}/values-monitoring-policy.yaml":
            problems.append("VECTRA_POLICY_PATH no apunta al ConfigMap de la politica")
    return problems


@pytest.mark.parametrize("env", ENVS)
def test_env_the_variables_of_both_processes_contain_what_the_code_reads(env: str) -> None:
    docs = render(env)
    assert env_problems(docs) == []
    assert set(app.REQUIRED) <= set(env_map(service_container(docs)))
    assert {
        "VECTRA_REGISTRY_URL",
        "VECTRA_GOVERNANCE_URL",
        "VECTRA_PUSHGATEWAY_URL",
        "VECTRA_TOKEN_URL",
        "VECTRA_ASSERTION_AUDIENCE",
        "VECTRA_CLIENT_ID",
        "VECTRA_CLIENT_KEY_PATH",
        "VECTRA_POLICY_PATH",
    } <= names_read_by_the_cronjob() | {"VECTRA_REGISTRY_URL"}


@pytest.mark.parametrize("name", app.REQUIRED)
def test_env_a_required_variable_missing_from_the_deployment_is_a_problem(name: str) -> None:
    docs = edit(render(), _service(drop_env(name)))
    assert any(name in p for p in env_problems(docs))


def test_env_a_variable_the_cronjob_reads_missing_from_the_chart_is_a_problem() -> None:
    docs = edit(render(), _cron(drop_env("VECTRA_PUSHGATEWAY_URL")))
    assert any("VECTRA_PUSHGATEWAY_URL" in p for p in env_problems(docs))


def test_env_no_constant_of_the_code_is_an_environment_variable() -> None:
    constants = {n for n in dir(config) if n.isupper() and not n.startswith("_")}
    for env in ENVS:
        docs = render(env)
        names = set(env_map(service_container(docs))) | set(env_map(job_container(docs)))
        assert not (names & constants), names & constants
        assert all(n.startswith("VECTRA_") for n in names)


@pytest.mark.parametrize("env", ENVS)
def test_identity_each_process_has_its_own_key_client_and_service_account(env: str) -> None:
    assert identity_problems(render(env)) == []


@pytest.mark.parametrize(
    ("name", "change"),
    [
        ("clientId cambiado", _service(set_env("VECTRA_CLIENT_ID", "bias-monitoring-job"))),
        ("llave sin readOnly", mount_without_read_only),
        ("llave del otro proceso", wrong_key_mount),
        (
            "ExternalSecret de otro cliente",
            lambda d: of_kind(d, "ExternalSecret", "bias-monitoring-job-client")["spec"]["data"][0][
                "remoteRef"
            ].__setitem__("key", "identity/clients/bias-monitoring-service"),
        ),
        (
            "cuenta de servicio cambiada",
            _cron(set_at([*J_POD, "serviceAccountName"], "bias-monitoring-service")),
        ),
        (
            "politica en otra ruta",
            _cron(set_env("VECTRA_POLICY_PATH", "/etc/otro/values-monitoring-policy.yaml")),
        ),
    ],
)
def test_identity_each_mutation_is_found(name: str, change: Callable[[list[Doc]], None]) -> None:
    assert identity_problems(edit(render(), change)), name


def test_identity_the_secret_never_leaves_the_vault_inline() -> None:
    for env in ENVS:
        docs = render(env)
        assert not [d for d in docs if d["kind"] == "Secret"]
        assert "BEGIN" not in yaml.safe_dump_all(docs)


def bias_url_problems(docs: list[Doc]) -> list[str]:
    """El Service coincide con `biasUrl` de `governance/chart/values.yaml` (F25), leido del archivo."""
    values = yaml.safe_load((ROOT / "governance" / "chart" / "values.yaml").read_text(encoding="utf-8"))
    match = re.fullmatch(r"http://([\w-]+)\.([\w-]+)\.svc\.cluster\.local:(\d+)", values["peers"]["biasUrl"])
    assert match, values["peers"]["biasUrl"]
    name, namespace, port = match.group(1), match.group(2), int(match.group(3))
    services = [d for d in docs if d["kind"] == "Service" and d["metadata"]["name"] == name]
    if not services:
        return [f"ningun Service se llama {name} (biasUrl de governance)"]
    problems = []
    if services[0]["metadata"]["namespace"] != namespace:
        problems.append(f"el Service esta en {services[0]['metadata']['namespace']}, no en {namespace}")
    if port not in {p["port"] for p in services[0]["spec"]["ports"]}:
        problems.append(f"el Service no expone {port}")
    return problems


def test_identity_the_service_is_the_one_governance_calls_in_bias_url() -> None:
    assert bias_url_problems(render()) == []


def test_identity_a_renamed_service_does_not_match_bias_url() -> None:
    docs = edit(render(), lambda d: _replace(d, "Service", set_at(["metadata", "name"], "bias-monitoring")))
    assert bias_url_problems(docs)


def test_identity_the_active_deadline_is_the_one_of_the_code() -> None:
    for env in ENVS:
        assert (
            cronjob(render(env))["spec"]["jobTemplate"]["spec"]["activeDeadlineSeconds"]
            == config.ACTIVE_DEADLINE_SECONDS
        )


# --- CA-6: flows.yaml y CODEOWNERS --------------------------------------------------------------------------------------------------------

FLOWS: dict[str, Any] = yaml.safe_load((NETWORK / "flows.yaml").read_text(encoding="utf-8"))
FORBIDDEN: list[dict[str, Any]] = yaml.safe_load((NETWORK / "forbidden.yaml").read_text(encoding="utf-8"))[
    "forbidden"
]


def selector(endpoint: str) -> dict[str, str]:
    """El selector de pods que `generate.py` usa para el extremo (la misma funcion, no una copia)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("network_generate", NETWORK / "generate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.labels_of(FLOWS["workloads"][endpoint])  # type: ignore[no-any-return]


def pod_templates(docs: list[Doc]) -> list[tuple[str, str, dict[str, str]]]:
    """(cuenta de servicio, namespace, etiquetas) del pod de cada Deployment y CronJob."""
    return [
        (
            service_pod(docs)["serviceAccountName"],
            service(docs)["metadata"]["namespace"],
            service(docs)["spec"]["template"]["metadata"]["labels"],
        ),
        (
            job_pod(docs)["serviceAccountName"],
            cronjob(docs)["metadata"]["namespace"],
            cronjob(docs)["spec"]["jobTemplate"]["spec"]["template"]["metadata"]["labels"],
        ),
    ]


def matches(endpoint: str, docs: list[Doc]) -> bool:
    workload = FLOWS["workloads"][endpoint]
    want = selector(endpoint)
    return any(
        sa == workload["sa"] and ns == workload["ns"] and all(labels.get(k) == v for k, v in want.items())
        for sa, ns, labels in pod_templates(docs)
    )


def flow(flow_id: str, source: str | None = None) -> dict[str, Any]:
    return next(f for f in FLOWS["flows"] if f["id"] == flow_id and (source is None or source in f["from"]))


@pytest.mark.parametrize("env", ENVS)
def test_flows_the_labels_and_service_accounts_of_the_render_are_the_selectors_of_the_flows(env: str) -> None:
    docs = render(env)
    for endpoint in ("bias-monitoring-service", "bias-monitoring-job"):
        assert matches(endpoint, docs), f"el render no es {endpoint} para flows.yaml"
    for flow_id in ("F14", "F25", "F26", "F27", "F50", "F60", "F106"):
        assert any(f["id"] == flow_id for f in FLOWS["flows"]), f"falta {flow_id}"
    assert "bias-monitoring-service" in flow("F14")["to"] and "bias-monitoring-service" in flow("F25")["to"]
    assert {"bias-monitoring-service", "bias-monitoring-job"} <= set(flow("F26")["from"])
    assert flow("F27")["from"] == ["bias-monitoring-job"], "solo el CronJob congela"
    assert "bias-monitoring-job" in flow("F106")["from"] and "pushgateway" in flow("F106")["to"]
    assert {"bias-monitoring-service", "bias-monitoring-job"} <= set(flow("F50")["from"])
    assert any(
        f["id"] == "F60" and f["from"] == ["prometheus"] and 8081 in (f.get("ports") or [f.get("port")])
        for f in FLOWS["flows"]
    )
    assert any(f["from"] == "bias-monitoring-service" and f["to"] == "pushgateway" for f in FORBIDDEN), (
        "forbidden.yaml sigue negando servicio -> Pushgateway"
    )


def test_flows_a_changed_label_or_account_is_no_longer_the_selector() -> None:
    docs = edit(render(), _cron(drop_at([*J_JOB, "template", "metadata", "labels", "vectra.io/workload"])))
    assert not matches("bias-monitoring-job", docs)
    docs = edit(render(), _service(set_at([*S_POD, "serviceAccountName"], "otra")))
    assert not matches("bias-monitoring-service", docs)


def test_flows_no_new_flows_were_added_for_u9() -> None:
    """Sin egress (X02) y la unica llamada a governance es `freeze` desde el CronJob (X04): NFR-U9-34. Sin flujos nuevos: los de U9 son exactamente los que ya estaban (F14, F25, F26, F27, F50, F60, F106)."""
    mentioning = {
        f["id"]
        for f in FLOWS["flows"]
        if {"bias-monitoring-service", "bias-monitoring-job"} & (set(f["from"]) | set(f["to"]))
    }
    assert mentioning == {"F14", "F25", "F26", "F27", "F50", "F106"}


CODEOWNERS = ROOT.parent / ".github" / "CODEOWNERS"
POLICY_PATH = "vectra-risk/bias-monitoring/chart/values-monitoring-policy.yaml"


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


def test_codeowners_a_rule_covers_values_monitoring_policy() -> None:
    """P-1 = (a): la regla con comodin `**/values-monitoring-policy.yaml` cubre la ruta (INF-U9-03, BR-U9-13): cambiarla exige cumplimiento."""
    text = CODEOWNERS.read_text(encoding="utf-8")
    owners = codeowners_for(POLICY_PATH, text)
    assert owners and "@jjlloobb" in owners, f"ninguna regla de CODEOWNERS cubre {POLICY_PATH}"


def test_codeowners_without_the_rule_the_path_is_not_covered() -> None:
    text = "\n".join(
        line
        for line in CODEOWNERS.read_text(encoding="utf-8").splitlines()
        if "values-monitoring-policy" not in line
    )
    assert codeowners_for(POLICY_PATH, text) is None
    assert (
        codeowners_for(
            "vectra-risk/bias-monitoring/chart/values.yaml", CODEOWNERS.read_text(encoding="utf-8")
        )
        is None
    )
