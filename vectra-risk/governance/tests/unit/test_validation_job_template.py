"""Plantilla del Job de validacion que crea el lanzador (K01) y chart minimo de U4 (Paso 13; INF-U4-01, U1 P-U1-05)."""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from vectra_governance.k8s_jobs import CLIENT_SECRET, JobSpec, job_manifest

ROOT = Path(__file__).resolve().parents[3]
INFRA = ROOT / "aidlc-docs/construction/governance/infrastructure-design/infrastructure-design.md"
CHART = ROOT / "governance/chart"
SIDECAR = "config.alpha.linkerd.io/proxy-enable-native-sidecar"


def spec() -> JobSpec:
    return JobSpec(
        job_name="validation-1", mode="validacion", run_id="r1", model_version_id="mv-1", image="reg/job@sha256:" + "a" * 64,
        manifest_uri="s3://m", artifact_uri="s3://a", explainer_uri="s3://e", dataset_ref="s3://d", callback_url="http://g",
    )


def pod() -> dict[str, Any]:
    manifest: dict[str, Any] = job_manifest(spec())
    return manifest


def inf_u4_01_row() -> list[str]:
    """La fila del `model-validation-job` de la tabla de INF-U4-01, tal como la escribe el diseno."""
    for line in INFRA.read_text(encoding="utf-8").splitlines():
        if line.startswith("| `model-validation-job`"):
            return [cell.strip() for cell in line.strip("|").split("|")]
    raise AssertionError("INF-U4-01 sin fila de model-validation-job")


def quantities(cell: str) -> dict[str, str]:
    """`500m / 1 GiB (nota)` -> cpu y memoria en notacion de Kubernetes (`1 GiB` -> `1Gi`; `2 CPU` -> `2`)."""
    cpu, memory = (part.strip() for part in re.sub(r"\(.*?\)", "", cell).split("/"))
    return {"cpu": cpu.replace(" CPU", ""), "memory": memory.replace(" GiB", "Gi").replace(" MiB", "Mi")}


def test_the_manifest_carries_the_native_linkerd_sidecar_annotation_explicitly() -> None:
    annotations = pod()["spec"]["template"]["metadata"]["annotations"]
    assert annotations[SIDECAR] == "true"


def test_the_manifest_matches_inf_u4_01_read_from_the_design() -> None:
    _, requests, limits, scaling, priority = inf_u4_01_row()[:5]
    template = pod()["spec"]
    container = template["template"]["spec"]["containers"][0]
    assert container["resources"] == {"requests": quantities(requests), "limits": quantities(limits)}
    assert template["activeDeadlineSeconds"] == int(re.search(r"activeDeadlineSeconds: (\d+)", scaling).group(1))  # type: ignore[union-attr]
    assert template["template"]["spec"]["priorityClassName"] == priority.strip("`")


def test_the_manifest_is_the_staging_job_with_the_batch_guarantees_and_security() -> None:
    manifest = pod()
    job, pod_spec = manifest["spec"], manifest["spec"]["template"]["spec"]
    assert manifest["metadata"]["namespace"] == "vectra-staging"
    assert (job["ttlSecondsAfterFinished"], job["activeDeadlineSeconds"], job["backoffLimit"]) == (86400, 7200, 0)
    assert pod_spec["restartPolicy"] == "Never"
    assert pod_spec["serviceAccountName"] == "model-validation-job"
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["priorityClassName"] == "vectra-low"
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    container = pod_spec["containers"][0]
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["capabilities"] == {"drop": ["ALL"]}


def test_the_job_mounts_the_bucket_credential_and_the_client_key_without_literal_secrets() -> None:
    pod_spec = pod()["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    env = {e["name"]: e for e in container["env"]}
    assert env["VECTRA_S3_SECRET_KEY"]["valueFrom"]["secretKeyRef"] == {"name": "minio-validation", "key": "secretKey"}
    assert env["VECTRA_S3_ACCESS_KEY"]["value"] == "validation-readonly"
    assert env["VECTRA_CLIENT_KEY_PATH"]["value"] == "/var/run/vectra/client/private-key"
    assert {"name": "client-key", "secret": {"secretName": CLIENT_SECRET, "defaultMode": 0o400}} in pod_spec["volumes"]
    assert "value" not in env["VECTRA_S3_SECRET_KEY"]


@pytest.mark.skipif(shutil.which("helm") is None, reason="helm no disponible")
def test_the_chart_renders_the_service_account_and_the_external_secret_in_vectra_staging() -> None:
    out = subprocess.run(
        ["helm", "template", "governance", str(CHART), "--namespace", "vectra-staging"], check=True, capture_output=True, text=True
    ).stdout
    docs = {d["kind"]: d for d in yaml.safe_load_all(out) if d}
    account, secret = docs["ServiceAccount"], docs["ExternalSecret"]
    assert (account["metadata"]["name"], account["metadata"]["namespace"]) == ("model-validation-job", "vectra-staging")
    assert account["automountServiceAccountToken"] is False
    assert secret["metadata"]["namespace"] == "vectra-staging"
    assert secret["spec"]["target"]["name"] == CLIENT_SECRET  # el Secret que monta el Job
    assert secret["spec"]["data"] == [
        {"secretKey": "private-key", "remoteRef": {"key": "identity/clients/model-validation-job", "property": "private-key"}}
    ]
    assert set(docs) == {"ServiceAccount", "ExternalSecret"}  # el resto de U4 es de U04-T06
