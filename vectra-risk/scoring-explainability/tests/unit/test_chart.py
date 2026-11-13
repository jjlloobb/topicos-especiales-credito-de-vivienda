"""Chart de U7 (Paso 15 acotado a la demo; INF-U7-01, 03, 04, 05; P-U7-06; NFR-U7-20, 30) y candidata C-2 (hosts de KServe).

`helm template` de los tres entornos, con los values que usa Argo CD (`env_values` y `values/<env>/scoring-explainability.yaml`), y `conftest`
con `scoring-explainability/policies/conftest/` (por documento y con todo el render junto). Cada `# regla: x` de las politicas tiene aqui un
caso que falla (una mutacion del render por regla) y el chart sin tocar pasa. Ademas: las variables y la identidad de los dos servicios contra
el codigo, las rutas de las sondas contra `ops_server` de U0, `flows.yaml` y las plantillas de URL de KServe contra `components.yaml`.
Necesita `platform/install-tools.sh` (helm y conftest en `platform/.tools/bin`): si faltan, las pruebas **fallan**.
"""

import copy
import importlib.util
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import explainability.app as xapp
import explainability.config as xcfg
import pytest
import scoring.app as sapp
import scoring.config as scfg
import yaml
from vectra_common import ops_server

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / "scoring-explainability" / "chart"
POLICIES = ROOT / "scoring-explainability" / "policies" / "conftest"
GITOPS = ROOT / "vectra-risk-gitops"
NETWORK = ROOT / "platform" / "network"
BIN = ROOT / "platform" / ".tools" / "bin"
ENVS = ("kind", "staging", "prod")
SERVICES = ("scoring-service", "explainability-service")
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
COMPONENT = next(c for c in COMPONENTS if c["name"] == "scoring-explainability")


def render(env: str = "kind", *extra: str) -> list[Doc]:
    """Lo que Argo CD renderiza: los values del entorno y los de la unidad, en el orden de `generate.value_files`."""
    files = [GITOPS / "envs" / env / "values.yaml", *(ROOT / f for f in GENERATE.value_files(COMPONENT, env))]
    command = [tool("helm"), "template", "scoring-explainability", str(CHART)]
    for path in files:
        command += ["-f", str(path)]
    out = subprocess.run([*command, *extra], check=True, capture_output=True, text=True).stdout  # noqa: S603
    return [d for d in yaml.safe_load_all(out) if d]


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


def of_kind(docs: list[Doc], kind: str, name: str = "scoring-service") -> Doc:
    return next(d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name)


def deployment(docs: list[Doc], name: str = "scoring-service") -> Doc:
    return of_kind(docs, "Deployment", name)


def pod(docs: list[Doc], name: str = "scoring-service") -> Doc:
    return deployment(docs, name)["spec"]["template"]["spec"]  # type: ignore[no-any-return]


def container(docs: list[Doc], name: str = "scoring-service") -> Doc:
    return pod(docs, name)["containers"][0]  # type: ignore[no-any-return]


def env_map(c: Doc) -> dict[str, str]:
    return {e["name"]: e.get("value", "") for e in c["env"]}


def edit(docs: list[Doc], change: Callable[[list[Doc]], None]) -> list[Doc]:
    copied = copy.deepcopy(docs)
    change(copied)
    return copied


# --- el chart sin tocar -------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
def test_the_chart_as_is_passes_both_conftest_passes_in_every_environment(env: str) -> None:
    docs = render(env)
    assert conftest(docs).returncode == 0, conftest(docs).stdout
    assert conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0
    assert len(docs) == 14


