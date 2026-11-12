"""Paso 13: arranque real (`python -m vectra_case.app`, un proceso, no `runpy`) y apagado con `SIGTERM` (INF-U8-06; NFR-U8-22).

La app necesita las variables obligatorias del Deployment; un servidor HTTP local hace de endpoint de tokens, de registro y de
governance. Usa los puertos de U0 (8080 y 8081): si estan ocupados la prueba falla con un mensaje claro.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest
from case_pg import Db, url
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from u8_support import insert_fail_closed, seed_case

pytestmark = pytest.mark.integration
# uvicorn vuelve a emitir la senal capturada tras un apagado ordenado: el proceso termina con 0 o con -SIGTERM.
CLEAN_EXIT = (0, -signal.SIGTERM)
ROOT = Path(__file__).resolve().parents[3]


class Stub:
    """Token, registro (lento, con ack) y governance (caido) en un solo servidor."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.entries: list[dict[str, Any]] = []
        self.lock = threading.Lock()
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                return

            def _send(self, status: int, body: dict[str, Any]) -> None:
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self) -> None:  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("content-length", 0)))
                if self.path == "/token":
                    return self._send(200, {"access_token": "t", "expires_in": 300})
                entry = json.loads(raw)
                with stub.lock:
                    stub.entries.append(entry)
                    seq = len(stub.entries)
                time.sleep(stub.delay)
                return self._send(
                    200,
                    {"registry_entry_id": str(seq), "seq": seq, "recorded_at": "2026-11-11T12:00:00+00:00"},
                )

            def do_GET(self) -> None:  # noqa: N802
                self._send(503, {})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def start(db: Db, stub: Stub, tmp_path: Path) -> subprocess.Popen[bytes]:
    for port in (8080, 8081):
        assert port_free(port), (
            f"el puerto {port} esta ocupado: la prueba de arranque real lo necesita (puertos fijos de U0)"
        )
    key = tmp_path / "client.pem"
    key.write_bytes(
        ec.generate_private_key(ec.SECP256R1()).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    base = f"http://127.0.0.1:{stub.port}"
    env = {
        **os.environ,
        "CASE_DB_DSN": url(db.pg, db.name, "case_app", "case_app"),
        "CASE_GOVERNANCE_URL": base,
        "CASE_REGISTRY_URL": base,
        "CASE_CORE_ENABLED": "false",
        "CASE_ALLOW_TEST_SCENARIOS": "false",
        "VECTRA_OIDC_ISSUER": "http://issuer.test",
        "VECTRA_JWKS_URL": f"{base}/jwks",
        "VECTRA_CLIENT_ID": "case-service",
        "VECTRA_TOKEN_URL": f"{base}/token",
        "VECTRA_CLIENT_KEY_PATH": str(key),
    }
    log = (tmp_path / "service.log").open("wb")
    return subprocess.Popen(
        [sys.executable, "-m", "vectra_case.app"], env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT
    )


def wait_ready(proc: subprocess.Popen[bytes], timeout: float = 40.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert proc.poll() is None, "el proceso termino antes de quedar listo"
        try:
            return httpx.get("http://127.0.0.1:8081/readyz", timeout=1.0).status_code
        except httpx.HTTPError:
            time.sleep(0.3)
    raise AssertionError("el servicio no respondio /readyz")


def test_python_dash_m_starts_for_real_and_readyz_is_200_with_case_db_up(db: Db, tmp_path: Path) -> None:
    stub = Stub(0.0)
    proc = start(db, stub, tmp_path)
    try:
        assert wait_ready(proc) == 200
        assert httpx.get("http://127.0.0.1:8081/healthz", timeout=2).status_code == 200
        started = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=15) in CLEAN_EXIT
        assert time.monotonic() - started <= 10  # espera de <= 10 s
    finally:
        if proc.poll() is None:
            proc.kill()
        stub.close()


def test_missing_mandatory_variables_make_the_process_fail_to_start(db: Db, tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CASE_", "VECTRA_"))}
    done = subprocess.run(
        [sys.executable, "-m", "vectra_case.app"],
        env=env,
        cwd=ROOT,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert done.returncode != 0 and b"KeyError" in done.stderr


def test_sigterm_during_a_reconciler_batch_finishes_the_batch_without_half_sent_evidence(
    db: Db, tmp_path: Path
) -> None:
    case_id = seed_case(db, state="no_disponible")
    insert_fail_closed(db, case_id, 12)
    stub = Stub(1.0)
    proc = start(db, stub, tmp_path)
    try:
        deadline = time.monotonic() + 40
        while not stub.entries and time.monotonic() < deadline:
            assert proc.poll() is None
            time.sleep(0.1)
        assert stub.entries, "el reconciliador no envio nada"
        proc.send_signal(signal.SIGTERM)  # a mitad del lote
        assert proc.wait(timeout=20) in CLEAN_EXIT
    finally:
        if proc.poll() is None:
            proc.kill()
        stub.close()
    sent = len(stub.entries)
    states = [r[0] for r in db.query("SELECT state FROM evidence_outbox")]
    assert sent == 12 and states.count("confirmada") == sent, (
        sent,
        states,
    )  # cada envio quedo registrado: nada a medio enviar
    assert "pendiente_registro" not in states
