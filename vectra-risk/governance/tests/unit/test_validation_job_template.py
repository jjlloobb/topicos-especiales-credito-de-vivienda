"""Plantilla del Job de validacion que crea el lanzador (K01) y chart minimo de U4 (Paso 13; INF-U4-01, U1 P-U1-05)."""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from vectra_contracts.models.governance import PolicyDraft
from vectra_governance.k8s_jobs import CLIENT_SECRET, JobSpec, job_manifest

ROOT = Path(__file__).resolve().parents[3]
INFRA = ROOT / "aidlc-docs/construction/governance/infrastructure-design/infrastructure-design.md"
CHART = ROOT / "governance/chart"
SIDECAR = "config.alpha.linkerd.io/proxy-enable-native-sidecar"


def spec() -> JobSpec:
    return JobSpec(
        job_name="validation-1", mode="validacion", run_id="r1", model_version_id="mv-1", image="reg/job@sha256:" + "a" * 64,
        manifest_uri="s3://m", artifact_uri="s3://a", explainer_uri="s3://e", dataset_ref="s3://d", callback_url="http://g",
        policy=PolicyDraft(cutoff="0.0800", low_confidence_threshold="0.0300", channel_rules=[], normative=[]),
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
    """NFR-U4-23: `runAsNonRoot`, `readOnlyRootFilesystem` y `automountServiceAccountToken: false` en el Job."""
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


# --- F-03 (ronda 2): la CA interna para pedir el token por https (VECTRA_CA_BUNDLE, deps._verify_context) -----------------------


def _self_signed_ca(directory: Path) -> Path:
    """Una CA de prueba con SAN 127.0.0.1: el servidor la usa como su certificado y el Job la confia por `VECTRA_CA_BUNDLE`."""
    import datetime as dt
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "vectra-test-ca")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=1))
        .not_valid_after(now + dt.timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    (directory / "ca.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (directory / "ca.key").write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    return directory / "ca.crt"


def test_the_real_token_provider_builds_its_tls_context_with_the_ca_the_manifest_mounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin `poster` inyectado: con solo lo que el manifiesto monta y fija, el proveedor de `vectra_common` pide su token por https."""
    import asyncio
    import http.server
    import json
    import ssl
    import threading

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from vectra_validation.config import from_env
    from vectra_validation.run import token_provider

    pod_spec = pod()["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    env = {e["name"]: e["value"] for e in container["env"] if "value" in e}
    ca_path = env.get("VECTRA_CA_BUNDLE")
    assert ca_path, "el manifiesto no fija VECTRA_CA_BUNDLE"
    mount = next(m for m in container["volumeMounts"] if ca_path.startswith(m["mountPath"].rstrip("/") + "/"))
    volume = next(v for v in pod_spec["volumes"] if v["name"] == mount["name"])
    assert mount["readOnly"] is True
    assert volume["configMap"]["name"] == "vectra-internal-ca"
    assert {"key": "ca.crt", "path": ca_path.rsplit("/", 1)[1]} in volume["configMap"]["items"]

    ca = _self_signed_ca(tmp_path)
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.dumps({"access_token": "tok", "expires_in": 60}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            return None

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(ca, tmp_path / "ca.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    key = tmp_path / "private-key"
    key.write_text(
        ec.generate_private_key(ec.SECP256R1())
        .private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        .decode()
    )
    # El archivo de la CA existe donde el manifiesto monta el ConfigMap; aqui es el de la prueba (el resto del entorno es el del manifiesto).
    cluster_env = {
        **env,
        "VECTRA_TOKEN_URL": f"https://127.0.0.1:{server.server_port}/token",
        "VECTRA_CLIENT_KEY_PATH": str(key),
        "VECTRA_S3_SECRET_KEY": "x",
    }
    monkeypatch.setenv("VECTRA_CA_BUNDLE", str(ca))
    try:
        assert asyncio.run(token_provider(from_env(cluster_env)).token()) == "tok"
    finally:
        server.shutdown()
