"""Permisos de carpetas contra un Grafana doble (F110). El caso real: platform/tests/test_grafana_folder_permissions.py."""

import json
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote_plus

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import folder_permissions as fp  # noqa: E402

FOLDERS = [{"uid": "vectra-sesgo", "title": "Vectra / Sesgo", "teams": {"cro": "View", "cumplimiento": "View"}}]


class Fake:
    def __init__(self):
        self.folders, self.writes, self.pushed = {}, [], []
        self.teams = {"cro": 1, "cumplimiento": 2}
        self.team_conflict = False


@pytest.fixture
def server():
    fake = Fake()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, status, body=None):
            raw = json.dumps(body).encode() if body is not None else b""
            self.send_response(status)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            match = re.match(r"/api/folders/([^/]+)(/permissions)?$", self.path)
            if self.path.startswith("/api/teams/search"):
                name = unquote_plus(self.path.split("name=")[1])
                self.send(200, {"teams": [{"id": fake.teams[name], "name": name}] if name in fake.teams else []})
            elif match and match.group(1) in fake.folders:
                self.send(200, fake.folders[match.group(1)] if match.group(2) else {"uid": match.group(1)})
            else:
                self.send(404, {})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            fake.writes.append(self.path)
            if self.path == "/api/teams":
                if fake.team_conflict:
                    self.send(409, {"message": "Team name taken"})
                    return
                fake.teams[body["name"]] = len(fake.teams) + 1
            elif self.path == "/api/folders":
                if body["uid"] in fake.folders:
                    self.send(409, {"message": "folder exists"})
                    return
                fake.folders[body["uid"]] = [{"role": "Viewer", "permission": 1}, {"role": "Editor", "permission": 2}]
            else:
                fake.folders[self.path.split("/")[3]] = [{"teamId": i["teamId"], "permission": i["permission"]} for i in body["items"]]
            self.send(200, {})

        def do_PUT(self):
            fake.pushed.append((self.path, self.rfile.read(int(self.headers["Content-Length"])).decode()))
            self.send(200)

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield fake, f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_missing_folder_is_created_with_only_team_permissions(server):
    fake, url = server
    fp.apply(fp.Grafana(url, "t"), FOLDERS)
    assert fake.folders["vectra-sesgo"] == [{"teamId": 1, "permission": 1}, {"teamId": 2, "permission": 1}]


def test_role_permissions_are_removed(server):
    fake, url = server
    fake.folders["vectra-sesgo"] = [{"role": "Viewer", "permission": 1}]
    fp.apply(fp.Grafana(url, "t"), FOLDERS)
    assert all("role" not in item for item in fake.folders["vectra-sesgo"])


def test_second_run_writes_nothing(server):
    fake, url = server
    fp.apply(fp.Grafana(url, "t"), FOLDERS)
    writes = len(fake.writes)
    fp.apply(fp.Grafana(url, "t"), FOLDERS)
    assert len(fake.writes) == writes


def test_check_reports_drift_and_changes_nothing(server):
    fake, url = server
    g = fp.Grafana(url, "t")
    assert fp.drift(g, FOLDERS) == 1
    fp.apply(g, FOLDERS)
    assert fp.drift(g, FOLDERS) == 0
    fake.folders["vectra-sesgo"].append({"role": "Viewer", "permission": 1})
    writes = len(fake.writes)
    assert fp.drift(g, FOLDERS) == 1
    assert len(fake.writes) == writes


def test_metric_pushed_to_expected_group(server):
    fake, url = server
    fp.push_metric(url, 1)
    assert fake.pushed == [("/metrics/job/grafana-folder-permissions", "vectra_grafana_folder_permissions_drift 1\n")]


def test_apply_creates_missing_teams_only_once(server):
    fake, url = server
    del fake.teams["cumplimiento"]
    fp.apply(fp.Grafana(url, "t"), FOLDERS)
    assert fake.writes.count("/api/teams") == 1
    assert {item["teamId"] for item in fake.folders["vectra-sesgo"]} == {fake.teams["cro"], fake.teams["cumplimiento"]}
    fp.apply(fp.Grafana(url, "t"), FOLDERS)
    assert fake.writes.count("/api/teams") == 1


