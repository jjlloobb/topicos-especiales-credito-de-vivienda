"""Chart minimo de U3: CronJob `registry-aggregator` y ServiceAccounts (Paso 12 acotado a la demo; BR-U3-17; P-U3-08; NFR-U3-42).

`helm template` + `conftest` con las politicas de `decision-registry/chart/policy/`: limites de tiempo, `Forbid`, anotacion del sidecar
nativo y sin Secret plano. Cada `# regla: x` de las politicas tiene aqui un caso que falla (una mutacion del render, por regla) y
el chart sin tocar pasa. Necesita `platform/install-tools.sh` (helm y conftest en `platform/.tools/bin`).
"""

import copy
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
    assert len(docs) == 6


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
