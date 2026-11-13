"""El proceso **real** publica y se apaga con codigo 0 (CA-3; INF-U11-01; NFR-U11-21).

`vectra_product.main.main` corre como subproceso con las variables `VECTRA_*`, un puerto libre pasado como argumento, el doble de U3
y un emisor de token de prueba servidos por HTTP (puertos libres). La prueba lee de vuelta `/readyz`, `/metrics` y las rutas por HTTP
y guarda en `tmp_path` lo que **leyo del proceso**: `readyz.txt`, `metrics.txt`, `paths.txt` y `exit-code.txt`.

NFR-U11-21: no hay rutas de negocio en 8081. Si la maquina esta cargada, el arranque del interprete puede tardar varios segundos; el
umbral de 10 s de apagado no se sube (se repite la corrida en serie y se anota el `uptime`).
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from entries import render, specs_on, us503_specs
from http_servers import ASSERTION_AUDIENCE, Server, registry_app, token_app
from registry_double import RegistryDouble
from vectra_product.main import main

SHUTDOWN_SECONDS = 10.0
POLICY = """noise_floor: 0.6
noise_sustain_days: 3
noise_min_decisions: 50
target_complete_response: 1.0
target_origination_hours: 1
target_origination_ratio: 0.8
target_sustained_ratio_month6: 0.7
target_north_star: null
"""
CODE = "import sys\nfrom vectra_product.main import main\nsys.exit(main(port=int(sys.argv[1])))\n"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class RealProcess:
    def __init__(self, tmp_path: Path, double: RegistryDouble) -> None:
        self.double = double
        self.assertion_audiences: list[str] = []
        self.servers = [
            Server(registry_app(double)).start(),
            Server(token_app(self.assertion_audiences)).start(),
        ]
        key = tmp_path / "client.pem"
        key.write_bytes(
            ec.generate_private_key(ec.SECP256R1()).private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        policy = tmp_path / "values-product-metrics-policy.yaml"
        policy.write_text(POLICY, encoding="utf-8")
        self.port = free_port()
        self.log_path = tmp_path / "process.log"
        self._log = self.log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", CODE, str(self.port)],
            stdout=self._log,
            stderr=subprocess.STDOUT,
            env={
                **os.environ,
                "VECTRA_REGISTRY_URL": self.servers[0].url,
                "VECTRA_CLIENT_ID": "product-metrics",
                "VECTRA_TOKEN_URL": self.servers[1].url + "/token",
                "VECTRA_ASSERTION_AUDIENCE": ASSERTION_AUDIENCE,
                "VECTRA_CLIENT_KEY_PATH": str(key),
                "VECTRA_POLICY_PATH": str(policy),
            },
        )

    def get(self, path: str) -> httpx.Response | None:
        try:
            return httpx.get(f"http://127.0.0.1:{self.port}{path}", timeout=5)
        except httpx.TransportError:
            return None

    def wait_for(self, path: str, status: int | None = None, seconds: float = 60.0) -> httpx.Response:
        """El primer `GET` que responde (con ese `status`, si se pide)."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            assert self.process.poll() is None, f"el proceso termino al arrancar: {self.process.returncode}"
            answer = self.get(path)
            if answer is not None and (status is None or answer.status_code == status):
                return answer
            time.sleep(0.05)
        raise AssertionError(f"{path} no respondio {status} en {seconds} s")

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        self._log.close()
        for server in self.servers:
            server.stop()


def stamp_now() -> datetime:
    return datetime.now(UTC)


