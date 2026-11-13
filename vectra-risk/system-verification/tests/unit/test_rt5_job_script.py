"""CA-6 (U12-T03): el analizador del log esta atado al Job real de U8 (leccion de la enmienda §8).

La prueba lee `case-management/chart/templates/rt5-demo-job.yaml`, extrae el guion de Python de `args` y lo ejecuta contra un servidor HTTP de la biblioteca estandar en `127.0.0.1` y un puerto libre;
la salida real del guion se pasa al analizador. Si U8 cambia el formato de la linea, esta prueba falla.
"""

import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from external_paths import ROOT
from vectra_verification.scenarios import rt5

TEMPLATE = ROOT / "case-management" / "chart" / "templates" / "rt5-demo-job.yaml"


def extract_script(template: Path = TEMPLATE) -> str:
    """El guion de `args: - |` hasta `env:`, sin la sangria del YAML."""
    text = template.read_text(encoding="utf-8")
    match = re.search(r"args:\n\s+- \|\n(?P<body>.*?)\n\s+env:", text, re.S)
    assert match, "no se encontro el guion de `args` en la plantilla del Job"
    lines = match.group("body").splitlines()
    indent = min(len(line) - len(line.lstrip()) for line in lines if line.strip())
    return "\n".join(line[indent:] for line in lines) + "\n"


class Server:
    def __init__(self, status: int, proxy_error: str | None) -> None:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("content-length", 0)))
                outer.paths.append(self.path)
                self.send_response(status)
                if proxy_error is not None:
                    self.send_header("l5d-proxy-error", proxy_error)
                self.send_header("content-length", "0")
                self.end_headers()

            def log_message(self, *args: object) -> None:
                return

        self.paths: list[str] = []
        self.http = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.http.server_address[1]
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)

    def __enter__(self) -> "Server":
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.http.shutdown()
        self.http.server_close()


def run_script(script: str, port: int) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CASE_CORE_URL": f"http://127.0.0.1:{port}", "RT5_CREDIT_ID": "credito-1"}
    return subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=30, check=False
    )  # noqa: S603


def test_the_job_script_with_a_403_from_the_proxy_exits_0_and_the_analyzer_sees_the_proxy() -> None:
    with Server(403, "unauthorized") as server:
        done = run_script(extract_script(), server.port)
    assert done.returncode == 0 and server.paths == ["/v1/credits/credito-1/status"]
    line = rt5.parse_log(done.stdout)
    assert line.kind == "proxy" and line.code == 403 and line.value == "unauthorized"


def test_the_job_script_with_a_403_without_the_header_exits_0_and_the_analyzer_sees_the_application() -> None:
    with Server(403, None) as server:
        done = run_script(extract_script(), server.port)
    assert done.returncode == 0, "el Job sale con 0 ante CUALQUIER 403: un Job completo no prueba nada"
    line = rt5.parse_log(done.stdout)
    assert line.kind == "application" and line.code == 403 and line.value == "None"


def test_the_job_script_with_a_200_exits_1_and_the_analyzer_sees_the_code() -> None:
    with Server(200, None) as server:
        done = run_script(extract_script(), server.port)
    assert done.returncode == 1
    line = rt5.parse_log(done.stdout)
    assert line.kind == "other_code" and line.code == 200


def test_the_job_script_without_a_server_exits_2_and_the_analyzer_sees_no_response() -> None:
    with Server(200, None) as free:
        port = free.port
    done = run_script(extract_script(), port)  # el puerto ya no escucha
    assert done.returncode == 2
    assert rt5.parse_log(done.stdout).kind == "no_response"


def test_if_the_template_format_changes_the_analyzer_fails(tmp_path: Path) -> None:
    """Rojo: en una copia de la plantilla `"->"` pasa a `"=>"`; el analizador deja de ver la linea."""
    changed = tmp_path / "rt5-demo-job.yaml"
    changed.write_text(TEMPLATE.read_text(encoding="utf-8").replace('"->"', '"=>"'), encoding="utf-8")
    with Server(403, "unauthorized") as server:
        done = run_script(extract_script(changed), server.port)
    assert rt5.parse_log(done.stdout).kind == "absent"
    with pytest.raises(AssertionError):
        assert rt5.parse_log(done.stdout).kind == "proxy"
