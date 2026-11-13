"""Pasos 11 y 12 (CA-4): el contenedor real arranca con las variables **que pone el chart** (leccion de U04-T06 y U04-T08).

Las variables y la politica salen del render de kind (`helm template` con los values de Argo CD). Solo cambian las URLs por las de dobles HTTP
locales (registro, governance y Pushgateway de `world`, detras de `http_bridge`; Keycloak con `/token` y JWKS de `http_doubles`), el `issuer`
(el de los tokens de prueba) y la llave por una de prueba en el mismo path. La imagen es la de `make -C bias-monitoring image`, con la raiz
de solo lectura, el usuario `65532` y `--network host` (los dobles escuchan en `127.0.0.1` y el servicio en 8080 y 8081, como en
`test_entrypoint.py`). **Sin Docker la prueba falla; no se salta.** Se corre con `make -C bias-monitoring image` hecho antes (el objetivo `check` lo hace).
"""

from __future__ import annotations

import json
import re
import shlex
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from chart_render import Doc, render
from http_bridge import Bridge
from http_doubles import Keycloak
from scenario import seed
from strategies import auth as u0_auth
from world import PRIVATE_KEY_PEM, World, freeze_record

IMAGE = "localhost:5001/vectra/bias-monitoring:dev"
APP_URL, OPS_URL = "http://127.0.0.1:8080", "http://127.0.0.1:8081"
KEY_NAME = "private-key"


def docker(*args: str, timeout: float = 120, check: bool = False) -> subprocess.CompletedProcess[str]:
    if args[0] in {
        "run",
        "stop",
    }:  # con `pytest -s` queda el `docker run` exacto en la salida (bitacora de U09-T04)
        print("$ docker", shlex.join(args))
    try:
        return subprocess.run(  # noqa: S603, S607 - docker local, sin entrada externa
            ["docker", *args], capture_output=True, text=True, timeout=timeout, check=check
        )
    except FileNotFoundError:
        pytest.fail("Docker no esta disponible: la prueba de la imagen falla, no se salta (CA-4)")


@pytest.fixture(scope="module", autouse=True)
def image_and_docker() -> None:
    probe = docker("image", "inspect", IMAGE, "--format", "{{.Id}}")
    assert probe.returncode == 0, (
        f"falta la imagen {IMAGE}: corre `make -C bias-monitoring image`\n{probe.stderr}"
    )


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


class Doubles:
    """Los cuatro dobles de la corrida, en sockets reales."""

    def __init__(self) -> None:
        self.world = World()
        self.keycloak = Keycloak().start()
        self.registry = Bridge(self.world.registry.handle).start()
        self.governance = Bridge(self.world.governance.handle).start()
        self.pushgateway = Bridge(self.world.pushgateway.handle).start()

    def stop(self) -> None:
        for double in (self.keycloak, self.registry, self.governance, self.pushgateway):
            double.stop()


@pytest.fixture
def doubles() -> Iterator[Doubles]:
    d = Doubles()
    yield d
    d.stop()


def pod_of(docs: list[Doc], kind: str) -> Doc:
    workload = next(d for d in docs if d["kind"] == kind)
    template = (
        workload["spec"]["template"]
        if kind == "Deployment"
        else workload["spec"]["jobTemplate"]["spec"]["template"]
    )
    return template["spec"]  # type: ignore[no-any-return]


def mounts_of(pod: Doc) -> dict[str, str]:
    """El `mountPath` de cada volumen del contenedor: lo que el chart monta y donde."""
    return {m["name"]: m["mountPath"] for m in pod["containers"][0]["volumeMounts"]}


