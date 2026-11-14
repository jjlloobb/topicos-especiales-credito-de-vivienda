"""El escritor unico (U12-T04, CA-9): filtra antes de escribir, no deja temporales, resume lo que pasa del tope, y ningun otro modulo de `src/` escribe archivos."""

import ast
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import pytest

from vectra_verification import store
from vectra_verification.evidence import EvidenceError
from vectra_verification.store import Store, StoreError

SRC = Path(__file__).resolve().parents[2] / "src" / "vectra_verification"
JWT = (
    "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3ZlY3RyYSIsInN1YiI6IngifQ.c2lnbmF0dXJlLXRlc3Q"
)
SECRET = "semilla+Zq81/xkLm=secreta"


def test_a_file_is_written_filtered_and_hashed(tmp_path: Path) -> None:
    out = Store(tmp_path / "v", lambda: (SECRET,))
    stored = out.write("RT-5.json", '{"ok": 1, "Authorization": "Bearer abc"}')
    text = (tmp_path / "v" / "RT-5.json").read_text()
    assert "abc" not in text and '"ok": 1' in text
    assert stored.sha256 == hashlib.sha256(text.encode()).hexdigest() == out.sha256("RT-5.json")
    assert [p.name for p in (tmp_path / "v").iterdir()] == ["RT-5.json"]  # ningun temporal


@pytest.mark.parametrize("leak", [JWT, SECRET, quote(SECRET, safe="")])
def test_a_secret_or_a_jwt_fails_and_leaves_no_file_and_no_temporary(tmp_path: Path, leak: str) -> None:
    out = Store(tmp_path / "v", lambda: (SECRET,))
    with pytest.raises(EvidenceError):
        out.write("RT-2.json", f'{{"detail": "x {leak} y"}}')
    assert not (tmp_path / "v").exists() or list((tmp_path / "v").iterdir()) == []


def test_a_failure_while_renaming_removes_the_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = Store(tmp_path, lambda: ())

    def boom(*args: object) -> None:
        raise OSError("sin permiso")

    monkeypatch.setattr(store.os, "replace", boom)
    with pytest.raises(OSError, match="sin permiso"):
        out.write("a.json", "{}")
    assert list(tmp_path.iterdir()) == []


def test_new_refuses_an_existing_file_and_keeps_it(tmp_path: Path) -> None:
    out = Store(tmp_path, lambda: ())
    out.write("manifest.json", '{"a": 1}', new=True)
    with pytest.raises(StoreError, match="store_exists"):
        out.write("manifest.json", '{"a": 2}', new=True)
    assert out.read_text("manifest.json") == '{"a": 1}'
    out.write("manifest.json", '{"a": 3}')  # sin `new` se reemplaza
    assert json.loads(out.read_text("manifest.json")) == {"a": 3}


@pytest.mark.parametrize("name", ["../fuera.json", "a/b.json", ".oculto", "", "a b.json", "x\\y"])
def test_names_are_plain_file_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(StoreError, match="store_name_invalid"):
        Store(tmp_path, lambda: ()).write(name, "{}")


def test_a_file_over_the_limit_becomes_a_summary_with_the_hash_of_the_original(tmp_path: Path) -> None:
    out = Store(tmp_path, lambda: (), limit=100)
    big = "x" * 101
    stored = out.write("log.txt", big)
    summary = json.loads(out.read_text("log.txt"))
    assert stored.summarized and summary["original_bytes"] == 101
    assert summary["original_sha256"] == hashlib.sha256(
        big.encode()
    ).hexdigest() and big not in out.read_text("log.txt")
    assert not out.write("chico.txt", "x" * 100).summarized
    assert store.FILE_LIMIT == 50 * 1024 * 1024


def test_the_kubectl_json_and_the_job_log_are_written_with_the_dev_token_root_in_them(tmp_path: Path) -> None:
    """El token de desarrollo `root` de kind no es un secreto (F-09): no bloquea el log del Job ni el JSON de `kubectl` que dicen `/dev/root` o el logger `root`."""
    out = Store(tmp_path, lambda: ())  # `Credentials.secret_values()` no incluye `root` en kind
    out.write(
        "rt5-job.log", "rt5-demo: POST http://x -> 403 l5d-proxy-error: unauthorized\nlogger root: ok\n"
    )
    out.write("rt5-job.json", json.dumps({"volumes": [{"hostPath": "/dev/root"}], "kind": "Job"}))
    assert out.names() == ["rt5-job.json", "rt5-job.log"]


def test_reading_helpers(tmp_path: Path) -> None:
    out = Store(tmp_path / "nueva", lambda: ())
    assert out.names() == [] and out.sha256("a.json") is None and not out.exists("a.json")


# --- la prueba estatica: solo `store.py` escribe archivos (CA-9) ------------------------------------------------------------------------------------


def _writes(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id
                if isinstance(func, ast.Name)
                else ""
            )
            if name in {
                "write_text",
                "write_bytes",
                "dump",
                "copy",
                "copyfile",
                "copy2",
                "copytree",
                "move",
                "rename",
                "unlink",
                "rmtree",
                "touch",
                "mkdir",
                "makedirs",
                "mkstemp",
                "NamedTemporaryFile",
            }:
                found.append(f"{name}:{node.lineno}")
            if (
                name == "replace"
                and isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
            ):
                found.append(f"os.replace:{node.lineno}")
            if name == "open":
                modes = [a.value for a in node.args[1:2] if isinstance(a, ast.Constant)] + [
                    k.value.value
                    for k in node.keywords
                    if k.arg == "mode" and isinstance(k.value, ast.Constant)
                ]
                if node.args and not modes and isinstance(func, ast.Attribute):
                    modes = [node.args[0].value] if isinstance(node.args[0], ast.Constant) else []
                if any(isinstance(m, str) and set(m) & set("wax+") for m in modes):
                    found.append(f"open:{node.lineno}")
        if isinstance(node, ast.Import) and any(a.name == "shutil" for a in node.names):
            found.append(f"import shutil:{node.lineno}")
        if isinstance(node, ast.ImportFrom) and node.module == "shutil":
            found.append(f"from shutil:{node.lineno}")
    return found


def test_no_module_of_src_but_the_store_writes_files() -> None:
    offenders = {}
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "store.py":
            continue
        found = _writes(ast.parse(path.read_text(encoding="utf-8")))
        if found:
            offenders[str(path.relative_to(SRC))] = found
    assert offenders == {}


def test_the_static_check_sees_a_direct_write() -> None:
    for source in (
        "from pathlib import Path\nPath('x').write_text('a')\n",
        "open('x', 'w')\n",
        "open('x', mode='ab')\n",
        "import json\njson.dump({}, f)\n",
        "import shutil\n",
        "from shutil import copy\n",
        "import os\nos.replace('a', 'b')\n",
    ):
        assert _writes(ast.parse(source)), source
    assert not _writes(ast.parse("open('x')\nopen('x', 'r')\nPath('x').read_text()\n"))
