"""Los scripts de `model-serving/docs/kind/` (U06-T03) contra dobles: un servidor HTTP local y un `kubectl` falso. Ninguno toca un cluster."""

import json
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

KIND = Path(__file__).resolve().parents[2] / "docs/kind"
M1, M2 = "mv-2026-01-01-26300247", "mv-2026-02-01-a1b2c3d4"


def run(script: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(KIND / script), *args], capture_output=True, text=True, check=False, env=env
    )


class Predict(BaseHTTPRequestHandler):
    replies: list[tuple[int, str]] = []
    served = 0

    def do_POST(self) -> None:  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        status, version = self.replies[min(type(self).served, len(self.replies) - 1)]
        type(self).served += 1
        body = json.dumps(
            {"predictions": [{"score": 0.1, "confidence": "high", "model_version_id": version}]}
        ).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def server():
    started: list[HTTPServer] = []

    def start(replies: list[tuple[int, str]]) -> str:
        handler = type("H", (Predict,), {"replies": replies, "served": 0})
        httpd = HTTPServer(("127.0.0.1", 0), handler)
        started.append(httpd)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{httpd.server_port}/v1/models/m:predict"

    yield start
    for httpd in started:
        httpd.shutdown()


@pytest.fixture
def payload(tmp_path: Path) -> Path:
    path = tmp_path / "payload.json"
    path.write_text('{"instances": [{"features": {}}]}', encoding="utf-8")
    return path


def traffic(url: str, payload: Path, tmp_path: Path, versions: str) -> subprocess.CompletedProcess[str]:
    return run(
        "traffic.sh",
        "--url",
        url,
        "--payload",
        str(payload),
        "--versions",
        versions,
        "--duration",
        "1",
        "--interval",
        "0.05",
        "--out",
        str(tmp_path / "t.log"),
    )


def test_traffic_counts_zero_mismatches_when_every_response_has_an_accepted_version(
    server, payload, tmp_path
):
    result = traffic(server([(200, M1)]), payload, tmp_path, f"{M1},{M2}")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "version_mismatch=0" in result.stdout and "errores=0" in result.stdout


def test_traffic_fails_on_a_version_outside_the_accepted_set(server, payload, tmp_path):
    result = traffic(server([(200, M1), (200, M2)]), payload, tmp_path, M1)
    assert result.returncode == 1
    assert not re.search(r"version_mismatch=0\b", result.stdout)


def test_traffic_reports_server_errors_apart_from_mismatches(server, payload, tmp_path):
    result = traffic(server([(503, M1)]), payload, tmp_path, M1)
    assert result.returncode == 2 and "version_mismatch=0" in result.stdout


def test_traffic_dry_run_sends_nothing(payload):
    result = run(
        "traffic.sh",
        "--url",
        "http://127.0.0.1:9/x",
        "--payload",
        str(payload),
        "--versions",
        M1,
        "--dry-run",
    )
    assert result.returncode == 0 and result.stdout.startswith("dry-run:")


def test_traffic_requires_its_arguments():
    assert run("traffic.sh").returncode == 64


