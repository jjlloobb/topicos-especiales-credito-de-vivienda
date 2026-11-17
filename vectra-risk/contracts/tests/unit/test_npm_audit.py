"""La excepcion de la auditoria de npm es de un solo aviso y caduca (U00-T06)."""

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest
from tools import npm_audit

ROOT = Path(__file__).resolve().parents[2]
VIGENTE = npm_audit.EXEMPT_UNTIL
CADUCADA = VIGENTE + datetime.timedelta(days=1)


def advisory(ghsa: str, severity: str = "high") -> dict:
    return {"name": "x", "severity": severity, "url": f"https://github.com/advisories/{ghsa}"}


def report(**vulns: dict) -> dict:
    return {"vulnerabilities": vulns}


def picomatch_tree(extra: list | None = None) -> dict:
    return report(
        picomatch={"severity": "high", "via": [advisory(npm_audit.EXEMPT_ADVISORY), *(extra or [])]},
        vite={"severity": "high", "via": ["picomatch", "tinyglobby"]},
        tinyglobby={"severity": "high", "via": ["picomatch", "fdir"]},
        fdir={"severity": "high", "via": ["picomatch"]},
    )


def test_the_exempt_advisory_in_force_is_green():
    blocking, exempt = npm_audit.evaluate(picomatch_tree(), VIGENTE)
    assert blocking == []
    assert exempt == ["fdir", "picomatch", "tinyglobby", "vite"]


def test_the_exempt_advisory_expired_is_red():
    blocking, exempt = npm_audit.evaluate(picomatch_tree(), CADUCADA)
    assert blocking == ["fdir", "picomatch", "tinyglobby", "vite"]
    assert exempt == []


def test_another_high_advisory_is_red():
    blocking, _ = npm_audit.evaluate(report(lodash={"severity": "high", "via": [advisory("GHSA-aaaa-bbbb-cccc")]}), VIGENTE)
    assert blocking == ["lodash"]


def test_critical_is_red():
    blocking, _ = npm_audit.evaluate(report(x={"severity": "critical", "via": [advisory("GHSA-aaaa-bbbb-cccc", "critical")]}), VIGENTE)
    assert blocking == ["x"]


def test_another_advisory_behind_the_same_package_is_red():
    tree = picomatch_tree([advisory("GHSA-aaaa-bbbb-cccc")])
    blocking, _ = npm_audit.evaluate(tree, VIGENTE)
    assert "vite" in blocking and "picomatch" in blocking


def test_moderate_and_low_do_not_block():
    blocking, exempt = npm_audit.evaluate(report(x={"severity": "moderate", "via": [advisory("GHSA-aaaa-bbbb-cccc", "moderate")]}), VIGENTE)
    assert (blocking, exempt) == ([], [])


def test_a_high_package_with_no_advisory_is_red():
    blocking, _ = npm_audit.evaluate(report(x={"severity": "high", "via": ["ghost"]}), VIGENTE)
    assert blocking == ["x"]


def test_cyclic_dependencies_end():
    tree = report(a={"severity": "high", "via": ["b", advisory("GHSA-aaaa-bbbb-cccc")]}, b={"severity": "high", "via": ["a"]})
    assert npm_audit.evaluate(tree, VIGENTE)[0] == ["a", "b"]


@pytest.mark.parametrize("bad", [{}, {"error": {"code": "ENOAUDIT"}}, {"vulnerabilities": []}])
def test_an_unexpected_answer_is_red(bad):
    blocking, _ = npm_audit.evaluate(bad, VIGENTE)
    assert blocking


def run_main(tmp_path, content: str, *args: str) -> int:
    path = tmp_path / "audit.json"
    path.write_text(content, encoding="utf-8")
    return npm_audit.main(["--from-file", str(path), *args])


def test_main_exit_codes(tmp_path, capsys):
    tree = json.dumps(picomatch_tree())
    assert run_main(tmp_path, tree, "--today", VIGENTE.isoformat()) == 0
    assert "hasta" in capsys.readouterr().out
    assert run_main(tmp_path, tree, "--today", CADUCADA.isoformat()) == 1
    assert "caducada" in capsys.readouterr().out
    assert run_main(tmp_path, json.dumps(report(x={"severity": "high", "via": [advisory("GHSA-aaaa-bbbb-cccc")]})), "--today", VIGENTE.isoformat()) == 1
    assert run_main(tmp_path, "no es json") == 1
    assert run_main(tmp_path, json.dumps(report())) == 0


def test_main_without_a_file_runs_npm_audit(monkeypatch):
    seen = []

    def fake(cmd, **kwargs):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, stdout=json.dumps(report()))

    monkeypatch.setattr(npm_audit.subprocess, "run", fake)
    assert npm_audit.main([]) == 0
    assert seen == [["npm", "audit", "--json"]]


def test_the_workflow_runs_the_script_and_not_a_weaker_audit():
    text = (ROOT.parents[1] / ".github/workflows/contracts.yml").read_text(encoding="utf-8")
    assert "uv run python contracts/tools/npm_audit.py" in text
    assert "--omit=dev" not in text and "continue-on-error" not in text


def test_the_script_runs_as_a_program(tmp_path):
    path = tmp_path / "a.json"
    path.write_text(json.dumps(report()), encoding="utf-8")
    done = subprocess.run([sys.executable, str(ROOT / "tools/npm_audit.py"), "--from-file", str(path)], capture_output=True, text=True, check=False)
    assert done.returncode == 0
