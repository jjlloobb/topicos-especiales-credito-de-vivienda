"""Paso 9 (CA-2): `python -m vectra_bias.app` arranca de verdad con las variables de `config_from_env` y nada mas (P-U9-05; NFR-U9-12).

Dobles HTTP reales en `127.0.0.1` (Keycloak con JWKS y token, y las rutas de U3), la llave del cliente y la politica en un directorio
temporal. El servicio escucha en 8080 y 8081 (U0 no tiene parametros de puerto): si estan ocupados la prueba **falla** con un mensaje claro.
"""

from __future__ import annotations

import re
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from http_doubles import Keycloak, RegistryU3
from scenario import POLICY
from service_support import write_policy
from strategies import auth as u0_auth
from world import PRIVATE_KEY_PEM, freeze_record

APP_URL, OPS_URL = "http://127.0.0.1:8080", "http://127.0.0.1:8081"
SERVICE = "bias-monitoring-service"


@pytest.fixture(autouse=True)
def ports_are_free() -> None:
    busy = []
    for port in (8080, 8081):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                busy.append(port)
    if busy:
        pytest.fail(
            f"los puertos {busy} de 127.0.0.1 estan ocupados: libere 8080 y 8081 (el servicio no tiene parametros de puerto)"
        )


@pytest.fixture
def world(tmp_path: Path):
    keycloak = Keycloak().start()
    registry = RegistryU3([freeze_record("v1", datetime(2026, 11, 8, 12, tzinfo=UTC))]).start()
    (tmp_path / "client.pem").write_text(PRIVATE_KEY_PEM, encoding="utf-8")
    write_policy(tmp_path / "policy.yaml", POLICY)
    env = {
        "VECTRA_REGISTRY_URL": registry.url,
        "VECTRA_TOKEN_URL": keycloak.url + "/token",
        "VECTRA_CLIENT_ID": SERVICE,
        "VECTRA_CLIENT_KEY_PATH": str(tmp_path / "client.pem"),
        "VECTRA_OIDC_ISSUER": u0_auth.ISSUER,
        "VECTRA_JWKS_URL": keycloak.url + "/jwks",
        "VECTRA_POLICY_PATH": str(tmp_path / "policy.yaml"),
    }
    yield keycloak, registry, env, tmp_path
    keycloak.stop()
    try:
        registry.stop()
    except Exception:  # noqa: BLE001 - ya apagado por la prueba
        pass


@contextmanager
def launched(env: dict[str, str], tmp_path: Path) -> Iterator[subprocess.Popen]:
    """El subproceso real, con `-X importtime` y solo las variables dadas (mas `PATH`)."""
    out, err = (tmp_path / "stdout.log").open("w"), (tmp_path / "stderr.log").open("w")
    process = subprocess.Popen(  # noqa: S603 - el interprete de las pruebas, sin entrada externa
        [sys.executable, "-X", "importtime", "-m", "vectra_bias.app"],
        env={"PATH": "/usr/bin", **env},
        stdout=out,
        stderr=err,
    )
    try:
        yield process
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
        out.close()
        err.close()


def wait_for(url: str, expected: int = 200, seconds: float = 10.0) -> httpx.Response | None:
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


def cumplimiento() -> dict[str, str]:
    return u0_auth.bearer(aud=SERVICE, roles=["cumplimiento"])


def test_the_real_process_serves_with_the_real_variables_and_never_imports_the_freeze_client(world):
    keycloak, registry, env, tmp_path = world
    with launched(env, tmp_path) as process:
        assert wait_for(OPS_URL + "/healthz") is not None, "/healthz no respondio 200 en 10 s"
        assert wait_for(OPS_URL + "/readyz") is not None
        response = httpx.get(APP_URL + "/v1/freezes", headers=cumplimiento(), timeout=5)
        assert response.status_code == 200
        assert [s["freeze_id"] for s in response.json()] == ["freeze-v1"]  # la lista del doble de U3
        assert (
            "bias-monitoring-service",
            "decision-registry-service",
            "registry:read:monitoring",
        ) in registry.tokens
        assert {r["client_id"] for r in keycloak.requests} == {SERVICE}
        assert process.poll() is None
    imported = (tmp_path / "stderr.log").read_text(encoding="utf-8")
    modules = re.findall(r"\|\s+(vectra_bias(?:\.\w+)*)\s*$", imported, flags=re.MULTILINE)
    assert {"vectra_bias.dashboard", "vectra_bias.freezes", "vectra_bias.compare"} <= set(
        modules
    )  # el importtime si se midio (`app` corre como `__main__`)
    assert "vectra_bias.freeze_client" not in modules and "vectra_bias.run" not in modules


def test_with_the_registry_off_the_pod_stays_ready_and_the_query_is_a_503(world):
    _, registry, env, tmp_path = world
    registry.stop()
    with launched(env, tmp_path):
        assert wait_for(OPS_URL + "/healthz") is not None
        assert wait_for(OPS_URL + "/readyz") is not None  # NFR-U9-12: readiness solo del proceso
        response = httpx.get(APP_URL + "/v1/freezes", headers=cumplimiento(), timeout=10)
        assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
        assert httpx.get(OPS_URL + "/readyz", timeout=2).status_code == 200


def test_sigterm_ends_the_process_in_10_seconds_or_less(world):
    _, _, env, tmp_path = world
    with launched(env, tmp_path) as process:
        assert wait_for(OPS_URL + "/healthz") is not None
        began = time.monotonic()
        process.send_signal(signal.SIGTERM)
        process.wait(10)
        assert time.monotonic() - began <= 10
        assert process.returncode is not None


def test_a_missing_variable_stops_the_start_and_the_message_names_it(world):
    _, _, env, tmp_path = world
    del env["VECTRA_REGISTRY_URL"]
    with launched(env, tmp_path) as process:
        assert process.wait(15) != 0
    assert "VECTRA_REGISTRY_URL" in (tmp_path / "stderr.log").read_text(encoding="utf-8")


def test_an_out_of_range_policy_stops_the_start(world):
    _, _, env, tmp_path = world
    (tmp_path / "policy.yaml").write_text(
        'threshold_pp: 5\nn_min: 30\nwindow_days: 5\nschedule: "2,17,32,47 * * * *"\nstale_after: 1h\n',
        encoding="utf-8",
    )
    with launched(env, tmp_path) as process:
        assert process.wait(15) != 0
    message = (tmp_path / "stderr.log").read_text(encoding="utf-8")
    assert "VECTRA_POLICY_PATH" in message and "window_days_out_of_range" in message
