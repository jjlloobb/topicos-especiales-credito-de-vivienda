"""U01-T08: el storage initializer de KServe necesita `AWS_*` en `minio-kserve` y el endpoint de MinIO (F46).

KServe v0.21.0 (`pkg/credentials/service_account_credentials.go`) solo reconoce un Secret S3 con la clave
`AWS_SECRET_ACCESS_KEY` (o la de `credentials.s3.s3SecretAccessKeyName`); el endpoint sale de `credentials.s3` en el
ConfigMap `inferenceservice-config`, que el chart `kserve-resources` genera desde `kserve.storage.s3.*`.
"""

import json
from pathlib import Path

import pytest
import yaml
from test_upstream_charts import of, render

ROOT = Path(__file__).resolve().parents[2]
RENDERED = ROOT / "platform/rendered"
# F46: predictor y explainer (vectra-serving) y staging-isvc (vectra-staging) -> minio:9000. MinIO no tiene TLS propio:
# el cifrado en transito es el mTLS de Linkerd (mismo endpoint en loki.yaml y tempo.yaml, en todos los entornos).
ENDPOINT = "minio.vectra-data.svc:9000"


def external_secrets(env):
    documents = yaml.safe_load_all((RENDERED / env / "data.yaml").read_text(encoding="utf-8"))
    return {(d["metadata"]["namespace"], d["metadata"]["name"]): d for d in documents if d and d["kind"] == "ExternalSecret"}


def keys(secret):
    return {item["secretKey"]: item["remoteRef"] for item in secret["spec"]["data"]}


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
@pytest.mark.parametrize("namespace", ["vectra-serving", "vectra-staging"])
def test_minio_kserve_has_aws_keys_in_serving_namespaces(env, namespace):
    data = keys(external_secrets(env)[(namespace, "minio-kserve")])
    assert data["AWS_ACCESS_KEY_ID"] == {"key": "minio/kserve", "property": "accessKey"}
    assert data["AWS_SECRET_ACCESS_KEY"] == {"key": "minio/kserve", "property": "secretKey"}


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_minio_kserve_keeps_provisioning_keys_in_vectra_data(env):
    data = keys(external_secrets(env)[("vectra-data", "minio-kserve")])
    assert data["accessKey"] == {"key": "minio/kserve", "property": "accessKey"}
    assert data["secretKey"] == {"key": "minio/kserve", "property": "secretKey"}


def test_kserve_operator_points_the_storage_initializer_at_minio():
    configmap = next(d for d in of(render("kserve"), "ConfigMap") if d["metadata"]["name"] == "inferenceservice-config")
    s3 = json.loads(configmap["data"]["credentials"])["s3"]
    assert s3["s3Endpoint"] == ENDPOINT
    assert s3["s3UseHttps"] == "0"
    assert s3["s3AccessKeyIDName"] == "AWS_ACCESS_KEY_ID"
    assert s3["s3SecretAccessKeyName"] == "AWS_SECRET_ACCESS_KEY"


def test_endpoint_matches_the_port_of_f46():
    flows = yaml.safe_load((ROOT / "platform/network/flows.yaml").read_text(encoding="utf-8"))
    f46 = next(f for f in flows["flows"] if f["id"] == "F46")
    assert ENDPOINT.endswith(f":{f46['port']}")
