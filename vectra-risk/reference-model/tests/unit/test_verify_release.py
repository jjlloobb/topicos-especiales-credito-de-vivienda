"""El script de verificacion de SHA-256 de la entrega (Paso 9, NFR-U5-03): un paquete bueno pasa y uno alterado falla."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_release.py"
FILES = {"predictor.json": b'{"a": 1}', "background.csv": b"x,y\n1,2\n"}


def _package(directory: Path) -> Path:
    directory.mkdir(parents=True)
    entries = []
    for name, data in FILES.items():
        (directory / name).write_bytes(data)
        entries.append({"name": name, "sha256": hashlib.sha256(data).hexdigest()})
    (directory / "manifest.json").write_text(json.dumps({"files": entries}))
    return directory


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), *map(str, args)]
    return subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603


def test_verify_release_passes_on_a_good_package(tmp_path: Path) -> None:
    result = _run(_package(tmp_path / "package"))
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_verify_release_fails_on_a_tampered_file(tmp_path: Path) -> None:
    package = _package(tmp_path / "package")
    (package / "predictor.json").write_bytes(b'{"a": 2}')
    result = _run(package)
    assert result.returncode == 1
    assert "sha256 distinto en predictor.json" in result.stderr


def test_verify_release_fails_on_a_missing_or_unlisted_file(tmp_path: Path) -> None:
    package = _package(tmp_path / "package")
    (package / "background.csv").unlink()
    (package / "extra.bin").write_bytes(b"\x7fELF")
    result = _run(package)
    assert result.returncode == 1
    assert "falta background.csv" in result.stderr
    assert "extra.bin no esta en el manifiesto" in result.stderr


def test_verify_release_fails_without_a_readable_manifest(tmp_path: Path) -> None:
    package = _package(tmp_path / "package")
    (package / "manifest.json").write_text("{")
    assert _run(package).returncode == 1


def test_verify_release_rejects_a_name_outside_the_directory(tmp_path: Path) -> None:
    package = _package(tmp_path / "package")
    (tmp_path / "secret.txt").write_bytes(b"s")
    manifest = {"files": [{"name": "../secret.txt", "sha256": hashlib.sha256(b"s").hexdigest()}]}
    (package / "manifest.json").write_text(json.dumps(manifest))
    assert "fuera del directorio" in _run(package).stderr


@pytest.mark.parametrize("runs", [4, 5])
def test_verify_release_out_requires_exactly_five_proxy_runs(tmp_path: Path, runs: int) -> None:
    _package(tmp_path / "package")
    for n in range(1, runs + 1):
        _package(tmp_path / "proxy" / f"run-{n}")
    result = _run("--out", tmp_path)
    assert (result.returncode == 0) == (runs == 5), result.stderr
