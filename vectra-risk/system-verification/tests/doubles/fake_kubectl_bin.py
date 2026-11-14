"""Un `kubectl` de mentira como **ejecutable** (U12-T04, CA-5): los `verify/*.sh` lo encuentran en el `PATH` y nunca llegan al `kubectl` real ni a un cluster. Responde solo `get`, `logs` y `port-forward`; el `port-forward` abre
un servidor HTTP local con la API de lectura de Prometheus y escribe `Forwarding from 127.0.0.1:<puerto> -> 9090` como el real. Lo que responde sale de un JSON de estado (`state`); cada llamada queda en un archivo de registro."""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path
from typing import Any

SCRIPT = r"""#!{python}
import http.server, json, os, sys, threading, urllib.parse
state = json.load(open(os.environ["FAKE_KUBECTL_STATE"]))
args = sys.argv[1:]
with open(os.environ["FAKE_KUBECTL_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
if args[:1] == ["--context"]:
    args = args[2:]
if state.get("down"):
    sys.stderr.write("Unable to connect to the server\n")
    sys.exit(1)

def option(name):
    return args[args.index(name) + 1] if name in args else None

verb, ns, out, selector = args[0], option("-n"), option("-o"), option("-l")
if verb == "get":
    resource = args[1]
    if resource == "pods":
        names = state.get("pods", {{}}).get(f"{{ns}}|{{selector}}", [])
        if out == "name":
            print("\n".join("pod/" + n for n in names))
        else:
            print(" ".join(state.get("phases", {{}}).get(f"{{ns}}|{{selector}}", [])))
    elif resource.startswith("job/"):
        job = state.get("jobs", {{}}).get(resource.split("/", 1)[1])
        if job is None:
            sys.stderr.write('Error from server (NotFound): jobs.batch not found\n')
            sys.exit(1)
        print(resource if out == "name" else job.get("succeeded", ""))
    elif resource == "inferenceservices.serving.kserve.io":
        print(state.get("isvc", {{}}).get(args[2], ""))
    else:
        sys.stderr.write("recurso desconocido para el doble\n")
        sys.exit(1)
elif verb == "logs":
    print(state.get("log", ""), end="")
elif verb == "port-forward":
    if state.get("pf_fails"):
        sys.stderr.write("error: lost connection to pod\n")
        sys.exit(1)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            return None

        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("query", [""])[0]
            if state.get("prom_down"):
                self.send_response(503); self.end_headers(); self.wfile.write(b"{{}}"); return
            values = state.get("prom", {{}}).get(query, [])
            result = [{{"metric": {{}}, "value": [0, str(v)]}} for v in values]
            body = json.dumps({{"status": "success", "data": {{"resultType": "vector", "result": result}}}}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    print(f"Forwarding from 127.0.0.1:{{server.server_address[1]}} -> 9090", flush=True)
    server.serve_forever()
else:
    sys.stderr.write("verbo fuera del doble\n")
    sys.exit(1)
"""


def install(directory: Path, state: dict[str, Any]) -> dict[str, str]:
    """Escribe el ejecutable y el estado en `directory`; devuelve las variables de entorno que los `verify` necesitan (con `PATH` al frente)."""
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / "kubectl"
    binary.write_text(SCRIPT.format(python=sys.executable), encoding="utf-8")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return {
        "FAKE_KUBECTL_STATE": str(directory / "state.json"),
        "FAKE_KUBECTL_LOG": str(directory / "calls.log"),
    }
