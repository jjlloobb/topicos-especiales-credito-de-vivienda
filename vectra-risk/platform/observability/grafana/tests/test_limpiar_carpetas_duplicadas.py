"""La limpieza de carpetas duplicadas contra un Grafana doble: nunca borra contenido ni imprime la credencial."""

import base64
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import limpiar_carpetas_duplicadas as cleanup  # noqa: E402

USER, PASSWORD = "admin-de-prueba", "s3creto-que-no-debe-verse"  # noqa: S105
BASIC = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
ENV = {"GRAFANA_ADMIN_USER": USER, "GRAFANA_ADMIN_PASSWORD": PASSWORD}
KEPT = {"vectra-sesgo", "vectra-producto", "vectra-operacion"}


class Fake:
    """Carpetas {uid: (titulo, padre)} y tableros {uid: carpeta}; borra en cascada, como Grafana."""

    def __init__(self):
        self.folders = {
            "vectra-sesgo": ("Vectra / Sesgo", ""),
            "vectra-producto": ("Vectra / Producto", ""),
            "vectra-operacion": ("Vectra / Operación", ""),
        }
        self.dashboards = {"vectra-producto-panel": "vectra-producto", "vectra-slo": "vectra-operacion"}
        self.alert_rules: dict[str, int] = {}
        self.hidden_dashboards: dict[str, int] = {}  # tableros que la busqueda aun no lista
        self.deleted: list[str] = []
        self.requests: list[tuple[str, str]] = []
        self.fail_delete_after: int | None = None
        self.unauthorized = 0

    def leak(self, count):
        for i in range(count):
            self.folders[f"raiz{i:04d}"] = ("Vectra", "")
            self.folders[f"op{i:04d}"] = ("Operación", f"raiz{i:04d}")
            self.folders[f"prod{i:04d}"] = ("Producto", f"raiz{i:04d}")

    def descendants(self, uid):
        kids = [k for k, (_, parent) in self.folders.items() if parent == uid]
        return kids + [d for k in kids for d in self.descendants(k)]

    def counts(self, uid):
        tree = [uid, *self.descendants(uid)]
        return {
            "folders": len(tree) - 1,
            "dashboards": sum(1 for f in self.dashboards.values() if f in tree) + sum(self.hidden_dashboards.get(f, 0) for f in tree),
            "alertrules": sum(self.alert_rules.get(f, 0) for f in tree),
            "librarypanels": 0,
        }


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

        def authorized(self):
            if self.headers.get("Authorization") == f"Basic {BASIC}":
                return True
            fake.unauthorized += 1
            self.send(401, {"message": "Unauthorized"})
            return False

        def do_GET(self):
            if not self.authorized():
                return
            url = urlparse(self.path)
            fake.requests.append(("GET", url.path))
            if url.path == "/api/search":
                query = parse_qs(url.query)
                limit, page = int(query["limit"][0]), int(query["page"][0])
                if query["type"] == ["dash-folder"]:
                    rows = [{"uid": u, "title": t, "folderUid": p} if p else {"uid": u, "title": t} for u, (t, p) in fake.folders.items()]
                else:
                    rows = [{"uid": u, "title": u, "folderUid": f} for u, f in fake.dashboards.items()]
                return self.send(200, rows[(page - 1) * limit : page * limit])
            uid = unquote(url.path.split("/")[3])
            if uid not in fake.folders:
                return self.send(404, {"message": "folder not found"})
            return self.send(200, fake.counts(uid))

        def do_DELETE(self):
            if not self.authorized():
                return
            url = urlparse(self.path)
            fake.requests.append(("DELETE", url.path))
            uid = unquote(url.path.split("/")[3])
            if fake.fail_delete_after is not None and len(fake.deleted) >= fake.fail_delete_after:
                return self.send(503, {"message": "database is locked"})
            if uid not in fake.folders:
                return self.send(404, {"message": "folder not found"})
            tree = [uid, *fake.descendants(uid)]
            for gone in tree:
                del fake.folders[gone]
            fake.dashboards = {d: f for d, f in fake.dashboards.items() if f not in tree}
            fake.deleted.append(uid)
            return self.send(200, {"message": "deleted"})

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield fake, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def run(url, *args, env=ENV):
    pauses = []
    code = cleanup.main(["--url", url, *args], environ=env, sleep=pauses.append)
    return code, pauses