def real_env(pod: Doc, doubles: Doubles, process: str) -> dict[str, str]:
    """Las variables del render, con las URLs de los dobles. Nada mas cambia, salvo el `issuer` de los tokens de prueba."""
    env = {e["name"]: e["value"] for e in pod["containers"][0]["env"]}
    urls = {
        "VECTRA_REGISTRY_URL": doubles.registry.url,
        "VECTRA_TOKEN_URL": doubles.keycloak.url + "/token",
        "VECTRA_JWKS_URL": doubles.keycloak.url + "/jwks",
        "VECTRA_GOVERNANCE_URL": doubles.governance.url,
        "VECTRA_PUSHGATEWAY_URL": doubles.pushgateway.url,
    }
    for name, url in urls.items():
        if name in env:
            env[name] = url
    if "VECTRA_OIDC_ISSUER" in env:
        env["VECTRA_OIDC_ISSUER"] = u0_auth.ISSUER
    return env


def run_args(
    docs: list[Doc], doubles: Doubles, process: str, tmp_path: Path, drop: tuple[str, ...] = ()
) -> tuple[list[str], dict[str, str]]:
    """Los argumentos de `docker run` de un proceso: variables, montajes de solo lectura (llave de prueba y politica del render) y el `command` del chart."""
    kind = "Deployment" if process == "service" else "CronJob"
    pod = pod_of(docs, kind)
    env = {k: v for k, v in real_env(pod, doubles, process).items() if k not in drop}
    mounts = mounts_of(pod)
    key_dir = next(
        v for name, v in mounts.items() if name in ("service-identity", "job-identity")
    )  # `/var/run/vectra/client`: el mismo path que pone el chart
    policy_dir = mounts["monitoring-policy"]
    key = tmp_path / f"{process}.pem"
    key.write_text(PRIVATE_KEY_PEM, encoding="utf-8")
    key.chmod(0o444)  # el Secret del chart se monta 0444: el contenedor corre como 65532
    policy = tmp_path / f"{process}-policy.yaml"
    policy.write_text(
        next(d for d in docs if d["kind"] == "ConfigMap")["data"]["values-monitoring-policy.yaml"],
        encoding="utf-8",
    )
    policy.chmod(0o444)
    args = [
        "--network",
        "host",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "65532:65532",
    ]
    args += [
        "-v",
        f"{key}:{key_dir}/{KEY_NAME}:ro",
        "-v",
        f"{policy}:{policy_dir}/values-monitoring-policy.yaml:ro",
    ]
    for name, value in env.items():
        args += ["-e", f"{name}={value}"]
    command = pod["containers"][0]["command"]
    return [*args, IMAGE, *command], env


def key_path(env: dict[str, str]) -> str:
    return env["VECTRA_CLIENT_KEY_PATH"]


@contextmanager
def service_container(args: list[str]) -> Iterator[str]:
    name = f"bias-image-test-{uuid.uuid4().hex[:8]}"
    started = docker("run", "-d", "--name", name, *args)
    assert started.returncode == 0, started.stderr
    try:
        yield name
    finally:
        docker("rm", "-f", name)


def wait_for(url: str, seconds: float = 20.0) -> httpx.Response | None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == 200:
                return response
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    return None


def test_the_service_starts_from_the_chart_variables_and_answers_the_contract(
    doubles: Doubles, tmp_path: Path
) -> None:
    docs = render("kind")
    args, env = run_args(docs, doubles, "service", tmp_path)
    assert key_path(env) == "/var/run/vectra/client/private-key"
    doubles.world.registry.freezes = [freeze_record("v1", datetime(2026, 11, 8, 12, tzinfo=UTC))]
    with service_container(args) as name:
        logs = lambda: docker("logs", name)  # noqa: E731
        assert wait_for(OPS_URL + "/readyz") is not None, (
            f"/readyz no respondio 200 en 20 s\n{logs().stdout}{logs().stderr}"
        )
        assert wait_for(OPS_URL + "/healthz") is not None
        response = httpx.get(
            APP_URL + "/v1/freezes",
            headers=u0_auth.bearer(aud="bias-monitoring-service", roles=["cumplimiento"]),
            timeout=10,
        )
        assert response.status_code == 200, response.text
        assert [s["freeze_id"] for s in response.json()] == [
            "freeze-v1"
        ]  # la lista del doble de U3, con el token del cliente del chart
        assert {r["client_id"] for r in doubles.keycloak.requests} == {"bias-monitoring-service"}
        assert (
            httpx.get(APP_URL + "/v1/freezes", timeout=5).status_code == 401
        )  # sin token: el contrato de U0
        stopped = docker("stop", "-t", "15", name, timeout=40)
        assert stopped.returncode == 0
        exit_code = docker("inspect", name, "--format", "{{.State.ExitCode}}").stdout.strip()
        assert exit_code in {"0", "143"}, f"SIGTERM: salio con {exit_code}"


