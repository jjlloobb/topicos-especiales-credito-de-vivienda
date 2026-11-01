"""Job de permisos de carpetas contra un Grafana real (F110; Paso 10).

Requiere una API de Docker en DOCKER_HOST: sin ella, falla. Sin acceso a Docker, Podman sin root sirve:
`podman system service --time=0 unix://$XDG_RUNTIME_DIR/tc.sock`, con
`DOCKER_HOST=unix://$XDG_RUNTIME_DIR/tc.sock` y `TESTCONTAINERS_RYUK_DISABLED=true`.

La imagen es publica: no hace falta `docker login`. Si falta y `~/.docker/config.json` usa un almacen de
credenciales, la descarga puede fallar al consultarlo. Se evita con una configuracion vacia:
`mkdir -p /tmp/dockercfg && echo '{}' > /tmp/dockercfg/config.json`, con
`DOCKER_CONFIG=/tmp/dockercfg` y `REGISTRY_AUTH_FILE=/tmp/dockercfg/config.json`.
"""

import base64
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from docker.errors import APIError
from testcontainers.core.container import DockerContainer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "observability/grafana"))
import folder_permissions as fp  # noqa: E402
import yaml  # noqa: E402

CONFIG = Path(__file__).resolve().parents[1] / "observability/grafana/folder-permissions.yaml"
FOLDERS = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["folders"]
# La misma version que trae el chart kube-prometheus-stack de components.yaml.
IMAGE = "docker.io/grafana/grafana:13.3.0"
SESGO = next(f for f in FOLDERS if f["uid"] == "vectra-sesgo")


def call(url, method, path, body=None, user="admin", password="admin", token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url + path, data=data, method=method, headers=headers)  # noqa: S310
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        raw = response.read()
    return json.loads(raw) if raw else None


def status_as(url, path, user):
    try:
        call(url, "GET", path, user=user, password="clave-de-prueba")  # noqa: S106
    except urllib.error.HTTPError as exc:
        return exc.code
    return 200


def stop(container):
    """Podman sin root puede quejarse al limpiar su red aunque el contenedor ya se haya eliminado."""
    try:
        container.stop()
    except APIError as exc:
        if "rootless netns" not in str(exc):
            raise


@pytest.fixture(scope="module")
def grafana():
    container = DockerContainer(IMAGE).with_exposed_ports(3000).with_env("GF_SECURITY_ADMIN_PASSWORD", "admin").start()
    try:
        url = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(3000)}"
        for _ in range(120):
            try:
                if call(url, "GET", "/api/health")["database"] == "ok":
                    break
            except (urllib.error.URLError, ConnectionError, OSError):
                pass
            time.sleep(1)
        else:
            pytest.fail("Grafana no arranco")
        teams = {}
        for team in {name for folder in FOLDERS for name in folder["teams"]}:
            teams[team] = call(url, "POST", "/api/teams", {"name": team})["teamId"]
        for login, team in (("ana", "cro"), ("beto", "operacion")):
            user_id = call(url, "POST", "/api/admin/users", {"login": login, "password": "clave-de-prueba", "email": f"{login}@x.test"})["id"]
            call(url, "POST", f"/api/teams/{teams[team]}/members", {"userId": user_id})
        account = call(url, "POST", "/api/serviceaccounts", {"name": "folder-permissions", "role": "Admin"})
        token = call(url, "POST", f"/api/serviceaccounts/{account['id']}/tokens", {"name": "job"})["key"]
        yield url, fp.Grafana(url, token)
    finally:
        stop(container)


def test_job_creates_missing_folder_and_a_later_dashboard_inherits(grafana):
    url, client = grafana
    assert not client.folder_exists("vectra-sesgo")
    fp.apply(client, FOLDERS)
    assert client.folder_exists("vectra-sesgo")
    saved = call(url, "POST", "/api/dashboards/db", {"folderUid": "vectra-sesgo", "dashboard": {"uid": "sesgo-1", "title": "Sesgo", "panels": []}})
    assert call(url, "GET", f"/api/dashboards/uid/{saved['uid']}")["meta"]["folderUid"] == "vectra-sesgo"
    assert status_as(url, "/api/dashboards/uid/sesgo-1", "ana") == 200, "cro ve la carpeta de sesgo"
    assert status_as(url, "/api/dashboards/uid/sesgo-1", "beto") == 403, "operacion no la ve"


def test_folder_has_exactly_the_declared_team_permissions(grafana):
    _, client = grafana
    fp.apply(client, FOLDERS)
    for folder in FOLDERS:
        assert fp.current_items(client, folder["uid"]) == fp.normalized(fp.desired_items(client, folder)), folder["uid"]


def test_second_apply_writes_nothing_and_there_is_no_drift(grafana):
    _, client = grafana
    fp.apply(client, FOLDERS)
    assert fp.drift(client, FOLDERS) == 0
    writes = []
    original = client.request

    def spy(method, path, body=None):
        if method != "GET":
            writes.append(path)
        return original(method, path, body)

    client.request = spy
    try:
        fp.apply(client, FOLDERS)
    finally:
        client.request = original
    assert writes == []


def test_a_manual_change_is_drift_and_apply_repairs_it(grafana):
    url, client = grafana
    fp.apply(client, FOLDERS)
    extra = [*fp.desired_items(client, SESGO), {"role": "Viewer", "permission": 1}]
    call(url, "POST", "/api/folders/vectra-sesgo/permissions", {"items": extra})
    assert fp.drift(client, FOLDERS) == 1
    fp.apply(client, FOLDERS)
    assert fp.drift(client, FOLDERS) == 0
