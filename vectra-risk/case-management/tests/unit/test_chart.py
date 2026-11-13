"""Chart de U8 (Paso 20; INF-U8-01 a 07; P-U8-10; NFR-U8-10, 12, 14, 20, 26, 43, 44; INF-U8-05; US-609, US-603) y sus reglas de `conftest`.

`helm template` de los tres entornos, con los values que usa Argo CD (`env_values`, `values-kind.yaml` en kind y `values/<env>/case-management.yaml`), y `conftest`
con `case-management/policies/conftest/` (por documento, con todo el render junto y sobre los ARCHIVOS de values). Cada `# regla: x` de las politicas tiene aqui un
caso que falla (una mutacion del render o del archivo por regla) y el chart sin tocar pasa. Ademas: las variables, la base, la identidad y las sondas contra el
codigo (`Settings.from_env`, `WorkerSettings.from_env`, `migrations/env.py`, `ops_server`, `config`), las URL y la red contra `flows.yaml`, la cuota (INF-U8-05) y las
conexiones (NFR-U8-14) recalculadas, y el render de kind de U1 (`render_env`, P-2) contra el del chart.
Necesita `platform/install-tools.sh` (helm y conftest en `platform/.tools/bin`): si faltan, las pruebas **fallan**.
"""

import ast
import copy
import importlib.util
import re
import subprocess
import sys
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import vectra_case.app as case_app
import vectra_case.config as config
import vectra_case.worker as case_worker
import yaml
from vectra_common import ops_server

ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "case-management"
CHART = CASE / "chart"
POLICIES = CASE / "policies" / "conftest"
GITOPS = ROOT / "vectra-risk-gitops"
NETWORK = ROOT / "platform" / "network"
BIN = ROOT / "platform" / ".tools" / "bin"
ENVS = ("kind", "staging", "prod")
APP = ("case-service", "case-worker")
MOCK = "core-banking-mock"
RUN_ID = "20261112-0900"
# U02-T21: Keycloak publica solo el emisor publico de cada entorno (identity-edge/docs/emisor-de-tokens.md); `jwksUrl` y `tokenUrl` siguen internos.
PUBLIC_ISSUER = {
    "kind": "https://vectra.localtest.me/auth/realms/vectra",
    "staging": "https://vectra.staging.banco.internal/auth/realms/vectra",
    "prod": "https://vectra.banco.internal/auth/realms/vectra",
}
Doc = dict[str, Any]


def tool(name: str) -> str:
    path = BIN / name
    assert path.is_file(), f"falta {path}: corre platform/install-tools.sh"
    return str(path)


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATE = _load(GITOPS / "generate.py", "gitops_generate")
COMPONENTS: list[Doc] = yaml.safe_load((GITOPS / "components.yaml").read_text(encoding="utf-8"))["components"]
COMPONENT = next(c for c in COMPONENTS if c["name"] == "case-management")
FLOWS: Doc = yaml.safe_load((NETWORK / "flows.yaml").read_text(encoding="utf-8"))
FORBIDDEN: list[Doc] = yaml.safe_load((NETWORK / "forbidden.yaml").read_text(encoding="utf-8"))["forbidden"]


@cache
def _render(env: str, extra: tuple[str, ...]) -> tuple[Doc, ...]:
    """Lo que Argo CD renderiza: los values del entorno y los de la unidad, en el orden de `generate.value_files`."""
    files = [GITOPS / "envs" / env / "values.yaml", *(ROOT / f for f in GENERATE.value_files(COMPONENT, env))]
    command = [tool("helm"), "template", "case-management", str(CHART), "--namespace", "vectra-app"]
    for path in files:
        command += ["-f", str(path)]
    out = subprocess.run([*command, *extra], check=True, capture_output=True, text=True).stdout  # noqa: S603
    return tuple(d for d in yaml.safe_load_all(out) if d)


def render(env: str = "kind", *extra: str) -> list[Doc]:
    return copy.deepcopy(list(_render(env, extra)))


def render_rt5() -> list[Doc]:
    return render("kind", "--set", f"probes.runId={RUN_ID}")


