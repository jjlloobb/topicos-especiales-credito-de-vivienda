"""Un `kubectl`, un `free` y un `docker` de mentira como **ejecutables** para los guiones de `docs/kind/` (U12-T06, CA-5). Nunca llegan al `kubectl` real ni a un cluster.

`kubectl`: responde segun una lista de reglas (`rules`): la primera cuyas palabras (`match`) estan **todas** en los argumentos da su `stdout`, `stderr` y `rc`; sin regla, falla con el mensaje
`sin regla` (asi un guion que pide algo no previsto se nota). `port-forward` abre un servidor HTTP local y escribe `Forwarding from 127.0.0.1:<puerto> -> N` como el real: sirve la API de lectura
de Prometheus (`prom_query`: una subcadena de la consulta y su resultado; `prom_rules`, `prom_targets`, `prom_series`) o, si el namespace es `vault`, la lectura de `identity/synthetic-users` (`vault_keys`: nombres y valores). Cada llamada
queda en un archivo de registro (un JSON por linea) para comprobar los verbos. `free` y `docker` imprimen lo que diga `free_text` y `docker_text`.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

KUBECTL = r"""#!{python}
import http.server, json, os, sys, threading, urllib.parse
state = json.load(open(os.environ["KIND_FAKE_STATE"]))
args = sys.argv[1:]
with open(os.environ["KIND_FAKE_LOG"], "a") as log:
    log.write(json.dumps(["kubectl"] + args) + "\n")
if args[:1] == ["--context"]:
    args = args[2:]
verb = args[0] if args else ""
if verb == "port-forward":
    namespace = args[args.index("-n") + 1] if "-n" in args else ""
    if state.get("pf_fails"):
        sys.stderr.write("error: lost connection to pod\n")
        sys.exit(1)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            return None

        def reply(self, status, body):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(url.query)
            if namespace == "vault":
                if self.headers.get("X-Vault-Token") != state.get("vault_token", "root"):
                    return self.reply(403, {{"errors": ["permission denied"]}})
                return self.reply(200, {{"data": {{"data": state.get("vault_keys", {{}})}}}})
            if state.get("prom_down"):
                return self.reply(503, {{}})
            if url.path == "/api/v1/query":
                expr = query.get("query", [""])[0]
                series = next((v for k, v in state.get("prom_query", {{}}).items() if k in expr), [])
                if isinstance(series, str):
                    return self.reply(400, {{"status": "error", "error": series}})
                return self.reply(200, {{"status": "success", "data": {{"resultType": "vector", "result": series}}}})
            if url.path == "/api/v1/rules":
                return self.reply(200, {{"status": "success", "data": {{"groups": state.get("prom_rules", [])}}}})
            if url.path == "/api/v1/targets":
                return self.reply(200, {{"status": "success", "data": {{"activeTargets": state.get("prom_targets", [])}}}})
            if url.path == "/api/v1/series":
                name = query.get("match[]", [""])[0]
                return self.reply(200, {{"status": "success", "data": state.get("prom_series", {{}}).get(name, [])}})
            return self.reply(404, {{}})

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    print(f"Forwarding from 127.0.0.1:{{server.server_address[1]}} -> 9090", flush=True)
    server.serve_forever()
for rule in state.get("rules", []):
    if all(word in args for word in rule["match"]):
        sys.stdout.write(rule.get("stdout", ""))
        sys.stderr.write(rule.get("stderr", ""))
        sys.exit(rule.get("rc", 0))
sys.stderr.write("sin regla para: " + " ".join(args) + "\n")
sys.exit(1)
"""

PLAIN = r"""#!/bin/sh
cat "$KIND_FAKE_{name}_FILE"
"""


def install(
    directory: Path, state: dict[str, Any], *, free_text: str = "", docker_text: str = ""
) -> dict[str, str]:
    """Escribe los ejecutables y el estado en `directory`; devuelve las variables de entorno de un guion (con `PATH` al frente)."""
    directory.mkdir(parents=True, exist_ok=True)
    kubectl = directory / "kubectl"
    kubectl.write_text(KUBECTL.format(python=sys.executable), encoding="utf-8")
    kubectl.chmod(kubectl.stat().st_mode | stat.S_IXUSR)
    for name, text in (("free", free_text), ("docker", docker_text)):
        binary = directory / name
        binary.write_text(PLAIN.replace("{name}", name.upper()), encoding="utf-8")
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        (directory / f"{name}.txt").write_text(text, encoding="utf-8")
    (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return {
        "PATH": f"{directory}{os.pathsep}{os.environ['PATH']}",
        "KIND_FAKE_STATE": str(directory / "state.json"),
        "KIND_FAKE_LOG": str(directory / "calls.log"),
        "KIND_FAKE_FREE_FILE": str(directory / "free.txt"),
        "KIND_FAKE_DOCKER_FILE": str(directory / "docker.txt"),
    }


def calls(directory: Path) -> list[list[str]]:
    log = directory / "calls.log"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
