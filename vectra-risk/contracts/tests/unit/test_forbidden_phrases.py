"""BR-U0-94, NFR-U0-47."""

import subprocess
import sys
from pathlib import Path

import pytest
from tools.forbidden_phrases import find_violations, load_patterns

PATTERNS = load_patterns()


@pytest.mark.parametrize("text", ["Modelo LIBRE DE SESGO", "Sin sésgo", "Sin sésgos"])
def test_br_u0_94_fails(text):
    assert find_violations(text, PATTERNS)


@pytest.mark.parametrize("text", ["modelo imparcialmente auditado", "unbiasedness", "mide y alerta, no certifica"])
def test_br_u0_94_passes(text):
    assert not find_violations(text, PATTERNS)


def test_br_u0_94_cli_reports_file_line_phrase(tmp_path: Path):
    target = tmp_path / "t.txt"
    target.write_text("ok\nsistema imparcial\n", encoding="utf-8")
    tool = Path(__file__).resolve().parents[2] / "tools" / "forbidden_phrases.py"
    result = subprocess.run([sys.executable, str(tool), str(target)], capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert f"{target}:2" in result.stdout and "sistema imparcial" in result.stdout


def test_br_u0_94_codeowners():
    root = Path(__file__).resolve().parents[4]
    assert "contracts/forbidden-phrases.yaml" in (root / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