def test_the_real_process_serves_ops_routes_publishes_after_the_first_pass_and_exits_0_on_sigterm(
    tmp_path: Path,
) -> None:
    now = stamp_now()
    double = RegistryDouble([render(s) for s in us503_specs(now=now)])
    double.latency = 2.0  # la primera pasada tarda: `/readyz` da 503 hasta que termina
    process = RealProcess(tmp_path, double)
    try:
        first = process.wait_for("/readyz")
        readyz = [first.status_code]
        assert (
            first.status_code == 503 and "not_ready" in first.text
        )  # sin instantanea y con el breaker cerrado
        ready = process.wait_for("/readyz", 200)
        readyz.append(ready.status_code)
        (tmp_path / "readyz.txt").write_text("\n".join(str(code) for code in readyz) + "\n", encoding="utf-8")

        metrics = process.wait_for("/metrics", 200)
        (tmp_path / "metrics.txt").write_text(metrics.text, encoding="utf-8")
        paths = []
        for path in ("/metrics", "/healthz", "/readyz", "/v1/entries"):
            answer = process.get(path)
            assert answer is not None
            paths.append(f"{path} {answer.status_code}")
        (tmp_path / "paths.txt").write_text("\n".join(paths) + "\n", encoding="utf-8")

        sent = time.monotonic()
        process.process.send_signal(signal.SIGTERM)
        code = process.process.wait(timeout=SHUTDOWN_SECONDS)
        elapsed = time.monotonic() - sent
        (tmp_path / "exit-code-idle.txt").write_text(f"{code}\n", encoding="utf-8")
        assert code == 0 and elapsed <= SHUTDOWN_SECONDS
    finally:
        process.stop()

    text = (tmp_path / "metrics.txt").read_text(encoding="utf-8")
    assert any(
        line.startswith("vectra_product_north_star_ratio{")
        and 'period="day"' in line
        and 'channel="all"' in line
        and 'outcome="all"' in line
        and 'model_version_id="all"' in line
        and line.endswith(" 0.4")
        for line in text.splitlines()
    )
    assert "vectra_product_metrics_last_success_timestamp " in text
    assert "vectra_product_last_full_recompute_timestamp " in text
    assert (tmp_path / "readyz.txt").read_text(encoding="utf-8") == "503\n200\n"
    assert (tmp_path / "paths.txt").read_text(encoding="utf-8").splitlines() == [
        "/metrics 200",
        "/healthz 200",
        "/readyz 200",
        "/v1/entries 404",
    ]
    assert double.max_active == 1  # nunca dos lecturas a la vez


def test_sigterm_while_a_pass_reads_a_slow_page_finishes_the_page_and_exits_0_within_10_seconds(
    tmp_path: Path,
) -> None:
    now = stamp_now()
    double = RegistryDouble([render(s) for s in specs_on(1, 6, 1, now=now)])
    double.max_page = 2  # tres paginas por pasada
    double.latency = 3.0
    process = RealProcess(tmp_path, double)
    try:
        deadline = time.monotonic() + 60
        while double.calls < 1:  # la primera pagina esta en vuelo (lenta)
            assert process.process.poll() is None and time.monotonic() < deadline
            time.sleep(0.02)
        assert double.completed == []
        sent = time.monotonic()
        process.process.send_signal(signal.SIGTERM)
        code = process.process.wait(timeout=SHUTDOWN_SECONDS)
        elapsed = time.monotonic() - sent
        # C-2 (F-01 de U11-T02): lo que el doble completo **en el instante en que el proceso sale**, antes de parar los servidores. `process.stop()` apaga el doble
        # con gracia y deja terminar su manejador: leerlo despues haria pasar a un planificador que cancela la pagina (el manejador del doble sigue solo).
        completed_at_exit = list(double.completed)
    finally:
        process.stop()
    (tmp_path / "exit-code.txt").write_text(f"{code}\n", encoding="utf-8")
    assert code == 0  # y no -15: uvicorn no vuelve a emitir la señal
    assert elapsed <= SHUTDOWN_SECONDS
    assert completed_at_exit == [1], (
        "el proceso salio con la pagina en vuelo sin terminar: se cancelo en lugar de terminar"
    )
    assert double.completed == [1]  # la pagina en vuelo termino: el doble la vio completa
    assert double.calls == 1  # y no se pidio ninguna mas
    assert (tmp_path / "exit-code.txt").read_text(encoding="utf-8") == "0\n"


def test_invalid_policy_exits_nonzero_without_serving_anything(tmp_path: Path) -> None:
    port = free_port()
    (tmp_path / "bad.yaml").write_text("noise_floor: 7\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", CODE, str(port)],
        env={
            **os.environ,
            "VECTRA_REGISTRY_URL": "http://registry.invalid",
            "VECTRA_POLICY_PATH": str(tmp_path / "bad.yaml"),
        },
        timeout=60,
        check=False,
    )
    assert result.returncode == 2
    with socket.socket() as sock:  # nunca sirvio nada: el puerto sigue libre
        sock.bind(("127.0.0.1", port))