def helm_fails(*args: str) -> str:
    """El mensaje de un `helm template` que no rinde (y falla si rinde)."""
    result = subprocess.run(  # noqa: S603
        [tool("helm"), "template", "case-management", str(CHART), "--namespace", "vectra-app", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, "el chart rindio y debia fallar"
    return result.stderr


def conftest(docs: list[Doc], *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [tool("conftest"), "test", "--policy", str(POLICIES), *extra, "-"],
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


def of_kind(docs: list[Doc], kind: str, name: str = "case-service") -> Doc:
    return next(d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name)


def deployment(docs: list[Doc], name: str = "case-service") -> Doc:
    return of_kind(docs, "Deployment", name)


def pod(docs: list[Doc], name: str = "case-service") -> Doc:
    return deployment(docs, name)["spec"]["template"]["spec"]  # type: ignore[no-any-return]


def container(docs: list[Doc], name: str = "case-service") -> Doc:
    return pod(docs, name)["containers"][0]  # type: ignore[no-any-return]


def env_map(c: Doc) -> dict[str, str]:
    return {e["name"]: e.get("value", "") for e in c["env"]}


def migration(docs: list[Doc]) -> Doc:
    return of_kind(docs, "Job", "case-migration")


def rt5(docs: list[Doc]) -> Doc:
    return next(d for d in docs if d["kind"] == "Job" and d["metadata"]["name"].startswith("rt5-demo-"))


def edit(docs: list[Doc], change: Callable[[list[Doc]], None]) -> list[Doc]:
    copied = copy.deepcopy(docs)
    change(copied)
    return copied


# --- mutaciones: una por regla -----------------------------------------------------------------------------------------------------------


def at(doc: Any, path: list[Any]) -> Any:
    for key in path:
        doc = doc[key]
    return doc


def set_at(path: list[Any], value: Any) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        at(doc, path[:-1])[path[-1]] = value

    return change


def drop_at(path: list[Any]) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        parent = at(doc, path[:-1])
        if isinstance(parent, list):
            del parent[path[-1]]
        else:
            parent.pop(path[-1], None)

    return change


def _doc(
    kind: str, name: str = "case-service"
) -> Callable[[Callable[[Doc], None]], Callable[[list[Doc]], None]]:
    def wrap(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
        def apply(docs: list[Doc]) -> None:
            change(of_kind(docs, kind, name))

        return apply

    return wrap


def dep(change: Callable[[Doc], None], name: str = "case-service") -> Callable[[list[Doc]], None]:
    return _doc("Deployment", name)(change)


def job(change: Callable[[Doc], None], name: str = "case-migration") -> Callable[[list[Doc]], None]:
    return _doc("Job", name)(change)


def rt5_job(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
    def apply(docs: list[Doc]) -> None:
        change(rt5(docs))

    return apply


def append_doc(document: Doc) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.append(document)


def drop_doc(kind: str, name: str) -> Callable[[list[Doc]], None]:
    def apply(docs: list[Doc]) -> None:
        docs.remove(of_kind(docs, kind, name))

    return apply


def set_env(name: str, value: str) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        for e in at(doc, POD + ["containers", 0, "env"]):
            if e["name"] == name:
                e["value"] = value
                e.pop("valueFrom", None)
                return
        raise AssertionError(name)

    return change


def add_env(name: str, value: str) -> Callable[[Doc], None]:
    return lambda doc: at(doc, POD + ["containers", 0, "env"]).append({"name": name, "value": value})


def drop_env(name: str) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        env = at(doc, POD + ["containers", 0, "env"])
        env[:] = [e for e in env if e["name"] != name]

    return change


POD = ["spec", "template", "spec"]
CONT = [*POD, "containers", 0]
LABELS = ["spec", "template", "metadata", "labels"]
WORKER = "case-worker"
SEC_REF = [*CONT, "env"]


def secret_name(name: str) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        for e in at(doc, [*POD, "containers", 0, "env"]):
            if e["name"] == "PGUSER":
                e["valueFrom"]["secretKeyRef"]["name"] = name

    return change


def prom(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
    return _doc("PrometheusRule", "case-management")(change)


def rule_of(d: Doc) -> Doc:
    return at(d, ["spec", "groups", 0, "rules", 0])  # type: ignore[no-any-return]


def _expr(change: Callable[[str], str]) -> Callable[[Doc], None]:
    def apply(d: Doc) -> None:
        rule_of(d)["expr"] = change(rule_of(d)["expr"])

    return apply


MOCK_PORTS = [{"name": "http", "containerPort": 8080}, {"name": "metrics", "containerPort": 8081}]

# (nombre del caso, regla que debe fallar, mutacion del render de kind), salvo que el nombre lleve `[prod]` o `[rt5]` (el render de ese caso).
CASES: list[tuple[str, str, Callable[[list[Doc]], None]]] = [
    # secretos
    (
        "un Secret en el render",
        "no-plain-secret",
        append_doc(
            {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "s", "namespace": "vectra-app"}}
        ),
    ),
    (
        "credenciales en el DSN",
        "no-plain-secret",
        dep(
            set_env("CASE_DB_DSN", "postgresql://usuario:clave@case-db-rw.vectra-data.svc.cluster.local/case")
        ),
    ),
    ("PGUSER de otra base", "no-plain-secret", dep(secret_name("pg-role-gov-app"))),
    (
        "una variable desde un Secret",
        "no-plain-secret",
        dep(
            lambda d: at(d, [*CONT, "env"]).append(
                {"name": "X_KEY", "valueFrom": {"secretKeyRef": {"name": "otro", "key": "k"}}}
            )
        ),
    ),
    # variables
    ("LEASE como variable de entorno", "constant-env", dep(add_env("LEASE", "30"), WORKER)),
    (
        "SCORING_TIMEOUT como variable de entorno",
        "constant-env",
        dep(add_env("SCORING_TIMEOUT", "7"), WORKER),
    ),
    ("variable de mas", "service-env", dep(add_env("FOO", "1"), WORKER)),
    ("sin CASE_SCORING_URL en el worker", "service-env", dep(drop_env("CASE_SCORING_URL"), WORKER)),
    ("sin CASE_REGISTRY_URL en case-service", "service-env", dep(drop_env("CASE_REGISTRY_URL"))),
    ("core habilitado sin CASE_CORE_URL", "service-env", dep(drop_env("CASE_CORE_URL"))),
    ("CASE_CORE_URL con el core apagado", "service-env", dep(set_env("CASE_CORE_ENABLED", "false"))),
    ("sin RETENTION_UNDECIDED_YEARS", "service-env", job(drop_env("RETENTION_UNDECIDED_YEARS"))),
    # forma
    ("worker con 1 replica", "service-shape", dep(set_at(["spec", "replicas"], 1), WORKER)),
    ("sin replicas declaradas (1 por defecto)", "service-shape", dep(drop_at(["spec", "replicas"]), WORKER)),
    (
        "dos contenedores",
        "service-shape",
        dep(lambda d: at(d, [*POD, "containers"]).append(copy.deepcopy(at(d, CONT)))),
    ),
    ("otra cuenta de servicio", "service-shape", dep(set_at([*POD, "serviceAccountName"], "otra"))),
    ("etiqueta del pod distinta", "service-shape", dep(set_at([*LABELS, "app.kubernetes.io/name"], "otro"))),
    (
        "pod sin vectra.io/workload",
        "service-shape",
        dep(drop_at([*LABELS, "vectra.io/workload"])),
    ),
    (
        "criticidad baja",
        "service-shape",
        dep(set_at(["metadata", "labels", "vectra.io/criticality"], "low"), WORKER),
    ),
    (
        "el mock sin vectra.io/hpa-exempt",
        "mock-exempt",
        dep(drop_at(["metadata", "annotations", "vectra.io/hpa-exempt"]), MOCK),
    ),
    (
        "el mock con la justificacion vacia",
        "mock-exempt",
        dep(set_at(["metadata", "annotations", "vectra.io/hpa-exempt"], ""), MOCK),
    ),
    (
        "rollout con maxUnavailable 1",
        "service-rollout",
        dep(set_at(["spec", "strategy", "rollingUpdate", "maxUnavailable"], 1)),
    ),
    (
        "vectra-normal en case-service",
        "service-priority",
        dep(set_at([*POD, "priorityClassName"], "vectra-normal")),
    ),
    (
        "vectra-high en la migracion",
        "service-priority",
        job(set_at([*POD, "priorityClassName"], "vectra-high")),
    ),
    (
        "vectra-high en el mock",
        "service-priority",
        dep(set_at([*POD, "priorityClassName"], "vectra-high"), MOCK),
    ),
    ("sin spread por zona", "service-spread", dep(set_at([*POD, "topologySpreadConstraints"], []), WORKER)),
    ("limits de 1Gi", "service-resources", dep(set_at([*CONT, "resources", "limits", "memory"], "1Gi"))),
    (
        "request de CPU de 100m",
        "service-resources",
        dep(set_at([*CONT, "resources", "requests", "cpu"], "100m"), WORKER),
    ),
    (
        "request de memoria de 1Gi",
        "service-resources",
        dep(set_at([*CONT, "resources", "requests", "memory"], "1Gi")),
    ),
    (
        "migracion con limits distintos",
        "service-resources",
        job(set_at([*CONT, "resources", "limits", "cpu"], "2")),
    ),
    ("case-service sin preStop", "service-prestop", dep(drop_at([*CONT, "lifecycle"]))),
    (
        "preStop de 1 s",
        "service-prestop",
        dep(set_at([*CONT, "lifecycle", "preStop", "sleep", "seconds"], 1)),
    ),
    (
        "preStop en el worker",
        "service-prestop",
        dep(set_at([*CONT, "lifecycle"], {"preStop": {"sleep": {"seconds": 5}}}), WORKER),
    ),
    (
        "terminationGracePeriodSeconds 10 en case-service",
        "service-grace",
        dep(set_at([*POD, "terminationGracePeriodSeconds"], 10)),
    ),
    (
        "terminationGracePeriodSeconds 20 en el worker",
        "service-grace",
        dep(set_at([*POD, "terminationGracePeriodSeconds"], 20), WORKER),
    ),
    (
        "sin terminationGracePeriodSeconds",
        "service-grace",
        dep(drop_at([*POD, "terminationGracePeriodSeconds"])),
    ),
    (
        "liveness en /livez",
        "service-probes",
        dep(set_at([*CONT, "livenessProbe", "httpGet", "path"], "/livez")),
    ),
    (
        "readiness en otra ruta",
        "service-probes",
        dep(set_at([*CONT, "readinessProbe", "httpGet", "path"], "/ready"), WORKER),
    ),
    ("sonda al 8080", "service-probes", dep(set_at([*CONT, "readinessProbe", "httpGet", "port"], "http"))),
    ("readiness cada 10 s", "service-probes", dep(set_at([*CONT, "readinessProbe", "periodSeconds"], 10))),
    (
        "liveness cada 5 s",
        "service-probes",
        dep(set_at([*CONT, "livenessProbe", "periodSeconds"], 5), WORKER),
    ),
    (
        "un startupProbe",
        "service-probes",
        dep(set_at([*CONT, "startupProbe"], {"httpGet": {"path": "/healthz", "port": "metrics"}})),
    ),
    (
        "el worker con el 8080",
        "service-ports",
        dep(
            set_at(
                [*CONT, "ports"],
                [{"name": "http", "containerPort": 8080}, {"name": "metrics", "containerPort": 8081}],
            ),
            WORKER,
        ),
    ),
    ("el mock sin el 8080", "service-ports", dep(set_at([*CONT, "ports"], MOCK_PORTS[1:]), MOCK)),
    (
        "el worker con la orden del servicio",
        "service-command",
        dep(set_at([*CONT, "command"], ["python", "-m", "vectra_case.app"]), WORKER),
    ),
    (
        "la migracion sin alembic.ini",
        "service-command",
        job(set_at([*CONT, "command"], ["alembic", "upgrade", "head"])),
    ),
    (
        "el mock con otra orden",
        "service-command",
        dep(set_at([*CONT, "command"], ["python", "-m", "vectra_case.app"]), MOCK),
    ),
    (
        "Deployment sin sidecar nativo",
        "service-sidecar",
        dep(
            drop_at(
                [
                    "spec",
                    "template",
                    "metadata",
                    "annotations",
                    "config.alpha.linkerd.io/proxy-enable-native-sidecar",
                ]
            ),
            WORKER,
        ),
    ),
    (
        "Job de migracion sin sidecar nativo",
        "service-sidecar",
        job(
            drop_at(
                [
                    "spec",
                    "template",
                    "metadata",
                    "annotations",
                    "config.alpha.linkerd.io/proxy-enable-native-sidecar",
                ]
            )
        ),
    ),
    ("VECTRA_CLIENT_ID ajeno", "service-identity", dep(set_env("VECTRA_CLIENT_ID", "case-worker"))),
    (
        "imagen por etiqueta",
        "workload-image",
        dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/case-management:dev"), WORKER),
    ),
    (
        "imagen de otro repositorio",
        "workload-image",
        dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/otra@sha256:" + "a" * 64)),
    ),
    (
        "el mock con la imagen del servicio",
        "workload-image",
        dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/case-management@sha256:" + "a" * 64), MOCK),
    ),
    (
        "digest incompleto",
        "workload-image",
        dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/case-service@sha256:abc")),
    ),
    ("pod como root", "hardening", dep(set_at([*POD, "securityContext", "runAsNonRoot"], False))),
    ("runAsUser 0", "hardening", dep(set_at([*POD, "securityContext", "runAsUser"], 0), WORKER)),
    (
        "sistema de archivos escribible",
        "hardening",
        dep(set_at([*CONT, "securityContext", "readOnlyRootFilesystem"], False)),
    ),
    (
        "privilegios escalables",
        "hardening",
        dep(set_at([*CONT, "securityContext", "allowPrivilegeEscalation"], True), MOCK),
    ),
    (
        "un hostPath",
        "hardening",
        dep(lambda d: at(d, [*POD, "volumes"]).append({"name": "h", "hostPath": {"path": "/"}})),
    ),
    ("montaje de escritura", "read-only-mounts", dep(set_at([*CONT, "volumeMounts", 1, "readOnly"], False))),
    # documentos de apoyo
    ("el mock en vectra-app", "namespace", dep(set_at(["metadata", "namespace"], "vectra-app"), MOCK)),
    ("el Service en default", "namespace", _doc("Service")(set_at(["metadata", "namespace"], "default"))),
    (
        "cuenta con Secret",
        "service-account-doc",
        _doc("ServiceAccount")(set_at(["secrets"], [{"name": "x"}])),
    ),
    (
        "cuenta sin automount",
        "service-account-doc",
        _doc("ServiceAccount", WORKER)(set_at(["automountServiceAccountToken"], False)),
    ),
    (
        "cuenta ajena",
        "service-account-doc",
        _doc("ServiceAccount", "migration-case")(set_at(["metadata", "name"], "otra")),
    ),
    (
        "el Service del worker con el 8080",
        "service-doc",
        _doc("Service", WORKER)(
            lambda d: d["spec"]["ports"].append({"name": "http", "port": 8080, "targetPort": "http"})
        ),
    ),
    (
        "el Service del mock sin el 8080",
        "service-doc",
        _doc("Service", MOCK)(
            set_at(["spec", "ports"], [{"name": "metrics", "port": 8081, "targetPort": "metrics"}])
        ),
    ),
    ("un Service ajeno", "service-doc", _doc("Service")(set_at(["metadata", "name"], "otro"))),
    ("HPA de 1 a 6", "hpa-doc", _doc("HorizontalPodAutoscaler")(set_at(["spec", "minReplicas"], 1))),
    ("HPA hasta 8", "hpa-doc", _doc("HorizontalPodAutoscaler", WORKER)(set_at(["spec", "maxReplicas"], 8))),
    (
        "HPA al 50 % de CPU",
        "hpa-doc",
        _doc("HorizontalPodAutoscaler")(
            set_at(["spec", "metrics", 0, "resource", "target", "averageUtilization"], 50)
        ),
    ),
    (
        "HPA con estabilizacion de 30 s hacia arriba",
        "hpa-doc",
        _doc("HorizontalPodAutoscaler")(
            set_at(["spec", "behavior", "scaleUp", "stabilizationWindowSeconds"], 30)
        ),
    ),
    (
        "HPA con estabilizacion de 60 s hacia abajo",
        "hpa-doc",
        _doc("HorizontalPodAutoscaler", WORKER)(
            set_at(["spec", "behavior", "scaleDown", "stabilizationWindowSeconds"], 60)
        ),
    ),
    (
        "el HPA escala el mock",
        "hpa-doc",
        _doc("HorizontalPodAutoscaler")(set_at(["spec", "scaleTargetRef", "name"], MOCK)),
    ),
    ("PDB con minAvailable 2", "pdb-doc", _doc("PodDisruptionBudget")(set_at(["spec", "minAvailable"], 2))),
    (
        "PDB que selecciona otro nombre",
        "pdb-doc",
        _doc("PodDisruptionBudget")(
            set_at(["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro")
        ),
    ),
    (
        "PDB sin vectra.io/workload",
        "pdb-doc",
        _doc("PodDisruptionBudget", WORKER)(
            drop_at(["spec", "selector", "matchLabels", "vectra.io/workload"])
        ),
    ),
    (
        "ServiceMonitor sin honorLabels",
        "servicemonitor-doc",
        _doc("ServiceMonitor")(set_at(["spec", "endpoints", 0, "honorLabels"], False)),
    ),
    (
        "ServiceMonitor de otro Service",
        "servicemonitor-doc",
        _doc("ServiceMonitor", WORKER)(
            set_at(["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro")
        ),
    ),
    (
        "ServiceMonitor con dos endpoints",
        "servicemonitor-doc",
        _doc("ServiceMonitor", MOCK)(lambda d: d["spec"]["endpoints"].append({"port": "http"})),
    ),
    (
        "un CronJob (P-12)",
        "no-cronjob",
        append_doc(
            {
                "apiVersion": "batch/v1",
                "kind": "CronJob",
                "metadata": {"name": "case-retention", "namespace": "vectra-app"},
            }
        ),
    ),
    (
        "una HTTPRoute",
        "u1-owned",
        append_doc(
            {
                "apiVersion": "gateway.networking.k8s.io/v1",
                "kind": "HTTPRoute",
                "metadata": {"name": "core-mock-catch-all", "namespace": "vectra-mock"},
            }
        ),
    ),
    (
        "una AuthorizationPolicy",
        "u1-owned",
        append_doc(
            {
                "apiVersion": "policy.linkerd.io/v1alpha1",
                "kind": "AuthorizationPolicy",
                "metadata": {"name": "x", "namespace": "vectra-mock"},
            }
        ),
    ),
    # la migracion
    (
        "migracion sin el hook de sync",
        "migration-job",
        job(drop_at(["metadata", "annotations", "argocd.argoproj.io/hook"])),
    ),
    ("migracion con otra cuenta", "migration-job", job(set_at([*POD, "serviceAccountName"], "case-service"))),
    ("migracion sin vectra.io/workload", "migration-job", job(drop_at([*LABELS, "vectra.io/workload"]))),
    ("migracion sin backoffLimit", "migration-job", job(drop_at(["spec", "backoffLimit"]))),
    ("migracion sin activeDeadlineSeconds", "migration-job", job(drop_at(["spec", "activeDeadlineSeconds"]))),
    (
        "migracion con restartPolicy OnFailure",
        "migration-job",
        job(set_at([*POD, "restartPolicy"], "OnFailure")),
    ),
    ("migracion con el usuario del servicio", "migration-job", job(secret_name("pg-role-case-app"))),
    # el Job rt5-demo ([rt5]: el render de kind con `probes.runId`)
    (
        "[rt5] con la cuenta del worker",
        "rt5-job",
        rt5_job(set_at([*POD, "serviceAccountName"], "case-worker")),
    ),
    (
        "[rt5] con otra etiqueta de nombre",
        "rt5-job",
        rt5_job(set_at([*LABELS, "app.kubernetes.io/name"], "rt5-demo")),
    ),
    (
        "[rt5] con vectra.io/workload: case-service",
        "rt5-job",
        rt5_job(set_at([*LABELS, "vectra.io/workload"], "case-service")),
    ),
    ("[rt5] con backoffLimit 1", "rt5-job", rt5_job(set_at(["spec", "backoffLimit"], 1))),
    ("[rt5] con restartPolicy OnFailure", "rt5-job", rt5_job(set_at([*POD, "restartPolicy"], "OnFailure"))),
    (
        "[rt5] con ttlSecondsAfterFinished",
        "rt5-job",
        rt5_job(set_at(["spec", "ttlSecondsAfterFinished"], 86400)),
    ),
    (
        "[rt5] con la llave de Keycloak montada",
        "rt5-job",
        rt5_job(
            set_at(
                [*POD, "volumes"],
                [{"name": "service-identity", "secret": {"secretName": "case-service-client"}}],
            )
        ),
    ),
    (
        "[rt5] con un nombre sin el formato",
        "rt5-job",
        rt5_job(set_at(["metadata", "name"], "rt5-demo-manual")),
    ),
    # la PrometheusRule
    (
        "una segunda alerta",
        "prometheus-rule",
        prom(
            lambda d: d["spec"]["groups"][0]["rules"].append(
                {"alert": "Otra", "expr": "vector(1)", "labels": {"severity": "SEV3"}}
            )
        ),
    ),
    (
        "una regla de grabacion",
        "prometheus-rule",
        prom(lambda d: d["spec"]["groups"][0]["rules"].append({"record": "x:y", "expr": "vector(1)"})),
    ),
    ("la alerta con for", "prometheus-rule", prom(lambda d: rule_of(d).update({"for": "1m"}))),
    ("la alerta SEV3", "prometheus-rule", prom(lambda d: rule_of(d)["labels"].update({"severity": "SEV3"}))),
    (
        "otro runbook",
        "prometheus-rule",
        prom(lambda d: rule_of(d)["annotations"].update({"runbook_url": "x.md"})),
    ),
    (
        "sin el filtro de route_name",
        "prometheus-rule",
        prom(_expr(lambda e: e.replace(', route_name="core-mock-catch-all"', ""))),
    ),
    ("sin offset 5m", "prometheus-rule", prom(_expr(lambda e: e.replace(" offset 5m", "")))),
    ("sin or vector(0)", "prometheus-rule", prom(_expr(lambda e: e.replace(" or vector(0)", "")))),
    (
        "increase() sobre la serie de Linkerd",
        "prometheus-rule",
        prom(
            _expr(
                lambda e: e.replace(
                    "sum(inbound_http_authz_deny_total{", "sum(increase(inbound_http_authz_deny_total{", 1
                )
            )
        ),
    ),
    # el render completo
    (
        "un documento repetido",
        "documents-exact",
        lambda docs: docs.append(copy.deepcopy(of_kind(docs, "ServiceAccount", WORKER))),
    ),
    ("sin el ExternalSecret del worker", "documents-exact", drop_doc("ExternalSecret", "case-worker-client")),
    ("sin el Job de migracion", "documents-exact", drop_doc("Job", "case-migration")),
    ("el mock sin su PDB", "documents-exact", drop_doc("PodDisruptionBudget", MOCK)),
    (
        "[rt5] dos Job rt5-demo",
        "documents-exact",
        lambda docs: docs.append(
            {
                **copy.deepcopy(rt5(docs)),
                "metadata": {**rt5(docs)["metadata"], "name": "rt5-demo-20261112-0901"},
            }
        ),
    ),
    ("el core apagado con el mock", "core-consistency", dep(set_env("CASE_CORE_ENABLED", "false"))),
    (
        "el core encendido sin el mock",
        "core-consistency",
        lambda docs: [
            drop_doc(k, n)(docs)
            for k, n in (
                ("Deployment", MOCK),
                ("Service", MOCK),
                ("PodDisruptionBudget", MOCK),
                ("ServiceAccount", MOCK),
                ("ServiceMonitor", MOCK),
                ("PrometheusRule", "case-management"),
            )
        ],
    ),
    (
        "etiqueta del pod fuera de flows.yaml",
        "service-labels",
        dep(set_at([*LABELS, "app.kubernetes.io/name"], "case")),
    ),
    (
        "cuenta de servicio fuera del render",
        "service-account-exists",
        drop_doc("ServiceAccount", "case-worker"),
    ),
    ("llave fuera del volumen", "identity", dep(set_env("VECTRA_CLIENT_KEY_PATH", "/tmp/private-key"))),
    (
        "la llave de otro proceso",
        "identity",
        dep(set_env("VECTRA_CLIENT_KEY_PATH", "/var/run/vectra/client/otra"), WORKER),
    ),
    (
        "ExternalSecret con otra llave de la boveda",
        "identity",
        _doc("ExternalSecret", "case-service-client")(
            set_at(["spec", "data", 0, "remoteRef", "key"], "identity/clients/case-worker")
        ),
    ),
    (
        "ExternalSecret que crea otro Secret",
        "identity",
        _doc("ExternalSecret", "case-worker-client")(set_at(["spec", "target", "name"], "otro")),
    ),
    ("el worker con el Secret de case-service", "identity", dep(secret_name("pg-role-case-app"), WORKER)),
    (
        "[rt5] el Service selecciona el Job",
        "rt5-selector",
        rt5_job(set_at([*LABELS, "vectra.io/workload"], "case-service")),
    ),
    (
        "el Service sin vectra.io/workload en el pod",
        "rt5-selector",
        dep(drop_at([*LABELS, "vectra.io/workload"])),
    ),
    (
        "el mismo digest pero la misma orden",
        "distinct-commands",
        dep(set_at([*CONT, "command"], ["python", "-m", "vectra_case.app"]), WORKER),
    ),
    (
        "imagenes distintas en los dos Deployment",
        "distinct-commands",
        dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/case-management@sha256:" + "b" * 64), WORKER),
    ),
]


@pytest.mark.parametrize("env", ENVS)
def test_the_chart_as_is_passes_every_conftest_pass_in_every_environment(env: str) -> None:
    docs = render(env)
    assert conftest(docs).returncode == 0, conftest(docs).stdout
    assert conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0
    assert len(docs) == (16 if env == "prod" else 22)


def test_rt5_the_chart_with_the_job_passes_every_conftest_pass() -> None:
    docs = render_rt5()
    assert conftest(docs).returncode == 0, conftest(docs).stdout
    assert conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0


@pytest.mark.parametrize(("name", "rule", "change"), CASES, ids=[c[0] for c in CASES])
def test_each_mutation_of_the_render_fails_its_rule(
    name: str, rule: str, change: Callable[[list[Doc]], None]
) -> None:
    base = render_rt5() if name.startswith("[rt5]") else render()
    output = failures(edit(base, change))
    assert f"{rule}:" in output, f"{name}: ninguna regla {rule} fallo\n{output}"


@pytest.mark.parametrize("env", ENVS)
def test_inventory_each_environment_renders_exactly_what_the_task_lists(env: str) -> None:
    """CA-2: el inventario por entorno. Prod: nada en `vectra-mock`, ninguna PrometheusRule, ningun CronJob; kind y staging, el mock y la regla."""
    docs = render(env)
    kinds = sorted(d["kind"] for d in docs)
    base = (
        ["Deployment"] * 2
        + ["ExternalSecret"] * 2
        + ["HorizontalPodAutoscaler"] * 2
        + ["Job"]
        + ["PodDisruptionBudget"] * 2
    )
    base += ["Service"] * 2 + ["ServiceAccount"] * 3 + ["ServiceMonitor"] * 2
    if env == "prod":
        assert kinds == sorted(base)
        assert not [d for d in docs if d["metadata"].get("namespace") == "vectra-mock"]
    else:
        expected = [
            *base,
            "Deployment",
            "PodDisruptionBudget",
            "PrometheusRule",
            "Service",
            "ServiceAccount",
            "ServiceMonitor",
        ]
        assert kinds == sorted(expected)
        assert {d["metadata"]["namespace"] for d in docs if d["metadata"]["name"] == MOCK} == {"vectra-mock"}
    assert "CronJob" not in kinds and not [d for d in docs if d["metadata"]["name"].startswith("rt5-demo")]


@pytest.mark.parametrize("env", ENVS)
@pytest.mark.parametrize("name", APP)
def test_each_process_follows_inf_u8_04_and_06(env: str, name: str) -> None:
    docs = render(env)
    spec = deployment(docs, name)["spec"]
    assert spec["replicas"] == 2, "test_kind_profile.py cuenta spec.replicas"
    assert spec["strategy"]["rollingUpdate"] == {"maxSurge": 1, "maxUnavailable": 0}
    p, c = pod(docs, name), container(docs, name)
    assert p["priorityClassName"] == "vectra-high"
    assert deployment(docs, name)["metadata"]["labels"]["vectra.io/criticality"] == "high"
    cpu, memory = ("250m", "256Mi") if name == "case-service" else ("200m", "256Mi")
    if env == "kind":
        memory = "128Mi"  # P-1 = (b), decision del usuario (2026-11-12): solo en kind
    assert c["resources"] == {
        "requests": {"cpu": cpu, "memory": memory},
        "limits": {"cpu": "1", "memory": "512Mi"},
    }
    assert c["readinessProbe"]["httpGet"] == {"path": "/readyz", "port": "metrics"}
    assert c["livenessProbe"]["httpGet"] == {"path": "/healthz", "port": "metrics"}
    assert (c["readinessProbe"]["periodSeconds"], c["livenessProbe"]["periodSeconds"]) == (5, 10)
    assert "startupProbe" not in c
    assert (p["securityContext"]["runAsUser"], p["securityContext"]["runAsGroup"]) == (65532, 65532)
    hpa = of_kind(docs, "HorizontalPodAutoscaler", name)["spec"]
    assert (hpa["minReplicas"], hpa["maxReplicas"]) == (2, 6)
    assert hpa["metrics"][0]["resource"]["target"]["averageUtilization"] == 70
    assert (
        hpa["behavior"]["scaleUp"]["stabilizationWindowSeconds"],
        hpa["behavior"]["scaleDown"]["stabilizationWindowSeconds"],
    ) == (60, 300)
    assert of_kind(docs, "PodDisruptionBudget", name)["spec"]["minAvailable"] == 1
    assert p["topologySpreadConstraints"][0]["topologyKey"] == "topology.kubernetes.io/zone"
    assert deployment(docs, name)["spec"]["template"]["metadata"]["annotations"] == {
        "config.alpha.linkerd.io/proxy-enable-native-sidecar": "true"
    }


@pytest.mark.parametrize("env", ENVS)
def test_the_mock_and_the_migration_follow_inf_u8_02_and_04(env: str) -> None:
    docs = render(env)
    job_pod = migration(docs)["spec"]["template"]
    assert job_pod["spec"]["priorityClassName"] == "vectra-low"
    assert job_pod["spec"]["containers"][0]["resources"] == {
        "requests": {"cpu": "100m", "memory": "128Mi"},
        "limits": {"cpu": "500m", "memory": "256Mi"},
    }
    if env == "prod":
        assert not [d for d in docs if d["metadata"]["name"] == MOCK]
        return
    mock = deployment(docs, MOCK)
    assert mock["spec"]["replicas"] == 2 and mock["metadata"]["annotations"]["vectra.io/hpa-exempt"]
    assert mock["metadata"]["labels"]["vectra.io/criticality"] == "medium"
    mock_pod = pod(docs, MOCK)
    assert mock_pod["priorityClassName"] == "vectra-low"
    assert mock_pod["containers"][0]["resources"] == {
        "requests": {"cpu": "50m", "memory": "64Mi"},
        "limits": {"cpu": "250m", "memory": "128Mi"},
    }
    assert of_kind(docs, "PodDisruptionBudget", MOCK)["spec"]["minAvailable"] == 1
    assert not [
        d
        for d in docs
        if d["kind"] == "HorizontalPodAutoscaler" and d["spec"]["scaleTargetRef"]["name"] == MOCK
    ]
    assert {p["port"] for p in of_kind(docs, "Service", MOCK)["spec"]["ports"]} == {8080, 8081}  # F17 y F60
    assert {p["port"] for p in of_kind(docs, "Service", "case-worker")["spec"]["ports"]} == {
        8081
    }  # el worker no abre 8080


def test_there_is_no_demo_values_file_and_every_environment_keeps_two_replicas() -> None:
    """T6 / DD-3 b: sin `values-kind-demo.yaml` y sin 1 replica (`require-hpa-bounds`)."""
    assert not list((ROOT / "case-management").rglob("values-kind-demo.yaml"))
    assert not list((GITOPS / "values").rglob("*kind-demo*"))
    for env in ENVS:
        docs = render(env)
        assert {deployment(docs, n)["spec"]["replicas"] for n in APP} == {2}


def test_nfr_u8_10_two_deployments_one_image_by_digest_and_two_commands() -> None:
    """NFR-U8-10 (NFR-U8-12 y NFR-U8-20 en las pruebas de abajo): una imagen por digest y distinta orden."""
    for env in ENVS:
        docs = render(env)
        service, worker = container(docs), container(docs, WORKER)
        assert service["image"] == worker["image"] and "@sha256:" in service["image"]
        assert service["command"] == ["python", "-m", "vectra_case.app"] and worker["command"] == [
            "python",
            "-m",
            "vectra_case.worker",
        ]
        assert migration(docs)["spec"]["template"]["spec"]["containers"][0]["image"] == service["image"]


def test_nfr_u8_12_and_20_the_two_processes_are_high_criticality_with_hpa_pdb_and_spread() -> None:
    docs = render("staging")
    for name in APP:
        assert deployment(docs, name)["metadata"]["labels"]["vectra.io/criticality"] == "high"
        assert pod(docs, name)["priorityClassName"] == "vectra-high"
        assert of_kind(docs, "HorizontalPodAutoscaler", name)["spec"]["maxReplicas"] == 6
        assert of_kind(docs, "PodDisruptionBudget", name)["spec"]["minAvailable"] == 1


# --- las variables, la base, la identidad y las sondas contra el codigo -------------------------------------------------------------------


def env_py_variables() -> dict[str, str]:
    """`RETENTION_VARIABLES` de `migrations/env.py`, leido del codigo (el modulo necesita el contexto de alembic para importarse)."""
    tree = ast.parse((CASE / "migrations" / "env.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "RETENTION_VARIABLES":
            return dict(ast.literal_eval(node.value))
    raise AssertionError("RETENTION_VARIABLES")


def reads_from_env(function: Callable[[dict[str, str]], Any], environment: dict[str, str]) -> set[str]:
    """Las variables que `from_env` realmente lee del entorno que pone el chart: el entorno registra cada acceso."""
    seen: set[str] = set()

    class Spy(dict):  # type: ignore[type-arg]
        def __getitem__(self, key: str) -> str:
            seen.add(key)
            return super().__getitem__(key)

    function(Spy(environment))
    return seen


@pytest.mark.parametrize("env", ENVS)
def test_env_each_container_has_what_its_code_reads_and_no_constant(env: str) -> None:
    docs = render(env)
    service, worker = env_map(container(docs)), env_map(container(docs, WORKER))
    read_service = reads_from_env(lambda e: case_app.Settings.from_env(e), service)
    read_worker = reads_from_env(lambda e: case_worker.WorkerSettings.from_env(e), worker)
    assert read_service <= set(service) and read_worker <= set(worker), (
        read_service - set(service),
        read_worker - set(worker),
    )
    u0 = {
        "VECTRA_OIDC_ISSUER",
        "VECTRA_JWKS_URL",
        "VECTRA_CLIENT_ID",
        "VECTRA_TOKEN_URL",
        "VECTRA_CLIENT_KEY_PATH",
        "VECTRA_CA_BUNDLE",
    }
    assert u0 <= set(service) and {
        "VECTRA_CLIENT_ID",
        "VECTRA_TOKEN_URL",
        "VECTRA_CLIENT_KEY_PATH",
        "VECTRA_CA_BUNDLE",
    } <= set(worker)
    assert not {"VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL"} & set(worker)
    constants = {n for n in dir(config) if n.isupper() and not n.startswith("_")}
    names = {
        e["name"]
        for d in docs
        if d["kind"] in {"Deployment", "Job"}
        for e in d["spec"]["template"]["spec"]["containers"][0]["env"]
    }
    assert constants and not constants & names, "INF-U8-07: una constante de config.py es variable de entorno"
    mig = env_map(migration(docs)["spec"]["template"]["spec"]["containers"][0])
    assert set(env_py_variables().values()) <= set(mig) and "CASE_DATABASE_URL" in mig
    assert (service["CASE_CORE_ENABLED"], service["CASE_ALLOW_TEST_SCENARIOS"]) == (
        ("false", "false") if env == "prod" else ("true", "true")
    )
    assert ("CASE_CORE_URL" in service) == (env != "prod")
    assert service["VECTRA_CLIENT_ID"] == "case-service" and worker["VECTRA_CLIENT_ID"] == "case-worker"
    mock_env = (
        env_map(container(docs, MOCK))
        if env != "prod"
        else {"VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL", "VECTRA_CA_BUNDLE"}
    )
    assert set(mock_env) == {"VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL", "VECTRA_CA_BUNDLE"}


@pytest.mark.parametrize("env", ENVS)
def test_env_the_processes_start_with_exactly_the_variables_the_chart_injects(env: str) -> None:
    """`Settings.from_env` y `WorkerSettings.from_env` aceptan el entorno que pone el chart."""
    docs = render(env)
    settings = case_app.Settings.from_env(env_map(container(docs)))
    assert settings.governance_url.startswith("http://governance-service.vectra-app")
    assert settings.registry_url.startswith("http://decision-registry-service.vectra-app")
    assert settings.core_enabled == (env != "prod") and (settings.core_url is None) == (env == "prod")
    assert settings.allow_test_scenarios == (env != "prod")
    worker = case_worker.WorkerSettings.from_env(env_map(container(docs, WORKER)))
    assert worker.scoring_url.startswith("http://scoring-service.vectra-app")


def test_env_a_missing_required_variable_is_found_by_the_code_check() -> None:
    docs = edit(render(), dep(drop_env("CASE_SCORING_URL"), WORKER))
    with pytest.raises(KeyError):
        case_worker.WorkerSettings.from_env(env_map(container(docs, WORKER)))


def flow(flow_id: str) -> Doc:
    return next(f for f in FLOWS["flows"] if f["id"] == flow_id)


def url_of(flow_id: str, target: str | None = None) -> str:
    """`http://<Service>.<namespace>.svc.cluster.local:<puerto>` del destino de un flujo de `flows.yaml`."""
    f = flow(flow_id)
    name = target or f["to"][0]
    workload = FLOWS["workloads"][name]
    return f"http://{workload['name']}.{workload['ns']}.svc.cluster.local:{f['port']}"


@pytest.mark.parametrize("env", ENVS)
def test_env_the_urls_are_the_services_and_ports_of_the_flows(env: str) -> None:
    docs = render(env)
    service, worker = env_map(container(docs)), env_map(container(docs, WORKER))
    assert worker["CASE_SCORING_URL"] == url_of("F15")
    assert service["CASE_REGISTRY_URL"] == url_of("F16")
    assert service["CASE_GOVERNANCE_URL"] == worker["CASE_GOVERNANCE_URL"] == url_of("F104")
    if env != "prod":
        assert service["CASE_CORE_URL"] == url_of("F17")


@pytest.mark.parametrize("env", ENVS)
def test_dsn_no_credentials_the_case_db_host_verify_full_and_the_ca_of_each_role(env: str) -> None:
    """INF-U8-01 y NFR-U8-40: el DSN va sin credenciales, apunta a `case-db-rw`, con `sslmode=verify-full` y la CA interna (P-6 = a)."""
    docs = render(env)
    roles = {"case-service": "pg-role-case-app", "case-worker": "pg-role-case-worker"}
    for name, secret in roles.items():
        c = container(docs, name)
        dsn = env_map(c)["CASE_DB_DSN"]
        assert (
            dsn
            == "postgresql://case-db-rw.vectra-data.svc.cluster.local/case?sslmode=verify-full&sslrootcert=/etc/vectra/ca/ca.crt"
        )
        assert "@" not in dsn
        refs = {e["name"]: e["valueFrom"]["secretKeyRef"] for e in c["env"] if "valueFrom" in e}
        assert refs == {
            "PGUSER": {"name": secret, "key": "username"},
            "PGPASSWORD": {"name": secret, "key": "password"},
        }
        mounts = {m["mountPath"] for m in c["volumeMounts"]}
        assert "/etc/vectra/ca" in mounts  # la CA interna para verify-full y para Keycloak (P-6)
    m = migration(docs)["spec"]["template"]["spec"]["containers"][0]
    assert env_map(m)["CASE_DATABASE_URL"] == env_map(container(docs))["CASE_DB_DSN"]
    refs = {e["valueFrom"]["secretKeyRef"]["name"] for e in m["env"] if "valueFrom" in e}
    assert refs == {"pg-role-case-migrator"}
    assert not [d for d in docs if d["kind"] == "Secret"]


def test_dsn_the_sslmode_is_a_value_and_other_modes_do_not_add_a_root_certificate() -> None:
    out = subprocess.run(  # noqa: S603
        [tool("helm"), "template", "case-management", str(CHART), "--set", "database.sslmode=require"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert 'sslmode=require"' in out and "sslrootcert" not in out
    assert "database.sslmode es obligatorio" in helm_fails("--set", "database.sslmode=null")


@pytest.mark.parametrize("env", ENVS)
def test_identity_each_process_mounts_only_its_own_key_read_only(env: str) -> None:
    docs = render(env)
    for name in APP:
        c = container(docs, name)
        mount = next(m for m in c["volumeMounts"] if m["name"] == "service-identity")
        assert mount["readOnly"] is True
        assert env_map(c)["VECTRA_CLIENT_KEY_PATH"] == f"{mount['mountPath']}/private-key"
        volume = next(v for v in pod(docs, name)["volumes"] if v["name"] == "service-identity")
        assert volume["secret"]["secretName"] == f"{name}-client"
        es = of_kind(docs, "ExternalSecret", f"{name}-client")["spec"]
        assert es["data"][0]["remoteRef"] == {"key": f"identity/clients/{name}", "property": "private-key"}
        assert es["target"]["name"] == f"{name}-client"
    for kind_name in (MOCK, "case-migration"):
        assert not [d for d in docs if d["kind"] == "ExternalSecret" and kind_name in d["metadata"]["name"]]
    assert "service-identity" not in {
        v["name"] for v in migration(docs)["spec"]["template"]["spec"]["volumes"]
    }


def test_identity_the_clients_exist_in_the_kind_realm_and_the_vault_paths() -> None:
    realm = (ROOT / "identity-edge" / "keycloak" / "realm" / "realm.kind.yaml").read_text(encoding="utf-8")
    assert len(re.findall(r"clientId: (case-service|case-worker)$", realm, flags=re.M)) == 2
    sys.path.insert(0, str(ROOT / "platform" / "kind"))
    import vault_paths  # type: ignore[import-not-found]

    assert {"case-service", "case-worker"} <= set(vault_paths.service_account_clients())
    data = yaml.safe_load((ROOT / "platform" / "data" / "chart" / "values.yaml").read_text(encoding="utf-8"))
    for role in ("case_app", "case_worker", "case_migrator"):
        assert "vectra-app" in data["roleConsumers"][role]


@pytest.mark.parametrize("env", ENVS)
def test_probes_the_paths_are_routes_that_ops_server_serves(env: str) -> None:
    """INF-U8-04 dice `/livez`, pero `ops_server` (U0) sirve `/healthz`: una sonda a una ruta inexistente reiniciaria los pods."""
    routes = {r.path for r in ops_server.create_ops_app(init_process=False).routes}  # type: ignore[attr-defined]
    assert {"/healthz", "/readyz"} <= routes and "/livez" not in routes
    docs = render(env)
    names = [*APP, *([] if env == "prod" else [MOCK])]
    for name in names:
        for probe in ("readinessProbe", "livenessProbe"):
            assert container(docs, name)[probe]["httpGet"]["path"] in routes


@pytest.mark.parametrize("env", ENVS)
def test_probes_the_termination_grace_of_the_worker_covers_the_code_constant(env: str) -> None:
    """P-4 = (a): el chart usa 40 s, el peor caso real (~34 s); `config.WORKER_TERMINATION_GRACE` (30 s) es el minimo."""
    docs = render(env)
    assert pod(docs, WORKER)["terminationGracePeriodSeconds"] >= config.WORKER_TERMINATION_GRACE
    assert pod(docs, WORKER)["terminationGracePeriodSeconds"] == 40
    assert (
        pod(docs)["terminationGracePeriodSeconds"] == 20
        and container(docs)["lifecycle"]["preStop"]["sleep"]["seconds"] == 5
    )
    assert "lifecycle" not in container(docs, WORKER)


def test_probes_a_lower_grace_than_the_code_constant_is_found() -> None:
    docs = edit(render(), dep(set_at([*POD, "terminationGracePeriodSeconds"], 20), WORKER))
    assert pod(docs, WORKER)["terminationGracePeriodSeconds"] < config.WORKER_TERMINATION_GRACE


def test_constants_none_of_config_is_an_environment_variable_in_any_environment() -> None:
    constants = {n for n in dir(config) if n.isupper() and not n.startswith("_")}
    for env in ENVS:
        docs = render_rt5() if env == "kind" else render(env)
        names = {
            e["name"]
            for d in docs
            if d["kind"] in {"Deployment", "Job"}
            for e in d["spec"]["template"]["spec"]["containers"][0]["env"]
        }
        assert not constants & names
    assert (
        "LEASE" in constants and "SCORING_TIMEOUT" in constants
    )  # los de los casos de conftest existen de verdad


CONSTANTS = sorted(n for n in dir(config) if n.isupper() and not n.startswith("_"))


@pytest.mark.parametrize("name", CONSTANTS)
def test_constants_each_constant_of_config_as_an_environment_variable_fails_conftest(name: str) -> None:
    """INF-U8-07: ninguna constante de `config.py` (importada, no copiada) puede ser variable de entorno del worker; la regla lo rechaza."""
    docs = edit(render(), dep(add_env(name, "1"), WORKER))
    assert conftest(docs).returncode != 0, name


# --- el Job rt5-demo ----------------------------------------------------------------------------------------------------------------------


def test_rt5_the_job_runs_as_case_service_without_the_workload_label_or_a_key_or_the_database() -> None:
    docs = render_rt5()
    j = rt5(docs)
    assert j["metadata"]["name"] == f"rt5-demo-{RUN_ID}"
    spec = j["spec"]
    assert spec["backoffLimit"] == 0 and "ttlSecondsAfterFinished" not in spec
    template = spec["template"]
    assert (
        template["spec"]["serviceAccountName"] == "case-service"
        and template["spec"]["restartPolicy"] == "Never"
    )
    assert template["metadata"]["labels"]["app.kubernetes.io/name"] == "case-service"
    assert "vectra.io/workload" not in template["metadata"]["labels"]
    assert template["metadata"]["annotations"] == {
        "config.alpha.linkerd.io/proxy-enable-native-sidecar": "true"
    }
    assert template["spec"]["priorityClassName"] == "vectra-low" and "volumes" not in template["spec"]
    c = template["spec"]["containers"][0]
    assert c["image"] == container(docs)["image"]
    assert {e["name"] for e in c["env"]} == {"CASE_CORE_URL", "RT5_CREDIT_ID"} and not any(
        "valueFrom" in e for e in c["env"]
    )
    assert env_map(c)["CASE_CORE_URL"] == env_map(container(docs))["CASE_CORE_URL"]
    # el selector del Service y del PDB de case-service NO coincide con las etiquetas del Job y SI con las del Deployment
    labels = template["metadata"]["labels"]
    deployment_labels = deployment(docs)["spec"]["template"]["metadata"]["labels"]
    for selector in (
        of_kind(docs, "Service")["spec"]["selector"],
        of_kind(docs, "PodDisruptionBudget")["spec"]["selector"]["matchLabels"],
    ):
        assert not all(labels.get(k) == v for k, v in selector.items())
        assert all(deployment_labels.get(k) == v for k, v in selector.items())


def test_rt5_the_job_script_exits_zero_only_for_a_403_and_prints_the_proxy_header() -> None:
    script = rt5(render_rt5())["spec"]["template"]["spec"]["containers"][0]["args"][0]
    assert (
        "sys.exit(0 if code == 403 else 1)" in script
        and "l5d-proxy-error" in script
        and "sys.exit(2)" in script
    )
    assert "authorization" not in script.lower()  # sin token
    compile(script, "rt5-demo", "exec")


def test_rt5_the_job_only_exists_with_the_kind_switch_and_a_run_id() -> None:
    assert not [
        d for d in render("kind") if d["kind"] == "Job" and d["metadata"]["name"].startswith("rt5-demo")
    ]
    for env in ("staging", "prod"):
        docs = render(env, "--set", f"probes.runId={RUN_ID}")
        assert not [d for d in docs if d["metadata"]["name"].startswith("rt5-demo")], env
    assert len([d for d in render_rt5() if d["metadata"]["name"].startswith("rt5-demo")]) == 1


@pytest.mark.parametrize(
    "bad", ["manual", "20261112", "2026-11-12", "20261112-09", "20261112-09000", "x20261112-0900"]
)
def test_run_id_a_value_without_the_format_does_not_render_even_with_the_switch_off(bad: str) -> None:
    assert "probes.runId debe cumplir" in helm_fails("--set", f"probes.runId={bad}")


# --- los values por entorno -----------------------------------------------------------------------------------------------------------------


def values_conftest(namespace: str, document: Doc) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [tool("conftest"), "test", "--policy", str(POLICIES), "--namespace", namespace, "-"],
        input=yaml.safe_dump(document, sort_keys=False),
        capture_output=True,
        text=True,
        check=False,
    )


def values_file(env: str) -> Doc:
    return yaml.safe_load((GITOPS / "values" / env / "case-management.yaml").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


VALUES_CASES: list[tuple[str, str, str, Callable[[Doc], None]]] = [
    (
        "prod con la corrida",
        "values.prod",
        "prod-no-run-id",
        lambda v: v.setdefault("probes", {}).update({"runId": RUN_ID}),
    ),
    (
        "prod con el interruptor de las sondas",
        "values.prod",
        "prod-no-run-id",
        lambda v: v.setdefault("probes", {}).update({"enabled": True}),
    ),
    (
        "prod con el core encendido",
        "values.prod",
        "prod-switches",
        lambda v: v["core"].update({"enabled": True}),
    ),
    (
        "prod con el mock encendido",
        "values.prod",
        "prod-switches",
        lambda v: v["coreMock"].update({"enabled": True}),
    ),
    (
        "prod con escenarios de prueba",
        "values.prod",
        "prod-switches",
        lambda v: v.update({"allowTestScenarios": True}),
    ),
    ("prod sin core.enabled", "values.prod", "prod-switches", lambda v: v.pop("core")),
    ("prod sin coreMock.enabled", "values.prod", "prod-switches", lambda v: v.pop("coreMock")),
    ("prod sin allowTestScenarios", "values.prod", "prod-switches", lambda v: v.pop("allowTestScenarios")),
    (
        "staging con la corrida",
        "values.staging",
        "staging-no-run-id",
        lambda v: v.setdefault("probes", {}).update({"runId": RUN_ID}),
    ),
    (
        "staging con el interruptor de las sondas",
        "values.staging",
        "staging-no-run-id",
        lambda v: v.setdefault("probes", {}).update({"enabled": True}),
    ),
]


@pytest.mark.parametrize("env", ["prod", "staging"])
def test_values_the_files_of_staging_and_prod_pass_their_own_namespace(env: str) -> None:
    assert values_conftest(f"values.{env}", values_file(env)).returncode == 0


@pytest.mark.parametrize(
    ("name", "namespace", "rule", "change"), VALUES_CASES, ids=[c[0] for c in VALUES_CASES]
)
def test_values_each_mutation_of_the_files_fails_its_rule(
    name: str, namespace: str, rule: str, change: Callable[[Doc], None]
) -> None:
    document = copy.deepcopy(values_file(namespace.split(".")[1]))
    change(document)
    result = values_conftest(namespace, document)
    assert result.returncode != 0 and f"{rule}:" in result.stdout + result.stderr, result.stdout


def test_values_prod_writes_the_three_switches_and_staging_and_kind_enable_them() -> None:
    assert values_file("prod") == {
        "core": {"enabled": False},
        "coreMock": {"enabled": False},
        "allowTestScenarios": False,
    }
    staging = values_file("staging")
    assert staging == {
        "core": {"enabled": True},
        "coreMock": {"enabled": True},
        "allowTestScenarios": True,
        "keycloak": {"issuer": PUBLIC_ISSUER["staging"]},
    }
    kind = values_file("kind")
    assert kind == {
        "allowTestScenarios": True,
        "probes": {"enabled": True},
        "keycloak": {"issuer": PUBLIC_ISSUER["kind"]},
    }
    # P-2 (a): `values-kind.yaml` lleva solo lo que `render_env("kind")` de U1 debe ver (el core, el mock y el request de P-1) y nada mas.
    assert yaml.safe_load((CHART / "values-kind.yaml").read_text(encoding="utf-8")) == {
        "core": {"enabled": True},
        "coreMock": {"enabled": True},
        "caseService": {"resources": {"requests": {"memory": "128Mi"}}},
        "caseWorker": {"resources": {"requests": {"memory": "128Mi"}}},
    }


def test_values_prod_render_has_no_mock_no_rule_no_core_and_no_test_scenarios() -> None:
    docs = render("prod")
    assert not [
        d for d in docs if d["metadata"].get("namespace") == "vectra-mock" or d["kind"] == "PrometheusRule"
    ]
    assert "CoreWriteAttempt" not in yaml.safe_dump_all(docs)
    service = env_map(container(docs))
    assert (service["CASE_CORE_ENABLED"], service["CASE_ALLOW_TEST_SCENARIOS"]) == ("false", "false")
    # el render sin values de entorno es el de produccion (P-2): los defaults del chart
    bare = [
        d
        for d in yaml.safe_load_all(
            subprocess.run(
                [tool("helm"), "template", "case-management", str(CHART), "-n", "vectra-app"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )
        if d
    ]
    assert sorted((d["kind"], d["metadata"]["name"]) for d in bare) == sorted(
        (d["kind"], d["metadata"]["name"]) for d in docs
    )


def test_kind_values_only_the_memory_request_changes_in_kind_and_staging_and_prod_keep_inf_u8_04() -> None:
    """P-1 = (b), decision del usuario (2026-11-12): 128 MiB solo en kind; replicas, HPA, PDB y limits no cambian."""
    kind, staging, prod = render("kind"), render("staging"), render("prod")
    for name in APP:
        assert container(kind, name)["resources"]["requests"]["memory"] == "128Mi"
        for docs in (staging, prod):
            assert container(docs, name)["resources"]["requests"]["memory"] == "256Mi"
        for docs in (kind, staging, prod):
            assert container(docs, name)["resources"]["limits"]["memory"] == "512Mi"
        stripped = []
        for docs in (kind, staging):
            c = copy.deepcopy(container(docs, name))
            c["resources"]["requests"]["memory"] = "x"
            c["image"] = c["image"].split("@")[
                1
            ]  # diferencia declarada: el registro lo pone `imageRegistry` de cada entorno
            for e in c["env"]:
                if e["name"] == "VECTRA_OIDC_ISSUER":
                    e["value"] = "emisor"  # diferencia declarada: el emisor publico de cada entorno (U02-T21)
            c["env"] = [
                e
                for e in c["env"]
                if e["name"] not in {"CASE_CORE_ENABLED", "CASE_CORE_URL", "CASE_ALLOW_TEST_SCENARIOS"}
            ]
            stripped.append(c)
        assert stripped[0] == stripped[1]  # kind y staging solo se distinguen en el request de memoria
        assert (
            deployment(kind, name)["spec"]["replicas"] == deployment(staging, name)["spec"]["replicas"] == 2
        )
    assert (
        container(kind, MOCK)["resources"] == container(staging, MOCK)["resources"]
    )  # el mock ya pide 64 MiB


def test_retention_values_the_three_terms_are_required_and_change_the_migration_variables() -> None:
    for key in ("decided_years", "undecided_years", "intake_keys_days"):
        assert f"retention.{key} es obligatorio" in helm_fails("--set", f"retention.{key}=null")
    docs = _helm_set(
        "retention.undecided_years=5", "retention.decided_years=11", "retention.intake_keys_days=45"
    )
    mig = env_map(migration(docs)["spec"]["template"]["spec"]["containers"][0])
    assert (
        mig["RETENTION_UNDECIDED_YEARS"],
        mig["RETENTION_DECIDED_YEARS"],
        mig["RETENTION_INTAKE_KEYS_DAYS"],
    ) == ("5", "11", "45")
    defaults = env_map(migration(render("staging"))["spec"]["template"]["spec"]["containers"][0])
    assert (
        defaults["RETENTION_DECIDED_YEARS"],
        defaults["RETENTION_UNDECIDED_YEARS"],
        defaults["RETENTION_INTAKE_KEYS_DAYS"],
    ) == ("10", "2", "30")
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    assert set(values["retention"]) == {"decided_years", "undecided_years", "intake_keys_days"}, (
        "sin retention.schedule ni retention.timeZone (P-12)"
    )


def _helm_set(*sets: str) -> list[Doc]:
    command = [tool("helm"), "template", "case-management", str(CHART), "-n", "vectra-app"]
    for s in sets:
        command += ["--set", s]
    return [
        d
        for d in yaml.safe_load_all(
            subprocess.run(command, capture_output=True, text=True, check=True).stdout
        )
        if d
    ]  # noqa: S603


def test_without_a_digest_it_does_not_render() -> None:
    for key in ("caseManagement", "coreMock"):
        assert f"images.{key}.digest es obligatorio" in helm_fails(
            "--set", f"images.{key}.digest=null", "--set", "coreMock.enabled=true"
        )


@pytest.mark.parametrize("env", ENVS)
def test_issuer_case_service_and_the_mock_validate_tokens_against_the_public_issuer_of_the_environment(
    env: str,
) -> None:
    """U02-T21: `VECTRA_OIDC_ISSUER` es el emisor publico del entorno (el `iss` de los tokens), no la URL interna de Keycloak; `jwksUrl` y `tokenUrl` siguen internos."""
    docs = render(env)
    names = ["case-service", *([] if env == "prod" else [MOCK])]
    for name in names:
        e = env_map(container(docs, name))
        assert e["VECTRA_OIDC_ISSUER"] == PUBLIC_ISSUER[env], name
        assert "keycloak-admin" in e["VECTRA_JWKS_URL"]
    assert "keycloak-admin" in env_map(container(docs, WORKER))["VECTRA_TOKEN_URL"]


def test_issuer_the_internal_url_as_issuer_is_found() -> None:
    internal = "https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra"
    docs = [
        d
        for d in yaml.safe_load_all(
            subprocess.run(
                [
                    tool("helm"),
                    "template",
                    "case-management",
                    str(CHART),
                    "--set",
                    f"keycloak.issuer={internal}",
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )
        if d
    ]
    assert env_map(container(docs))["VECTRA_OIDC_ISSUER"] != PUBLIC_ISSUER["prod"]


def test_the_example_digests_are_distinct_from_the_ones_of_the_other_charts_and_not_all_zeros() -> None:
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    mine = {values["images"][k]["digest"] for k in ("caseManagement", "coreMock")}
    assert len(mine) == 2 and "sha256:" + "0" * 64 not in mine
    others: set[str] = set()
    for chart in ROOT.glob("*/chart/values.yaml"):
        if chart.parent.parent.name != "case-management":
            others |= set(re.findall(r"sha256:0{50,}[0-9a-f]+", chart.read_text(encoding="utf-8")))
    assert not mine & others, mine & others


# --- cuota, conexiones, flujos y la ruta catch-all ---------------------------------------------------------------------------------------


def _cpu(value: str) -> float:
    return float(value[:-1]) / 1000 if value.endswith("m") else float(value)


def _gib(value: str) -> float:
    return float(value[:-2]) / 1024 if value.endswith("Mi") else float(value[:-2])


PROXY = {"requests": (0.100, 20 / 1024), "limits": (0.500, 128 / 1024)}
HEADROOM = 1.3  # el 30 % de NFR-U1-13


def _pod_cost(spec: Doc, kind: str) -> tuple[float, float]:
    cpu = memory = 0.0
    for c in spec["containers"]:
        cpu += _cpu(c["resources"][kind]["cpu"])
        memory += _gib(c["resources"][kind]["memory"])
    return cpu + PROXY[kind][0], memory + PROXY[kind][1]


def contribution(docs: list[Doc], namespace: str) -> dict[str, tuple[float, float]]:
    """Requests y limits (CPU, GiB) de un namespace con el pico de INF-U8-05: HPA al maximo y 1 pod de `maxSurge` por Deployment, y el Job de migracion; con el 30 %."""
    total = {"requests": [0.0, 0.0], "limits": [0.0, 0.0]}
    hpas = {
        d["spec"]["scaleTargetRef"]["name"]: d["spec"]["maxReplicas"]
        for d in docs
        if d["kind"] == "HorizontalPodAutoscaler"
    }
    for d in docs:
        if (
            d["metadata"].get("namespace") != namespace
            or d["kind"] not in {"Deployment", "Job"}
            or d["metadata"]["name"].startswith("rt5-demo")
        ):
            continue
        pods = (
            1
            if d["kind"] == "Job"
            else hpas.get(d["metadata"]["name"], d["spec"]["replicas"])
            + d["spec"]["strategy"]["rollingUpdate"]["maxSurge"]
        )
        for kind in total:
            cpu, memory = _pod_cost(d["spec"]["template"]["spec"], kind)
            total[kind][0] += pods * cpu * HEADROOM
            total[kind][1] += pods * memory * HEADROOM
    return {k: (v[0], v[1]) for k, v in total.items()}


def quota_line(namespace: str) -> Doc:
    quotas = yaml.safe_load(
        (ROOT / "platform" / "policies" / "quotas" / "quotas.yaml").read_text(encoding="utf-8")
    )
    return quotas["namespaces"][namespace]["contributions"]["U8"]  # type: ignore[no-any-return]


def test_quota_inf_u8_05_vectra_app_matches_quotas_yaml_apart_from_the_cronjob_term() -> None:
    """El aporte de `vectra-app` recalculado desde el render de staging no supera la linea de `quotas.yaml`; la diferencia es el CronJob de INF-U8-05 (P-12: no se rinde)."""
    got = contribution(render("staging"), "vectra-app")
    line = quota_line("vectra-app")
    cronjob = {
        "requests": ((0.1 + 0.1) * HEADROOM, (148 / 1024) * HEADROOM),
        "limits": ((0.5 + 0.5) * HEADROOM, (384 / 1024) * HEADROOM),
    }
    for index, kind in enumerate(("requests", "limits")):
        for axis in (0, 1):
            declared = line[kind][axis]
            assert got[kind][axis] <= declared, (kind, axis, got[kind][axis], declared)
            assert abs(got[kind][axis] + cronjob[kind][axis] - declared) <= 0.02, (
                kind,
                axis,
                got[kind][axis] + cronjob[kind][axis],
                declared,
            )
        assert index in (0, 1)


def test_quota_inf_u8_05_vectra_mock_matches_quotas_yaml_to_the_cent() -> None:
    got = contribution(render("staging"), "vectra-mock")
    line = quota_line("vectra-mock")
    for kind in ("requests", "limits"):
        for axis in (0, 1):
            assert abs(got[kind][axis] - line[kind][axis]) <= 0.006, (
                kind,
                axis,
                got[kind][axis],
                line[kind][axis],
            )


def test_quota_a_bigger_request_than_the_line_is_found() -> None:
    docs = edit(render("staging"), dep(set_at([*CONT, "resources", "requests", "memory"], "1Gi")))
    assert contribution(docs, "vectra-app")["requests"][1] > quota_line("vectra-app")["requests"][1]


def test_connections_nfr_u8_14_the_pools_fit_max_connections_of_case_db() -> None:
    """12 replicas como maximo (2 HPA x 6) x `CASE_DB_POOL_MAX` x 1,2 + 2 <= `maxConnections` de `case-db`. La medicion con carga queda diferida (T3)."""
    docs = render("staging")
    replicas = sum(of_kind(docs, "HorizontalPodAutoscaler", n)["spec"]["maxReplicas"] for n in APP)
    assert replicas == 12
    data = yaml.safe_load((ROOT / "platform" / "data" / "chart" / "values.yaml").read_text(encoding="utf-8"))
    max_connections = data["clusters"]["case-db"]["maxConnections"]
    assert replicas * config.CASE_DB_POOL_MAX * 1.2 + 2 <= max_connections, (
        replicas * config.CASE_DB_POOL_MAX * 1.2 + 2,
        max_connections,
    )


def test_flows_inf_u8_05_the_flows_are_already_in_flows_yaml_and_x01_is_forbidden() -> None:
    ids = {f["id"] for f in FLOWS["flows"]}
    assert {"F04", "F07", "F10", "F15", "F16", "F17", "F40", "F44", "F50", "F60", "F104", "F105"} <= ids
    assert flow("F15")["from"] == ["case-worker"] and flow("F40")["from"] == ["case-service", "case-worker"]
    assert flow("F104")["from"] == ["case-worker", "case-service"]
    x01 = {f["from"] for f in FORBIDDEN if f["id"] == "X01" and f["to"] == MOCK}
    assert x01 == {"scoring-service", "explainability-service"}


@pytest.mark.parametrize("env", ENVS)
def test_flows_the_labels_and_service_accounts_of_the_render_are_the_selectors_of_the_flows(env: str) -> None:
    docs = render(env)
    for name in (*APP, *([] if env == "prod" else [MOCK])):
        workload = FLOWS["workloads"][name]
        assert (
            deployment(docs, name)["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/name"]
            == workload["name"]
        )
        assert pod(docs, name)["serviceAccountName"] == workload["sa"]
        assert deployment(docs, name)["metadata"]["namespace"] == workload["ns"]
    migration_workload = FLOWS["workloads"]["migration-case"]
    assert (
        migration(docs)["spec"]["template"]["metadata"]["labels"]["vectra.io/workload"]
        == migration_workload["workload"]
    )
    assert migration(docs)["spec"]["template"]["spec"]["serviceAccountName"] == migration_workload["sa"]


def test_flows_a_changed_label_or_account_is_no_longer_the_selector() -> None:
    docs = edit(render(), dep(set_at([*LABELS, "app.kubernetes.io/name"], "case")))
    assert (
        deployment(docs)["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/name"]
        != FLOWS["workloads"]["case-service"]["name"]
    )
    docs = edit(render(), job(set_at([*POD, "serviceAccountName"], "otra")))
    assert (
        migration(docs)["spec"]["template"]["spec"]["serviceAccountName"]
        != FLOWS["workloads"]["migration-case"]["sa"]
    )


def generated_mock() -> list[Doc]:
    path = NETWORK / "generated" / "kind" / "vectra-mock.yaml"
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def test_catch_all_the_route_name_of_the_alert_is_the_one_u1_generates_without_an_authorization_policy() -> (
    None
):
    catch_all = FLOWS["http_routes"][MOCK]["_catch_all"]
    docs = generated_mock()
    routes = {d["metadata"]["name"]: d for d in docs if d["kind"] == "HTTPRoute"}
    assert catch_all in routes, sorted(routes)
    policies = [d for d in docs if d["kind"] == "AuthorizationPolicy"]
    assert not [p for p in policies if p["spec"]["targetRef"]["name"] == catch_all], (
        "la ruta catch-all no lleva AuthorizationPolicy"
    )
    allowed = [p for p in policies if p["spec"]["targetRef"]["kind"] == "HTTPRoute"]
    assert {p["spec"]["targetRef"]["name"] for p in allowed} == {"core-banking-mock-case-service"}
    auth = next(d for d in docs if d["kind"] == "MeshTLSAuthentication")
    assert auth["spec"]["identities"] == [
        "case-service.vectra-app.serviceaccount.identity.linkerd.cluster.local"
    ]
    get_route = routes["core-banking-mock-case-service"]
    assert get_route["spec"]["rules"][0]["matches"][0]["method"] == "GET"
    rule = rule_of(of_kind(render("kind"), "PrometheusRule", "case-management"))
    assert (
        f'route_name="{catch_all}"' in rule["expr"]
        and f'namespace="{FLOWS["workloads"][MOCK]["ns"]}"' in rule["expr"]
    )


def test_kind_render_the_u1_view_of_kind_is_the_chart_render_of_kind() -> None:
    """P-2 (C-9): `render_env("kind")` de U1 solo pasa `values-kind.yaml`: los Deployment de U8 que ve (nombre, replicas y request de memoria) son los del render del chart."""
    sys.path.insert(0, str(ROOT / "platform" / "tests"))
    import integration  # type: ignore[import-not-found]

    seen = {
        d["metadata"]["name"]: (
            d["spec"]["replicas"],
            d["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"]["memory"],
        )
        for name, group in integration.render_env("kind")
        if name == "case-management"
        for d in group
        if d["kind"] == "Deployment"
    }
    mine = {
        d["metadata"]["name"]: (
            d["spec"]["replicas"],
            d["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"]["memory"],
        )
        for d in render("kind")
        if d["kind"] == "Deployment"
    }
    assert seen == mine and set(seen) == {"case-service", "case-worker", MOCK}
    assert seen["case-service"] == (2, "128Mi") and seen[MOCK] == (2, "64Mi")


# --- Application ------------------------------------------------------------------------------------------------------------------------


def test_the_application_entry_is_wave_5_in_vectra_app_with_env_values_and_kind_values() -> None:
    assert COMPONENT["wave"] == 5 and COMPONENT["namespace"] == "vectra-app"
    assert COMPONENT["path"] == "case-management/chart" and COMPONENT.get("env_values") is True
    assert COMPONENT["kind_values"] == ["case-management/chart/values-kind.yaml"]
    assert not [c for c in COMPONENTS if "core-banking-mock" in c["name"]], "P-3 = (a): una sola Application"
    assert GENERATE.value_files(COMPONENT, "kind") == [
        "case-management/chart/values-kind.yaml",
        "vectra-risk-gitops/values/kind/case-management.yaml",
    ]
    for env in ("staging", "prod"):
        assert GENERATE.value_files(COMPONENT, env) == [
            f"vectra-risk-gitops/values/{env}/case-management.yaml"
        ]
        app = yaml.safe_load((GITOPS / "apps" / env / "case-management.yaml").read_text(encoding="utf-8"))
        assert "automated" not in app["spec"].get("syncPolicy", {})
        assert app["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "5"
    assert not (GITOPS / "apps" / "prod" / "core-banking-mock.yaml").exists()


def test_every_rule_of_the_policies_has_a_case_that_fails_it() -> None:
    declared = set()
    for rego in POLICIES.glob("*.rego"):
        declared |= set(re.findall(r"^# regla: (\S+)", rego.read_text(encoding="utf-8"), flags=re.MULTILINE))
    covered = {c[1] for c in CASES} | {c[2] for c in VALUES_CASES}
    assert declared - covered == set(), f"reglas sin caso: {sorted(declared - covered)}"
    assert covered - declared == set(), f"casos de reglas que no existen: {sorted(covered - declared)}"
