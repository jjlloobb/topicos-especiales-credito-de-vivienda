"""Pasos 10 y 11 (CA-4): el contenedor real arranca con las variables **que pone el chart** y el archivo de parametros **que monta el chart** (U04-T06, F-01).

Un chart que renderiza bien no prueba que el contenedor arranque. Las variables y el `data` del `ConfigMap` de parametros salen del render de kind (`helm template`
con los values de Argo CD). Solo cambian las URLs por las de dobles HTTP locales del registro y del emisor de token (`http_servers`, U11-T02; escuchan en
`0.0.0.0` y el contenedor llega por `host.docker.internal`) y la llave por una de prueba en la misma ruta. La imagen es la de `make -C product-metrics image` y corre con
`docker run --read-only --user 65532:65532`. El 8081 del contenedor se publica en un puerto libre del host (nunca en el 8081). **Sin Docker la prueba falla; no se salta.**
Se corre con `make -C product-metrics image` hecho antes (el objetivo `check` lo hace).
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from chart_render import Doc, render
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from entries import render as render_entry
from entries import us503_specs
from http_servers import ASSERTION_AUDIENCE, Server, registry_app, token_app
from registry_double import RegistryDouble
from vectra_product import collector, config, params

IMAGE = "localhost:5001/vectra/product-metrics:dev"
SHUTDOWN_SECONDS = 10.0
POLICY_KEY = params.POLICY_PATH.name
HOST_ALIAS = "host.docker.internal"


def docker(*args: str, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    if args[0] in {
        "run",
        "stop",
    }:  # con `pytest -s` queda el `docker run` exacto en la salida (bitacora de U11-T03)
        print("$ docker", shlex.join(args))
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603, S607 - docker local
    except FileNotFoundError:
        pytest.fail("Docker no esta disponible: la prueba de la imagen falla, no se salta (CA-4)")


@pytest.fixture(scope="module", autouse=True)
def image_is_built() -> None:
    probe = docker("image", "inspect", IMAGE, "--format", "{{.Id}}")
    assert probe.returncode == 0, (
        f"falta la imagen {IMAGE}: corre `make -C product-metrics image`\n{probe.stderr}"
    )


@dataclass
class Doubles:
    double: RegistryDouble
    servers: list[Server]

    @property
    def registry_url(self) -> str:
        return self.servers[0].url.replace("127.0.0.1", HOST_ALIAS)

    @property
    def token_url(self) -> str:
        return self.servers[1].url.replace("127.0.0.1", HOST_ALIAS) + "/token"


@contextmanager
def doubles(latency: float = 0.0) -> Iterator[Doubles]:
    double = RegistryDouble([render_entry(s) for s in us503_specs(now=datetime.now(UTC))])
    double.latency = latency
    servers = [
        Server(registry_app(double), host="0.0.0.0").start(),
        Server(token_app(), host="0.0.0.0").start(),
    ]  # noqa: S104 - el contenedor llega por la interfaz del puente
    try:
        yield Doubles(double, servers)
    finally:
        for server in servers:
            server.stop()


def kind_pod() -> Doc:
    deployment = next(d for d in render("kind") if d["kind"] == "Deployment")
    return deployment["spec"]["template"]["spec"]  # type: ignore[no-any-return]


def kind_policy_text() -> str:
    return next(
        d
        for d in render("kind")
        if d["kind"] == "ConfigMap" and d["metadata"]["name"] == "product-metrics-policy"
    )["data"][POLICY_KEY]  # type: ignore[no-any-return]


def mounts_of(pod: Doc) -> dict[str, str]:
    return {m["name"]: m["mountPath"] for m in pod["containers"][0]["volumeMounts"]}


def chart_env(pod: Doc, d: Doubles, drop: tuple[str, ...] = ()) -> dict[str, str]:
    """Las variables del render de kind, con las URLs de los dobles. Nada mas cambia."""
    env = {e["name"]: e["value"] for e in pod["containers"][0]["env"]}
    urls = {"VECTRA_REGISTRY_URL": d.registry_url, "VECTRA_TOKEN_URL": d.token_url}
    for name, url in urls.items():
        if (
            name in env
        ):  # solo se cambia la URL de una variable que el chart pone: una que el chart no pone no aparece aqui
            env[name] = url
    if (
        "VECTRA_ASSERTION_AUDIENCE" in env
    ):  # el render local trae el emisor de produccion; el doble de Keycloak acepta el de prueba
        env["VECTRA_ASSERTION_AUDIENCE"] = ASSERTION_AUDIENCE
    return {k: v for k, v in env.items() if k not in drop}


class Container:
    """Un contenedor `docker run -d --read-only --user 65532:65532`, con las variables y los montajes del chart. `stop` lo borra siempre."""

    def __init__(
        self, tmp_path: Path, d: Doubles, *, policy_text: str | None = None, drop: tuple[str, ...] = ()
    ) -> None:
        pod = kind_pod()
        mounts = mounts_of(pod)
        env = chart_env(pod, d, drop)
        key = tmp_path / "private-key"
        key.write_bytes(
            ec.generate_private_key(ec.SECP256R1()).private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )
        key.chmod(0o444)  # el contenedor corre como 65532 y el volumen del Secret es 0444 (defaultMode 292)
        policy_dir = tmp_path / "policy"
        policy_dir.mkdir()
        (policy_dir / POLICY_KEY).write_text(
            policy_text if policy_text is not None else kind_policy_text(), encoding="utf-8"
        )
        policy_dir.chmod(0o755)
        (policy_dir / POLICY_KEY).chmod(0o444)
        key_dir = tmp_path / "client"
        key_dir.mkdir()
        key.rename(key_dir / "private-key")
        key_dir.chmod(0o755)
        self.name = f"u11-t03-{uuid.uuid4().hex[:8]}"
        args = [
            "run", "-d", "--name", self.name, "--read-only", "--user", "65532:65532",
            "--add-host", f"{HOST_ALIAS}:host-gateway", "-p", "127.0.0.1::8081",
            "-v", f"{key_dir}:{mounts['client-identity']}:ro",
            "-v", f"{policy_dir}:{mounts['product-metrics-policy']}:ro",
        ]  # fmt: skip
        for name, value in env.items():
            args += ["-e", f"{name}={value}"]
        started = docker(*args, IMAGE)
        assert started.returncode == 0, started.stderr
        self.port: int | None = None

    def host_port(self) -> int:
        if self.port is None:
            answer = docker("port", self.name, "8081/tcp").stdout.strip().splitlines()[0]
            self.port = int(answer.rsplit(":", 1)[1])
        return self.port

    def get(self, path: str) -> httpx.Response | None:
        try:
            return httpx.get(f"http://127.0.0.1:{self.host_port()}{path}", timeout=5)
        except (httpx.TransportError, IndexError):
            return None

    def state(self) -> dict[str, Any]:
        return json.loads(docker("inspect", self.name).stdout)[0]["State"]  # type: ignore[no-any-return]

    def wait_for(self, path: str, status: int | None = None, seconds: float = 90.0) -> httpx.Response:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            assert self.state()["Running"], (
                f"el contenedor termino al arrancar: {self.state()}\n{self.logs()}"
            )
            answer = self.get(path)
            if answer is not None and (status is None or answer.status_code == status):
                return answer
            time.sleep(0.1)
        raise AssertionError(f"{path} no respondio {status} en {seconds} s\n{self.logs()}")

    def wait_for_exit(self, seconds: float = 60.0) -> int:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            state = self.state()
            if not state["Running"]:
                return int(state["ExitCode"])
            time.sleep(0.1)
        raise AssertionError(f"el contenedor no salio en {seconds} s\n{self.logs()}")

    def logs(self) -> str:
        out = docker("logs", self.name)
        return out.stdout + out.stderr

    def stop(self) -> None:
        docker("rm", "-f", self.name)


@contextmanager
def container(tmp_path: Path, d: Doubles, **kwargs: Any) -> Iterator[Container]:
    c = Container(tmp_path, d, **kwargs)
    try:
        yield c
    finally:
        c.stop()


def log_lines(text: str) -> list[dict[str, Any]]:
    lines = [line for line in text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def allowed_family(name: str) -> bool:
    """Una serie publicada es de la allowlist: la clave tal cual o, de un contador o un histograma, su familia (`_total`, `_created`, `_bucket`, `_sum`, `_count`)."""
    base = re.sub(r"_(total|bucket|sum|count|created)$", "", name)
    allowed = {*collector.PRODUCT_SERIES, *collector.OPERATION_SERIES}
    return bool({name, base, f"{base}_total"} & allowed)


# --- el chart y la imagen dicen lo mismo ---------------------------------------------------------------------------------------------------


def test_the_image_and_the_chart_agree_on_user_command_and_port() -> None:
    inspected = json.loads(docker("image", "inspect", IMAGE).stdout)[0]["Config"]
    pod = kind_pod()
    c = pod["containers"][0]
    assert (
        inspected["User"]
        == f"{pod['securityContext']['runAsUser']}:{pod['securityContext']['runAsGroup']}"
        == "65532:65532"
    )
    assert inspected["Cmd"] == c["command"] == ["python", "-m", "vectra_product.main"]
    assert set(inspected["ExposedPorts"]) == {"8081/tcp"} == {f"{p['containerPort']}/tcp" for p in c["ports"]}


# --- el contenedor real -------------------------------------------------------------------------------------------------------------------


def test_the_real_container_starts_with_the_chart_env_serves_readyz_503_then_200_and_stops_with_exit_0_within_10_seconds(
    tmp_path: Path,
) -> None:
    with doubles(latency=2.0) as d, container(tmp_path, d) as c:
        first = c.wait_for("/healthz", 200)  # `/healthz` responde enseguida: el proceso esta vivo
        assert first.status_code == 200
        readyz = c.wait_for("/readyz")
        assert readyz.status_code == 503, (
            "sin instantanea y con el breaker cerrado, la primera pasada aun no termino"
        )
        assert c.wait_for("/readyz", 200).status_code == 200
        text = c.wait_for("/metrics", 200).text
        assert any(line.startswith("vectra_product_north_star_decisions{") for line in text.splitlines())
        names = {m for m in re.findall(r"^(vectra_product_[a-z0-9_]+)", text, flags=re.MULTILINE)}
        assert names and all(allowed_family(n) for n in names), (
            f"series fuera de la allowlist: {sorted(n for n in names if not allowed_family(n))}"
        )
        assert "vectra_product_metrics_last_success_timestamp " in text
        memory = docker(
            "stats", "--no-stream", "--format", "{{.MemUsage}} ({{.MemPerc}})", c.name
        ).stdout.strip()
        print(f"memoria del contenedor tras la primera pasada: {memory}")  # un dato para U12, sin umbral
        (tmp_path / "memory.txt").write_text(memory + "\n", encoding="utf-8")
        sent = time.monotonic()
        stopped = docker("stop", "-t", "10", c.name, timeout=60)
        elapsed = time.monotonic() - sent
        assert stopped.returncode == 0
        state = c.state()
        assert state["ExitCode"] == 0 and not state["OOMKilled"], state
        assert elapsed <= SHUTDOWN_SECONDS, f"docker stop tardo {elapsed:.1f} s"
        assert d.double.max_active == 1


def test_no_log_line_of_the_container_keeps_only_level_timestamp_and_service(tmp_path: Path) -> None:
    """C-6 (F-06 de U11-T02): `uvicorn` y `httpx` loggean por `logging` estandar; el filtro de U0 deja de ellos solo `level`, `timestamp` y `service`."""
    with doubles() as d, container(tmp_path, d) as c:
        c.wait_for("/readyz", 200)
        docker("stop", "-t", "10", c.name, timeout=60)
        lines = log_lines(c.logs())
    # con los loggers de terceros en WARNING el contenedor puede no loguear nada en una corrida sana: lo que no puede haber es una linea sin contenido
    bare = [line for line in lines if set(line) <= {"level", "timestamp", "service"}]
    assert bare == [], f"lineas de log sin contenido: {bare[:3]}"


def test_without_the_registry_url_the_container_exits_3_and_logs_registry_url_missing(tmp_path: Path) -> None:
    with doubles() as d, container(tmp_path, d, drop=("VECTRA_REGISTRY_URL",)) as c:
        assert c.wait_for_exit() == 3
        text = c.logs()
    assert "registry_url_missing" in text
    assert all(set(line) > {"level", "timestamp", "service"} for line in log_lines(text))


def test_with_noise_sustain_days_15_in_the_mounted_file_the_container_exits_2_without_serving_anything(
    tmp_path: Path,
) -> None:
    bad = yaml.safe_dump({**yaml.safe_load(kind_policy_text()), "noise_sustain_days": 15})
    with doubles() as d, container(tmp_path, d, policy_text=bad) as c:
        assert c.wait_for_exit() == 2
        assert c.get("/healthz") is None, "con parametros invalidos no se sirve nada"
        text = c.logs()
    assert "params_invalid" in text
    assert config.NOISE_SUSTAIN_DAYS_MAX == 14


def test_without_the_token_url_the_container_never_becomes_ready(tmp_path: Path) -> None:
    """Rojo de CA-3: quitar `VECTRA_TOKEN_URL` del `Deployment` rompe el contenedor, no solo el render."""
    with doubles() as d, container(tmp_path, d, drop=("VECTRA_TOKEN_URL",)) as c:
        try:
            code = c.wait_for_exit(seconds=30)
        except AssertionError:
            code = None
        ready = c.get("/readyz")
        assert code is not None or ready is None or ready.status_code != 200, (
            "el contenedor llego a /readyz 200 sin VECTRA_TOKEN_URL"
        )


def test_the_container_never_writes_to_its_read_only_root(tmp_path: Path) -> None:
    """INF-U11-01: `readOnlyRootFilesystem` sin `emptyDir`: nada escribe en disco (la prueba corre con `--read-only` y el contenedor funciona)."""
    with doubles() as d, container(tmp_path, d) as c:
        c.wait_for("/readyz", 200)
        assert c.state()["Running"] and "Read-only file system" not in c.logs()