@pytest.mark.parametrize("env", ENVS)
@pytest.mark.parametrize("name", SERVICES)
def test_each_service_follows_inf_u7_01_and_03(env: str, name: str) -> None:
    docs = render(env)
    spec = deployment(docs, name)["spec"]
    assert spec["replicas"] == 2, "test_kind_profile.py cuenta spec.replicas"
    assert spec["strategy"]["rollingUpdate"] == {"maxSurge": 1, "maxUnavailable": 0}
    p = pod(docs, name)
    c = container(docs, name)
    assert p["priorityClassName"] == "vectra-high" and p["terminationGracePeriodSeconds"] == 20
    assert c["lifecycle"]["preStop"]["sleep"]["seconds"] == 5
    assert c["resources"] == {
        "requests": {"cpu": "250m", "memory": "256Mi"},
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
    assert hpa["behavior"]["scaleUp"]["stabilizationWindowSeconds"] == 60
    assert hpa["behavior"]["scaleDown"]["stabilizationWindowSeconds"] == 300
    assert of_kind(docs, "PodDisruptionBudget", name)["spec"]["minAvailable"] == 1
    assert deployment(docs, name)["spec"]["template"]["metadata"]["annotations"] == {
        "config.alpha.linkerd.io/proxy-enable-native-sidecar": "true"
    }


def test_there_is_no_demo_values_file_and_kind_keeps_two_replicas() -> None:
    """T6 / DD-3 b: sin `values-kind-demo.yaml`; los values de kind no bajan las replicas (`require-hpa-bounds`)."""
    assert not list((ROOT / "scoring-explainability").rglob("values-kind-demo.yaml"))
    assert not list((GITOPS / "values").rglob("*kind-demo*"))
    docs = render("kind")
    assert {deployment(docs, n)["spec"]["replicas"] for n in SERVICES} == {2}


def test_without_a_digest_it_does_not_render() -> None:
    for key in ("scoring", "explainability"):
        result = subprocess.run(  # noqa: S603
            [tool("helm"), "template", "x", str(CHART), "--set", f"images.{key}.digest="],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0 and f"images.{key}.digest es obligatorio" in result.stderr


def test_without_the_kserve_url_templates_it_does_not_render() -> None:
    """C-2: sin plantillas (vacias) no hay render, y las plantillas no estan escritas en las plantillas del chart (salen de los values)."""
    for key, message in (
        ("predictorUrlTemplate", "kserve.predictorUrlTemplate"),
        ("explainerUrlTemplate", "kserve.explainerUrlTemplate"),
    ):
        result = subprocess.run(  # noqa: S603
            [tool("helm"), "template", "x", str(CHART), "--set", f"kserve.{key}="],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0 and f"{message} es obligatorio" in result.stderr
    assert not re.search(
        r"svc\.cluster\.local.*(predictor|explainer)|(predictor|explainer).*svc\.cluster\.local",
        _templates_text(),
    )


def _templates_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (CHART / "templates").glob("*") if p.is_file())


# --- una mutacion del render por regla ----------------------------------------------------------------------------------------------------


def _doc(
    kind: str, name: str = "scoring-service"
) -> Callable[[Callable[[Doc], None]], Callable[[list[Doc]], None]]:
    def wrap(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
        return lambda docs: change(of_kind(docs, kind, name))

    return wrap


def dep(change: Callable[[Doc], None], name: str = "scoring-service") -> Callable[[list[Doc]], None]:
    return _doc("Deployment", name)(change)


POD = ["spec", "template", "spec"]
CONT = [*POD, "containers", 0]


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
        c = at(doc, CONT)
        c["env"] = [e for e in c["env"] if e["name"] != name]

    return change


def add_env(name: str, value: str = "1") -> Callable[[Doc], None]:
    return lambda doc: at(doc, CONT)["env"].append({"name": name, "value": value})


def append_doc(doc: Doc) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.append(doc)


def drop_doc(kind: str, name: str) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.remove(of_kind(docs, kind, name))


EXPL = "explainability-service"
Case = tuple[str, str, Callable[[list[Doc]], None]]
CASES: list[Case] = [
    # hpa-doc
    ("HPA con minReplicas 1", "hpa-doc", _doc("HorizontalPodAutoscaler")(set_at(["spec", "minReplicas"], 1))),
    (
        "HPA con maxReplicas 7",
        "hpa-doc",
        _doc("HorizontalPodAutoscaler", EXPL)(set_at(["spec", "maxReplicas"], 7)),
    ),
    (
        "HPA al 80 % de CPU",
        "hpa-doc",
        _doc("HorizontalPodAutoscaler")(
            set_at(["spec", "metrics", 0, "resource", "target", "averageUtilization"], 80)
        ),
    ),
    (
        "HPA sin 60 s hacia arriba",
        "hpa-doc",
        _doc("HorizontalPodAutoscaler")(
            set_at(["spec", "behavior", "scaleUp", "stabilizationWindowSeconds"], 0)
        ),
    ),
    (
        "HPA sin 300 s hacia abajo",
        "hpa-doc",
        _doc("HorizontalPodAutoscaler", EXPL)(
            set_at(["spec", "behavior", "scaleDown", "stabilizationWindowSeconds"], 30)
        ),
    ),
    (
        "HPA de otro Deployment",
        "hpa-doc",
        _doc("HorizontalPodAutoscaler")(set_at(["spec", "scaleTargetRef", "name"], "otro")),
    ),
    # pdb-doc y service-pdb
    ("sin PDB en explainability", "service-pdb", drop_doc("PodDisruptionBudget", EXPL)),
    ("sin HPA en scoring", "service-pdb", drop_doc("HorizontalPodAutoscaler", "scoring-service")),
    ("PDB con minAvailable 0", "pdb-doc", _doc("PodDisruptionBudget")(set_at(["spec", "minAvailable"], 0))),
    (
        "PDB que no selecciona el servicio",
        "pdb-doc",
        _doc("PodDisruptionBudget")(
            set_at(["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro")
        ),
    ),
    # service-priority, spread, resources, replicas
    (
        "vectra-normal en scoring",
        "service-priority",
        dep(set_at([*POD, "priorityClassName"], "vectra-normal")),
    ),
    ("sin spread por zona", "service-spread", dep(set_at([*POD, "topologySpreadConstraints"], []), EXPL)),
    ("requests de 100m", "service-resources", dep(set_at([*CONT, "resources", "requests", "cpu"], "100m"))),
    (
        "limits de 1Gi",
        "service-resources",
        dep(set_at([*CONT, "resources", "limits", "memory"], "1Gi"), EXPL),
    ),
    ("1 replica", "service-shape", dep(set_at(["spec", "replicas"], 1))),
    ("sin replicas declaradas y 1 por defecto", "service-shape", dep(drop_at(["spec", "replicas"]), EXPL)),
    (
        "dos contenedores",
        "service-shape",
        dep(lambda d: at(d, [*POD, "containers"]).append(copy.deepcopy(at(d, CONT)))),
    ),
    ("otra cuenta de servicio", "service-shape", dep(set_at([*POD, "serviceAccountName"], "otra"))),
    ("criticidad baja", "service-shape", dep(set_at(["metadata", "labels", "vectra.io/criticality"], "low"))),
    (
        "rollout con maxUnavailable 1",
        "service-rollout",
        dep(set_at(["spec", "strategy", "rollingUpdate", "maxUnavailable"], 1)),
    ),
    # preStop y gracia (INF-U7-03)
    ("sin preStop.sleep", "service-prestop", dep(drop_at([*CONT, "lifecycle"]))),
    (
        "preStop.sleep de 1 s",
        "service-prestop",
        dep(set_at([*CONT, "lifecycle", "preStop", "sleep", "seconds"], 1), EXPL),
    ),
    (
        "terminationGracePeriodSeconds 10",
        "service-grace",
        dep(set_at([*POD, "terminationGracePeriodSeconds"], 10)),
    ),
    (
        "sin terminationGracePeriodSeconds",
        "service-grace",
        dep(drop_at([*POD, "terminationGracePeriodSeconds"]), EXPL),
    ),
    # probes
    (
        "liveness en /livez",
        "service-probes",
        dep(set_at([*CONT, "livenessProbe", "httpGet", "path"], "/livez")),
    ),
    (
        "readiness en /healthz",
        "service-probes",
        dep(set_at([*CONT, "readinessProbe", "httpGet", "path"], "/healthz")),
    ),
    (
        "readiness en 8080",
        "service-probes",
        dep(set_at([*CONT, "readinessProbe", "httpGet", "port"], "http"), EXPL),
    ),
    ("readiness cada 10 s", "service-probes", dep(set_at([*CONT, "readinessProbe", "periodSeconds"], 10))),
    ("liveness cada 5 s", "service-probes", dep(set_at([*CONT, "livenessProbe", "periodSeconds"], 5))),
    (
        "con startupProbe",
        "service-probes",
        dep(
            set_at(
                [*CONT, "startupProbe"],
                {"httpGet": {"path": "/healthz", "port": "metrics"}, "periodSeconds": 2},
            )
        ),
    ),
    ("puertos distintos", "service-ports", dep(set_at([*CONT, "ports", 1, "containerPort"], 9090))),
    (
        "sin sidecar nativo de Linkerd",
        "service-sidecar",
        dep(set_at(["spec", "template", "metadata", "annotations"], {})),
    ),
    # variables de entorno (INF-U7-04)
    ("variable PRE_REGISTRY_BUDGET", "budget-env", dep(add_env("PRE_REGISTRY_BUDGET", "700"))),
    (
        "variable APPEND_TIMEOUT_MS en explainability",
        "budget-env",
        dep(add_env("APPEND_TIMEOUT_MS", "2500"), EXPL),
    ),
    ("variable ajena al servicio", "service-env", dep(add_env("SCORING_DEBUG"))),
    ("falta SCORING_GOVERNANCE_URL", "service-env", dep(drop_env("SCORING_GOVERNANCE_URL"))),
    (
        "falta la plantilla del explicador",
        "service-env",
        dep(drop_env("EXPLAINABILITY_EXPLAINER_URL_TEMPLATE"), EXPL),
    ),
    ("VECTRA_CLIENT_ID de otro cliente", "service-identity", dep(set_env("VECTRA_CLIENT_ID", EXPL))),
    # secretos
    (
        "un Secret en el render",
        "no-plain-secret",
        append_doc(
            {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "s", "namespace": "vectra-app"}}
        ),
    ),
    (
        "credenciales en una URL",
        "no-plain-secret",
        dep(set_env("SCORING_REGISTRY_URL", "http://u:p@registro:8080")),
    ),
    (
        "variable desde un Secret",
        "no-plain-secret",
        dep(
            lambda d: at(d, CONT)["env"].append(
                {"name": "X", "valueFrom": {"secretKeyRef": {"name": "s", "key": "k"}}}
            )
        ),
    ),
    # imagen y endurecimiento
    (
        "imagen por etiqueta",
        "workload-image",
        dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/scoring-service:dev")),
    ),
    (
        "repositorio de otro servicio",
        "workload-image",
        dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/otra@sha256:" + "0" * 64)),
    ),
    (
        "digest corto",
        "workload-image",
        dep(set_at([*CONT, "image"], "kind-registry:5000/vectra/scoring-service@sha256:abc"), EXPL),
    ),
    ("sin runAsNonRoot", "hardening", dep(set_at([*POD, "securityContext", "runAsNonRoot"], False))),
    ("runAsUser 0", "hardening", dep(set_at([*POD, "securityContext", "runAsUser"], 0))),
    ("runAsGroup 0", "hardening", dep(set_at([*POD, "securityContext", "runAsGroup"], 0))),
    ("sin seccomp", "hardening", dep(drop_at([*POD, "securityContext", "seccompProfile"]))),
    (
        "sistema de archivos escribible",
        "hardening",
        dep(set_at([*CONT, "securityContext", "readOnlyRootFilesystem"], False)),
    ),
    (
        "privilegios escalables",
        "hardening",
        dep(set_at([*CONT, "securityContext", "allowPrivilegeEscalation"], True), EXPL),
    ),
    (
        "un hostPath",
        "hardening",
        dep(lambda d: at(d, [*POD, "volumes"]).append({"name": "h", "hostPath": {"path": "/"}})),
    ),
    ("montaje de escritura", "read-only-mounts", dep(set_at([*CONT, "volumeMounts", 1, "readOnly"], False))),
    # documentos de apoyo
    ("namespace distinto", "namespace", _doc("Service")(set_at(["metadata", "namespace"], "default"))),
    ("Service con otros puertos", "service-doc", _doc("Service")(set_at(["spec", "ports", 0, "port"], 9090))),
    ("Service ajeno", "service-doc", _doc("Service", EXPL)(set_at(["metadata", "name"], "otro"))),
    (
        "cuenta de servicio con Secret",
        "service-account-doc",
        _doc("ServiceAccount")(set_at(["secrets"], [{"name": "x"}])),
    ),
    (
        "cuenta sin automount",
        "service-account-doc",
        _doc("ServiceAccount", EXPL)(set_at(["automountServiceAccountToken"], False)),
    ),
    (
        "ServiceMonitor sin honorLabels",
        "servicemonitor-doc",
        _doc("ServiceMonitor")(set_at(["spec", "endpoints", 0, "honorLabels"], False)),
    ),
    (
        "ServiceMonitor de otro Service",
        "servicemonitor-doc",
        _doc("ServiceMonitor")(set_at(["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otro")),
    ),
    (
        "ServiceMonitor con dos endpoints",
        "servicemonitor-doc",
        _doc("ServiceMonitor", EXPL)(lambda d: at(d, ["spec", "endpoints"]).append({"port": "http"})),
    ),
    (
        "ServiceMonitor al 8080",
        "servicemonitor-port",
        _doc("ServiceMonitor")(set_at(["spec", "endpoints", 0, "port"], "http")),
    ),
    (
        "targetPort inexistente",
        "service-port-names",
        _doc("Service")(set_at(["spec", "ports", 1, "targetPort"], "nada")),
    ),
    # el render completo y la identidad
    (
        "una PrometheusRule (Paso 16, T2)",
        "documents-exact",
        append_doc(
            {
                "apiVersion": "monitoring.coreos.com/v1",
                "kind": "PrometheusRule",
                "metadata": {"name": "r", "namespace": "vectra-app"},
            }
        ),
    ),
    (
        "sin el ExternalSecret de scoring",
        "documents-exact",
        drop_doc("ExternalSecret", "scoring-service-client"),
    ),
    (
        "etiqueta del pod distinta de la de flows.yaml",
        "service-labels",
        dep(set_at(["spec", "template", "metadata", "labels", "app.kubernetes.io/name"], "scoring")),
    ),
    (
        "cuenta de servicio fuera del render",
        "service-account-exists",
        drop_doc("ServiceAccount", EXPL),
    ),
    ("llave fuera del volumen", "identity", dep(set_env("VECTRA_CLIENT_KEY_PATH", "/tmp/private-key"))),
    (
        "ExternalSecret con otra llave de la boveda",
        "identity",
        _doc("ExternalSecret", "scoring-service-client")(
            set_at(["spec", "data", 0, "remoteRef", "key"], "identity/clients/otro")
        ),
    ),
    (
        "ExternalSecret que crea otro Secret",
        "identity",
        _doc("ExternalSecret", EXPL + "-client")(set_at(["spec", "target", "name"], "otro")),
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
    for rego in POLICIES.glob("*.rego"):
        declared |= set(re.findall(r"^# regla: (\S+)", rego.read_text(encoding="utf-8"), flags=re.MULTILINE))
    covered = {c[1] for c in CASES}
    assert declared - covered == set(), f"reglas sin caso: {sorted(declared - covered)}"
    assert covered - declared == set(), f"casos de reglas que no existen: {sorted(covered - declared)}"


# --- variables, identidad y sondas contra el codigo ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
def test_env_each_service_has_what_its_code_requires_and_no_constant(env: str) -> None:
    docs = render(env)
    scoring, explainability = env_map(container(docs)), env_map(container(docs, EXPL))
    assert set(sapp.REQUIRED_ENV) <= set(scoring) and set(xapp.REQUIRED_ENV) <= set(explainability)
    assert {"VECTRA_CLIENT_ID", "VECTRA_TOKEN_URL", "VECTRA_ASSERTION_AUDIENCE", "VECTRA_CLIENT_KEY_PATH"} <= set(scoring) & set(
        explainability
    )
    constants = {n for mod in (scfg, xcfg) for n in dir(mod) if n.isupper() and not n.startswith("_")}
    assert constants and not constants & (set(scoring) | set(explainability)), (
        "INF-U7-04: un presupuesto es variable de entorno"
    )
    assert scoring["VECTRA_CLIENT_ID"] == "scoring-service" and explainability["VECTRA_CLIENT_ID"] == EXPL


def test_env_a_required_variable_missing_from_the_deployment_is_found_by_the_code_check() -> None:
    docs = edit(render(), dep(drop_env("SCORING_REGISTRY_URL")))
    assert not set(sapp.REQUIRED_ENV) <= set(env_map(container(docs)))


@pytest.mark.parametrize("env", ENVS)
def test_the_services_start_with_exactly_the_variables_the_chart_injects(env: str) -> None:
    """`settings_from_env` de cada servicio acepta el entorno que pone el chart (las plantillas de URL llevan `{inference_service}`)."""
    docs = render(env)
    assert sapp.settings_from_env(env_map(container(docs))).governance_url.startswith(
        "http://governance-service.vectra-app"
    )
    assert xapp.settings_from_env(env_map(container(docs, EXPL))).registry_url.startswith(
        "http://decision-registry-service.vectra-app"
    )


def test_probes_the_paths_are_routes_that_ops_server_serves() -> None:
    """INF-U7-01 dice `/livez`, pero `ops_server` (U0) sirve `/healthz`: una sonda a una ruta inexistente reiniciaria los pods."""
    routes = {r.path for r in ops_server.create_ops_app(init_process=False).routes}  # type: ignore[attr-defined]
    assert {"/healthz", "/readyz"} <= routes and "/livez" not in routes
    docs = render()
    for name in SERVICES:
        for probe in ("readinessProbe", "livenessProbe"):
            assert container(docs, name)[probe]["httpGet"]["path"] in routes


@pytest.mark.parametrize("env", ENVS)
def test_identity_each_service_has_its_own_key_client_and_service_account(env: str) -> None:
    docs = render(env)
    for name in SERVICES:
        secret = f"{name}-client"
        es = of_kind(docs, "ExternalSecret", secret)
        assert es["spec"]["data"] == [
            {
                "secretKey": "private-key",
                "remoteRef": {"key": f"identity/clients/{name}", "property": "private-key"},
            }
        ]
        volume = next(
            v for v in pod(docs, name)["volumes"] if v.get("secret", {}).get("secretName") == secret
        )
        mount = next(m for m in container(docs, name)["volumeMounts"] if m["name"] == volume["name"])
        assert mount["readOnly"] is True
        assert env_map(container(docs, name))["VECTRA_CLIENT_KEY_PATH"] == f"{mount['mountPath']}/private-key"
        assert pod(docs, name)["serviceAccountName"] == name


# --- C-2: los hosts de KServe -------------------------------------------------------------------------------------------------------------

SERVING_NAMESPACE = next(c for c in COMPONENTS if c["name"] == "model-serving")["namespace"]


def kserve_problems(docs: list[Doc]) -> list[str]:
    """Las dos plantillas: `{inference_service}`, el sufijo del Service de KServe y el namespace de la Application `model-serving`."""
    found = {
        "predictor": env_map(container(docs))["SCORING_PREDICTOR_URL_TEMPLATE"],
        "explainer": env_map(container(docs, EXPL))["EXPLAINABILITY_EXPLAINER_URL_TEMPLATE"],
    }
    problems = []
    for role, template in found.items():
        host = template.partition("://")[2]
        if "{inference_service}" not in template:
            problems.append(f"{role}: sin {{inference_service}}")
        if not host.startswith(f"{{inference_service}}-{role}."):
            problems.append(f"{role}: el Service de KServe es <isvc>-{role}, no {host}")
        if host.split("/")[0].split(".")[1:3] != [SERVING_NAMESPACE, "svc"]:
            problems.append(f"{role}: el namespace es el de model-serving ({SERVING_NAMESPACE}), no {host}")
    return problems


@pytest.mark.parametrize("env", ENVS)
def test_kserve_the_url_templates_point_at_the_services_in_the_model_serving_namespace(env: str) -> None:
    docs = render(env)
    assert kserve_problems(docs) == []
    assert env_map(container(docs))["SCORING_PREDICTOR_URL_TEMPLATE"] == (
        f"http://{{inference_service}}-predictor.{SERVING_NAMESPACE}.svc.cluster.local"
    )


def test_kserve_a_wrong_suffix_or_namespace_or_missing_placeholder_is_found() -> None:
    base = render()
    wrong_suffix = edit(
        base,
        dep(
            set_env(
                "SCORING_PREDICTOR_URL_TEMPLATE",
                f"http://{{inference_service}}.{SERVING_NAMESPACE}.svc.cluster.local",
            )
        ),
    )
    assert any("predictor" in p for p in kserve_problems(wrong_suffix))
    wrong_ns = edit(
        base,
        dep(
            set_env(
                "EXPLAINABILITY_EXPLAINER_URL_TEMPLATE",
                "http://{inference_service}-explainer.vectra-app.svc.cluster.local",
            ),
            EXPL,
        ),
    )
    assert any("namespace" in p for p in kserve_problems(wrong_ns))
    no_holder = edit(
        base,
        dep(
            set_env(
                "SCORING_PREDICTOR_URL_TEMPLATE",
                f"http://modelo-predictor.{SERVING_NAMESPACE}.svc.cluster.local",
            )
        ),
    )
    assert any("{inference_service}" in p for p in kserve_problems(no_holder))


def test_kserve_the_namespace_is_read_from_components_and_the_port_is_the_default_80() -> None:
    """El Service de KServe expone el puerto 80 (`CommonDefaultHttpPort`, v0.21.0) con `targetPort` 8080, como F19 y F22 de flows.yaml."""
    assert SERVING_NAMESPACE == "vectra-serving"
    flows = yaml.safe_load((NETWORK / "flows.yaml").read_text(encoding="utf-8"))["flows"]
    by_id = {f["id"]: f for f in flows}
    assert (by_id["F19"]["port"], by_id["F19"]["target_port"]) == (80, 8080)
    assert (by_id["F22"]["port"], by_id["F22"]["target_port"]) == (80, 8080)
    for env in ENVS:
        for template in (
            env_map(container(render(env)))["SCORING_PREDICTOR_URL_TEMPLATE"],
            env_map(container(render(env), EXPL))["EXPLAINABILITY_EXPLAINER_URL_TEMPLATE"],
        ):
            assert not re.search(r":\d+(/|$)", template.partition("://")[2]), (
                "el puerto es el 80 por omision del esquema"
            )


# --- INF-U7-05: flows.yaml ----------------------------------------------------------------------------------------------------------------

FLOWS: dict[str, Any] = yaml.safe_load((NETWORK / "flows.yaml").read_text(encoding="utf-8"))
FORBIDDEN: list[dict[str, Any]] = yaml.safe_load((NETWORK / "forbidden.yaml").read_text(encoding="utf-8"))[
    "forbidden"
]
NETWORK_MODULE = _load(NETWORK / "generate.py", "network_generate")


def selector(endpoint: str) -> dict[str, str]:
    """El selector de pods que `generate.py` usa para el extremo (la misma funcion, no una copia)."""
    return NETWORK_MODULE.labels_of(FLOWS["workloads"][endpoint])  # type: ignore[no-any-return]


def matches(endpoint: str, docs: list[Doc]) -> bool:
    workload = FLOWS["workloads"][endpoint]
    want = selector(endpoint)
    d = deployment(docs, endpoint)
    return bool(
        d["spec"]["template"]["spec"]["serviceAccountName"] == workload["sa"]
        and d["metadata"]["namespace"] == workload["ns"]
        and all(d["spec"]["template"]["metadata"]["labels"].get(k) == v for k, v in want.items())
    )


@pytest.mark.parametrize("env", ENVS)
def test_flows_the_labels_and_service_accounts_of_the_render_are_the_selectors_of_the_flows(env: str) -> None:
    docs = render(env)
    for endpoint in SERVICES:
        assert matches(endpoint, docs), f"el render no es {endpoint} para flows.yaml"


def test_flows_a_changed_label_or_account_is_no_longer_the_selector() -> None:
    docs = edit(
        render(), dep(set_at(["spec", "template", "metadata", "labels", "app.kubernetes.io/name"], "scoring"))
    )
    assert not matches("scoring-service", docs)
    docs = edit(render(), dep(set_at([*POD, "serviceAccountName"], "otra"), EXPL))
    assert not matches(EXPL, docs)


def test_flows_inf_u7_05_the_flows_are_already_in_flows_yaml_and_x01_x02_are_forbidden() -> None:
    ids = {f["id"] for f in FLOWS["flows"]}
    assert {"F12", "F15", "F18", "F19", "F20", "F21", "F22", "F23", "F103"} <= ids
    forbidden = {(f["id"], f["from"]) for f in FORBIDDEN if f["id"] in {"X01", "X02"}}
    for service in ("scoring-service", EXPL):
        assert {("X01", service), ("X02", service)} <= forbidden
    mentioning = {f["id"] for f in FLOWS["flows"] if set(SERVICES) & (set(f["from"]) | set(f["to"]))}
    assert {"F12", "F15", "F18", "F19", "F20", "F21", "F22", "F23", "F103"} <= mentioning


# --- Application (Paso 17) ----------------------------------------------------------------------------------------------------------------


def test_the_application_entry_is_wave_5_in_vectra_app_with_env_values() -> None:
    assert COMPONENT["wave"] == 5 and COMPONENT["namespace"] == "vectra-app"
    assert COMPONENT["path"] == "scoring-explainability/chart" and COMPONENT.get("env_values") is True
    for env in ENVS:
        assert GENERATE.value_files(COMPONENT, env) == [
            f"vectra-risk-gitops/values/{env}/scoring-explainability.yaml"
        ]
        app = yaml.safe_load(
            (GITOPS / "apps" / env / "scoring-explainability.yaml").read_text(encoding="utf-8")
        )
        assert "automated" not in app["spec"].get("syncPolicy", {})
        assert app["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "5"
