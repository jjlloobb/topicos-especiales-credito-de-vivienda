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
from urllib.parse import parse_qs

import jwt
import pytest
from api_support import FakeModelStore, registration_body
from evidence_support import FakeRegistry
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from evidence_support import policy_draft
from fastapi.testclient import TestClient
from governance_pg import Db, admin_url
from minio_support import ACCESS_KEY, SECRET_KEY, Minio, minio  # noqa: F401
from strategies import auth as u0_auth
from vectra_governance.evidence import RegistryUnavailable
from vectra_governance.service import build_app

pytestmark = pytest.mark.integration

#: La `aud` que Keycloak acepta: su emisor. Distinta de la URL de token (`{registry}/token`).
ASSERTION_AUDIENCE = "https://vectra.localtest.me/auth/realms/vectra"


def now() -> datetime:
    return datetime.now(UTC)


class RegistryServer:
    """`POST /v1/entries` de U3 sobre HTTP real: lo que escribe queda en `fake.chain`; exige el Bearer de servicio."""

    def __init__(self) -> None:
        self.fake = FakeRegistry(now)  # type: ignore[arg-type]
        self.tokens: list[str | None] = []
        self.grants: list[str] = []
        fake, tokens, grants = self.fake, self.tokens, self.grants

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                raw = self.rfile.read(int(self.headers["content-length"]))
                if self.path == "/token":  # el endpoint de tokens de U2: `client_credentials` con `private_key_jwt`
                    grants.append(raw.decode())
                    assertion = parse_qs(raw.decode())["client_assertion"][0]
                    if jwt.decode(assertion, options={"verify_signature": False})["aud"] != ASSERTION_AUDIENCE:
                        self.send_response(400)  # Keycloak: `invalid_client`, `Invalid token audience`
                        self.send_header("content-length", "0")
                        self.end_headers()
                        return
                    answer = json.dumps({"access_token": "tok-real", "expires_in": 300}).encode()
                    self.send_response(200)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(answer)))
                    self.end_headers()
                    self.wfile.write(answer)
                    return
                body = json.loads(raw)
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


def client_key(directory: Path) -> Path:
    """Una llave ES256 de prueba, como la que monta el chart en `VECTRA_CLIENT_KEY_PATH`."""
    path = directory / "private-key"
    path.write_bytes(
        ec.generate_private_key(ec.SECP256R1()).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    return path


def chart_env(db: Db, minio: Minio, registry_url: str, key: Path) -> dict[str, str]:  # noqa: F811
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
        "GOVERNANCE_BIAS_URL": "http://bias-monitoring-service.vectra-app.svc.cluster.local:8080",
        "VECTRA_CLIENT_ID": "governance-service",
        "VECTRA_CLIENT_KEY_PATH": str(key),
        "VECTRA_TOKEN_URL": f"{registry_url}/token",
        "VECTRA_ASSERTION_AUDIENCE": ASSERTION_AUDIENCE,
        "GOVERNANCE_REPLICA": "build-app-test",
    }


def ingeniero() -> dict[str, str]:
    return u0_auth.bearer(sub="ing-1", roles=["ingeniero_riesgo"], acr="mfa", auth_time=int(time.time()) - 60)


def app_for(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> Any:
    for name in ("PGUSER", "PGPASSWORD"):  # libpq las lee del entorno del proceso, como en el pod
        monkeypatch.setenv(name, env[name])
    return build_app(env, authenticator=u0_auth.authenticator())  # el token de servicio es el real (`private_key_jwt`)


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
    db: Db, minio: Minio, registry: RegistryServer, package_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path  # noqa: F811
) -> None:
    model_id = json.loads((package_dir / "manifest.json").read_bytes())["model_version_id"]
    minio.upload_package(package_dir, model_id)  # s3://model-store/<model_version_id>/ (reference-model/docs/release.md)
    body = registration_body(package_dir, FakeModelStore(), model_id)
    assert body["manifest_uri"] == f"s3://model-store/{model_id}/manifest.json"
    app = app_for(monkeypatch, chart_env(db, minio, registry.url, client_key(tmp_path)))
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
        assert set(registry.tokens) == {"Bearer tok-real"}  # el token de servicio (private_key_jwt) del registro
        assert len(registry.grants) == 1 and "client_assertion=" in registry.grants[0] and "scope=registry%3Aappend%3Agovernance" in registry.grants[0]
        # Un objeto que no esta en MinIO: 422 del contrato, no un 500
        missing = client.post("/v1/models", headers=ingeniero(), json={**body, "manifest_uri": f"s3://model-store/{model_id}x/manifest.json"})
        assert missing.status_code == 422, missing.text
    assert wait_until(lambda: threads() == set(), 10), threads()  # Background se detuvo al cerrar
    # los pools se cerraron: no queda ninguna conexion de esta replica en la base
    assert db.query("SELECT count(*) FROM pg_stat_activity WHERE application_name LIKE 'governance:build-app-test:%%'") == [(0,)]