def test_team_created_by_another_process_is_not_an_error(server):
    fake, url = server
    fake.teams, fake.team_conflict = {}, True
    fp.Grafana(url, "t").ensure_team("cro")
    assert fake.writes == ["/api/teams"]


def test_other_team_errors_are_raised(server):
    _, url = server

    class Denied(fp.Grafana):
        def request(self, method, path, body=None):
            if method == "POST":
                raise HTTPError(path, 403, "denegado", None, None)
            return {"teams": []}

    with pytest.raises(HTTPError):
        Denied(url, "t").ensure_team("cro")


def test_missing_team_has_a_clear_error_naming_it(server):
    _, url = server
    with pytest.raises(fp.TeamMissingError, match="'nadie'"):
        fp.Grafana(url, "t").team_id("nadie")


def test_team_name_is_url_encoded(server):
    fake, url = server
    fake.teams["con espacio"] = 9
    assert fp.Grafana(url, "t").team_id("con espacio") == 9


def test_check_counts_a_missing_team_as_drift_and_pushes_the_metric(server, monkeypatch, tmp_path):
    fake, url = server
    client = fp.Grafana(url, "t")
    fp.apply(client, FOLDERS)
    del fake.teams["cro"]
    writes = len(fake.writes)
    assert fp.drift(client, FOLDERS) == 1
    config = tmp_path / "permisos.yaml"
    config.write_text(fp.yaml.safe_dump({"folders": FOLDERS}), encoding="utf-8")
    monkeypatch.setenv("FOLDER_PERMISSIONS", str(config))
    monkeypatch.setenv("GRAFANA_URL", url)
    monkeypatch.setenv("GRAFANA_TOKEN", "t")
    monkeypatch.setenv("PUSHGATEWAY_URL", url)
    assert fp.main(["folder_permissions.py", "check"]) == 0
    assert fake.pushed == [("/metrics/job/grafana-folder-permissions", "vectra_grafana_folder_permissions_drift 1\n")]
    assert len(fake.writes) == writes


@pytest.fixture
def slow_server():
    """Servidor que no responde a tiempo las primeras `slow` peticiones; registra cada peticion recibida."""
    state = {"slow": 2, "seen": [], "status": 200}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            state["seen"].append(self.path)
            if len(state["seen"]) <= state["slow"]:
                time.sleep(0.6)
            raw = b'{"ok": true}'
            self.send_response(state["status"])
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except OSError:
                pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield state, f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture
def fast_timeouts(monkeypatch):
    monkeypatch.setattr(fp, "TIMEOUT", 0.2)
    monkeypatch.setattr(fp, "BACKOFF", 0.01)


@pytest.fixture
def sleeps(monkeypatch):
    """Registra las esperas entre intentos sin dormir de verdad."""
    recorded = []
    monkeypatch.setattr(fp.time, "sleep", recorded.append)
    return recorded


def failing_urlopen(monkeypatch, error):
    calls = []

    def urlopen(request, timeout):
        calls.append(request.full_url)
        raise error

    monkeypatch.setattr(fp.urllib.request, "urlopen", urlopen)
    return calls


def test_request_retries_on_timeout(slow_server, fast_timeouts):
    state, url = slow_server
    assert fp.Grafana(url, "t").request("GET", "/api/x") == {"ok": True}
    assert len(state["seen"]) == 3


def test_request_fails_clearly_after_three_timeouts(slow_server, fast_timeouts):
    state, url = slow_server
    state["slow"] = 99
    with pytest.raises(fp.RequestTimeoutError, match=r"GET /api/x agoto el tiempo de espera en 3 intentos"):
        fp.Grafana(url, "t").request("GET", "/api/x")
    assert len(state["seen"]) == 3


def test_forbidden_is_not_retried(slow_server, fast_timeouts):
    state, url = slow_server
    state["slow"], state["status"] = 0, 403
    with pytest.raises(HTTPError):
        fp.Grafana(url, "t").request("GET", "/api/x")
    assert len(state["seen"]) == 1


