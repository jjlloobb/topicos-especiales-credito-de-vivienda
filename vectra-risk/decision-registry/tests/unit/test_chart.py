"""Chart de U3: Deployment del servicio, HPA, PDB, ServiceMonitor, Job de migracion, CronJob `registry-aggregator` y ServiceAccounts
(Pasos 12, 13 y 15 acotados a la demo; BR-U3-17; P-U3-08; NFR-U3-10, 11, 41, 42; INF-U3-03, INF-U3-06).

`helm template` + `conftest` con las politicas de `decision-registry/chart/policy/`: limites de tiempo, `Forbid`, anotacion del sidecar
nativo, sin Secret plano, HPA de 2 a 6 al 70 %, spread por zona, PDB, `vectra-critical`, DSN sin clave en la URL y el hook de migracion. Cada `# regla: x` de las politicas tiene aqui un caso que falla (una mutacion del render, por regla) y
el chart sin tocar pasa. Necesita `platform/install-tools.sh` (helm y conftest en `platform/.tools/bin`).
"""

import copy
import importlib.util
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / "decision-registry" / "chart"
BIN = ROOT / "platform" / ".tools" / "bin"
Doc = dict[str, Any]


def tool(name: str) -> str:
    path = BIN / name
    assert path.is_file(), f"falta {path}: corre platform/install-tools.sh"
    return str(path)


def render() -> list[Doc]:
    out = subprocess.run(  # noqa: S603
        [tool("helm"), "template", "decision-registry", str(CHART)], check=True, capture_output=True, text=True
    ).stdout
    return [d for d in yaml.safe_load_all(out) if d]


