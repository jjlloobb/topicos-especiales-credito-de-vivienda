"""CA-1 (U04-T08; INF-U4-01, NFR-U4-03, P-U4-03, F47): el contenedor de `governance-service` arranca de verdad.

Construye la imagen (`make -C governance image`, `localhost:5001/vectra/governance:dev`) y la corre como la corre el chart: usuario
65532, raiz de solo lectura, sin capacidades y con las variables de `governance/chart/templates/service.yaml`. Postgres (migrado) y
MinIO (con un paquete real de U5) son contenedores de prueba en una red de Docker propia, de modo que el servicio los alcanza por
nombre; los puertos 8080 y 8081 se publican en el anfitrion para sondearlos. El JWKS lo sirve otro contenedor de la misma imagen.

Comprueba `/healthz` y `/readyz` (8081) en 200, `GET /v1/serving-config` (503 `dependency_unavailable` sin politica activa), 401 sin
token, y que no hay trazas en el log.
"""

import json
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import docker
import httpx
import pytest
from api_support import FakeModelStore, registration_body
from governance_pg import Db
from minio_support import ACCESS_KEY, SECRET_KEY, Minio, minio  # noqa: F401
from strategies import auth as u0_auth

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[3]
IMAGE = "localhost:5001/vectra/governance:dev"
SERVING = "governance:read-serving"


@pytest.fixture(scope="session")
def image() -> str:
    """La misma construccion que `make -C governance image` (con cache de capas, es rapida si nada cambio)."""
    subprocess.run(  # noqa: S603
        ["docker", "build", "-q", "-t", IMAGE, "-f", "governance/Dockerfile", "."], cwd=ROOT, check=True, capture_output=True
    )
    return IMAGE


@pytest.fixture
def network() -> Iterator[Any]:
    client = docker.from_env()
    net = client.networks.create("u04-t08-" + uuid.uuid4().hex[:8])
    try:
        yield net
    finally:
        net.remove()


def wait(url: str, expected: int, timeout: float = 40.0) -> httpx.Response | None:
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        try:
            last = httpx.get(url, timeout=2)
            if last.status_code == expected:
                return last
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    return last


def published(container: Any, port: int) -> str:
    container.reload()
    mapped = container.attrs["NetworkSettings"]["Ports"][f"{port}/tcp"][0]["HostPort"]
    return f"http://127.0.0.1:{mapped}"


def test_ca_1_the_image_starts_with_postgres_minio_and_the_chart_variables(
    image: str, network: Any, db: Db, minio: Minio, package_dir: Path  # noqa: F811
) -> None:
    client = docker.from_env()
    network.connect(db.pg.get_wrapped_container(), aliases=["governance-db"])
    assert minio.container is not None
    network.connect(minio.container.get_wrapped_container(), aliases=["minio"])
    model_id = json.loads((package_dir / "manifest.json").read_bytes())["model_version_id"]
    minio.upload_package(package_dir, model_id)
    assert registration_body(package_dir, FakeModelStore(), model_id)["manifest_uri"].startswith("s3://model-store/")

    jwks = json.dumps(u0_auth.jwks_document())
    serve_jwks = (
        "import http.server\n"
        "class H(http.server.BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        body = " + repr(jwks) + ".encode()\n"
        "        self.send_response(200); self.send_header('content-type', 'application/json'); self.end_headers(); self.wfile.write(body)\n"
        "http.server.HTTPServer(('0.0.0.0', 8000), H).serve_forever()\n"
    )
    keycloak = client.containers.run(
        image, entrypoint=["python", "-c", serve_jwks], detach=True, network=network.name, name=f"{network.name}-jwks"
    )
    # Las variables del Deployment (`service.yaml`); el DSN y los hosts apuntan a los contenedores de la red.
    env = {
        "GOVERNANCE_DATABASE_DSN": f"postgresql://governance-db:5432/{db.name}?sslmode=disable",
        "PGUSER": "gov_app",
        "PGPASSWORD": "gov_app",
        "GOVERNANCE_S3_ENDPOINT": "http://minio:9000",
        "GOVERNANCE_S3_ACCESS_KEY": ACCESS_KEY,
        "GOVERNANCE_S3_SECRET_KEY": SECRET_KEY,
        "GOVERNANCE_VALIDATION_IMAGE": "kind-registry:5000/vectra/model-validation-job@sha256:" + "3" * 64,
        "GOVERNANCE_VALIDATION_DATASET": "s3://validation-datasets",
        "GOVERNANCE_CALLBACK_URL": "http://governance-service.vectra-app.svc.cluster.local:8080",
        "GOVERNANCE_JOB_S3_ENDPOINT": "http://minio.vectra-data.svc.cluster.local:9000",
        "GOVERNANCE_JOB_TOKEN_URL": "https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra/protocol/openid-connect/token",
        "VECTRA_OIDC_ISSUER": u0_auth.ISSUER,
        "VECTRA_JWKS_URL": f"http://{keycloak.name}:8000/certs",
        "VECTRA_CA_BUNDLE": "/etc/vectra/ca/ca.crt",
    }
    service = client.containers.run(
        image,  # el CMD de la imagen: `python -m vectra_governance.service`
        detach=True,
        network=network.name,
        environment=env,
        user="65532:65532",
        read_only=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        ports={"8080/tcp": None, "8081/tcp": None},
    )
    try:
        ops, api = published(service, 8081), published(service, 8080)
        assert (health := wait(f"{ops}/healthz", 200)) is not None and health.status_code == 200, service.logs().decode()
        ready = wait(f"{ops}/readyz", 200)
        assert ready is not None and ready.status_code == 200, service.logs().decode()
        assert httpx.get(f"{ops}/metrics", timeout=5).status_code == 200
        # Sin politica activa ni version servible: el contrato dice 503 (`dependency_unavailable`); sin token, 401.
        token = u0_auth.bearer(sub="svc-scoring", roles=None, acr=None, auth_time=None, scope=SERVING, azp="scoring-service", aud="governance-service")
        config = httpx.get(f"{api}/v1/serving-config", headers=token, timeout=5)
        assert config.status_code == 503 and config.json()["code"] == "dependency_unavailable", config.text
        assert httpx.get(f"{api}/v1/serving-config", timeout=5).status_code == 401
        logs = service.logs().decode()
        assert "Traceback" not in logs and "No module named" not in logs, logs
    finally:
        service.remove(force=True)
        keycloak.remove(force=True)
        network.disconnect(db.pg.get_wrapped_container())
        network.disconnect(minio.container.get_wrapped_container())