def test_dry_run_is_the_default_and_only_counts(server, capsys):
    fake, url = server
    fake.leak(4)
    before = dict(fake.folders)
    code, pauses = run(url)
    out = capsys.readouterr().out
    assert code == 0 and fake.folders == before and not fake.deleted and not pauses
    assert not [r for r in fake.requests if r[0] == "DELETE"]
    assert "Carpetas en Grafana: 15" in out and "duplicadas vacias: 12" in out and "no se borro nada" in out


def test_explicit_dry_run_does_not_delete_and_excludes_execute(server):
    fake, url = server
    fake.leak(1)
    assert run(url, "--dry-run")[0] == 0 and not fake.deleted
    with pytest.raises(SystemExit):
        run(url, "--dry-run", "--execute")
    assert not fake.deleted


def test_execute_deletes_only_empty_duplicates_leaves_first(server, capsys):
    fake, url = server
    fake.leak(3)
    dashboards = dict(fake.dashboards)
    code, _ = run(url, "--execute")
    assert code == 0
    assert set(fake.folders) == KEPT and fake.dashboards == dashboards
    assert len(fake.deleted) == 9
    for i in range(3):  # cada raiz se borra despues de sus dos hijas: ningun borrado en cascada
        root = fake.deleted.index(f"raiz{i:04d}")
        assert fake.deleted.index(f"op{i:04d}") < root and fake.deleted.index(f"prod{i:04d}") < root
    assert "Borradas: 9." in capsys.readouterr().out


def test_never_deletes_a_tree_that_holds_a_dashboard(server):
    """El arbol que la fuga creo de ultimo todavia tiene los tableros si el arreglo no se ha desplegado."""
    fake, url = server
    fake.leak(2)
    fake.dashboards["vectra-resiliencia"] = "op0001"
    code, _ = run(url, "--execute")
    assert code == 0
    assert {"raiz0001", "op0001", "prod0001"} <= set(fake.folders)
    assert fake.dashboards["vectra-resiliencia"] == "op0001"
    assert sorted(fake.deleted) == ["op0000", "prod0000", "raiz0000"]


def test_counts_are_checked_again_before_each_delete(server, capsys):
    """La busqueda puede ir atrasada: un tablero o una regla que no listo frena el borrado de esa carpeta y de su raiz."""
    fake, url = server
    fake.leak(2)
    fake.hidden_dashboards["op0000"] = 1
    fake.alert_rules["prod0001"] = 1
    code, _ = run(url, "--execute")
    assert code == 0
    assert sorted(fake.deleted) == ["op0001", "prod0000"]
    assert {"raiz0000", "op0000", "raiz0001", "prod0001"} <= set(fake.folders)
    assert "Omitidas por no estar vacias: 4." in capsys.readouterr().out


def test_never_touches_the_folders_of_the_permissions_job_even_when_empty(server):
    fake, url = server
    fake.dashboards.clear()
    fake.leak(1)
    assert run(url, "--execute")[0] == 0
    assert set(fake.folders) == KEPT


def test_protected_uid_with_a_leak_title_survives(server, tmp_path):
    fake, url = server
    fake.folders["conservar"] = ("Vectra", "")
    fake.folders["hija"] = ("Operación", "conservar")
    permissions = tmp_path / "folder-permissions.yaml"
    folders = [{"uid": "conservar", "title": "Vectra / Operación", "teams": {}}]
    permissions.write_text(yaml.safe_dump({"folders": folders}, allow_unicode=True), encoding="utf-8")
    assert run(url, "--execute", "--permissions", str(permissions))[0] == 0
    assert not fake.deleted


def test_leaves_folders_that_do_not_have_the_leak_shape(server):
    fake, url = server
    fake.folders.update(
        {
            "ajena": ("Equipo de riesgo", ""),
            "suelta": ("Operación", ""),  # hija sin raiz `Vectra`
            "raizx": ("Vectra", ""),
            "notas": ("Notas", "raizx"),  # una carpeta ajena dentro de una raiz `Vectra`
            "raizy": ("Vectra", ""),
            "opy": ("Operación", "raizy"),
            "nieta": ("Producto", "opy"),  # mas honda de lo que la fuga creaba
        }
    )
    before = dict(fake.folders)
    assert run(url, "--execute")[0] == 0
    assert fake.folders == before and not fake.deleted