@pytest.fixture
def kubectl(tmp_path: Path):
    """Un `kubectl` falso: responde lo que diga `FAKE_<modo>` y registra cada llamada, para comprobar que solo lee."""
    script = tmp_path / "kubectl"
    script.write_text(
        '#!/usr/bin/env bash\necho "$*" >> "$FAKE_LOG"\n'
        'case "$1" in\n'
        '  top) cat "$FAKE_TOP" ;;\n'
        '  exec) echo "$FAKE_MANIFEST" ;;\n'
        '  get) case "$*" in\n'
        '         *initContainers*) echo "$FAKE_INIT" ;;\n'
        '         *serving-state*) echo "$FAKE_STATE" ;;\n'
        '         *hpa-exempt*) echo "$FAKE_EXEMPT" ;;\n'
        '         *) echo "$FAKE_REPLICAS" ;;\n'
        "       esac ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def env(kubectl: Path, tmp_path: Path, **fake: str) -> dict[str, str]:
    import os

    base = {"PATH": os.environ["PATH"], "KUBECTL": str(kubectl), "FAKE_LOG": str(tmp_path / "calls.log")}
    return {**base, **{f"FAKE_{k.upper()}": v for k, v in fake.items()}}


def only_reads(tmp_path: Path) -> None:
    calls = (tmp_path / "calls.log").read_text(encoding="utf-8").splitlines()
    assert calls and all(c.split()[0] in {"get", "top", "exec"} for c in calls)


def test_sample_replicas_passes_when_the_active_keeps_two(kubectl, tmp_path):
    result = run("sample-replicas.sh", "--namespace", "vectra-serving", "--deployments", "a-predictor,a-explainer", "--duration", "1", "--interval", "0.1",
                 "--out", str(tmp_path / "r.log"), env=env(kubectl, tmp_path, replicas="2 2"))  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr
    assert "minimo_observado=2" in result.stdout and "bajo_el_minimo=0" in result.stdout
    only_reads(tmp_path)


def test_sample_replicas_fails_when_ready_replicas_drop_below_two(kubectl, tmp_path):
    result = run("sample-replicas.sh", "--namespace", "vectra-serving", "--deployments", "a-predictor", "--duration", "1", "--interval", "0.1",
                 env=env(kubectl, tmp_path, replicas="2 1"))  # fmt: skip
    assert result.returncode == 1 and "minimo_observado=1" in result.stdout


def test_sample_replicas_counts_a_missing_status_as_zero(kubectl, tmp_path):
    result = run(
        "sample-replicas.sh",
        "--namespace",
        "n",
        "--deployments",
        "a-predictor",
        "--duration",
        "1",
        "--interval",
        "0.1",
        env=env(kubectl, tmp_path, replicas="2"),
    )
    assert result.returncode == 1 and "minimo_observado=0" in result.stdout


def test_memory_sums_kubectl_top_against_the_budget(kubectl, tmp_path):
    top = tmp_path / "top.txt"
    top.write_text("a-predictor-1 10m 120Mi\na-predictor-2 11m 130Mi\n", encoding="utf-8")
    out = tmp_path / "m.md"
    good = run(
        "memory.sh",
        "--namespace",
        "vectra-serving",
        "--label",
        "antes",
        "--budget-mib",
        "552",
        "--out",
        str(out),
        env=env(kubectl, tmp_path, top=str(top)),
    )
    assert good.returncode == 0 and "uso_total_mib=250" in out.read_text(encoding="utf-8")
    bad = run(
        "memory.sh",
        "--namespace",
        "vectra-serving",
        "--label",
        "durante",
        "--budget-mib",
        "200",
        "--out",
        str(out),
        env=env(kubectl, tmp_path, top=str(top)),
    )
    assert bad.returncode == 1
    only_reads(tmp_path)


def test_check_pods_init_order(kubectl, tmp_path):
    good = run(
        "check-pods.sh",
        "init-order",
        "p",
        "vectra-serving",
        env=env(kubectl, tmp_path, init="linkerd-init linkerd-proxy storage-initializer"),
    )
    assert good.returncode == 0 and good.stdout.strip().endswith("(posicion 2)"), good.stdout
    bad = run(
        "check-pods.sh",
        "init-order",
        "p",
        "vectra-serving",
        env=env(kubectl, tmp_path, init="storage-initializer linkerd-proxy"),
    )
    assert bad.returncode == 1


def test_check_pods_initializer_in_the_explainer(kubectl, tmp_path):
    assert (
        run(
            "check-pods.sh",
            "initializer",
            "p",
            "n",
            env=env(kubectl, tmp_path, init="linkerd-proxy storage-initializer"),
        ).returncode
        == 0
    )
    assert (
        run(
            "check-pods.sh", "initializer", "p", "n", env=env(kubectl, tmp_path, init="linkerd-proxy")
        ).returncode
        == 1
    )


def test_check_pods_manifest_and_propagation(kubectl, tmp_path):
    assert (
        run("check-pods.sh", "manifest", "p", "n", M1, env=env(kubectl, tmp_path, manifest=M1)).returncode
        == 0
    )
    assert (
        run("check-pods.sh", "manifest", "p", "n", M1, env=env(kubectl, tmp_path, manifest=M2)).returncode
        == 1
    )
    assert (
        run(
            "check-pods.sh",
            "propagation",
            "d",
            "n",
            "inactivo",
            env=env(kubectl, tmp_path, state="inactivo", exempt="true"),
        ).returncode
        == 0
    )
    assert (
        run(
            "check-pods.sh",
            "propagation",
            "d",
            "n",
            "inactivo",
            env=env(kubectl, tmp_path, state="", exempt=""),
        ).returncode
        == 1
    )
    only_reads(tmp_path)


def test_the_scripts_never_mutate_the_cluster():
    forbidden = re.compile(r"kubectl apply|helm (install|upgrade)|argocd app sync")
    assert not [s.name for s in KIND.glob("*") if forbidden.search(s.read_text(encoding="utf-8"))]
