#!/usr/bin/env python3
"""Aplica o comprueba los permisos de carpetas de Grafana por su API (F110).

`apply`: crea los equipos y las carpetas con UID fijo si faltan, y deja solo los permisos de equipo. Idempotente.
`check`: no cambia nada; empuja `vectra_grafana_folder_permissions_drift` al Pushgateway (F113). Un equipo que falta
es deriva de su carpeta, no un error del CronJob.

Autenticacion: el token de una cuenta de servicio de Grafana con rol Admin, que llega por ESO (F110). Crearla es un
paso del operador: platform/runbooks/install.md.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml

LEVELS = {"View": 1, "Edit": 2, "Admin": 4}
TIMEOUT = 5
ATTEMPTS = 3
BACKOFF = 2.0
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409


class TeamMissingError(LookupError):
    """El equipo no existe en Grafana."""

    def __init__(self, name: str) -> None:
        super().__init__(f"El equipo de Grafana {name!r} no existe; lo crea el modo `apply`")
        self.name = name


class RequestTimeoutError(TimeoutError):
    """La peticion agoto el tiempo en todos los intentos."""

    def __init__(self, method: str, path: str, attempts: int) -> None:
        super().__init__(f"{method} {path} agoto el tiempo de espera en {attempts} intentos")


def is_timeout(exc: BaseException) -> bool:
    return isinstance(exc, TimeoutError) or (isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, TimeoutError))


class Grafana:
    def __init__(self, url: str, token: str) -> None:
        self.url, self.token = url.rstrip("/"), token

    def request(self, method: str, path: str, body: Any = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        request = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)  # noqa: S310
        attempt = 0
        while True:
            attempt += 1
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
                    raw = response.read()
            except (TimeoutError, urllib.error.URLError) as exc:
                # HTTPError (4xx/5xx) es un URLError con respuesta: no se reintenta.
                if isinstance(exc, urllib.error.HTTPError) or not is_timeout(exc):
                    raise
                if attempt >= ATTEMPTS:
                    raise RequestTimeoutError(method, path, ATTEMPTS) from exc
                time.sleep(BACKOFF * attempt)
            else:
                return json.loads(raw) if raw else None

    def folder_exists(self, uid: str) -> bool:
        try:
            self.request("GET", f"/api/folders/{uid}")
        except urllib.error.HTTPError as exc:
            if exc.code == HTTP_NOT_FOUND:
                return False
            raise
        return True

    def ensure_folder(self, uid: str, title: str) -> None:
        """Idempotente, tambien si un intento anterior que agoto el tiempo ya creo la carpeta (409)."""
        try:
            self.request("POST", "/api/folders", {"uid": uid, "title": title})
        except urllib.error.HTTPError as exc:
            if exc.code != HTTP_CONFLICT:
                raise

    def find_team(self, name: str) -> int | None:
        query = urllib.parse.urlencode({"name": name})
        teams = self.request("GET", f"/api/teams/search?{query}")["teams"]
        return next((team["id"] for team in teams if team["name"] == name), None)

    def team_id(self, name: str) -> int:
        found = self.find_team(name)
        if found is None:
            raise TeamMissingError(name)
        return found

    def ensure_team(self, name: str) -> None:
        """Idempotente, tambien si otro proceso crea el equipo entre la busqueda y la creacion."""
        if self.find_team(name) is not None:
            return
        try:
            self.request("POST", "/api/teams", {"name": name})
        except urllib.error.HTTPError as exc:
            if exc.code != HTTP_CONFLICT:
                raise


def desired_items(grafana: Grafana, folder: dict[str, Any]) -> list[dict[str, int]]:
    return sorted(
        ({"teamId": grafana.team_id(name), "permission": LEVELS[level]} for name, level in folder["teams"].items()),
        key=lambda item: item["teamId"],
    )


def current_items(grafana: Grafana, uid: str) -> list[dict[str, int]]:
    """Todos los permisos de la carpeta, heredados incluidos; un permiso de rol es deriva."""
    items = grafana.request("GET", f"/api/folders/{uid}/permissions")
    return sorted(
        ({"teamId": i.get("teamId", 0), "permission": i["permission"], "role": i.get("role", "")} for i in items),
        key=lambda item: (item["teamId"], item["role"]),
    )


def normalized(desired: list[dict[str, int]]) -> list[dict[str, Any]]:
    return [{**item, "role": ""} for item in desired]


def apply(grafana: Grafana, folders: list[dict[str, Any]]) -> None:
    for name in sorted({team for folder in folders for team in folder["teams"]}):
        grafana.ensure_team(name)
    for folder in folders:
        if not grafana.folder_exists(folder["uid"]):
            grafana.ensure_folder(folder["uid"], folder["title"])
        desired = desired_items(grafana, folder)
        if current_items(grafana, folder["uid"]) != normalized(desired):
            grafana.request("POST", f"/api/folders/{folder['uid']}/permissions", {"items": desired})


def drift(grafana: Grafana, folders: list[dict[str, Any]]) -> int:
    count = 0
    for folder in folders:
        try:
            matches = grafana.folder_exists(folder["uid"]) and current_items(grafana, folder["uid"]) == normalized(desired_items(grafana, folder))
        except TeamMissingError as exc:
            print(f"Deriva en {folder['uid']}: {exc}", file=sys.stderr)
            matches = False
        if not matches:
            count += 1
    return count


def push_metric(pushgateway: str, value: int) -> None:
    body = f"vectra_grafana_folder_permissions_drift {value}\n".encode()
    url = f"{pushgateway.rstrip('/')}/metrics/job/grafana-folder-permissions"
    request = urllib.request.Request(url, data=body, method="PUT")  # noqa: S310
    with urllib.request.urlopen(request, timeout=TIMEOUT):  # noqa: S310
        pass


def main(argv: list[str]) -> int:
    mode = argv[1]
    config = yaml.safe_load(Path(os.environ["FOLDER_PERMISSIONS"]).read_text(encoding="utf-8"))["folders"]
    grafana = Grafana(os.environ["GRAFANA_URL"], os.environ["GRAFANA_TOKEN"])
    if mode == "apply":
        apply(grafana, config)
        return 0
    count = drift(grafana, config)
    push_metric(os.environ["PUSHGATEWAY_URL"], count)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
