"""MinIO real con Testcontainers para el cliente S3 de F47 (AUTONOMIA-01: Docker local, sin cluster).

La imagen es la de la plataforma (`platform/runbooks/install.md`, paso 5: `localhost:5001/minio:dev`); `MINIO_IMAGE` la cambia. Sube
los paquetes con la misma firma SigV4 del cliente (`sigv4_headers`), con las credenciales raiz del contenedor desechable.
"""

import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest
from testcontainers.core.container import DockerContainer
from vectra_governance.s3_store import BUCKET, sigv4_headers

ACCESS_KEY = "minio-test-user"
SECRET_KEY = "minio-test-secret-0123456789"  # noqa: S105 (contenedor desechable)
IMAGE = os.environ.get("MINIO_IMAGE", "localhost:5001/minio:dev")


class Minio:
    def __init__(self, host: str, port: int, container: DockerContainer | None = None) -> None:
        self.host, self.port, self.container = host, port, container
        self.endpoint = f"http://{host}:{port}"

    def _request(self, method: str, path: str, payload: bytes = b"", key: str = SECRET_KEY) -> httpx.Response:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        headers = sigv4_headers(method, f"{self.host}:{self.port}", path, ACCESS_KEY, key, stamp, payload)
        return httpx.request(method, f"{self.endpoint}{path}", headers=headers, content=payload, timeout=10)

    def make_bucket(self, bucket: str = BUCKET) -> None:
        response = self._request("PUT", f"/{bucket}")
        assert response.status_code in (200, 409), response.text

    def put(self, key: str, data: bytes, bucket: str = BUCKET) -> None:
        response = self._request("PUT", quote(f"/{bucket}/{key}", safe="/-_.~"), data)
        assert response.status_code == 200, response.text

    def upload_package(self, directory: Path, prefix: str) -> None:
        """Sube cada archivo del paquete de U5 a `s3://model-store/<prefix>/<archivo>`."""
        for path in sorted(directory.iterdir()):
            if path.is_file():
                self.put(f"{prefix}/{path.name}", path.read_bytes())


@pytest.fixture(scope="session")
def minio() -> Iterator[Minio]:
    container = (
        DockerContainer(IMAGE)
        .with_env("MINIO_ROOT_USER", ACCESS_KEY)
        .with_env("MINIO_ROOT_PASSWORD", SECRET_KEY)
        .with_exposed_ports(9000)
        .with_command("minio server /tmp/data --address :9000")
    )
    with container:
        server = Minio(container.get_container_host_ip(), int(container.get_exposed_port(9000)), container)
        end = time.monotonic() + 30
        while True:
            try:
                if httpx.get(f"{server.endpoint}/minio/health/live", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            assert time.monotonic() < end, "MinIO no arranco en 30 s"
            time.sleep(0.2)
        server.make_bucket()
        yield server
