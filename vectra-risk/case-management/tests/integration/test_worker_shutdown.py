"""Paso 15: arranque real de `python -m vectra_case.worker` (un proceso, no `runpy`) y apagado ordenado con `SIGTERM` (INF-U8-06; P-U8-06; NFR-U8-22).

El worker corre como proceso con las variables obligatorias; un servidor HTTP local hace de endpoint de tokens, de governance y de scoring.
Usa el puerto de sondas de U0 (8081): si esta ocupado la prueba falla con un mensaje claro. Despues de que el proceso termina se lee el caso
de la base: no se afirma sobre el codigo de salida de uvicorn (`bitacoras/U08-T03.md`), sino sobre el estado del caso.

P-2 (a) de U08-T04: `SCORING_TIMEOUT` es de 7 s (NFR-U8-30), asi que una respuesta «a los 10 s» nunca llega. La linea del plan se prueba con un
scoring que responde a los 5 s (dentro del timeout, muy por encima de los 0,5 s del `SIGTERM`), y un segundo caso con 10 s comprueba que el
intento termina a los 7 s como `scoring_unreachable` y el proceso sale antes de los 20 s.
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
from case_strategies import recommendation_from_wire
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from prometheus_client.parser import text_string_to_metric_families
from u8_support import GovernanceDouble
from vectra_case import metrics
from vectra_contracts.models.api import ScoringRequest
from worker_support import case_row, job_row, new_case

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]
OPS = "http://127.0.0.1:8081"


class Stub:
    """Token, governance (`serving-config` y `feature-spec`) y scoring (con latencia) en un solo servidor."""

    def __init__(self, scoring_delay: float) -> None:
        self.scoring_delay = scoring_delay
        self.requests: list[ScoringRequest] = []
        self.gov = GovernanceDouble()
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                return

            def _send(self, status: int, body: bytes) -> None:
                try:
                    self.send_response(status)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:  # el cliente ya corto la conexion (timeout de 7 s)
                    return

            def do_POST(self) -> None:  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("content-length", 0)))
                if self.path == "/token":
                    return self._send(200, json.dumps({"access_token": "t", "expires_in": 300}).encode())
                request = ScoringRequest.model_validate_json(raw)
                stub.requests.append(request)
                time.sleep(stub.scoring_delay)
                return self._send(
                    200, recommendation_from_wire(case_id=request.case_id).model_dump_json().encode()
                )

            def do_GET(self) -> None:  # noqa: N802
                if self.path.endswith("/feature-spec"):
                    return self._send(200, json.dumps(stub.gov.spec(self.path.split("/")[-2])).encode())
                return self._send(200, json.dumps(stub.gov.config()).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def start(db: Db, stub: Stub, tmp_path: Path) -> subprocess.Popen[bytes]:
    assert port_free(8081), (
        "el puerto 8081 esta ocupado: la prueba de arranque real lo necesita (puerto fijo de U0)"
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
        "CASE_DB_DSN": url(
            db.pg, db.name, "case_worker", "case_worker"
        ),  # el rol `case_worker`, nunca un superusuario
        "CASE_GOVERNANCE_URL": base,
        "CASE_SCORING_URL": base,
        "VECTRA_CLIENT_ID": "case-worker",
        "VECTRA_TOKEN_URL": f"{base}/token",
        "VECTRA_CLIENT_KEY_PATH": str(key),
    }
    log = (tmp_path / "worker.log").open("wb")
    return subprocess.Popen(
        [sys.executable, "-m", "vectra_case.worker"], env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT
    )


def wait_ready(proc: subprocess.Popen[bytes], timeout: float = 40.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert proc.poll() is None, "el proceso termino antes de quedar listo"
        try:
            return httpx.get(f"{OPS}/readyz", timeout=1.0).status_code
        except httpx.HTTPError:
            time.sleep(0.3)
    raise AssertionError("el worker no respondio /readyz")


def wait_until(predicate: Any, timeout: float, proc: subprocess.Popen[bytes]) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert proc.poll() is None, "el proceso termino antes de tiempo"
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_python_dash_m_worker_starts_for_real_and_readyz_is_200_with_case_db_up(
    db: Db, tmp_path: Path
) -> None:
    stub = Stub(0.0)
    proc = start(db, stub, tmp_path)
    try:
        assert wait_ready(proc) == 200
        assert httpx.get(f"{OPS}/healthz", timeout=2).status_code == 200
        assert port_free(8080)  # el worker no expone 8080
        # `GET /metrics` recien iniciado: las 36 series de `vectra_case_attempts_total` en 0 y ninguna etiqueta fuera de la allowlist (P-U8-06)
        families = {
            f.name: f for f in text_string_to_metric_families(httpx.get(f"{OPS}/metrics", timeout=2).text)
        }
        samples = [
            s for s in families["vectra_case_attempts"].samples if s.name == "vectra_case_attempts_total"
        ]
        assert len(samples) == 36 and {s.value for s in samples} == {0.0}
        assert {(s.labels["result"], s.labels["attempt"]) for s in samples} == {
            (r, a) for r in metrics.ATTEMPT_RESULTS for a in metrics.ATTEMPTS
        }
        used = {
            k
            for f in families.values()
            if f.name.startswith("vectra_case")
            for s in f.samples
            for k in s.labels
        }
        assert used <= metrics.ALLOWED_LABELS | {"le"}, used - metrics.ALLOWED_LABELS
        assert "vectra_case_time_to_ready_seconds" in families
        started = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=15) == 0  # con la cola vacia no hay nada que esperar
        assert time.monotonic() - started <= 10
    finally:
        if proc.poll() is None:
            proc.kill()
        stub.close()


def test_missing_mandatory_variables_make_the_worker_fail_to_start(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CASE_", "VECTRA_"))}
    done = subprocess.run(
        [sys.executable, "-m", "vectra_case.worker"],
        env=env,
        cwd=ROOT,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert done.returncode != 0 and b"KeyError" in done.stderr


def test_sigterm_at_0_5_s_with_a_scoring_that_answers_at_5_s_finishes_the_attempt_and_the_case_is_listo(
    db: Db, tmp_path: Path
) -> None:
    case_id = new_case(db, job_attempt=None)
    stub = Stub(5.0)
    proc = start(db, stub, tmp_path)
    try:
        assert wait_ready(proc) == 200
        from u8_support import seed_job

        seed_job(db, case_id)
        assert wait_until(lambda: len(stub.requests) == 1, 30, proc)  # el intento esta en vuelo
        time.sleep(0.5)
        started = time.monotonic()
        proc.send_signal(signal.SIGTERM)  # a los 0,5 s de la llamada
        assert proc.wait(timeout=20) == 0
        elapsed = time.monotonic() - started
    finally:
        if proc.poll() is None:
            proc.kill()
        stub.close()
    row = case_row(db, case_id)  # se lee de la base despues de que el proceso termina
    assert (row["state"], row["attempts"], row["recommendation_entry_id"]) == ("listo", 1, "7")
    assert 3 <= elapsed <= 10, elapsed  # espero la llamada en vuelo (~4,5 s mas), no 20 s
    assert db.query("SELECT count(*) FROM evaluation_jobs WHERE case_id = %s", case_id) == [(0,)]


def test_sigterm_with_a_scoring_that_answers_at_10_s_ends_the_attempt_at_7_s_as_unreachable_and_exits_before_20_s(
    db: Db, tmp_path: Path
) -> None:
    case_id = new_case(db, job_attempt=None)
    stub = Stub(10.0)
    proc = start(db, stub, tmp_path)
    try:
        assert wait_ready(proc) == 200
        from u8_support import seed_job

        seed_job(db, case_id)
        assert wait_until(lambda: len(stub.requests) == 1, 30, proc)
        time.sleep(0.5)
        started = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=20) == 0
        elapsed = time.monotonic() - started
    finally:
        if proc.poll() is None:
            proc.kill()
        stub.close()
    row, job = case_row(db, case_id), job_row(db, case_id)
    assert (row["state"], row["attempts"], row["last_cause"], row["ever_degraded"]) == (
        "en_sincronizacion",
        1,
        "scoring_unreachable",
        True,
    )
    assert (
        job is not None and job["locked_until"] is None and job["attempt"] == 1
    )  # reprogramado y sin arrendamiento
    assert 5 <= elapsed < 20, (
        elapsed
    )  # el intento termino a los ~7 s de la llamada (timeout de scoring), antes de la gracia de 20 s