def test_max_caps_one_run_and_the_next_run_continues(server, capsys):
    fake, url = server
    fake.leak(5)
    code, _ = run(url, "--execute", "--max", "4")
    assert code == 0 and len(fake.deleted) == 4
    assert "Quedan por borrar: 11" in capsys.readouterr().out
    for _ in range(3):
        run(url, "--execute", "--max", "4")
    assert set(fake.folders) == KEPT and len(fake.deleted) == 15


def test_pauses_after_every_delete_and_longer_after_each_batch(server):
    fake, url = server
    fake.leak(2)
    _, pauses = run(url, "--execute", "--pause", "0.5", "--batch", "3", "--batch-pause", "9")
    assert pauses == [0.5, 0.5, 9.0, 0.5, 0.5, 9.0]


def test_stops_at_the_first_server_error(server, capsys):
    fake, url = server
    fake.leak(3)
    fake.fail_delete_after = 2
    code, _ = run(url, "--execute")
    captured = capsys.readouterr()
    assert code == 1 and len(fake.deleted) == 2
    assert len([r for r in fake.requests if r[0] == "DELETE"]) == 3
    assert "HTTP 503" in captured.err and "Borradas: 2." in captured.out


def test_listing_error_deletes_nothing(server, capsys):
    fake, url = server
    fake.leak(1)
    code, _ = run(url, "--execute", env={"GRAFANA_ADMIN_USER": USER, "GRAFANA_ADMIN_PASSWORD": "otra"})
    captured = capsys.readouterr()
    assert code == 1 and not fake.deleted and fake.unauthorized == 1
    assert "HTTP 401" in captured.err and "otra" not in captured.err + captured.out


def test_listing_pages_through_every_folder(server, monkeypatch, capsys):
    fake, url = server
    monkeypatch.setattr(cleanup, "PAGE", 4)
    fake.leak(3)
    assert run(url)[0] == 0
    assert "duplicadas vacias: 9" in capsys.readouterr().out
    assert len([r for r in fake.requests if r == ("GET", "/api/search")]) == 5  # 12 carpetas en 4 paginas y 2 tableros en 1


@pytest.mark.parametrize("mode", [[], ["--execute"]])
def test_never_prints_the_credential(server, capsys, mode):
    fake, url = server
    fake.leak(2)
    fake.fail_delete_after = 1
    run(url, *mode)
    captured = capsys.readouterr()
    for secret in (PASSWORD, BASIC, USER):
        assert secret not in captured.out + captured.err
    assert PASSWORD not in repr(cleanup.Grafana(url, USER, PASSWORD)) and BASIC not in repr(cleanup.Grafana(url, USER, PASSWORD))


def test_credentials_from_a_directory_and_missing_credentials(server, tmp_path, capsys):
    fake, url = server
    fake.leak(1)
    (tmp_path / "admin-user").write_text(USER + "\n", encoding="utf-8")
    (tmp_path / "admin-password").write_text(PASSWORD + "\n", encoding="utf-8")
    assert run(url, "--credentials-dir", str(tmp_path), env={})[0] == 0 and fake.unauthorized == 0
    assert run(url, env={})[0] == 2
    assert "Falta la credencial" in capsys.readouterr().err


def test_password_cannot_be_passed_as_an_argument(server):
    _, url = server
    with pytest.raises(SystemExit):
        run(url, "--password", PASSWORD)


def test_is_empty_requires_known_keys_and_all_zeros():
    assert cleanup.is_empty({"folders": 0, "dashboards": 0, "alertrules": 0, "librarypanels": 0})
    assert not cleanup.is_empty({"folders": 0, "dashboards": 0, "nuevo_recurso": 1})
    assert not cleanup.is_empty({"dashboards": 0})
    assert not cleanup.is_empty(None)


def test_duplicate_shape_comes_from_the_permissions_file():
    folders = yaml.safe_load(cleanup.DEFAULT_PERMISSIONS.read_text(encoding="utf-8"))["folders"]
    roots, children = cleanup.duplicate_shape(folders)
    assert roots == {"Vectra"} and children == {"Sesgo", "Producto", "Operación"}