def conftest(docs: list[Doc], *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [tool("conftest"), "test", "--policy", str(CHART / "policy"), *extra, "-"],
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


def cronjob(docs: list[Doc]) -> Doc:
    return next(d for d in docs if d["kind"] == "CronJob")


def of_kind(docs: list[Doc], kind: str) -> Doc:
    return next(d for d in docs if d["kind"] == kind)


def deployment(docs: list[Doc]) -> Doc:
    return of_kind(docs, "Deployment")


def service_container(docs: list[Doc]) -> Doc:
    return deployment(docs)["spec"]["template"]["spec"]["containers"][0]  # type: ignore[no-any-return]


def migration(docs: list[Doc]) -> Doc:
    return next(d for d in docs if d["kind"] == "Job" and d["metadata"]["name"] == "registry-migration")


def migration_container(docs: list[Doc]) -> Doc:
    return migration(docs)["spec"]["template"]["spec"]["containers"][0]  # type: ignore[no-any-return]


def pod(docs: list[Doc]) -> Doc:
    return cronjob(docs)["spec"]["jobTemplate"]["spec"]["template"]["spec"]  # type: ignore[no-any-return]


def container(docs: list[Doc]) -> Doc:
    return pod(docs)["containers"][0]  # type: ignore[no-any-return]


def edit(docs: list[Doc], change: Callable[[list[Doc]], None]) -> list[Doc]:
    copied = copy.deepcopy(docs)
    change(copied)
    return copied


def test_el_chart_sin_tocar_pasa_las_dos_pasadas() -> None:
    docs = render()
    assert conftest(docs).returncode == 0
    assert conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0
    assert len(docs) == 14


def test_el_cronjob_cumple_el_diseno() -> None:
    cron = cronjob(render())
    spec = cron["spec"]
    assert spec["schedule"] == "*/5 * * * *" and spec["concurrencyPolicy"] == "Forbid"
    assert spec["jobTemplate"]["spec"]["activeDeadlineSeconds"] == 280
    template = spec["jobTemplate"]["spec"]["template"]
    assert template["metadata"]["annotations"]["config.alpha.linkerd.io/proxy-enable-native-sidecar"] == "true"
    assert template["spec"]["priorityClassName"] == "vectra-high"
    assert template["spec"]["containers"][0]["command"] == ["vectra-registry", "aggregator", "run"]


def test_sin_digest_no_se_renderiza() -> None:
    result = subprocess.run(  # noqa: S603
        [tool("helm"), "template", "x", str(CHART), "--set", "image.digest="], capture_output=True, text=True, check=False
    )
    assert result.returncode != 0 and "image.digest es obligatorio" in result.stderr


def _set(path: list[str | int], value: Any) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        node: Any = cronjob(docs)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return change


def _drop(path: list[str]) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        node: Any = cronjob(docs)
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return change


SPEC = ["spec"]
JOB = ["spec", "jobTemplate", "spec"]
POD = [*JOB, "template", "spec"]
CTR = [*POD, "containers", 0]


def _env(name: str, **fields: Any) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        env = container(docs)["env"]
        env[:] = [e for e in env if e["name"] != name]
        env.append({"name": name, **fields})

    return change


def _sa(docs: list[Doc]) -> Doc:
    return next(d for d in docs if d["kind"] == "ServiceAccount")


CASES: list[tuple[str, Callable[[list[Doc]], None]]] = [
    ("cronjob-shape", _set(["metadata", "name"], "otro")),
    ("cronjob-shape", _set(["metadata", "namespace"], "default")),
    ("cronjob-shape", _set([*POD, "restartPolicy"], "OnFailure")),
    ("cronjob-shape", lambda docs: pod(docs).__setitem__("initContainers", [{"name": "i"}])),
    ("schedule", _set([*SPEC, "schedule"], "*/10 * * * *")),
    ("concurrency", _set([*SPEC, "concurrencyPolicy"], "Allow")),
    ("concurrency", _drop([*SPEC, "concurrencyPolicy"])),
    ("deadline", _set([*JOB, "activeDeadlineSeconds"], 300)),
    ("deadline", _drop([*JOB, "activeDeadlineSeconds"])),
    ("deadline", _set([*JOB, "backoffLimit"], 3)),
    ("priority", _set([*POD, "priorityClassName"], "vectra-low")),
    ("native-sidecar", _drop([*JOB, "template", "metadata", "annotations", "config.alpha.linkerd.io/proxy-enable-native-sidecar"])),
    ("native-sidecar", _set([*JOB, "template", "metadata", "annotations", "config.alpha.linkerd.io/proxy-enable-native-sidecar"], "false")),
    ("service-account", _set([*POD, "serviceAccountName"], "registry-checkpoint")),
    ("workload-label", _set([*JOB, "template", "metadata", "labels", "vectra.io/workload"], "otro")),
    ("image", _set([*CTR, "image"], "kind-registry:5000/vectra/decision-registry:latest")),
    ("image", _set([*CTR, "image"], "docker.io/otro/imagen@sha256:" + "a" * 64)),
    ("image", _set([*CTR, "image"], "kind-registry:5000/vectra/decision-registry@sha256:abc")),
    ("command", _set([*CTR, "command"], ["vectra-registry", "aggregator", "run", "--until-head"])),
    ("no-plain-secret", _env("PGPASSWORD", value="clave")),
    ("no-plain-secret", _env("PGPASSWORD", valueFrom={"secretKeyRef": {"name": "otro", "key": "password"}})),
    ("no-plain-secret", _env("REGISTRY_AGGREGATOR_DSN", value="postgresql://registry_aggregator:clave@registry-db-rw/registry")),
    ("no-plain-secret", lambda docs: container(docs).__setitem__("env", [e for e in container(docs)["env"] if e["name"] != "PGUSER"])),
    ("no-plain-secret", lambda docs: docs.append({"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "x", "namespace": "vectra-app"}})),
    ("resources", _drop([*CTR, "resources", "requests"])),
    ("resources", _drop([*CTR, "resources", "limits"])),
    ("hardening", _set([*POD, "securityContext", "runAsNonRoot"], False)),
    ("hardening", _set([*POD, "securityContext", "seccompProfile", "type"], "Unconfined")),
    ("hardening", _set([*CTR, "securityContext", "readOnlyRootFilesystem"], False)),
    ("service-account-doc", lambda docs: _sa(docs)["metadata"].__setitem__("namespace", "default")),
    ("service-account-doc", lambda docs: _sa(docs).__setitem__("automountServiceAccountToken", False)),
    ("service-account-doc", lambda docs: _sa(docs).__setitem__("secrets", [{"name": "x"}])),
    ("documents-exact", lambda docs: docs.append(copy.deepcopy(docs[0]))),
    ("documents-exact", lambda docs: docs.pop(0)),
    ("documents-exact", lambda docs: docs.append({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "x", "namespace": "vectra-app"}})),
    ("service-account-exists", lambda docs: docs.__setitem__(slice(None), [d for d in docs if not (d["kind"] == "ServiceAccount" and d["metadata"]["name"] == "registry-aggregator")])),
    ("no-external-secret", lambda docs: docs.append({"apiVersion": "external-secrets.io/v1", "kind": "ExternalSecret", "metadata": {"name": "x", "namespace": "vectra-app"}})),
]



def _env_of(container_of: Callable[[list[Doc]], Doc], name: str) -> Callable[[list[Doc]], Doc]:
    def get(docs: list[Doc]) -> Doc:
        return next(e for e in container_of(docs)["env"] if e["name"] == name)

    return get


def _at(getter: Callable[[list[Doc]], Doc], path: list[str | int], value: Any) -> Callable[[list[Doc]], None]:
    """Cambia `value` en `path` dentro del documento que devuelve `getter`."""

    def change(docs: list[Doc]) -> None:
        node: Any = getter(docs)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return change


def _del(getter: Callable[[list[Doc]], Doc], path: list[str | int]) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        node: Any = getter(docs)
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return change


def _kind(kind: str) -> Callable[[list[Doc]], Doc]:
    return lambda docs: of_kind(docs, kind)


def _remove(kind: str) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.__setitem__(slice(None), [d for d in docs if d["kind"] != kind])


def _dsn(name: str, value: str) -> Callable[[list[Doc]], None]:
    return lambda docs: _env_of(service_container, name)(docs).__setitem__("value", value)


def _drop_env(container_of: Callable[[list[Doc]], Doc], name: str) -> Callable[[list[Doc]], None]:
    return lambda docs: container_of(docs).__setitem__("env", [e for e in container_of(docs)["env"] if e["name"] != name])


def _extra_job(name: str) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        job = copy.deepcopy(migration(docs))
        job["metadata"]["name"] = name
        docs.append(job)

    return change


D = deployment
SPOD = ["spec", "template", "spec"]
SCTR = [*SPOD, "containers", 0]
MIG = migration
MCTR = [*SPOD, "containers", 0]
GOOD_DIGEST = "kind-registry:5000/vectra/decision-registry@sha256:" + "a" * 64
RW = "postgresql://registry-db-rw.vectra-data.svc.cluster.local/registry?sslmode=require"

CASES += [
    # Deployment decision-registry-service
    ("service-shape", _at(D, ["metadata", "name"], "otro")),
    ("service-shape", _at(D, ["metadata", "namespace"], "default")),
    ("service-shape", _at(D, ["spec", "replicas"], 1)),
    ("service-shape", _at(D, [*SPOD, "serviceAccountName"], "default")),
    ("service-shape", _at(D, ["spec", "template", "metadata", "labels", "app.kubernetes.io/name"], "otro")),
    ("service-shape", _at(D, ["metadata", "labels", "vectra.io/criticality"], "high")),
    ("service-shape", lambda docs: D(docs)["spec"]["template"]["spec"]["containers"].append({"name": "otro"})),
    ("service-priority", _at(D, [*SPOD, "priorityClassName"], "vectra-high")),
    ("service-spread", _del(D, [*SPOD, "topologySpreadConstraints"])),
    ("service-spread", _at(D, [*SPOD, "topologySpreadConstraints", 0, "topologyKey"], "kubernetes.io/hostname")),
    ("service-resources", _at(D, [*SCTR, "resources", "requests", "cpu"], "100m")),
    ("service-resources", _at(D, [*SCTR, "resources", "limits", "memory"], "1Gi")),
    ("service-ports", _at(D, [*SCTR, "ports", 1, "containerPort"], 9090)),
    ("service-probes", _at(D, [*SCTR, "readinessProbe", "httpGet", "path"], "/healthz")),
    ("service-probes", _at(D, [*SCTR, "readinessProbe", "httpGet", "port"], "http")),
    ("service-probes", _del(D, [*SCTR, "readinessProbe"])),
    ("service-probes", _at(D, [*SCTR, "livenessProbe", "httpGet", "path"], "/readyz")),
    ("service-probes", _del(D, [*SCTR, "livenessProbe"])),
    # DSN: sin clave en la URL, el host de cada rol y el Secret de cada rol
    ("service-dsn", _dsn("REGISTRY_RW_APP_DSN", RW.replace("postgresql://", "postgresql://registry_app:secreto@"))),
    ("service-dsn", _dsn("REGISTRY_RW_APP_DSN", RW + "&password=secreto&passfile=/run/pgpass/pgpass")),
    ("service-dsn", _dsn("REGISTRY_RW_HEALTH_DSN", RW + "&user=x")),
    ("service-dsn", _dsn("REGISTRY_RO_VERIFIER_DSN", RW + "&user=x&passfile=/run/pgpass/pgpass")),
    ("service-dsn", _drop_env(service_container, "REGISTRY_RW_APP_DSN")),
    ("service-dsn", _drop_env(service_container, "REGISTRY_VERIFIER_PASSWORD")),
    ("service-dsn", lambda docs: _env_of(service_container, "REGISTRY_APP_PASSWORD")(docs).update({"valueFrom": {"secretKeyRef": {"name": "otro", "key": "password"}}})),
    ("service-checkpoint-keys", _drop_env(service_container, "REGISTRY_CHECKPOINT_PUBLIC_KEYS")),
    ("service-checkpoint-keys", lambda docs: _env_of(service_container, "REGISTRY_CHECKPOINT_PUBLIC_KEYS")(docs).update({"valueFrom": {"configMapKeyRef": {"name": "otro", "key": "k"}}})),
    ("workload-image", _at(D, [*SCTR, "image"], "kind-registry:5000/vectra/decision-registry:dev")),
    ("workload-image", _at(D, [*SCTR, "image"], "docker.io/otro/imagen@sha256:" + "a" * 64)),
    ("workload-image", _at(MIG, [*MCTR, "image"], GOOD_DIGEST[:-60])),
    ("workload-hardening", _at(D, [*SPOD, "securityContext", "runAsNonRoot"], False)),
    ("workload-hardening", _at(D, [*SPOD, "securityContext", "runAsUser"], 0)),
    ("workload-hardening", _at(D, [*SPOD, "securityContext", "seccompProfile", "type"], "Unconfined")),
    ("workload-hardening", _at(D, [*SCTR, "securityContext", "readOnlyRootFilesystem"], False)),
    ("workload-hardening", _at(D, [*SPOD, "volumes", 0], {"name": "x", "hostPath": {"path": "/"}})),
    ("workload-hardening", _at(MIG, [*MCTR, "securityContext", "allowPrivilegeEscalation"], True)),
    ("service-oidc", _drop_env(service_container, "VECTRA_OIDC_ISSUER")),
    ("service-oidc", _drop_env(service_container, "VECTRA_CA_BUNDLE")),
    ("service-oidc", lambda docs: _env_of(service_container, "VECTRA_JWKS_URL")(docs).__setitem__("value", "http://keycloak/certs")),
    ("workload-hardening", _at(D, [*SPOD, "volumes", 1], {"name": "otro", "secret": {"secretName": "x"}})),
    ("workload-hardening", _at(D, [*SPOD, "volumes", 1], {"name": "keycloak-ca", "secret": {"secretName": "identity-ca"}})),
    ("servicemonitor-doc", _del(_kind("ServiceMonitor"), ["spec", "endpoints", 0, "honorLabels"])),
    # Job de migracion
    ("migration-hook", _del(MIG, ["metadata", "annotations", "argocd.argoproj.io/hook"])),
    ("migration-hook", _at(MIG, ["metadata", "annotations", "argocd.argoproj.io/hook"], "PostSync")),
    ("migration-hook", _del(MIG, ["metadata", "annotations", "argocd.argoproj.io/hook-delete-policy"])),
    ("migration-shape", _at(MIG, [*SPOD, "serviceAccountName"], "decision-registry-service")),
    ("migration-shape", _at(MIG, ["spec", "template", "metadata", "labels", "vectra.io/workload"], "otro")),
    ("migration-shape", _del(MIG, ["spec", "template", "metadata", "labels", "vectra.io/workload"])),
    ("migration-shape", _at(MIG, ["spec", "activeDeadlineSeconds"], 900)),
    ("migration-shape", _at(MIG, [*SPOD, "priorityClassName"], "vectra-high")),
    ("migration-shape", _del(MIG, ["spec", "template", "metadata", "annotations"])),
    ("migration-shape", _at(MIG, [*SPOD, "restartPolicy"], "OnFailure")),
    ("migration-command", _at(MIG, [*MCTR, "command"], ["alembic", "downgrade", "base"])),
    ("migration-credentials", lambda docs: _env_of(migration_container, "PGPASSWORD")(docs).update({"valueFrom": {"secretKeyRef": {"name": "pg-role-registry-app", "key": "password"}}})),
    ("migration-credentials", _drop_env(migration_container, "PGUSER")),
    ("migration-credentials", _drop_env(migration_container, "REGISTRY_CHECKPOINT_KEY_FINGERPRINT")),
    ("migration-credentials", lambda docs: _env_of(migration_container, "REGISTRY_DATABASE_URL")(docs).__setitem__("value", RW.replace("postgresql://", "postgresql://u:p@"))),
    ("migration-credentials", lambda docs: _env_of(migration_container, "REGISTRY_DATABASE_URL")(docs).__setitem__("value", RW.replace("-rw", "-ro"))),
    ("migration-resources", _at(MIG, [*MCTR, "resources", "limits", "memory"], "512Mi")),
    # HPA, PDB, ServiceMonitor y ConfigMap
    ("hpa-doc", _at(_kind("HorizontalPodAutoscaler"), ["spec", "minReplicas"], 1)),
    ("hpa-doc", _at(_kind("HorizontalPodAutoscaler"), ["spec", "maxReplicas"], 7)),
    ("hpa-doc", _at(_kind("HorizontalPodAutoscaler"), ["spec", "metrics", 0, "resource", "target", "averageUtilization"], 80)),
    ("hpa-doc", _at(_kind("HorizontalPodAutoscaler"), ["spec", "scaleTargetRef", "name"], "otro")),
    ("pdb-doc", _at(_kind("PodDisruptionBudget"), ["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro")),
    ("pdb-doc", _at(_kind("PodDisruptionBudget"), ["spec", "minAvailable"], 0)),
    ("servicemonitor-doc", _at(_kind("ServiceMonitor"), ["metadata", "namespace"], "default")),
    ("servicemonitor-doc", _at(_kind("ServiceMonitor"), ["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro")),
    ("servicemonitor-doc", lambda docs: _kind("ServiceMonitor")(docs)["spec"]["endpoints"].append({"port": "metrics"})),
    ("servicemonitor-port", _at(_kind("ServiceMonitor"), ["spec", "endpoints", 0, "port"], "http")),
    ("servicemonitor-port", _del(_kind("ServiceMonitor"), ["spec", "endpoints", 0, "port"])),
    ("service-port-names", _at(_kind("Service"), ["spec", "ports", 1, "targetPort"], "otro")),
    ("service-pdb", _remove("PodDisruptionBudget")),
    ("service-pdb", _remove("HorizontalPodAutoscaler")),
    ("service-pdb", _at(_kind("PodDisruptionBudget"), ["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro")),
    ("checkpoint-config", _at(_kind("ConfigMap"), ["data", "REGISTRY_CHECKPOINT_PUBLIC_KEYS"], "")),
    ("checkpoint-config", _del(_kind("ConfigMap"), ["data", "REGISTRY_CHECKPOINT_KEY_FINGERPRINT"])),
    # Documentos: lo diferido no se cuela (T5) y el chart no crea Secrets
    ("forbidden-jobs", _extra_job("registry-aggregator-rebuild-20261109-0100")),
    ("forbidden-jobs", _extra_job("registry-aggregator-reset-20261109-0100")),
    ("forbidden-jobs", _extra_job("x06-probe")),
    ("documents-exact", _extra_job("registry-aggregator-rebuild-20261109-0100")),
    ("documents-exact", _remove("ServiceMonitor")),
    ("documents-exact", _remove("Service")),
    ("documents-exact", _remove("ConfigMap")),
    ("service-account-exists", lambda docs: docs.__setitem__(slice(None), [d for d in docs if not (d["kind"] == "ServiceAccount" and d["metadata"]["name"] == "migration-registry")])),
    ("service-account-exists", lambda docs: docs.__setitem__(slice(None), [d for d in docs if not (d["kind"] == "ServiceAccount" and d["metadata"]["name"] == "decision-registry-service")])),
    ("no-external-secret", lambda docs: docs.append({"apiVersion": "external-secrets.io/v1", "kind": "ExternalSecret", "metadata": {"name": "s3-banco", "namespace": "vectra-app"}})),
    ("no-plain-secret", lambda docs: docs.append({"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "pg-role-registry-app", "namespace": "vectra-app"}})),
]


@pytest.mark.parametrize(("rule", "change"), CASES, ids=[f"{r}-{i}" for i, (r, _) in enumerate(CASES)])
def test_cada_regla_tiene_un_caso_que_falla(rule: str, change: Callable[[list[Doc]], None]) -> None:
    mutated = edit(render(), change)
    output = failures(mutated)
    assert f"{rule}:" in output, output


def test_todas_las_reglas_de_las_politicas_tienen_caso() -> None:
    declared = set()
    for rego in (CHART / "policy").glob("*.rego"):
        declared |= {line.split("regla:")[1].strip() for line in rego.read_text().splitlines() if line.startswith("# regla:")}
    assert declared == {rule for rule, _ in CASES}


def test_el_sin_tocar_cumple_inf_u3_03_y_las_reglas_de_admision() -> None:
    """INF-U3-03 y `shared-infrastructure.md` §2: lo que Kyverno y conftest de U1 exigen se lee tambien del render."""
    docs = render()
    spec = deployment(docs)["spec"]
    pod = spec["template"]["spec"]
    assert spec["replicas"] >= 2 and pod["priorityClassName"] == "vectra-critical"
    assert deployment(docs)["metadata"]["labels"]["vectra.io/criticality"] == "critical"
    assert pod["topologySpreadConstraints"][0]["topologyKey"] == "topology.kubernetes.io/zone"
    hpa = of_kind(docs, "HorizontalPodAutoscaler")["spec"]
    assert (hpa["minReplicas"], hpa["maxReplicas"]) == (2, 6)
    assert hpa["metrics"][0]["resource"]["target"]["averageUtilization"] == 70
    assert of_kind(docs, "PodDisruptionBudget")["spec"]["selector"]["matchLabels"] == {"app.kubernetes.io/name": "decision-registry-service"}
    ctr = pod["containers"][0]
    assert ctr["resources"] == {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "512Mi"}}
    assert {p["containerPort"] for p in ctr["ports"]} == {8080, 8081}
    assert ctr["readinessProbe"]["httpGet"] == {"path": "/readyz", "port": "metrics"}


def test_el_servicemonitor_apunta_al_puerto_8081_del_service() -> None:
    """CA-5: el endpoint nombra el puerto 8081 del Service, el mismo que declara el contenedor."""
    docs = render()
    endpoint_ports = [e["port"] for e in of_kind(docs, "ServiceMonitor")["spec"]["endpoints"]]
    service_ports = {p["name"]: p for p in of_kind(docs, "Service")["spec"]["ports"]}
    container_ports = {p["name"]: p["containerPort"] for p in service_container(docs)["ports"]}
    assert endpoint_ports == ["metrics"]
    assert service_ports["metrics"]["port"] == 8081 and container_ports[service_ports["metrics"]["targetPort"]] == 8081


def test_los_pods_llevan_las_etiquetas_que_espera_flows_yaml() -> None:
    """INF-U3-06, NFR-U3-41, F42, F44, F96, F107: las etiquetas de cada pod son las que `platform/network/flows.yaml` selecciona."""
    spec = importlib.util.spec_from_file_location("network_generate", ROOT / "platform/network/generate.py")
    assert spec and spec.loader
    network = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(network)
    flows, _ = network.load()
    docs = render()
    pods = {
        "decision-registry-service": deployment(docs)["spec"]["template"],
        "registry-aggregator": cronjob(docs)["spec"]["jobTemplate"]["spec"]["template"],
        "migration-registry": migration(docs)["spec"]["template"],
    }
    for name, template in pods.items():
        workload = flows["workloads"][name]
        assert workload["ns"] == "vectra-app"
        assert template["spec"]["serviceAccountName"] == workload["sa"], name
        wanted = network.labels_of(workload)
        assert wanted.items() <= template["metadata"]["labels"].items(), (name, wanted)


def test_las_service_accounts_del_chart_son_las_de_flows_yaml() -> None:
    spec = importlib.util.spec_from_file_location("network_generate", ROOT / "platform/network/generate.py")
    assert spec and spec.loader
    network = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(network)
    flows, _ = network.load()
    in_flows = {w["sa"] for w in flows["workloads"].values() if w["ns"] == "vectra-app"}
    in_chart = {d["metadata"]["name"] for d in render() if d["kind"] == "ServiceAccount"}
    assert in_chart <= in_flows


def test_sin_llaves_de_checkpoint_no_se_renderiza() -> None:
    for key in ("checkpoint.publicKeys", "checkpoint.keyFingerprint"):
        result = subprocess.run(  # noqa: S603
            [tool("helm"), "template", "x", str(CHART), "--set", f"{key}="], capture_output=True, text=True, check=False
        )
        assert result.returncode != 0 and "es obligatorio" in result.stderr, key


def test_el_script_del_passfile_escapa_la_clave_y_no_deja_clave_en_el_render() -> None:
    """La clave nunca esta en el render; el `.pgpass` que arma el contenedor escapa `\\` y `:` (formato de libpq)."""
    docs = render()
    script = service_container(docs)["command"][2]
    assert "/run/pgpass/pgpass" in script and "exec python -m vectra_registry.service" in script
    text = yaml.safe_dump_all(docs)
    assert "password=" not in text.replace("passfile=", "") and "@sha256" in text
    run = subprocess.run(  # noqa: S603
        ["sh", "-c", script.replace("/run/pgpass/pgpass", "/dev/stdout").replace("exec python -m vectra_registry.service", "true")],
        env={
            "PATH": "/usr/bin:/bin",
            "REGISTRY_APP_USER": "app", "REGISTRY_APP_PASSWORD": "a:b\\c",
            "REGISTRY_HEALTH_USER": "h", "REGISTRY_HEALTH_PASSWORD": "hp",
            "REGISTRY_VERIFIER_USER": "v", "REGISTRY_VERIFIER_PASSWORD": "vp",
        },
        capture_output=True, text=True, check=True,
    )
    assert run.stdout.splitlines() == ["*:*:*:app:a\\:b\\\\c", "*:*:*:h:hp", "*:*:*:v:vp"]


def test_las_llaves_de_checkpoint_del_configmap_las_lee_el_servicio() -> None:
    """`REGISTRY_CHECKPOINT_PUBLIC_KEYS` (candidata de U03-T03): llaves Ed25519 de 32 bytes en base64, como las lee `service.py`."""
    import base64

    data = of_kind(render(), "ConfigMap")["data"]
    keys = [base64.b64decode(part, validate=True) for part in data["REGISTRY_CHECKPOINT_PUBLIC_KEYS"].split(",")]
    assert keys and all(len(key) == 32 for key in keys)
    assert data["REGISTRY_CHECKPOINT_KEY_FINGERPRINT"]


def test_el_repositorio_de_la_imagen_sale_del_registro_del_entorno() -> None:
    """Argo CD pasa `imageRegistry` de `envs/<env>/values.yaml` (`env_values: true`): kind y staging/prod arman su repositorio."""
    expected = {
        "kind-registry:5000": "kind-registry:5000/vectra/decision-registry",
        "registro.banco.internal/vectra": "registro.banco.internal/vectra/decision-registry",
    }
    for registry, repository in expected.items():
        out = subprocess.run(  # noqa: S603
            [tool("helm"), "template", "x", str(CHART), "--set", f"imageRegistry={registry}"], check=True, capture_output=True, text=True
        ).stdout
        docs = [d for d in yaml.safe_load_all(out) if d]
        assert conftest(docs).returncode == 0 and conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0, registry
        assert service_container(docs)["image"].startswith(repository + "@sha256:")
        assert migration_container(docs)["image"].startswith(repository + "@sha256:")
        assert container(docs)["image"].startswith(repository + "@sha256:")
