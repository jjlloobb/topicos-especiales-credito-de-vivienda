#!/usr/bin/env python3
"""Rutas de la boveda que usan los ExternalSecret de kind, y su siembra en Vault dev (INF-U1-10).

`list`: imprime `ruta propiedad`, sin tocar ningun cluster.
`seed`: escribe cada ruta en Vault con `kubectl exec`. Conserva lo que ya exista y genera el resto al azar, asi que se
puede repetir. Lo ejecuta un operador por medio de `seed-vault.sh`; nunca CI.

Las rutas salen de lo renderizado y no de una lista a mano: un ExternalSecret nuevo se siembra sin tocar este archivo,
siempre que su manifiesto este en SOURCES (lo comprueba `tests/test_vault_paths.py`).
"""

import json
import secrets
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

PLATFORM = Path(__file__).resolve().parents[1]
DATA_CHART = PLATFORM / "data/chart"
SOURCES = [
    PLATFORM / "observability/grafana/external-secrets.yaml",
    PLATFORM / "observability/grafana/manifests.yaml",
    PLATFORM / "restore-drill/cronjob.yaml",
    *sorted((PLATFORM / "secrets").glob("*.yaml")),
]
MINIO_VALUES = PLATFORM / "data/minio/values-kind.yaml"
ACCESS_KEY_PROPERTIES = {"accessKey", "access_key_id"}
#: Se reemplaza con `seed-vault.sh grafana-token`, cuando Grafana ya existe.
TOKEN_PENDING = "pendiente-de-bootstrap"  # noqa: S105
#: El relay de notificaciones (F72) es del banco. En kind, una URL valida que no entrega nada.
RELAY_KIND = "http://127.0.0.1:9/sin-relay-en-kind"
NOT_FOUND = 2  # codigo de salida de `vault kv get` cuando la ruta no existe
Refs = dict[str, set[str]]
Runner = Callable[[list[str], str | None], "subprocess.CompletedProcess[str]"]


def render_data_chart() -> str:
    command = ["helm", "template", "data", str(DATA_CHART), "-f", str(DATA_CHART / "values-kind.yaml")]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout  # noqa: S603


def external_secrets(text: str) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(text) if d and d.get("kind") == "ExternalSecret"]


def all_external_secrets() -> list[dict[str, Any]]:
    found = external_secrets(render_data_chart())
    for path in SOURCES:
        found += external_secrets(path.read_text(encoding="utf-8"))
    return found


def collect(documents: list[dict[str, Any]]) -> Refs:
    refs: Refs = {}
    for document in documents:
        if document["spec"].get("dataFrom"):
            raise ValueError(f"{document['metadata']['name']}: `dataFrom` no dice que propiedades sembrar")
        for item in document["spec"]["data"]:
            refs.setdefault(item["remoteRef"]["key"], set()).add(item["remoteRef"]["property"])
    return refs


def minio_users(documents: list[dict[str, Any]]) -> dict[str, str]:
    """Ruta de la boveda -> `accessKey` del usuario de MinIO que usa esa ruta para su clave."""
    values = yaml.safe_load(MINIO_VALUES.read_text(encoding="utf-8"))
    by_secret = {u["existingSecret"]: u["accessKey"] for u in values["users"]}
    found: dict[str, str] = {}
    for document in documents:
        user = by_secret.get(document["metadata"]["name"])
        if user is not None and document["metadata"]["namespace"] == "vectra-data":
            for item in document["spec"]["data"]:
                found[item["remoteRef"]["key"]] = user
    return found


def fixed_value(path: str, prop: str, users: dict[str, str]) -> str | None:
    """Lo que no puede ser aleatorio. CloudNativePG exige que el usuario sea el rol; MinIO, que sea el del chart."""
    if path.startswith("postgres/roles/") and prop == "username":
        return path.rsplit("/", 1)[1]
    if prop in ACCESS_KEY_PROPERTIES and path in users:
        return users[path]
    if path == "alertmanager/relay" and prop == "url":
        return RELAY_KIND
    if path == "grafana/admin" and prop == "user":
        return "admin"
    return None


def plan(refs: Refs, users: dict[str, str], current: Callable[[str], dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for path, properties in sorted(refs.items()):
        existing = current(path)
        data = dict(existing)
        for prop in sorted(properties):
            fixed = fixed_value(path, prop, users)
            if fixed is not None:
                data[prop] = fixed
            elif prop not in data:
                data[prop] = TOKEN_PENDING if path == "grafana/folder-permissions" else secrets.token_hex(24)
        result[path] = data
    return result


def kubectl_runner(command: list[str], stdin: str | None) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(command, input=stdin, capture_output=True, text=True, check=False)  # noqa: S603


class Vault:
    """Vault dev dentro del pod. Los valores van por stdin: no aparecen en la linea de comandos."""

    def __init__(self, context: str, token: str, run: Runner = kubectl_runner) -> None:
        self.prefix = ["kubectl", "--context", context, "exec", "-i", "-n", "vault", "vault-0", "--", "env", f"VAULT_TOKEN={token}", "vault", "kv"]
        self.run = run

    def read(self, path: str) -> dict[str, str]:
        result = self.run([*self.prefix, "get", "-format=json", f"secret/{path}"], None)
        if result.returncode == NOT_FOUND:
            return {}
        if result.returncode != 0:
            raise RuntimeError(f"No se pudo leer {path}: {result.stderr}")
        return json.loads(result.stdout)["data"]["data"]

    def write(self, path: str, data: dict[str, str]) -> None:
        result = self.run([*self.prefix, "put", f"secret/{path}", "-"], json.dumps(data))
        if result.returncode != 0:
            raise RuntimeError(f"No se pudo escribir {path}: {result.stderr}")


def seed(vault: Vault) -> list[str]:
    documents = all_external_secrets()
    planned = plan(collect(documents), minio_users(documents), vault.read)
    for path, data in planned.items():
        vault.write(path, data)
    return list(planned)


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "list":
        for path, properties in sorted(collect(all_external_secrets()).items()):
            for prop in sorted(properties):
                print(path, prop)
        return 0
    if len(argv) == 4 and argv[1] == "seed":
        for path in seed(Vault(argv[2], argv[3])):
            print("sembrada", path)
        return 0
    print("Uso: vault_paths.py list | seed <contexto> <token>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