@pytest.mark.parametrize("module", ["vectra_product.main"])
def test_python_dash_m_exposes_main_as_the_entry_point(module: str) -> None:
    """`python -m vectra_product.main` es el comando de arranque de la imagen (U11-T03): sin `VECTRA_REGISTRY_URL` sale con 3."""
    env = {k: v for k, v in os.environ.items() if k != "VECTRA_REGISTRY_URL"}
    result = subprocess.run([sys.executable, "-m", module], env=env, timeout=60, check=False)  # noqa: S603
    assert result.returncode == 3


def test_main_in_the_test_process_wires_the_environment_serves_and_returns_0_on_sigterm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El mismo `main()` que el subproceso, pero en este proceso: para que la cobertura lo vea (CANDIDATAS.md, linea 478).

    Un hilo espera a que `/readyz` responda 200 y le manda `SIGTERM` al proceso de la prueba; `main()` debe volver con 0."""
    now = stamp_now()
    double = RegistryDouble([render(s) for s in us503_specs(now=now)])
    servers = [Server(registry_app(double)).start(), Server(token_app()).start()]
    key = tmp_path / "client.pem"
    key.write_bytes(
        ec.generate_private_key(ec.SECP256R1()).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    policy = tmp_path / "policy.yaml"
    policy.write_text(POLICY, encoding="utf-8")
    port = free_port()
    for name, value in {
        "VECTRA_REGISTRY_URL": servers[0].url,
        "VECTRA_CLIENT_ID": "product-metrics",
        "VECTRA_TOKEN_URL": servers[1].url + "/token",
        "VECTRA_ASSERTION_AUDIENCE": ASSERTION_AUDIENCE,
        "VECTRA_CLIENT_KEY_PATH": str(key),
        "VECTRA_POLICY_PATH": str(policy),
    }.items():
        monkeypatch.setenv(name, value)
    outcome: list[str] = []

    def terminate_when_ready() -> None:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"http://127.0.0.1:{port}/readyz", timeout=2).status_code == 200:
                    outcome.append("ready")
                    break
            except httpx.TransportError:
                time.sleep(0.05)
        os.kill(os.getpid(), signal.SIGTERM)

    watcher = threading.Thread(target=terminate_when_ready, daemon=True)
    watcher.start()
    try:
        assert main(port) == 0
    finally:
        watcher.join(timeout=10)
        for server in servers:
            server.stop()
    assert outcome == ["ready"]


def test_no_log_line_of_the_real_process_keeps_only_level_timestamp_and_service(tmp_path: Path) -> None:
    """C-6 (F-06 de U11-T02): `uvicorn` y `httpx` loggean por `logging` estandar y el filtro de U0 dejaba de ellos solo `level`, `timestamp` y `service`.
    `main` los sube a WARNING; el proceso real, con una pasada, una lectura y un apagado, no deja ninguna linea sin contenido."""
    import json

    now = stamp_now()
    double = RegistryDouble([render(s) for s in us503_specs(now=now)])
    process = RealProcess(tmp_path, double)
    try:
        process.wait_for("/readyz", 200)
        process.process.send_signal(signal.SIGTERM)
        assert process.process.wait(timeout=SHUTDOWN_SECONDS) == 0
    finally:
        process.stop()
    lines = [
        json.loads(line) for line in process.log_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    bare = [line for line in lines if set(line) <= {"level", "timestamp", "service"}]
    assert bare == [], f"lineas de log sin contenido: {bare[:3]}"


def test_assertion_audience_the_real_process_signs_with_the_issuer_and_not_with_the_token_url(tmp_path: Path) -> None:
    double = RegistryDouble([render(s) for s in us503_specs(now=stamp_now())])
    process = RealProcess(tmp_path, double)
    try:
        process.wait_for("/readyz", 200)  # leer U3 exige el token: con otra `aud` el doble responde 400 y nunca queda listo
        assert process.assertion_audiences
        assert set(process.assertion_audiences) == {ASSERTION_AUDIENCE} != {process.servers[1].url + "/token"}
    finally:
        process.stop()
