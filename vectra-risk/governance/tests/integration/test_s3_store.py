"""CA-4 (U04-T08; F47, NFR-U4-25): el cliente S3 de F47 contra MinIO real (Testcontainers): firma SigV4, objeto ausente, credencial mala, timeout y
red caida. Un fallo del store es `DependencyUnavailable` (503 del contrato), nunca una excepcion sin traducir."""

import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from minio_support import ACCESS_KEY, SECRET_KEY, Minio, minio  # noqa: F401
from vectra_common.errors import DependencyUnavailable
from vectra_governance.s3_store import S3PackageStore

pytestmark = pytest.mark.integration


def store(minio: Minio, **over: object) -> S3PackageStore:  # noqa: F811
    args: dict[str, object] = {"endpoint": minio.endpoint, "access_key": ACCESS_KEY, "secret_key": SECRET_KEY, **over}
    return S3PackageStore(**args)  # type: ignore[arg-type]


def test_reads_the_exact_bytes_of_a_package_file_signed_with_sigv4(minio: Minio, package_dir: Path) -> None:  # noqa: F811
    minio.upload_package(package_dir, "mv-sigv4")
    reader = store(minio)
    for name in ("manifest.json", "predictor.json", "explainer.json"):
        assert reader.read(f"s3://model-store/mv-sigv4/{name}") == (package_dir / name).read_bytes()


def test_a_key_with_spaces_and_unicode_is_signed_on_the_encoded_path(minio: Minio) -> None:  # noqa: F811
    minio.put("mv-raro/archivo con espacio ñ.json", b'{"ok": true}')
    assert store(minio).read("s3://model-store/mv-raro/archivo con espacio ñ.json") == b'{"ok": true}'


def test_a_missing_object_is_file_not_found(minio: Minio) -> None:  # noqa: F811
    with pytest.raises(FileNotFoundError):
        store(minio).read("s3://model-store/mv-no-existe/manifest.json")


@pytest.mark.parametrize(
    "uri",
    [
        "s3://otro-bucket/mv/manifest.json",
        "http://model-store/mv/manifest.json",
        "s3://model-store/",
        "s3://model-store/mv/../otro/manifest.json",
        "s3://model-store/mv//manifest.json",
    ],
)
def test_a_uri_outside_the_model_store_is_never_requested(minio: Minio, uri: str) -> None:  # noqa: F811
    with pytest.raises(FileNotFoundError):
        store(minio).read(uri)


def test_a_wrong_secret_is_dependency_unavailable_not_a_500(minio: Minio, package_dir: Path) -> None:  # noqa: F811
    minio.upload_package(package_dir, "mv-secret")
    with pytest.raises(DependencyUnavailable):
        store(minio, secret_key="otra-clave-distinta-0123456789").read("s3://model-store/mv-secret/manifest.json")


@contextmanager
def silent_server() -> Iterator[int]:
    """Acepta la conexion y nunca responde: el timeout de lectura."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    held: list[socket.socket] = []
    stop = threading.Event()

    def accept() -> None:
        server.settimeout(0.1)
        while not stop.is_set():
            try:
                held.append(server.accept()[0])
            except OSError:
                continue

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    try:
        yield int(server.getsockname()[1])
    finally:
        stop.set()
        thread.join()
        for conn in held:
            conn.close()
        server.close()


def test_a_store_that_does_not_answer_times_out_as_dependency_unavailable() -> None:
    with silent_server() as port:
        reader = S3PackageStore(f"http://127.0.0.1:{port}", ACCESS_KEY, SECRET_KEY, timeout=0.3)
        with pytest.raises(DependencyUnavailable):
            reader.read("s3://model-store/mv/manifest.json")


def test_a_store_that_is_down_is_dependency_unavailable() -> None:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()  # nadie escucha en ese puerto
    with pytest.raises(DependencyUnavailable):
        S3PackageStore(f"http://127.0.0.1:{port}", ACCESS_KEY, SECRET_KEY).read("s3://model-store/mv/manifest.json")
