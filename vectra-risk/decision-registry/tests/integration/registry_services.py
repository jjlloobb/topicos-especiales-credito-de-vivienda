"""Vault dev y MinIO con object lock, con Testcontainers, para la CLI (Paso 11; NFR-U3-50; AUTONOMIA-01: sin cluster).

La imagen de Vault es `hashicorp/vault` (variable `VECTRA_VAULT_IMAGE`) en modo dev, con el motor Transit y una llave Ed25519
`registry-checkpoints`. MinIO es la imagen que construye U1 desde su codigo (`platform/data/minio/Dockerfile`; variable
`VECTRA_MINIO_IMAGE`, por omision `localhost:5001/minio:dev`): no hay imagen oficial accesible sin autenticacion. Los buckets se
crean con object lock, como en kind.
"""

import asyncio
import base64
import hashlib
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest
from testcontainers.core.container import DockerContainer
from vectra_registry.vault import Transit, batch_client
from vectra_registry.worm import S3

VAULT_IMAGE = os.environ.get("VECTRA_VAULT_IMAGE", "hashicorp/vault:1.20")
MINIO_IMAGE = os.environ.get("VECTRA_MINIO_IMAGE", "localhost:5001/minio:dev")
ROOT_TOKEN = "root-token"  # noqa: S105 (contenedor desechable)
S3_USER, S3_PASSWORD = "minioadmin", "minioadmin-secret"  # noqa: S105
CHECKPOINT_BUCKET = "vectra-registry-checkpoints"
ARCHIVE_BUCKET = "vectra-registry-archive"


def _wait(url: str, ok: tuple[int, ...] = (200,), timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code in ok:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    raise AssertionError(f"{url} no respondio")


@dataclass
class Vault:
    container: DockerContainer
    url: str
    public_key: bytes

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.public_key).hexdigest()

    @property
    def public_key_b64(self) -> str:
        return base64.b64encode(self.public_key).decode()

    def transit(self, token: str = ROOT_TOKEN) -> Transit:
        return Transit(batch_client("vault", self.url), token)

    def sign(self, message: bytes) -> str:
        return asyncio.run(self.transit().sign(message))

    def api(self, method: str, path: str, token: str = ROOT_TOKEN, **kwargs: object) -> httpx.Response:
        return httpx.request(method, f"{self.url}/v1/{path}", headers={"X-Vault-Token": token}, timeout=10, **kwargs)  # type: ignore[arg-type]


@pytest.fixture(scope="session")
def vault() -> Iterator[Vault]:
    container = (
        DockerContainer(VAULT_IMAGE)
        .with_env("VAULT_DEV_ROOT_TOKEN_ID", ROOT_TOKEN)
        .with_env("VAULT_DEV_LISTEN_ADDRESS", "0.0.0.0:8200")  # noqa: S104
        .with_kwargs(cap_add=["IPC_LOCK"])
        .with_exposed_ports(8200)
    )
    with container:
        url = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(8200)}"
        _wait(f"{url}/v1/sys/health")
        headers = {"X-Vault-Token": ROOT_TOKEN}
        httpx.post(f"{url}/v1/sys/mounts/transit", json={"type": "transit"}, headers=headers, timeout=10).raise_for_status()
        httpx.post(
            f"{url}/v1/transit/keys/registry-checkpoints", json={"type": "ed25519"}, headers=headers, timeout=10
        ).raise_for_status()
        keys = httpx.get(f"{url}/v1/transit/keys/registry-checkpoints", headers=headers, timeout=10).json()["data"]["keys"]
        yield Vault(container, url, base64.b64decode(keys["1"]["public_key"]))


@dataclass
class Minio:
    container: DockerContainer
    url: str

    def client(self) -> S3:
        return S3(batch_client("s3", self.url), self.url, S3_USER, S3_PASSWORD)

    def env(self) -> dict[str, str]:
        return {
            "REGISTRY_S3_ENDPOINT": self.url,
            "REGISTRY_S3_ACCESS_KEY": S3_USER,
            "REGISTRY_S3_SECRET_KEY": S3_PASSWORD,
            "REGISTRY_S3_CHECKPOINT_BUCKET": CHECKPOINT_BUCKET,
            "REGISTRY_S3_ARCHIVE_BUCKET": ARCHIVE_BUCKET,
        }


@pytest.fixture(scope="session")
def minio() -> Iterator[Minio]:
    container = (
        DockerContainer(MINIO_IMAGE)
        .with_env("MINIO_ROOT_USER", S3_USER)
        .with_env("MINIO_ROOT_PASSWORD", S3_PASSWORD)
        .with_command("minio server /data --address :9000")
        .with_kwargs(user="root", tmpfs={"/data": "rw"})
        .with_exposed_ports(9000)
    )
    with container:
        url = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(9000)}"
        _wait(f"{url}/minio/health/live")
        found = Minio(container, url)
        client = found.client()

        async def make() -> None:  # un solo bucle de eventos: el cliente de httpx no sobrevive a otro
            for bucket in (CHECKPOINT_BUCKET, ARCHIVE_BUCKET):
                await client.make_bucket(bucket, object_lock=True)

        asyncio.run(make())
        yield found