def test_request_waits_between_attempts_with_growing_backoff(monkeypatch, sleeps):
    calls = failing_urlopen(monkeypatch, TimeoutError())
    with pytest.raises(fp.RequestTimeoutError):
        fp.Grafana("http://x", "t").request("GET", "/api/x")
    assert len(calls) == 3
    assert sleeps == [fp.BACKOFF, fp.BACKOFF * 2]
    assert all(wait > 0 for wait in sleeps)


def test_connect_timeout_is_retried(monkeypatch, sleeps):
    calls = failing_urlopen(monkeypatch, fp.urllib.error.URLError(TimeoutError("timed out")))
    with pytest.raises(fp.RequestTimeoutError, match=r"GET /api/x"):
        fp.Grafana("http://x", "t").request("GET", "/api/x")
    assert len(calls) == 3
    assert len(sleeps) == 2


def test_refused_connection_is_not_retried(monkeypatch, sleeps):
    calls = failing_urlopen(monkeypatch, fp.urllib.error.URLError(ConnectionRefusedError()))
    with pytest.raises(fp.urllib.error.URLError) as raised:
        fp.Grafana("http://x", "t").request("GET", "/api/x")
    assert not isinstance(raised.value, fp.RequestTimeoutError)
    assert len(calls) == 1
    assert sleeps == []


def test_real_refused_connection_is_not_retried(monkeypatch, sleeps):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    real_urlopen, calls = fp.urllib.request.urlopen, []

    def counting_urlopen(request, timeout):
        calls.append(request.full_url)
        return real_urlopen(request, timeout=timeout)

    monkeypatch.setattr(fp.urllib.request, "urlopen", counting_urlopen)
    with pytest.raises(fp.urllib.error.URLError) as raised:
        fp.Grafana(f"http://127.0.0.1:{port}", "t").request("GET", "/api/x")
    assert not isinstance(raised.value, fp.RequestTimeoutError)
    assert len(calls) == 1
    assert sleeps == []


def test_server_errors_are_not_retried(slow_server, fast_timeouts):
    state, url = slow_server
    state["slow"], state["status"] = 0, 500
    with pytest.raises(HTTPError):
        fp.Grafana(url, "t").request("GET", "/api/x")
    assert len(state["seen"]) == 1


def test_folder_conflict_on_create_is_tolerated(server):
    fake, url = server

    class Late(fp.Grafana):
        def folder_exists(self, uid):
            return False

    fake.folders["vectra-sesgo"] = [{"role": "Viewer", "permission": 1}]
    fp.apply(Late(url, "t"), FOLDERS)
    assert fake.writes.count("/api/folders") == 1
    assert fake.folders["vectra-sesgo"] == [{"teamId": 1, "permission": 1}, {"teamId": 2, "permission": 1}]


def test_folder_created_by_a_timed_out_post_is_not_an_error(server, sleeps, monkeypatch):
    """Grafana crea la carpeta pero responde tarde; el reintento del POST recibe 409 y apply termina bien."""
    fake, url = server
    real_urlopen, timed_out = fp.urllib.request.urlopen, []

    def late_first_folder_post(request, timeout):
        response = real_urlopen(request, timeout=timeout)
        if request.get_method() == "POST" and request.full_url.endswith("/api/folders") and not timed_out:
            timed_out.append(True)
            response.close()
            raise TimeoutError("timed out")
        return response

    monkeypatch.setattr(fp.urllib.request, "urlopen", late_first_folder_post)
    fp.apply(fp.Grafana(url, "t"), FOLDERS)
    assert timed_out == [True]
    assert fake.writes.count("/api/folders") == 2
    assert len(sleeps) == 1
    assert fake.folders["vectra-sesgo"] == [{"teamId": 1, "permission": 1}, {"teamId": 2, "permission": 1}]


def test_other_folder_errors_are_raised(server):
    _, url = server

    class Denied(fp.Grafana):
        def request(self, method, path, body=None):
            raise HTTPError(path, 403, "denegado", None, None)

    with pytest.raises(HTTPError) as raised:
        Denied(url, "t").ensure_folder("vectra-sesgo", "Vectra / Sesgo")
    assert raised.value.code == 403
