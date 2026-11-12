"""Paso 8 (CA-6): `python -m console_bff.app` arranca de verdad, como proceso, y se apaga con `SIGTERM` (INF-U10-01; NFR-U10-60).

Un proceso lanzado tal cual (no `runpy`: el revisor de U04-T09 marco ese desvio), con solo las variables de entorno obligatorias.
Escucha en 8080 y 8081 (U0 no tiene parametros de puerto): si estan ocupados por otro proceso la prueba **espera** hasta 90 s
a que se liberen y, si no, **falla** con un mensaje claro (la maquina se comparte con otros agentes que corren servicios).
"""

import os
import re
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

OPS_URL, APP_URL = "http://127.0.0.1:8081", "http://127.0.0.1:8080"
ENV = {
    "VECTRA_OIDC_ISSUER": "http://kc.test/auth/realms/vectra",
    "VECTRA_JWKS_URL": "http://127.0.0.1:1/certs",
    "VECTRA_CASE_URL": "http://127.0.0.1:1",  # nadie escucha: los cinco destinos estan caidos
    "VECTRA_GOVERNANCE_URL": "http://127.0.0.1:1",
    "VECTRA_REGISTRY_URL": "http://127.0.0.1:1",
    "VECTRA_EXPLAINABILITY_URL": "http://127.0.0.1:1",
    "VECTRA_BIAS_URL": "http://127.0.0.1:1",
}


def _busy() -> list[int]:
    busy = []
    for port in (8080, 8081):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                busy.append(port)
    return busy


@pytest.fixture(autouse=True)
def ports_are_free() -> None:
    deadline = time.monotonic() + 90
    while _busy() and time.monotonic() < deadline:
        time.sleep(1)
    if _busy():
        pytest.fail(
            f"los puertos {_busy()} de 127.0.0.1 siguen ocupados tras 90 s: libere 8080 y 8081 (el servicio no tiene parametros de puerto)"
        )


@contextmanager
def launched(env: dict[str, str], tmp_path: Path) -> Iterator[subprocess.Popen[bytes]]:
    out, err = (tmp_path / "stdout.log").open("wb"), (tmp_path / "stderr.log").open("wb")
    process = subprocess.Popen(  # noqa: S603 - el interprete de las pruebas, sin entrada externa
        [sys.executable, "-m", "console_bff.app"],
        env={"PATH": os.environ.get("PATH", "/usr/bin"), **env},
        stdout=out,
        stderr=err,
    )
    try:
        yield process
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        out.close()
        err.close()


def wait_for(url: str, expected: int = 200, seconds: float = 30.0) -> httpx.Response | None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == expected:
                return response
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    return None


def test_the_real_process_starts_and_readyz_is_200_with_every_destination_down(tmp_path: Path) -> None:
    with launched(ENV, tmp_path) as process:
        assert wait_for(OPS_URL + "/readyz") is not None, "/readyz no respondio 200 en 30 s"
        assert httpx.get(OPS_URL + "/healthz", timeout=2).status_code == 200
        assert process.poll() is None
        # 8080 escucha y la solicitud sin token es 401 (el middleware de U0, antes de cualquier llamada a un destino)
        unauthenticated = httpx.get(APP_URL + "/api/console/cases", timeout=5)
        assert unauthenticated.status_code == 401 and unauthenticated.json()["code"] == "unauthenticated"
        # un proceso recien iniciado: las seis series del navegador en 0 (P-U10-09)
        text = ""
        for _ in range(50):  # el puerto es fijo: se espera a ver las series de *este* proceso, no las de otro
            text = httpx.get(OPS_URL + "/metrics", timeout=5).text
            if "vectra_console_client_errors_total" in text:
                break
            time.sleep(0.2)
        zeros = re.findall(
            r'^vectra_console_client_errors_total\{error_code="(\w+)"\} 0\.0$', text, flags=re.MULTILINE
        )
        assert len(zeros) == 6, text[:1500]
        # los cinco circuitos publicados y cerrados al arrancar
        assert (
            len(re.findall(r'^vectra_circuit_state\{dependency="\w+"\} 0\.0$', text, flags=re.MULTILINE)) == 5
        )


def test_without_the_case_url_the_process_ends_before_listening(tmp_path: Path) -> None:
    env = {k: v for k, v in ENV.items() if k != "VECTRA_CASE_URL"}
    with launched(env, tmp_path) as process:
        assert process.wait(30) != 0
        assert process.returncode == 2
    assert "VECTRA_CASE_URL" in (tmp_path / "stderr.log").read_text(encoding="utf-8")
    assert _busy() == []  # nunca llego a escuchar


def test_sigterm_ends_the_process_in_10_seconds_or_less(tmp_path: Path) -> None:
    with launched(ENV, tmp_path) as process:
        assert wait_for(OPS_URL + "/healthz") is not None
        began = time.monotonic()
        process.send_signal(signal.SIGTERM)
        process.wait(15)
        elapsed = time.monotonic() - began
    assert elapsed <= 10, elapsed  # GRACEFUL_SHUTDOWN de U0
    # uvicorn vuelve a emitir la senal tras cerrar: sin `_exit_clean` en `main()` el codigo seria -15 (-SIGTERM), no 0
    assert process.returncode == 0, process.returncode
