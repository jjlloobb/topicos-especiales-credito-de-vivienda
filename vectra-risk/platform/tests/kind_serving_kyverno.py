#!/usr/bin/env python3
"""Kyverno sobre lo que el chart de U6 rinde en kind con los InferenceService del pico de D2 (U01-T12 CA-2) y sobre lo que KServe genera a partir de ello (U01-T15).

1. `require-hpa-bounds` sobre los `InferenceService`. 2. El barrido de la clase: todas las politicas contra los Deployment y Pod que KServe crea en `vectra-serving` y
`vectra-staging` para `prod`, `staging` e `inactive`, con el `storage-initializer` que su webhook inyecta. 3. El minimo de 2 del modelo activo sigue vigilado sin `require-min-replicas`.

Necesita el binario `kyverno` de `platform/.tools/bin`, que el job `tests` de la CI no instala: por eso no es una prueba de pytest sino un paso de `make check-tools`
(como `rego_fixtures.py`), que la CI corre con las herramientas. Falla (rc 1) si Kyverno falla, no existe o no evalua nada: no se salta en silencio.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_kind_profile as kind  # noqa: E402

KYVERNO = kind.PLATFORM / ".tools/bin/kyverno"
POLICY = kind.PLATFORM / "policies/kyverno/require-hpa-bounds.yaml"


#: Campos del componente (`predictor`, `explainer`) que son del `InferenceService` y no del PodSpec que KServe copia a la plantilla del Deployment.
COMPONENT_EXTENSION = {"minReplicas", "maxReplicas", "scaleTarget", "scaleMetric", "autoScaling", "labels", "annotations", "batcher", "logger", "deploymentStrategy"}
#: Lo que KServe v0.21.0 inyecta en el Pod al admitirlo (`storage_initializer_injector.go`, `CreateInitContainerWithConfig` de `pkg/utils/storage.go`) con la imagen y los
#: recursos de `inferenceservice-config` (chart `kserve-resources` v0.21.0: `kserve/storage-initializer:<version>`, 100m/100Mi a 1/1Gi). No lleva `securityContext` propio.
STORAGE_INITIALIZER = {
    "name": "storage-initializer",
    "image": "kserve/storage-initializer:v0.21.0",
    "args": ["s3://model-store/<model_version_id>/", "/mnt/models"],
    "resources": {"requests": {"cpu": "100m", "memory": "100Mi"}, "limits": {"cpu": "1", "memory": "1Gi"}},
    "terminationMessagePolicy": "FallbackToLogsOnError",
}


def kserve_deployment(isvc: dict, component: str) -> dict:
    """El Deployment que `deployment_reconciler.go` (KServe v0.21.0, `createRawDefaultDeployment`) crea para un componente del `InferenceService`.

    Etiquetas: las del `InferenceService`, las del componente, `serving.kserve.io/inferenceservice` y `component` (`predictor.go`, `buildObjectMeta`); anotaciones: las del
    `InferenceService` y las del componente. `spec.replicas` solo se fija con `serving.kserve.io/autoscalerClass: none` (linea 173); con HPA queda sin fijar.
    """
    meta, extension = isvc["metadata"], isvc["spec"][component]
    labels = {**meta.get("labels", {}), **extension.get("labels", {}), "serving.kserve.io/inferenceservice": meta["name"], "component": component}
    annotations = {**meta.get("annotations", {}), **extension.get("annotations", {})}
    name = f"{meta['name']}-{component}"
    pod_spec = {key: value for key, value in extension.items() if key not in COMPONENT_EXTENSION}
    deployment: dict = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": meta["namespace"], "labels": labels, "annotations": annotations},
        "spec": {
            "selector": {"matchLabels": {"app": f"isvc.{name}"}},
            "template": {"metadata": {"labels": {**labels, "app": f"isvc.{name}"}, "annotations": dict(annotations)}, "spec": pod_spec},
        },
    }
    if annotations.get("serving.kserve.io/autoscalerClass") == "none":
        deployment["spec"]["replicas"] = extension["minReplicas"]
    return deployment


def kserve_pod(deployment: dict) -> dict:
    """El Pod que sale de esa plantilla, ya con el init container que inyecta el webhook de KServe (`storage-initializer`, antes de la admision de Kyverno)."""
    template = deployment["spec"]["template"]
    spec = {**template["spec"], "initContainers": [dict(STORAGE_INITIALIZER)]}
    meta = deployment["metadata"]
    return {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": f"{meta['name']}-0", "namespace": meta["namespace"], **template["metadata"]}, "spec": spec}


KYVERNO_POLICIES = kind.PLATFORM / "policies/kyverno"
#: Un modelo inactivo mas, ademas del pico de D2: el rollback de D2 lo pasa a `prod`.
SWEEP_INFERENCE_SERVICES = [*kind.PEAK_INFERENCE_SERVICES, {"modelVersionId": "mv-2025-12-01-0badc0de", "storageUri": "s3://model-store/mv-2025-12-01-0badc0de/", "profile": "inactive"}]
#: `verify-images` no se instala en kind (solo staging y prod, firmas reales de INF-U1-09) y Kyverno la evaluaria contra el registro.
NOT_INSTALLED_IN_KIND = {"verify-images", "kyverno-test"}


def _apply(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(KYVERNO), "apply", *args, "--table", "--remove-color"], capture_output=True, text=True, check=False)  # noqa: S603


def table(output: str) -> list[tuple[str, str, str, str]]:
    """Las filas (politica, regla, recurso, resultado) de la tabla de `kyverno apply --table`."""
    rows = []
    for line in output.splitlines():
        cells = [cell.strip() for cell in line.split("│")[1:-1]]
        if len(cells) == 6 and cells[0].isdigit():
            rows.append((cells[1], cells[2], cells[3], cells[4]))
    return rows


def sweep_policies(folder: Path) -> list[str]:
    """Todas las politicas de `platform/policies/kyverno`, con el `apiCall` de `require-pdb` y `deployment-needs-hpa-or-exemption` cambiado por un valor fijo.

    `kyverno apply` no resuelve `apiCall` sin clúster (`panic`), y `kyverno test` lo resuelve con los `values` de `fixtures/values.yaml`. Aqui el valor es 1 (hay PDB y HPA), y
    `main` comprueba que el chart renderiza ese PDB para cada Deployment `prod`: el HPA lo crea KServe despues y su regla es de auditoria.
    """
    paths = []
    for source in sorted(KYVERNO_POLICIES.glob("*.yaml")):
        policy = yaml.safe_load(source.read_text(encoding="utf-8"))
        if policy["kind"] != "ClusterPolicy" or policy["metadata"]["name"] in NOT_INSTALLED_IN_KIND:
            continue
        for rule in policy["spec"]["rules"]:
            for context in rule.get("context", []):
                if "apiCall" in context:
                    context.pop("apiCall")
                    context["variable"] = {"value": 1}
        target = folder / source.name
        target.write_text(yaml.safe_dump(policy), encoding="utf-8")
        paths.append(str(target))
    return paths


def pdb_selectors(documents: list[dict]) -> set[tuple[str, str]]:
    return {(d["metadata"]["namespace"], d["spec"]["selector"]["matchLabels"]["app.kubernetes.io/name"]) for d in documents if d["kind"] == "PodDisruptionBudget"}


def fixtures_drift(documents: list[dict]) -> list[str]:
    """Los Deployment de `fixtures/resources.yaml` de U01-T15 salen del render: si el chart de U6 cambia, hay que regenerarlos (`kserve_deployment` sobre el primer `prod`)."""
    expected = kserve_deployment(documents[0], "predictor")
    fixtures = {d["metadata"]["name"]: d for d in yaml.safe_load_all((KYVERNO_POLICIES / "fixtures/resources.yaml").read_text(encoding="utf-8")) if d}
    problems = []
    for name, replicas in (("kserve-prod-no-replicas", None), ("kserve-prod-one-replica", 1)):
        wanted = yaml.safe_load(yaml.safe_dump(expected))
        wanted["metadata"]["name"] = name
        if replicas is not None:
            wanted["spec"]["replicas"] = replicas
        if fixtures.get(name) != wanted:
            problems.append(f"fixtures/resources.yaml: {name} ya no coincide con el Deployment que KServe crea para el render del chart de U6")
    return problems


def sweep() -> int:
    """Barrido de la clase (U01-T15): todas las politicas de Kyverno contra los Deployment y Pod que KServe genera en `vectra-serving` y `vectra-staging` para los tres perfiles."""
    rendered = rendered_serving()
    documents = [d for d in rendered if d["kind"] == "InferenceService"]
    deployments = [kserve_deployment(d, c) for d in documents for c in ("predictor", "explainer") if c in d["spec"]]
    pods = [kserve_pod(d) for d in deployments]
    with tempfile.TemporaryDirectory() as folder:
        resources = Path(folder) / "generated.yaml"
        resources.write_text(yaml.safe_dump_all([*deployments, *pods]), encoding="utf-8")
        result = _apply([*sweep_policies(Path(folder)), "--resource", str(resources)])
    output = result.stdout + result.stderr
    rows = table(output)
    print("\n".join(f"{policy:28} {rule:42} {resource:62} {outcome}" for policy, rule, resource, outcome in rows) + "\n")
    problems = [f"{policy}/{rule} {outcome} sobre {resource}" for policy, rule, resource, outcome in rows if outcome in {"Fail", "Error"}]
    if result.returncode != 0 or "panic" in output:
        problems.append(f"kyverno apply rc {result.returncode}")
    if not any(outcome == "Pass" for *_, outcome in rows):
        problems.append("el barrido no evaluo nada")
    # Sin la exencion de KServe, `require-min-replicas` rechazaria el Deployment `prod` (sin `replicas`) y saldria como `Fail`; `kyverno apply` no lista las reglas excluidas.
    if not any(rule == "require-zone-spread" for _, rule, _, _ in rows):
        problems.append("el barrido no evaluo `require-spread-and-pdb` sobre los Deployment de vectra-serving")
    rendered_pdbs = pdb_selectors(rendered)
    for deployment in deployments:
        meta = deployment["metadata"]
        if meta["annotations"]["vectra.io/profile"] == "prod" and (meta["namespace"], meta["labels"]["app.kubernetes.io/name"]) not in rendered_pdbs:
            problems.append(f"el chart no renderiza el PodDisruptionBudget de {meta['name']}")
    problems += fixtures_drift(documents)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


def rendered_serving() -> list[dict]:
    with tempfile.TemporaryDirectory() as folder:
        overlay = Path(folder) / "inference-services.yaml"
        overlay.write_text(yaml.safe_dump({"inferenceServices": SWEEP_INFERENCE_SERVICES}), encoding="utf-8")
        return kind.integration.helm("model-serving", kind.SERVING_CHART, "vectra-serving", [kind.GITOPS / "envs/kind/values.yaml", kind.KIND_SERVING_VALUES, overlay])


def minimum_of_two_is_still_watched() -> int:
    """Sin `require-min-replicas` sobre el Deployment, el minimo de 2 lo vigila `active-inference-service-needs-two-replicas`: un `prod` con `minReplicas: 1` se rechaza."""
    prod = [d for d in kind.inference_services(kind.PEAK_INFERENCE_SERVICES) if d["metadata"]["annotations"]["vectra.io/profile"] == "prod"][0]
    prod["spec"]["predictor"]["minReplicas"] = 1
    with tempfile.TemporaryDirectory() as folder:
        resource = Path(folder) / "prod-min-one.yaml"
        resource.write_text(yaml.safe_dump(prod), encoding="utf-8")
        result = _apply([str(POLICY), "--resource", str(resource)])
    rows = table(result.stdout + result.stderr)
    print("\n".join(f"{policy:28} {rule:46} {outcome}" for policy, rule, _, outcome in rows))
    if ("require-hpa-bounds", "active-inference-service-needs-two-replicas", f"vectra-serving/InferenceService/{prod['metadata']['name']}", "Fail") in rows:
        return 0
    print("un InferenceService prod con minReplicas 1 ya no se rechaza", file=sys.stderr)
    return 1


def main() -> int:
    if not KYVERNO.is_file():
        print(f"falta {KYVERNO}: corre platform/install-tools.sh", file=sys.stderr)
        return 1
    documents = kind.inference_services(kind.PEAK_INFERENCE_SERVICES)
    if not documents:
        print("el chart de U6 no rindio ningun InferenceService en kind", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as folder:
        resource = Path(folder) / "inference-services.yaml"
        resource.write_text(yaml.safe_dump_all(documents), encoding="utf-8")
        result = subprocess.run([str(KYVERNO), "apply", str(POLICY), "--resource", str(resource)], capture_output=True, text=True, check=False)  # noqa: S603
    output = result.stdout + result.stderr
    print(output)
    bounds = 0 if result.returncode == 0 and "fail: 0, warn: 0, error: 0" in output and "pass: 0," not in output else 1
    return max(bounds, sweep(), minimum_of_two_is_still_watched())


if __name__ == "__main__":
    sys.exit(main())
