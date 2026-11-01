"""La herramienta de mutacion nunca da un resultado aprobado falso (NFR-U0-41)."""

import subprocess
from pathlib import Path

import pytest
from tools import mutation

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def work(tmp_path, monkeypatch):
    (tmp_path / "setup.cfg").write_text("", encoding="utf-8")
    allow = tmp_path / "allow.txt"
    allow.write_text("permitido*  # motivo\n", encoding="utf-8")
    monkeypatch.setattr(mutation, "ALLOWLIST", allow)
    monkeypatch.setattr("sys.argv", ["mutation.py", "--workdir", str(tmp_path)])
    return tmp_path


def run_with(monkeypatch, code, grouped):
    monkeypatch.setattr(mutation.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, code))
    monkeypatch.setattr(mutation, "results", lambda _: grouped)
    return mutation.main()


def test_clean_run_passes(work, monkeypatch):
    assert run_with(monkeypatch, 0, {"killed": ["a"]}) == 0


def test_failed_run_never_passes(work, monkeypatch):
    assert run_with(monkeypatch, 1, {"killed": ["a"]}) == 1


def test_no_results_never_passes(work, monkeypatch):
    assert run_with(monkeypatch, 0, {}) == 1


def test_unchecked_mutants_never_pass(work, monkeypatch):
    assert run_with(monkeypatch, 0, {"not checked": ["a"]}) == 1


def test_survivor_fails_unless_allowed(work, monkeypatch):
    assert run_with(monkeypatch, 0, {"survived": ["otro"]}) == 1
    assert run_with(monkeypatch, 0, {"survived": ["permitido_1"]}) == 0


def test_no_lines_excluded_from_mutation():
    """Excluir una linea reduce lo que mide la mutacion: se reemplaza por una prueba o por diseno."""
    marked = [p for p in (ROOT / "python").rglob("*.py") if "no mutate" in p.read_text(encoding="utf-8")]
    assert marked == []


def test_results_read_from_metadata(tmp_path):
    meta = tmp_path / "mutants/src/a.py.meta"
    meta.parent.mkdir(parents=True)
    meta.write_text('{"exit_code_by_key": {"k": 1, "s": 0, "n": null, "t": -24, "x": 5, "raro": 99}}', encoding="utf-8")
    grouped = mutation.results(tmp_path)
    assert grouped == {"killed": ["k"], "survived": ["s"], "not checked": ["n", "raro"], "timeout": ["t"], "no tests": ["x"]}


def test_mutant_without_tests_fails(work, monkeypatch):
    assert run_with(monkeypatch, 0, {"no tests": ["sin_prueba"]}) == 1
