"""Chart de U4 (Paso 16 acotado a la demo; NFR-U4-03, 25; INF-U4-01, INF-U4-04; F44, F47, F101, F102).

`helm template` + `conftest` con las politicas de `governance/chart/policy/`: HPA de 2 a 6 al 70 %, spread por zona, PDB, `vectra-high`,
recursos de INF-U4-01, DSN sin clave en la URL, el hook de migracion, RBAC de K01 y nada de `model-archive`. Cada `# regla: x` tiene aqui
un caso que falla (una mutacion del render por caso) y el chart sin tocar pasa. Necesita `platform/install-tools.sh`.
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
CHART = ROOT / "governance" / "chart"
BIN = ROOT / "platform" / ".tools" / "bin"
Doc = dict[str, Any]
Change = Callable[[list[Doc]], None]


def tool(name: str) -> str:
    path = BIN / name
    assert path.is_file(), f"falta {path}: corre platform/install-tools.sh"
    return str(path)


def helm(*extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [tool("helm"), "template", "governance", str(CHART), *extra], capture_output=True, text=True, check=False
    )


def render(*extra: str) -> list[Doc]:
    result = helm(*extra)
    assert result.returncode == 0, result.stderr
    return [d for d in yaml.safe_load_all(result.stdout) if d]


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


def of_kind(docs: list[Doc], kind: str, name: str | None = None) -> Doc:
    return next(d for d in docs if d["kind"] == kind and (name is None or d["metadata"]["name"] == name))


def deployment(docs: list[Doc]) -> Doc:
    return of_kind(docs, "Deployment")


def migration(docs: list[Doc]) -> Doc:
    return of_kind(docs, "Job", "governance-migration")


def service_container(docs: list[Doc]) -> Doc:
    return deployment(docs)["spec"]["template"]["spec"]["containers"][0]  # type: ignore[no-any-return]


def migration_container(docs: list[Doc]) -> Doc:
    return migration(docs)["spec"]["template"]["spec"]["containers"][0]  # type: ignore[no-any-return]


def edit(docs: list[Doc], change: Change) -> list[Doc]:
    copied = copy.deepcopy(docs)
    change(copied)
    return copied


def test_el_chart_sin_tocar_pasa_las_dos_pasadas() -> None:
    docs = render()
    assert conftest(docs).returncode == 0
    assert conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0
    assert len(docs) == 13


def test_sin_digest_no_se_renderiza() -> None:
    result = helm("--set", "image.digest=")
    assert result.returncode != 0 and "image.digest es obligatorio" in result.stderr


# --- ayudas de mutacion ------------------------------------------------------------------------------------------------------


def _at(getter: Callable[[list[Doc]], Doc], path: list[str | int], value: Any) -> Change:
    def change(docs: list[Doc]) -> None:
        node: Any = getter(docs)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return change


def _del(getter: Callable[[list[Doc]], Doc], path: list[str | int]) -> Change:
    def change(docs: list[Doc]) -> None:
        node: Any = getter(docs)
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return change


def _kind(kind: str, name: str | None = None) -> Callable[[list[Doc]], Doc]:
    return lambda docs: of_kind(docs, kind, name)


def _remove(kind: str, name: str | None = None) -> Change:
    return lambda docs: docs.__setitem__(
        slice(None), [d for d in docs if not (d["kind"] == kind and (name is None or d["metadata"]["name"] == name))]
    )


def _env(container_of: Callable[[list[Doc]], Doc], name: str) -> Callable[[list[Doc]], Doc]:
    return lambda docs: next(e for e in container_of(docs)["env"] if e["name"] == name)


def _drop_env(container_of: Callable[[list[Doc]], Doc], name: str) -> Change:
    return lambda docs: container_of(docs).__setitem__("env", [e for e in container_of(docs)["env"] if e["name"] != name])


def _set_env(container_of: Callable[[list[Doc]], Doc], name: str, value: str) -> Change:
    return lambda docs: _env(container_of, name)(docs).__setitem__("value", value)


def _extra(kind: str, name: str, namespace: str = "vectra-app", **fields: Any) -> Change:
    return lambda docs: docs.append(
        {"apiVersion": "v1", "kind": kind, "metadata": {"name": name, "namespace": namespace}, **fields}
    )


def _extra_job(name: str) -> Change:
    def change(docs: list[Doc]) -> None:
        job = copy.deepcopy(migration(docs))
        job["metadata"]["name"] = name
        docs.append(job)

    return change


D = deployment
MIG = migration
SPOD = ["spec", "template", "spec"]
SCTR = [*SPOD, "containers", 0]
GOOD_DIGEST = "kind-registry:5000/vectra/governance@sha256:" + "a" * 64
DSN = "postgresql://governance-db-rw.vectra-data.svc.cluster.local/governance?sslmode=require"
SUBJECT = {"kind": "ServiceAccount", "name": "governance-service", "namespace": "vectra-app"}


def _rules(docs: list[Doc]) -> list[Doc]:
    return of_kind(docs, "Role")["rules"]  # type: ignore[no-any-return]


CASES: list[tuple[str, Change]] = [
    # Deployment governance-service
    ("service-shape", _at(D, ["metadata", "name"], "otro")),
    ("service-shape", _at(D, ["metadata", "namespace"], "default")),
    ("service-shape", _at(D, ["spec", "replicas"], 1)),
    ("service-shape", _at(D, [*SPOD, "serviceAccountName"], "default")),
    ("service-shape", _at(D, ["spec", "template", "metadata", "labels", "app.kubernetes.io/name"], "otro")),
    ("service-shape", _at(D, ["metadata", "labels", "vectra.io/criticality"], "medium")),
    ("service-shape", lambda docs: D(docs)["spec"]["template"]["spec"]["containers"].append({"name": "otro"})),
    ("service-priority", _at(D, [*SPOD, "priorityClassName"], "vectra-low")),
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
    # DSN: sin clave en la URL, el host de escritura y el Secret del rol
    ("service-dsn", _set_env(service_container, "GOVERNANCE_DATABASE_DSN", DSN.replace("postgresql://", "postgresql://gov_app:secreto@"))),
    ("service-dsn", _set_env(service_container, "GOVERNANCE_DATABASE_DSN", DSN + "&password=secreto")),
    ("service-dsn", _set_env(service_container, "GOVERNANCE_DATABASE_DSN", DSN.replace("-rw", "-ro"))),
    ("service-dsn", _drop_env(service_container, "GOVERNANCE_DATABASE_DSN")),
    ("service-dsn", _drop_env(service_container, "PGPASSWORD")),
    (
        "service-dsn",
        lambda docs: _env(service_container, "PGPASSWORD")(docs).update({"valueFrom": {"secretKeyRef": {"name": "otro", "key": "password"}}}),
    ),
    # model-store (F47)
    (
        "service-model-store",
        lambda docs: _env(service_container, "GOVERNANCE_S3_SECRET_KEY")(docs).update({"valueFrom": {"secretKeyRef": {"name": "minio-root", "key": "rootPassword"}}}),
    ),
    ("service-model-store", _drop_env(service_container, "GOVERNANCE_S3_ENDPOINT")),
    # Lo que el servicio entrega al model-validation-job
    ("service-validation-config", _drop_env(service_container, "GOVERNANCE_CALLBACK_URL")),
    ("service-validation-config", _drop_env(service_container, "GOVERNANCE_JOB_TOKEN_URL")),
    ("service-validation-config", _set_env(service_container, "GOVERNANCE_VALIDATION_IMAGE", "kind-registry:5000/vectra/model-validation-job:dev")),
    ("service-oidc", _drop_env(service_container, "VECTRA_OIDC_ISSUER")),
    ("service-oidc", _drop_env(service_container, "VECTRA_CA_BUNDLE")),
    ("service-oidc", _set_env(service_container, "VECTRA_JWKS_URL", "http://keycloak/certs")),
    # Identidad propia y pares (U04-T08)
    ("service-identity", _drop_env(service_container, "VECTRA_CLIENT_ID")),
    ("service-identity", _drop_env(service_container, "VECTRA_TOKEN_URL")),
    ("service-identity", _drop_env(service_container, "GOVERNANCE_REGISTRY_URL")),
    ("service-identity", _drop_env(service_container, "GOVERNANCE_BIAS_URL")),
    ("service-identity", _drop_env(service_container, "VECTRA_CLIENT_KEY_PATH")),
    ("service-identity", _set_env(service_container, "VECTRA_CLIENT_KEY_PATH", "/otro/private-key")),
    ("service-identity", lambda docs: service_container(docs).__setitem__("volumeMounts", [m for m in service_container(docs)["volumeMounts"] if m["name"] != "service-identity"])),
    ("service-identity", lambda docs: [m.pop("readOnly") for m in service_container(docs)["volumeMounts"] if m["name"] == "service-identity"]),
    ("service-identity", lambda docs: [v["secret"].update({"secretName": "otro"}) for v in deployment(docs)["spec"]["template"]["spec"]["volumes"] if v["name"] == "service-identity"]),
    ("documents-exact", _remove("ExternalSecret", "governance-service-client")),
    ("no-plain-secret", _extra("ExternalSecret", "governance-service-client", "vectra-staging")),
    # Imagen y endurecimiento
    ("workload-image", _at(D, [*SCTR, "image"], "kind-registry:5000/vectra/governance:dev")),
    ("workload-image", _at(D, [*SCTR, "image"], "docker.io/otro/imagen@sha256:" + "a" * 64)),
    ("workload-image", _at(MIG, [*SCTR, "image"], GOOD_DIGEST[:-60])),
    ("workload-hardening", _at(D, [*SPOD, "securityContext", "runAsNonRoot"], False)),
    ("workload-hardening", _at(D, [*SPOD, "securityContext", "runAsUser"], 0)),
    ("workload-hardening", _at(D, [*SPOD, "securityContext", "seccompProfile", "type"], "Unconfined")),
    ("workload-hardening", _at(D, [*SCTR, "securityContext", "readOnlyRootFilesystem"], False)),
    ("workload-hardening", _at(D, [*SPOD, "volumes", 0], {"name": "x", "hostPath": {"path": "/"}})),
    ("workload-hardening", _at(D, [*SPOD, "volumes", 0], {"name": "otro", "secret": {"secretName": "x"}})),
    ("workload-hardening", _at(MIG, [*SCTR, "securityContext", "allowPrivilegeEscalation"], True)),
    # Job de migracion
    ("migration-hook", _del(MIG, ["metadata", "annotations", "argocd.argoproj.io/hook"])),
    ("migration-hook", _at(MIG, ["metadata", "annotations", "argocd.argoproj.io/hook"], "PostSync")),
    ("migration-hook", _del(MIG, ["metadata", "annotations", "argocd.argoproj.io/hook-delete-policy"])),
    ("migration-shape", _at(MIG, [*SPOD, "serviceAccountName"], "governance-service")),
    ("migration-shape", _at(MIG, ["spec", "template", "metadata", "labels", "vectra.io/workload"], "otro")),
    ("migration-shape", _del(MIG, ["spec", "template", "metadata", "labels", "vectra.io/workload"])),
    ("migration-shape", _at(MIG, ["spec", "activeDeadlineSeconds"], 900)),
    ("migration-shape", _at(MIG, [*SPOD, "priorityClassName"], "vectra-high")),
    ("migration-shape", _del(MIG, ["spec", "template", "metadata", "annotations"])),
    ("migration-shape", _at(MIG, [*SPOD, "restartPolicy"], "OnFailure")),
    ("migration-command", _at(MIG, [*SCTR, "command"], ["alembic", "downgrade", "base"])),
    (
        "migration-credentials",
        lambda docs: _env(migration_container, "PGPASSWORD")(docs).update({"valueFrom": {"secretKeyRef": {"name": "pg-role-gov-app", "key": "password"}}}),
    ),
    ("migration-credentials", _drop_env(migration_container, "PGUSER")),
    ("migration-credentials", _set_env(migration_container, "GOVERNANCE_DATABASE_URL", DSN.replace("postgresql://", "postgresql://u:p@"))),
    ("migration-credentials", _set_env(migration_container, "GOVERNANCE_DATABASE_URL", DSN.replace("-rw", "-ro"))),
    ("migration-resources", _at(MIG, [*SCTR, "resources", "limits", "memory"], "512Mi")),
    # HPA, PDB, ServiceMonitor
    ("hpa-doc", _at(_kind("HorizontalPodAutoscaler"), ["spec", "minReplicas"], 1)),
    ("hpa-doc", _at(_kind("HorizontalPodAutoscaler"), ["spec", "maxReplicas"], 7)),
    ("hpa-doc", _at(_kind("HorizontalPodAutoscaler"), ["spec", "metrics", 0, "resource", "target", "averageUtilization"], 80)),
    ("hpa-doc", _at(_kind("HorizontalPodAutoscaler"), ["spec", "scaleTargetRef", "name"], "otro")),
    ("pdb-doc", _at(_kind("PodDisruptionBudget"), ["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro")),
    ("pdb-doc", _at(_kind("PodDisruptionBudget"), ["spec", "minAvailable"], 0)),
    ("service-pdb", _remove("PodDisruptionBudget")),
    ("service-pdb", _remove("HorizontalPodAutoscaler")),
    ("service-pdb", _at(_kind("PodDisruptionBudget"), ["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro")),
    ("servicemonitor-doc", _del(_kind("ServiceMonitor"), ["spec", "endpoints", 0, "honorLabels"])),
    ("servicemonitor-doc", _at(_kind("ServiceMonitor"), ["metadata", "namespace"], "default")),
    ("servicemonitor-doc", _at(_kind("ServiceMonitor"), ["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro")),
    ("servicemonitor-doc", lambda docs: _kind("ServiceMonitor")(docs)["spec"]["endpoints"].append({"port": "metrics"})),
    ("servicemonitor-port", _at(_kind("ServiceMonitor"), ["spec", "endpoints", 0, "port"], "http")),
    ("servicemonitor-port", _del(_kind("ServiceMonitor"), ["spec", "endpoints", 0, "port"])),
    ("service-port-names", _at(_kind("Service"), ["spec", "ports", 1, "targetPort"], "otro")),
    # RBAC de K01
    ("rbac-k01", _at(_kind("Role"), ["metadata", "namespace"], "vectra-app")),
    ("rbac-k01", lambda docs: _rules(docs).append({"apiGroups": [""], "resources": ["secrets"], "verbs": ["get"]})),
    ("rbac-k01", lambda docs: _rules(docs)[0].__setitem__("verbs", ["create", "get", "delete"])),
    ("rbac-k01", lambda docs: _rules(docs)[0].__setitem__("verbs", ["*"])),
    ("rbac-k01", lambda docs: _rules(docs)[0].__setitem__("resources", ["jobs", "pods"])),
    ("rbac-k01", lambda docs: _rules(docs)[0].__setitem__("apiGroups", ["serving.kserve.io"])),
    ("rbac-k01", _at(_kind("RoleBinding"), ["subjects", 0, "name"], "default")),
    ("rbac-k01", _at(_kind("RoleBinding"), ["subjects", 0, "namespace"], "vectra-staging")),
    ("rbac-k01", _at(_kind("RoleBinding"), ["metadata", "namespace"], "vectra-app")),
    ("rbac-k01", _at(_kind("RoleBinding"), ["roleRef", "kind"], "ClusterRole")),
    ("rbac-k01", _extra("ClusterRoleBinding", "x")),
    # ServiceAccount y ExternalSecret del model-validation-job
    ("validation-job-objects", _extra("ServiceAccount", "otra", "vectra-staging")),
    ("validation-job-objects", _del(_kind("ServiceAccount", "model-validation-job"), ["automountServiceAccountToken"])),
    ("validation-job-objects", _at(_kind("ServiceAccount", "governance-service"), ["secrets"], [{"name": "x"}])),
    # Documentos: lo diferido no se cuela (T5) y el chart no crea Secrets
    ("no-model-archive", _extra("CronJob", "model-archive")),
    ("no-model-archive", _extra_job("model-archive-manual")),
    ("documents-exact", _extra("CronJob", "model-archive")),
    ("documents-exact", _extra_job("governance-migration-2")),
    ("documents-exact", _remove("ServiceMonitor")),
    ("documents-exact", _remove("Service")),
    ("documents-exact", _remove("Role")),
    ("documents-exact", lambda docs: docs.append(copy.deepcopy(docs[0]))),
    ("service-account-exists", _remove("ServiceAccount", "migration-governance")),
    ("service-account-exists", _remove("ServiceAccount", "governance-service")),
    ("no-plain-secret", _extra("Secret", "pg-role-gov-app")),
    ("no-plain-secret", _extra("ExternalSecret", "s3-banco")),
    ("no-plain-secret", _extra("ExternalSecret", "model-validation-job-client", "vectra-app")),
]


@pytest.mark.parametrize(("rule", "change"), CASES, ids=[f"{r}-{i}" for i, (r, _) in enumerate(CASES)])
def test_cada_regla_tiene_un_caso_que_falla(rule: str, change: Change) -> None:
    mutated = edit(render(), change)
    output = failures(mutated)
    assert f"{rule}:" in output, output


def test_todas_las_reglas_de_las_politicas_tienen_caso() -> None:
    declared = set()
    for rego in (CHART / "policy").glob("*.rego"):
        declared |= {line.split("regla:")[1].strip() for line in rego.read_text().splitlines() if line.startswith("# regla:")}
    assert declared == {rule for rule, _ in CASES}


# --- INF-U4-01, NFR-U4-03 y las reglas de admision ----------------------------------------------------------------------------


def test_el_sin_tocar_cumple_inf_u4_01_nfr_u4_03_y_las_reglas_de_admision() -> None:
    """INF-U4-01, NFR-U4-03 y `shared-infrastructure.md` §2: lo que Kyverno y conftest de U1 exigen se lee tambien del render."""
    docs = render()
    spec = deployment(docs)["spec"]
    pod = spec["template"]["spec"]
    assert spec["replicas"] >= 2 and pod["priorityClassName"] == "vectra-high"
    assert deployment(docs)["metadata"]["labels"]["vectra.io/criticality"] == "high"
    assert pod["topologySpreadConstraints"][0]["topologyKey"] == "topology.kubernetes.io/zone"
    hpa = of_kind(docs, "HorizontalPodAutoscaler")["spec"]
    assert (hpa["minReplicas"], hpa["maxReplicas"]) == (2, 6)
    assert hpa["metrics"][0]["resource"]["target"]["averageUtilization"] == 70
    assert of_kind(docs, "PodDisruptionBudget")["spec"]["minAvailable"] == 1
    assert of_kind(docs, "PodDisruptionBudget")["spec"]["selector"]["matchLabels"] == {"app.kubernetes.io/name": "governance-service"}
    ctr = pod["containers"][0]
    assert ctr["resources"] == {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "512Mi"}}
    assert {p["containerPort"] for p in ctr["ports"]} == {8080, 8081}
    assert ctr["readinessProbe"]["httpGet"] == {"path": "/readyz", "port": "metrics"}
    assert "@sha256:" in ctr["image"] and pod["securityContext"]["runAsNonRoot"] is True
    mig = migration(docs)
    assert mig["spec"]["activeDeadlineSeconds"] == 600
    assert mig["spec"]["template"]["spec"]["containers"][0]["resources"] == {
        "requests": {"cpu": "100m", "memory": "128Mi"},
        "limits": {"cpu": "500m", "memory": "256Mi"},
    }


def test_el_servicemonitor_apunta_al_puerto_8081_del_service() -> None:
    docs = render()
    endpoint_ports = [e["port"] for e in of_kind(docs, "ServiceMonitor")["spec"]["endpoints"]]
    service_ports = {p["name"]: p for p in of_kind(docs, "Service")["spec"]["ports"]}
    container_ports = {p["name"]: p["containerPort"] for p in service_container(docs)["ports"]}
    assert endpoint_ports == ["metrics"]
    assert service_ports["metrics"]["port"] == 8081 and container_ports[service_ports["metrics"]["targetPort"]] == 8081


def test_el_render_no_lleva_claves_ni_secrets_ni_archivo_de_modelos() -> None:
    docs = render()
    text = yaml.safe_dump_all(docs)
    assert not [d for d in docs if d["kind"] in {"Secret", "CronJob"}]
    assert "password=" not in text.lower() and "@sha256" in text
    assert "model-archive" not in text and "gov-archiver" not in text


# --- Flujos de U1 (F44, F47, F101, F102) y la ruta `freeze` -----------------------------------------------------------------------


def network() -> Any:
    spec = importlib.util.spec_from_file_location("network_generate", ROOT / "platform/network/generate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_los_pods_llevan_las_etiquetas_que_espera_flows_yaml() -> None:
    """INF-U4-04, F41, F44, F47: las etiquetas de cada pod son las que `platform/network/flows.yaml` selecciona."""
    net = network()
    flows, _ = net.load()
    docs = render()
    pods = {"governance-service": deployment(docs)["spec"]["template"], "migration-governance": migration(docs)["spec"]["template"]}
    for name, template in pods.items():
        workload = flows["workloads"][name]
        assert workload["ns"] == "vectra-app"
        assert template["spec"]["serviceAccountName"] == workload["sa"], name
        wanted = net.labels_of(workload)
        assert wanted.items() <= template["metadata"]["labels"].items(), (name, wanted)


def test_las_service_accounts_del_chart_son_las_de_flows_yaml() -> None:
    flows, _ = network().load()
    in_flows = {(w["ns"], w["sa"]) for w in flows["workloads"].values()}
    in_chart = {(d["metadata"]["namespace"], d["metadata"]["name"]) for d in render() if d["kind"] == "ServiceAccount"}
    assert in_chart <= in_flows


def test_los_flujos_f44_f47_f101_y_f102_estan_en_flows_yaml() -> None:
    """INF-U4-04: F44 (migracion), F47 (model-store) y F101/F102 (`model-archive`, diferido: el flujo ya esta). F100 es egress, diferido."""
    flows, _ = network().load()
    by_id = {f["id"]: f for f in flows["flows"]}
    assert {"F44", "F47", "F101", "F102"} <= by_id.keys()
    assert by_id["F47"]["from"] == ["governance-service"] and by_id["F47"]["to"] == ["minio"]
    assert ["migration-governance", "governance-db"] in by_id["F44"]["also"]
    assert by_id["F101"]["from"] == ["model-archive"] and by_id["F102"]["to"] == ["governance-db"]


def test_la_ruta_freeze_solo_admite_bias_monitoring_job() -> None:
    """INF-U4-04 (F27) y BR-U4-16: la `AuthorizationPolicy` de `freeze` se genera de `http_routes.governance-service`; solo `bias-monitoring-job`.

    BR-U4-16: bias solo puede llamar a `freeze` (X04); el servicio HTTP de bias (`bias-monitoring-service`) queda fuera de esa ruta.
    """
    flows, _ = network().load()
    routes = flows["http_routes"]["governance-service"]["_routes"]
    freeze = [r for r in routes.values() if any("freeze" in m.get("regex", m.get("exact", "")) for m in r["matches"])]
    assert len(freeze) == 1 and freeze[0]["sources"] == ["bias-monitoring-job"]
    assert "bias-monitoring-service" not in {s for r in freeze for s in r["sources"]}


def test_el_chart_no_declara_authorization_policy_ni_httproute() -> None:
    """Las genera U1 (`platform/network/generate.py`): aqui no hay ninguna."""
    kinds = {d["kind"] for d in render()}
    assert not kinds & {"AuthorizationPolicy", "HTTPRoute", "NetworkPolicy", "HTTPRoute.policy.linkerd.io"}


def test_el_repositorio_de_la_imagen_sale_del_registro_del_entorno() -> None:
    """Argo CD pasa `imageRegistry` de `envs/<env>/values.yaml` (`env_values: true`): kind y staging/prod arman su repositorio."""
    expected = {
        "kind-registry:5000": "kind-registry:5000/vectra/governance",
        "registro.banco.internal/vectra": "registro.banco.internal/vectra/governance",
    }
    for registry, repository in expected.items():
        docs = render("--set", f"imageRegistry={registry}")
        assert conftest(docs).returncode == 0 and conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0, registry
        assert service_container(docs)["image"].startswith(repository + "@sha256:")
        assert migration_container(docs)["image"].startswith(repository + "@sha256:")
        validation = next(e for e in service_container(docs)["env"] if e["name"] == "GOVERNANCE_VALIDATION_IMAGE")
        assert validation["value"].startswith(repository.removesuffix("/governance") + "/model-validation-job@sha256:")


def test_el_chart_entrega_callback_url_endpoint_s3_y_url_del_token_del_job() -> None:
    """Cierra las candidatas de U04-T04 (`callback_url`) y U04-T05 (`DEFAULT_S3_ENDPOINT`, `DEFAULT_TOKEN_URL`): salen del Deployment."""
    env = {e["name"]: e.get("value") for e in service_container(render())["env"]}
    assert env["GOVERNANCE_CALLBACK_URL"] == "http://governance-service.vectra-app.svc.cluster.local:8080"
    assert env["GOVERNANCE_JOB_S3_ENDPOINT"].startswith("http://minio.vectra-data")
    assert env["GOVERNANCE_JOB_TOKEN_URL"].endswith("/protocol/openid-connect/token")
