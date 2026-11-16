#!/usr/bin/env python3
"""Escribe el `Job` que arma `job_manifest` (el real) y el `Pod` de su plantilla, para pasarlos a `kyverno apply` (U04-T11).

`governance-service` crea el Job por la API de Kubernetes en tiempo de ejecucion: ningun chart lo rinde, asi que las politicas de
`platform/policies/kyverno` no lo ven en `policy-chart-u1`. Este script lo saca del codigo (con la imagen del chart: `kind-registry:5000/...@sha256:`)
y el objetivo `policy-job` de `governance/Makefile` lo evalua. Kyverno autogenera las reglas de `Pod` para `Job`; el `Pod` explicito
se evalua ademas porque es lo que admite el clúster (y donde la mutacion de la malla ya se aplico).

Uso: `render_validation_job.py DIRECTORIO`.
"""

import copy
import sys
from pathlib import Path

import yaml
from vectra_contracts.models.governance import PolicyDraft
from vectra_governance.k8s_jobs import JobSpec, job_manifest

IMAGE = "kind-registry:5000/vectra/model-validation-job@sha256:" + "3" * 64  # el repositorio de `governance/chart/values.yaml`


def main(out: Path) -> int:
    spec = JobSpec(
        job_name="validation-00000000-0000", mode="validacion", run_id="00000000-0000-0000-0000-000000000000",
        model_version_id="mv-2026-01-01-00000000", image=IMAGE, manifest_uri="s3://model-store/mv/manifest.json",
        artifact_uri="s3://model-store/mv/model.onnx", explainer_uri="s3://model-store/mv/explainer.json",
        dataset_ref="s3://validation-datasets/validation.parquet", callback_url="http://governance-service.vectra-app.svc.cluster.local:8080",
        s3_endpoint="http://minio.vectra-data.svc.cluster.local:9000", token_url="https://keycloak/token",
        assertion_audience="https://issuer.example/realms/vectra",
        policy=PolicyDraft(cutoff="0.0800", low_confidence_threshold="0.0300", channel_rules=[], normative=[]),
    )  # fmt: skip
    job = job_manifest(spec)
    template = copy.deepcopy(job["spec"]["template"])
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": f"{spec.job_name}-abcde", "namespace": job["metadata"]["namespace"], **template["metadata"]},
        "spec": template["spec"],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "job.yaml").write_text(yaml.safe_dump(job), encoding="utf-8")
    (out / "pod.yaml").write_text(yaml.safe_dump(pod), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
