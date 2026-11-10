"""CA-3 y CA-4 (U04-T08; F47, F24, P-U4-02, NFR-U4-03, NFR-U4-25): `build_app()` con las variables del chart, sobre PostgreSQL y MinIO reales (Testcontainers).

Registra un paquete real de U5 por `POST /v1/models` leyendolo de MinIO por F47, y comprueba el ciclo de vida: `Background` arranca
(hilos `reconcile` y `sweep`) y se detiene ordenadamente al cerrar la app, y los pools se cierran. El registro (U3) es un servidor
HTTP real con la semantica de `FakeRegistry`; el token de servicio y el validador de tokens son los de prueba de U0.
"""

import json
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from api_support import FakeModelStore, registration_body
from evidence_support import FakeRegistry
from fastapi.testclient import TestClient
from governance_pg import Db, admin_url
from minio_support import ACCESS_KEY, SECRET_KEY, Minio, minio  # noqa: F401
from strategies import auth as u0_auth
from vectra_governance.evidence import RegistryUnavailable
from vectra_governance.service import build_app

pytestmark = pytest.mark.integration


def now() -> datetime:
    return datetime.now(UTC)


class RegistryServer:
    """`POST /v1/entries` de U3 sobre HTTP real: lo que escribe queda en `fake.chain`; exige el Bearer de servicio."""

    def __init__(self) -> None:
        self.fake = FakeRegistry(now)  # type: ignore[arg-type]
        self.tokens: list[str | None] = []
        fake, tokens = self.fake, self.tokens

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                tokens.append(self.headers.get("authorization"))
                try:
                    ack = fake.append(body).model_dump_json().encode()
                    status = 200
                except RegistryUnavailable:
                    ack, status = b"{}", 503
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(ack)))
                self.end_headers()
                self.wfile.write(ack)

            def log_message(self, *_: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def registry() -> Iterator[RegistryServer]:
    server = RegistryServer()
    yield server
    server.close()


def chart_env(db: Db, minio: Minio, registry_url: str) -> dict[str, str]:  # noqa: F811
    """Las variables del Deployment del chart (`governance/chart/templates/service.yaml`) apuntando a los contenedores de prueba."""
    return {
        "GOVERNANCE_DATABASE_DSN": f"postgresql://{db.pg.get_container_host_ip()}:{db.pg.get_exposed_port(5432)}/{db.name}?sslmode=disable",
        "PGUSER": "gov_app",
        "PGPASSWORD": "gov_app",
        "GOVERNANCE_S3_ENDPOINT": minio.endpoint,
        "GOVERNANCE_S3_ACCESS_KEY": ACCESS_KEY,
        "GOVERNANCE_S3_SECRET_KEY": SECRET_KEY,
        "GOVERNANCE_VALIDATION_IMAGE": "registry.test/vectra/model-validation-job@sha256:" + "3" * 64,
        "GOVERNANCE_VALIDATION_DATASET": "s3://validation-datasets",
        "GOVERNANCE_CALLBACK_URL": "http://governance-service.vectra-app.svc.cluster.local:8080",
        "GOVERNANCE_JOB_S3_ENDPOINT": "http://minio.vectra-data.svc.cluster.local:9000",
        "GOVERNANCE_JOB_TOKEN_URL": "https://keycloak.test/token",
        "VECTRA_OIDC_ISSUER": u0_auth.ISSUER,
        "VECTRA_JWKS_URL": "http://keycloak.test/certs",
        "VECTRA_CA_BUNDLE": "/etc/vectra/ca/ca.crt",
        "GOVERNANCE_REGISTRY_URL": registry_url,
        "GOVERNANCE_REPLICA": "build-app-test",
    }


def ingeniero() -> dict[str, str]:
    return u0_auth.bearer(sub="ing-1", roles=["ingeniero_riesgo"], acr="mfa", auth_time=int(time.time()) - 60)


def app_for(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> Any:
    for name in ("PGUSER", "PGPASSWORD"):  # libpq las lee del entorno del proceso, como en el pod
        monkeypatch.setenv(name, env[name])
    return build_app(env, authenticator=u0_auth.authenticator(), tokens=lambda audience, scopes: lambda: f"tok-{audience}")


def threads() -> set[str]:
    return {t.name for t in threading.enumerate() if t.name.startswith("governance-") and t.is_alive()}


def wait_until(condition: Any, timeout: float = 10.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.05)
    return bool(condition())


def test_ca_3_build_app_registers_a_real_package_read_from_minio_and_background_stops_cleanly(
    db: Db, minio: Minio, registry: RegistryServer, package_dir: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    model_id = json.loads((package_dir / "manifest.json").read_bytes())["model_version_id"]
    minio.upload_package(package_dir, model_id)  # s3://model-store/<model_version_id>/ (reference-model/docs/release.md)
    body = registration_body(package_dir, FakeModelStore(), model_id)
    assert body["manifest_uri"] == f"s3://model-store/{model_id}/manifest.json"
    app = app_for(monkeypatch, chart_env(db, minio, registry.url))
    assert threads() == set()
    with TestClient(app, base_url="http://governance") as client, TestClient(app.state.ops_app) as ops:
        assert {"governance-reconcile", "governance-sweep"} <= threads()  # Background arranca con la app (y los hilos del cache)
        assert ops.get("/healthz").status_code == 200
        assert wait_until(lambda: ops.get("/readyz").status_code == 200)  # la copia de serving-config cargo
        response = client.post("/v1/models", headers=ingeniero(), json=body)
        assert response.status_code == 200, response.text
        assert response.json()["model_version_id"] == model_id and response.json()["state"] == "registrado"
        # lo que se registro salio de MinIO, no de un doble: la fila guarda el diccionario del paquete
        rows = db.query("SELECT state, registered_by, feature_dictionary FROM model_versions WHERE model_version_id = %s", model_id)
        assert [(r[0], r[1]) for r in rows] == [("registrado", "ing-1")]
        assert rows[0][2] == json.loads((package_dir / "feature_dictionary.json").read_bytes())
        assert db.query("SELECT status FROM transitions WHERE entity_id = %s", model_id) == [("confirmada",)]
        assert registry.fake.names(model_id) == ["registrado"]
        assert set(registry.tokens) == {"Bearer tok-decision-registry-service"}  # el token de servicio del registro
        # Un objeto que no esta en MinIO: 422 del contrato, no un 500
        missing = client.post("/v1/models", headers=ingeniero(), json={**body, "manifest_uri": f"s3://model-store/{model_id}x/manifest.json"})
        assert missing.status_code == 422, missing.text
    assert wait_until(lambda: threads() == set(), 10), threads()  # Background se detuvo al cerrar
    # los pools se cerraron: no queda ninguna conexion de esta replica en la base
    assert db.query("SELECT count(*) FROM pg_stat_activity WHERE application_name LIKE 'governance:build-app-test:%%'") == [(0,)]


def test_ca_4_a_store_that_is_down_answers_a_problem_503_never_a_500_without_a_body(
    db: Db, minio: Minio, registry: RegistryServer, package_dir: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    env = {**chart_env(db, minio, registry.url), "GOVERNANCE_S3_ENDPOINT": "http://127.0.0.1:9"}  # nadie escucha en el puerto 9
    body = registration_body(package_dir, FakeModelStore(), "mv-store-caido")
    with TestClient(app_for(monkeypatch, env), base_url="http://governance", raise_server_exceptions=False) as client:
        response = client.post("/v1/models", headers=ingeniero(), json=body)
    assert response.status_code == 503, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["status"] == 503 and response.json()["code"] == "dependency_unavailable"
    assert db.query("SELECT count(*) FROM model_versions") == [(0,)]


def test_a_wrong_minio_credential_is_also_a_problem_503(
    db: Db, minio: Minio, registry: RegistryServer, package_dir: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    env = {**chart_env(db, minio, registry.url), "GOVERNANCE_S3_SECRET_KEY": "otra-clave-distinta-0123456789"}
    minio.upload_package(package_dir, "mv-credencial")
    body = registration_body(package_dir, FakeModelStore(), "mv-credencial")
    with TestClient(app_for(monkeypatch, env), base_url="http://governance", raise_server_exceptions=False) as client:
        response = client.post("/v1/models", headers=ingeniero(), json=body)
    assert (response.status_code, response.json()["code"]) == (503, "dependency_unavailable")


_ = admin_url  # el fixture `db` ya trae las bases y los roles de U1