def test_the_cronjob_runs_to_completion_freezes_and_pushes_its_metrics(
    doubles: Doubles, tmp_path: Path
) -> None:
    docs = render("kind")
    args, env = run_args(docs, doubles, "job", tmp_path)
    assert set(env) == {
        "VECTRA_REGISTRY_URL",
        "VECTRA_GOVERNANCE_URL",
        "VECTRA_PUSHGATEWAY_URL",
        "VECTRA_POLICY_PATH",
        "VECTRA_TOKEN_URL",
        "VECTRA_ASSERTION_AUDIENCE",
        "VECTRA_CLIENT_ID",
        "VECTRA_CLIENT_KEY_PATH",
        "VECTRA_CA_BUNDLE",
    }
    seed(doubles.world, "v1", datetime.now(UTC).date(), days=5, model="high")
    result = docker("run", "--rm", *args, timeout=180)
    assert result.returncode == 0, (
        f"la corrida no termino bien: {result.returncode}\n{result.stdout}\n{result.stderr}"
    )
    # La corrida completa: congelo la version con la regla cumplida y empujo sus metricas al Pushgateway.
    assert doubles.world.governance.frozen == {"v1"}
    assert {"run", "success"} <= doubles.world.pushgateway.names()
    assert doubles.world.pushgateway.value("success", "vectra_bias_last_success_timestamp") is not None
    assert {r["client_id"] for r in doubles.keycloak.requests} == {"bias-monitoring-job"}
    assert any(
        method == "PUT" and path.startswith("/metrics/job/bias-monitoring/")
        for method, path in doubles.pushgateway.requests
    )
    last = json.loads(result.stdout.strip().splitlines()[-1])
    assert last["status"] == "completa"


def test_without_the_registry_url_the_service_does_not_start_and_the_log_names_the_variable_never_its_value(
    doubles: Doubles, tmp_path: Path
) -> None:
    docs = render("kind")
    args, _ = run_args(docs, doubles, "service", tmp_path, drop=("VECTRA_REGISTRY_URL",))
    result = docker("run", "--rm", *args, timeout=60)
    assert result.returncode == 2, f"{result.returncode}\n{result.stdout}\n{result.stderr}"
    assert "VECTRA_REGISTRY_URL" in result.stderr
    assert doubles.registry.url not in result.stdout + result.stderr  # nunca el valor
    assert not re.search(r"https?://", result.stderr)


def test_without_the_key_file_the_service_does_not_start_and_names_the_variable(
    doubles: Doubles, tmp_path: Path
) -> None:
    """Un chart que no monta la llave (el defecto de U04-T08) deja al pod sin arrancar con un mensaje que lo dice."""
    docs = render("kind")
    args, _ = run_args(docs, doubles, "service", tmp_path)
    flags = [a for a in args if a.endswith(f"/{KEY_NAME}:ro")]
    for flag in flags:
        index = args.index(flag)
        del args[index - 1 : index + 1]
    result = docker("run", "--rm", *args, timeout=60)
    assert result.returncode != 0
    assert "VECTRA_CLIENT_KEY_PATH" in result.stderr
