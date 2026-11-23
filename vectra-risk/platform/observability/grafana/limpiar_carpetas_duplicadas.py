#!/usr/bin/env python3
"""Borra las carpetas de Grafana duplicadas y VACIAS que dejo la fuga de `foldersFromFilesStructure` (2026-11).

La fuga creaba, en cada reescritura de un tablero, una carpeta raiz `Vectra` con subcarpetas `Operación` y
`Producto`. Las carpetas buenas son las de `folder-permissions.yaml` (`Vectra / Operación`, UID `vectra-operacion`...):
este guion nunca las toca. Correrlo solo DESPUES de desplegar el arreglo y de comprobar que el conteo ya no crece.

Por omision NO borra: lista, cuenta y sale. Con `--execute` borra, de las hojas hacia la raiz, hasta `--max`
carpetas por corrida. Antes de cada borrado vuelve a preguntar a Grafana que hay dentro (`/counts`) y solo borra si
no hay tableros, reglas, paneles de biblioteca ni subcarpetas. Ante el primer error del servidor se detiene.

Credencial: `GRAFANA_ADMIN_USER` y `GRAFANA_ADMIN_PASSWORD`, o `--credentials-dir` con los archivos `admin-user` y
`admin-password` (las claves del Secret `grafana-admin`). Nunca por argumento y nunca se imprime.

    kubectl --context kind-vectra port-forward -n vectra-observability svc/kube-prometheus-stack-grafana 13000:80 &
    export GRAFANA_ADMIN_USER="$(kubectl --context kind-vectra get secret grafana-admin -n vectra-observability \
        -o 'jsonpath={.data.admin-user}' | base64 -d)"
    export GRAFANA_ADMIN_PASSWORD="$(kubectl --context kind-vectra get secret grafana-admin -n vectra-observability \
        -o 'jsonpath={.data.admin-password}' | base64 -d)"
    uv run python platform/observability/grafana/limpiar_carpetas_duplicadas.py              # solo cuenta
    uv run python platform/observability/grafana/limpiar_carpetas_duplicadas.py --execute    # borra hasta --max
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_URL = "http://127.0.0.1:13000"
DEFAULT_PERMISSIONS = Path(__file__).resolve().parent / "folder-permissions.yaml"
PAGE = 1000
TIMEOUT = 30
HTTP_NOT_FOUND = 404
# Lo que `/api/folders/<uid>/counts` debe traer en cero. Una clave que falte o una nueva distinta de cero: no se borra.
SAFE_ZERO_KEYS = ("dashboards", "folders")


class CredentialsMissingError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Falta la credencial: GRAFANA_ADMIN_USER y GRAFANA_ADMIN_PASSWORD, o --credentials-dir con admin-user y admin-password"
        )


@dataclass(frozen=True)
class Folder:
    uid: str
    title: str
    parent: str  # "" en la raiz


@dataclass
class Plan:
    """Que se borraria, en orden (hojas antes que su raiz), y que se deja."""

    total: int = 0
    protected: int = 0
    with_content: int = 0
    other: int = 0
    deletable: list[Folder] = field(default_factory=list)


@dataclass
class Outcome:
    deleted: int = 0
    skipped: int = 0
    gone: int = 0
    error: str = ""


class Grafana:
    def __init__(self, url: str, user: str, password: str) -> None:
        self.url = url.rstrip("/")
        self._authorization = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()

    def __repr__(self) -> str:  # nunca la credencial, tampoco en una traza
        return f"Grafana({self.url!r})"

    def request(self, method: str, path: str) -> Any:
        headers = {"Authorization": self._authorization, "Accept": "application/json"}
        request = urllib.request.Request(self.url + path, method=method, headers=headers)  # noqa: S310
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
            raw = response.read()
        return json.loads(raw) if raw else None

    def search(self, kind: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        page = 1
        while True:
            query = urllib.parse.urlencode({"type": kind, "limit": PAGE, "page": page})
            batch = self.request("GET", f"/api/search?{query}")
            found.extend(batch)
            if len(batch) < PAGE:
                return found
            page += 1

    def folders(self) -> list[Folder]:
        return [Folder(f["uid"], f["title"], f.get("folderUid") or "") for f in self.search("dash-folder")]

    def dashboard_folders(self) -> set[str]:
        return {d.get("folderUid") or "" for d in self.search("dash-db")}

    def counts(self, uid: str) -> dict[str, int]:
        return self.request("GET", f"/api/folders/{urllib.parse.quote(uid, safe='')}/counts")

    def delete_folder(self, uid: str) -> None:
        # Sin `forceDeleteRules`: una carpeta con reglas de alerta no se borra.
        self.request("DELETE", f"/api/folders/{urllib.parse.quote(uid, safe='')}")


def duplicate_shape(permission_folders: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """De `Vectra / Operación` sale lo que la fuga creaba: raiz `Vectra` e hija `Operación`."""
    roots, children = set(), set()
    for folder in permission_folders:
        parts = [part.strip() for part in folder["title"].split("/")]
        if len(parts) == 2 and all(parts):  # noqa: PLR2004 - raiz e hija
            roots.add(parts[0])
            children.add(parts[1])
    return roots, children


def build_plan(
    folders: list[Folder], dashboard_folders: set[str], protected_uids: set[str], roots: set[str], children: set[str]
) -> Plan:
    """Solo arboles `raiz -> hijas` con la forma de la fuga, sin tableros, sin UID protegido y sin nada ajeno dentro."""
    by_parent: dict[str, list[Folder]] = {}
    for folder in folders:
        by_parent.setdefault(folder.parent, []).append(folder)
    plan = Plan(total=len(folders), protected=sum(1 for f in folders if f.uid in protected_uids))
    for root in sorted(by_parent.get("", []), key=lambda f: f.uid):
        if root.uid in protected_uids:
            continue
        if root.title not in roots:
            plan.other += 1
            continue
        kids = sorted(by_parent.get(root.uid, []), key=lambda f: f.uid)
        tree = [*kids, root]
        foreign = any(k.title not in children or k.uid in protected_uids or by_parent.get(k.uid) for k in kids)
        if foreign or any(f.uid in dashboard_folders for f in tree):
            plan.with_content += 1
            continue
        plan.deletable.extend(tree)
    return plan


def is_empty(counts: dict[str, int] | None) -> bool:
    if not isinstance(counts, dict) or any(key not in counts for key in SAFE_ZERO_KEYS):
        return False
    return all(value == 0 for value in counts.values())


def execute(  # noqa: PLR0913 - los frenos son parametros a proposito
    grafana: Grafana,
    plan: Plan,
    protected_uids: set[str],
    limit: int,
    pause: float,
    batch: int,
    batch_pause: float,
    sleep: Callable[[float], None] = time.sleep,
) -> Outcome:
    outcome = Outcome()
    for folder in plan.deletable:
        if outcome.deleted >= limit:
            break
        if folder.uid in protected_uids:  # segunda barrera: el plan ya las excluye
            outcome.skipped += 1
            continue
        try:
            if not is_empty(grafana.counts(folder.uid)):
                outcome.skipped += 1
                continue
            grafana.delete_folder(folder.uid)
        except urllib.error.HTTPError as exc:
            if exc.code == HTTP_NOT_FOUND:
                outcome.gone += 1
                continue
            outcome.error = f"HTTP {exc.code} en la carpeta {folder.uid}"
            break
        except (TimeoutError, urllib.error.URLError) as exc:
            outcome.error = f"{type(exc).__name__} en la carpeta {folder.uid}: Grafana no responde"
            break
        outcome.deleted += 1
        sleep(batch_pause if batch and outcome.deleted % batch == 0 else pause)
    return outcome


def read_credentials(directory: str | None, environ: dict[str, str]) -> tuple[str, str]:
    if directory:
        base = Path(directory)
        user = (base / "admin-user").read_text(encoding="utf-8").strip()
        password = (base / "admin-password").read_text(encoding="utf-8").strip()
    else:
        user, password = environ.get("GRAFANA_ADMIN_USER", ""), environ.get("GRAFANA_ADMIN_PASSWORD", "")
    if not user or not password:
        raise CredentialsMissingError
    return user, password


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Borra las carpetas duplicadas y vacias de Grafana. Sin --execute solo cuenta.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--credentials-dir", help="directorio con los archivos admin-user y admin-password")
    parser.add_argument("--permissions", type=Path, default=DEFAULT_PERMISSIONS, help="folder-permissions.yaml: las carpetas que se conservan")
    parser.add_argument("--execute", action="store_true", help="borra de verdad; sin esto es --dry-run")
    parser.add_argument("--dry-run", action="store_true", help="el modo por omision: solo cuenta")
    parser.add_argument("--max", type=int, default=2000, dest="limit", help="tope de carpetas borradas por corrida")
    parser.add_argument("--pause", type=float, default=0.25, help="segundos entre borrados")
    parser.add_argument("--batch", type=int, default=200, help="borrados por lote")
    parser.add_argument("--batch-pause", type=float, default=15.0, help="segundos de descanso tras cada lote")
    args = parser.parse_args(argv)
    if args.execute and args.dry_run:
        parser.error("--execute y --dry-run se excluyen")
    if args.limit < 1 or args.pause < 0 or args.batch < 0 or args.batch_pause < 0:
        parser.error("--max debe ser positivo y las pausas no pueden ser negativas")
    return args


def main(argv: list[str], environ: dict[str, str] | None = None, sleep: Callable[[float], None] = time.sleep) -> int:
    args = parse(argv)
    permission_folders = yaml.safe_load(args.permissions.read_text(encoding="utf-8"))["folders"]
    protected = {folder["uid"] for folder in permission_folders}
    roots, children = duplicate_shape(permission_folders)
    try:
        user, password = read_credentials(args.credentials_dir, dict(os.environ if environ is None else environ))
    except (CredentialsMissingError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    grafana = Grafana(args.url, user, password)
    try:
        plan = build_plan(grafana.folders(), grafana.dashboard_folders(), protected, roots, children)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: Grafana respondio HTTP {exc.code} al listar; no se borro nada", file=sys.stderr)
        return 1
    except (TimeoutError, urllib.error.URLError) as exc:
        print(f"ERROR: Grafana no responde al listar ({type(exc).__name__}); no se borro nada", file=sys.stderr)
        return 1
    print(f"Carpetas en Grafana: {plan.total}")
    print(f"  conservadas por UID ({', '.join(sorted(protected))}): {plan.protected}")
    print(f"  arboles con la forma de la fuga pero con contenido o carpetas ajenas (no se tocan): {plan.with_content}")
    print(f"  otras carpetas raiz (no se tocan): {plan.other}")
    print(f"  duplicadas vacias: {len(plan.deletable)}")
    if not args.execute:
        print(f"Simulacro: no se borro nada. Con --execute se borrarian hasta {min(args.limit, len(plan.deletable))} en esta corrida.")
        return 0
    outcome = execute(grafana, plan, protected, args.limit, args.pause, args.batch, args.batch_pause, sleep)
    pending = len(plan.deletable) - outcome.deleted - outcome.gone
    print(f"Borradas: {outcome.deleted}. Ya no existian: {outcome.gone}. Omitidas por no estar vacias: {outcome.skipped}.")
    print(f"Quedan por borrar: {pending} (las raices se borran cuando ya no tienen hijas; repite la corrida).")
    if outcome.error:
        print(f"ERROR: detenido: {outcome.error}. Espera a que Grafana se recupere antes de repetir.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
