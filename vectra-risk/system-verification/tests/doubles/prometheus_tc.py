"""Prometheus **real** por digest, con Testcontainers, sobre un bloque TSDB creado con `promtool tsdb create-blocks-from openmetrics` (U12-T03, P-1 (a) del usuario, 2026-11-13).

La imagen es la del digest de `platform/observability/values/kube-prometheus-stack.yaml` (`quay.io/prometheus/prometheus@sha256:...`); `promtool` sale **de esa misma imagen**. Los datos salen de un `Rt5Spec`
(`rt5_world.py`): la misma descripcion que usa el doble, con tiempos relativos a «ahora». Prometheus se raspa a si mismo cada segundo (hace falta `prometheus_tsdb_lowest_timestamp_seconds`).
Todo temporal vive dentro del worktree (`platform/.tools/tmp/u12t03/`, ignorado por git). La unica espera real es la de arranque del contenedor. La imagen no se borra al terminar.
"""

from __future__ import annotations

import re
import secrets
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

import httpx
from external_paths import ROOT
from rt5_world import Rt5Spec, every
from testcontainers.core.container import DockerContainer

VALUES = ROOT / "platform" / "observability" / "values" / "kube-prometheus-stack.yaml"
REPOSITORY = "quay.io/prometheus/prometheus"  # el del chart `kube-prometheus-stack`
SCRATCH = ROOT / "platform" / ".tools" / "tmp" / "u12t03"
LABEL = {"vectra.test": "u12t03"}
CONFIG = """global:
  scrape_interval: 1s
scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ["localhost:9090"]
"""


def image() -> str:
    match = re.search(r"image: \{ sha: ([0-9a-f]{64}) \}", VALUES.read_text(encoding="utf-8"))
    assert match, "el digest de Prometheus no esta en los values de la plataforma"
    return f"{REPOSITORY}@sha256:{match.group(1)}"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    assert port not in (443, 8080, 8081, 8200, 8443, 9090)
    return port


def _series(name: str, labels: str, samples: list[tuple[float, float]]) -> list[str]:
    return [f"{name}{labels} {value:g} {ts:.3f}" for ts, value in sorted(samples)]


def to_openmetrics(spec: Rt5Spec) -> str:
    """El archivo de entrada de `promtool`: una familia por nombre (OpenMetrics las quiere juntas) y `# EOF` al final."""
    lines: list[str] = ["# TYPE ALERTS gauge"]
    lines += _series(
        "ALERTS",
        '{alertname="CoreWriteAttempt",alertstate="firing",severity="SEV2"}',
        [(t.timestamp(), 1.0) for t in spec.alert],
    )
    lines.append("# TYPE inbound_http_authz_deny counter")
    lines += _series(
        "inbound_http_authz_deny_total",
        '{namespace="vectra-mock",route_name="core-mock-catch-all",direction="inbound"}',
        [(t.timestamp(), v) for t, v in spec.deny],
    )
    for namespace, route in spec.other_family:
        lines += _series(
            "inbound_http_authz_deny_total",
            f'{{namespace="{namespace}",route_name="{route}",direction="inbound"}}',
            [(t.timestamp(), 1.0) for t in every(spec.other_until - timedelta(minutes=10), spec.other_until)]
            if spec.other_until
            else [],
        )
    lines.append("# TYPE vectra_core_write_attempts counter")
    lines += _series("vectra_core_write_attempts_total", "", [(t.timestamp(), v) for t, v in spec.counter])
    lines.append("# EOF")
    return "\n".join(lines) + "\n"


def _wait(base_url: str, container: DockerContainer) -> None:
    deadline = time.monotonic() + 120
    last = ""
    while time.monotonic() < deadline:
        try:
            ready = httpx.get(f"{base_url}/-/ready", timeout=3.0)
            if ready.status_code == 200:
                found = httpx.get(
                    f"{base_url}/api/v1/query",
                    params={"query": "prometheus_tsdb_lowest_timestamp_seconds"},
                    timeout=3.0,
                )
                if found.status_code == 200 and found.json()["data"]["result"]:
                    return
        except httpx.HTTPError as error:
            last = type(error).__name__
        time.sleep(1.0)  # espera real, la unica permitida: el arranque del contenedor
    logs = container.get_logs()[0].decode(errors="replace")[-800:]
    raise AssertionError(f"Prometheus no arranco en 120 s ({last}): {logs}")


@contextmanager
def prometheus_with(spec: Rt5Spec) -> Iterator[str]:
    """Un Prometheus real con los datos de `spec`; devuelve su URL (`http://127.0.0.1:<puerto>`). Se borra al salir, tambien con un fallo."""
    token = secrets.token_hex(4)
    workdir = SCRATCH / f"prom-{token}"
    data = workdir / "data"
    data.mkdir(parents=True)
    (workdir / "prometheus.yml").write_text(CONFIG, encoding="utf-8")
    (workdir / "input.om").write_text(to_openmetrics(spec), encoding="utf-8")
    uid = subprocess.run(["id", "-u"], capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603, S607
    gid = subprocess.run(["id", "-g"], capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603, S607
    port = free_port()
    container: DockerContainer | None = None
    try:
        made = subprocess.run(  # noqa: S603
            [
                "docker",
                "run",
                "--rm",
                "--user",
                f"{uid}:{gid}",
                "--entrypoint",
                "promtool",
                "-v",
                f"{workdir}:/work",
                image(),
                "tsdb",
                "create-blocks-from",
                "openmetrics",
                "/work/input.om",
                "/work/data",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert made.returncode == 0, f"promtool fallo: {made.stdout[-500:]} {made.stderr[-500:]}"
        for path in [
            data,
            *data.rglob("*"),
        ]:  # la imagen corre como `nobody` (65532): debe poder escribir el WAL y los bloques
            path.chmod(0o777 if path.is_dir() else 0o666)
        container = (
            DockerContainer(image())
            .with_name(f"u12t03-prom-{token}")
            .with_kwargs(mem_limit="512m", labels=LABEL)
            .with_bind_ports(9090, ("127.0.0.1", port))
            .with_volume_mapping(str(workdir / "prometheus.yml"), "/etc/prometheus/prometheus.yml", "ro")
            .with_volume_mapping(str(data), "/prometheus", "rw")
            .with_command(
                "--config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/prometheus --storage.tsdb.retention.time=30d"
            )
        )
        container.start()
        base_url = f"http://127.0.0.1:{port}"
        _wait(base_url, container)
        yield base_url
    finally:
        try:
            if container is not None:
                container.stop(force=True, delete_volume=True)
        finally:
            # Prometheus (65532) crea carpetas que el usuario del host no puede borrar: se abren con la misma imagen, como root, antes de borrar.
            subprocess.run(  # noqa: S603
                [
                    "docker",
                    "run",
                    "--rm",
                    "--user",
                    "0",
                    "--entrypoint",
                    "chmod",
                    "-v",
                    f"{workdir}:/work",
                    image(),
                    "-R",
                    "a+rwX",
                    "/work",
                ],
                capture_output=True,
                check=False,
                timeout=60,
            )
            shutil.rmtree(workdir, ignore_errors=True)
