#!/usr/local/bin/python3
"""Un `kubectl` de mentira para **dentro del contenedor** (U12-T05, CA-3): `test_image.py` lo monta de solo lectura en `/doubles/` y pone `/doubles/bin` al frente del `PATH` (el `kubectl` real de la imagen no se toca; responde
`version --client` desde su propia ruta). Responde lo que RT-5 lee: el Job `rt5-demo-<runId>` y su log (`rt5_world.JobKubectl`), la lista de pods (vacia para los namespaces de K16; uno listo para Prometheus) y, en `port-forward`, abre un
servidor HTTP con el doble de Prometheus (`rt5_world.PromDouble`) y escribe `Forwarding from 127.0.0.1:<puerto> -> 9090` como el real. El Job corre 1 s despues de `started_at` y dura 2 s; las muestras salen de ahi.

`RT5_RUN_ID` y `RT5_STARTED_AT` (ISO) los pone la prueba, tomados del `manifest.json` que escribio `prepare`. Cada llamada queda en `$DOUBLE_KUBECTL_LOG` (un JSON por linea)."""

from __future__ import annotations

import http.server
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/doubles")

import httpx  # noqa: E402
from rt5_world import PromDouble, Rt5Spec, completed_job, every, JobKubectl  # noqa: E402

RUN_ID = os.environ["RT5_RUN_ID"]
STARTED = datetime.fromisoformat(os.environ["RT5_STARTED_AT"].replace("Z", "+00:00"))
JOB_START = STARTED + timedelta(seconds=1)
JOB_END = JOB_START + timedelta(seconds=2)


def spec() -> Rt5Spec:
    horizon = JOB_END + timedelta(minutes=20)
    return Rt5Spec(
        started_at=STARTED,
        alert=every(JOB_START, JOB_END + timedelta(minutes=5)),
        deny=[(t, 1.0) for t in every(JOB_START, JOB_END + timedelta(minutes=14))],
        counter=[(t, 0.0) for t in every(STARTED, horizon)],
        lowest=STARTED - timedelta(days=3),
    )


def serve_prometheus() -> None:
    double = PromDouble(spec())

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            return None

        def do_GET(self) -> None:  # noqa: N802
            reply = double.handle_request(httpx.Request("GET", f"http://prometheus{self.path}"))
            body = reply.read()
            self.send_response(reply.status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    sys.stdout.write(f"Forwarding from 127.0.0.1:{server.server_address[1]} -> 9090\n")
    sys.stdout.flush()
    server.serve_forever()


def main(argv: list[str]) -> int:
    with open(os.environ.get("DOUBLE_KUBECTL_LOG", "/dev/null"), "a", encoding="utf-8") as log:
        log.write(json.dumps(argv) + "\n")
    args = [a for a in argv if not a.startswith("--context")]
    if args[:1] == ["port-forward"]:
        serve_prometheus()
        return 0
    if args[:2] == ["get", "pods"]:
        selector = args[args.index("-l") + 1] if "-l" in args else ""
        namespace = args[args.index("-n") + 1] if "-n" in args else ""
        if namespace == "vectra-observability" and "prometheus" in selector:
            ready = {
                "metadata": {"name": "prometheus-0"},
                "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}]},
            }
            sys.stdout.write(json.dumps({"items": [ready]}))
            return 0
        if selector:
            return _real_job_kubectl(["kubectl", *args])
        sys.stdout.write(json.dumps({"items": []}))
        return 0
    return _real_job_kubectl(["kubectl", *args])


def _real_job_kubectl(args: list[str]) -> int:
    runner = JobKubectl(completed_job(JOB_START, JOB_END, f"rt5-demo-{RUN_ID}"))
    done = runner.run(args)
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
