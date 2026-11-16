#!/usr/bin/env python3
"""`require-hpa-bounds` (Kyverno) sobre los `InferenceService` que el chart de U6 rinde en kind con los InferenceService del pico de D2 (U01-T12 CA-2).

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
    return 0 if result.returncode == 0 and "fail: 0, warn: 0, error: 0" in output and "pass: 0," not in output else 1


if __name__ == "__main__":
    sys.exit(main())