def test_ca_4_a_store_that_is_down_answers_a_problem_503_never_a_500_without_a_body(
    db: Db, minio: Minio, registry: RegistryServer, package_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path  # noqa: F811
) -> None:
    env = {**chart_env(db, minio, registry.url, client_key(tmp_path)), "GOVERNANCE_S3_ENDPOINT": "http://127.0.0.1:9"}  # nadie escucha en el puerto 9
    body = registration_body(package_dir, FakeModelStore(), "mv-store-caido")
    with TestClient(app_for(monkeypatch, env), base_url="http://governance", raise_server_exceptions=False) as client:
        response = client.post("/v1/models", headers=ingeniero(), json=body)
    assert response.status_code == 503, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["status"] == 503 and response.json()["code"] == "dependency_unavailable"
    assert db.query("SELECT count(*) FROM model_versions") == [(0,)]


def test_a_wrong_minio_credential_is_also_a_problem_503(
    db: Db, minio: Minio, registry: RegistryServer, package_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path  # noqa: F811
) -> None:
    env = {**chart_env(db, minio, registry.url, client_key(tmp_path)), "GOVERNANCE_S3_SECRET_KEY": "otra-clave-distinta-0123456789"}
    minio.upload_package(package_dir, "mv-credencial")
    body = registration_body(package_dir, FakeModelStore(), "mv-credencial")
    with TestClient(app_for(monkeypatch, env), base_url="http://governance", raise_server_exceptions=False) as client:
        response = client.post("/v1/models", headers=ingeniero(), json=body)
    assert (response.status_code, response.json()["code"]) == (503, "dependency_unavailable")


def cro() -> dict[str, str]:
    return u0_auth.bearer(sub="cro-1", roles=["cro"], acr="mfa", auth_time=int(time.time()) - 60)


def test_ca_1_post_policies_reaches_confirmada_against_a_registry(
    db: Db, minio: Minio, registry: RegistryServer, monkeypatch: pytest.MonkeyPatch, tmp_path: Path  # noqa: F811
) -> None:
    with TestClient(app_for(monkeypatch, chart_env(db, minio, registry.url, client_key(tmp_path))), base_url="http://governance") as client:
        response = client.post("/v1/policies", headers=cro(), json=policy_draft().model_dump(mode="json"))
        assert response.status_code == 200, response.text
        policy_id = response.json()["policy_version_id"]
        assert db.query("SELECT status FROM transitions WHERE entity_id = %s", policy_id) == [("confirmada",)]
        assert registry.fake.names(policy_id) == ["propuesta"]
        assert set(registry.tokens) == {"Bearer tok-real"}


def test_f_02_without_the_client_key_it_warns_and_the_transition_stays_pendiente_registro_with_a_problem_503(
    db: Db, minio: Minio, registry: RegistryServer, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture  # noqa: F811
) -> None:
    env = {**chart_env(db, minio, registry.url, tmp_path / "no-esta"), "GOVERNANCE_REPLICA": "sin-llave"}
    with caplog.at_level("WARNING", logger="vectra_governance.service"):
        app = app_for(monkeypatch, env)
    assert any("no existe la llave del cliente governance-service" in r.getMessage() for r in caplog.records)
    with TestClient(app, base_url="http://governance", raise_server_exceptions=False) as client:
        response = client.post("/v1/policies", headers=cro(), json=policy_draft().model_dump(mode="json"))
    assert response.status_code == 503, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "dependency_unavailable"
    assert db.query("SELECT status FROM transitions") == [("pendiente_registro",)]
    assert registry.tokens == []  # nada llego al registro: no hubo token


def test_f_04_the_s3_client_is_closed_when_the_app_closes(
    db: Db, minio: Minio, registry: RegistryServer, monkeypatch: pytest.MonkeyPatch, tmp_path: Path  # noqa: F811
) -> None:
    app = app_for(monkeypatch, chart_env(db, minio, registry.url, client_key(tmp_path)))
    closed: list[bool] = []
    import vectra_governance.s3_store as s3

    original = s3.S3PackageStore.close
    monkeypatch.setattr(s3.S3PackageStore, "close", lambda self: (closed.append(True), original(self))[1])
    with TestClient(app, base_url="http://governance"):
        assert closed == []
    assert closed == [True]


_ = admin_url  # el fixture `db` ya trae las bases y los roles de U1
