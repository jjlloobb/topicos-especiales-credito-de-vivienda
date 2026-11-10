"""F-01 (ronda 1 de U08-T02): el token de construccion de `Recommendation` (P-U0-03, capa 3) no sale de `views` ni llega a otro modulo.

Rodeo temporal hasta que una tarea de U0 publique una via publica de lectura de `CaseDetail`; entonces estas pruebas se retiran
junto con la excepcion de `.importlinter`.
"""

import subprocess
from pathlib import Path
from typing import Any

from vectra_case import views
from vectra_contracts.outcome._internal import CONSTRUCTION_TOKEN

ROOT = Path(__file__).resolve().parents[3]  # vectra-risk/
SRC = ROOT / "case-management" / "src" / "vectra_case"


def _holds_token(value: Any, depth: int = 0) -> bool:
    if value is CONSTRUCTION_TOKEN:
        return True
    if depth > 3:
        return False
    if isinstance(value, dict):
        return any(_holds_token(k, depth + 1) or _holds_token(v, depth + 1) for k, v in value.items())
    if isinstance(value, list | tuple | set | frozenset):
        return any(_holds_token(v, depth + 1) for v in value)
    return False


def test_no_name_of_the_views_module_holds_the_token():
    assert not [name for name, value in vars(views).items() if _holds_token(value)]
    assert not hasattr(views, "_CONTEXT")
    assert not hasattr(views, "CONSTRUCTION_TOKEN")


def _lint_imports() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "lint-imports", "--config", "case-management/.importlinter"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_another_module_importing_the_token_breaks_lint_imports():
    probe = SRC / "sweeps.py"
    original = probe.read_text()
    try:
        probe.write_text(
            original + "\nfrom vectra_contracts.outcome._internal import CONSTRUCTION_TOKEN  # noqa: F401\n"
        )
        broken = _lint_imports()
    finally:
        probe.write_text(original)
    assert broken.returncode != 0
    assert "private-token" in broken.stdout or "token privado" in broken.stdout
    assert "BROKEN" in broken.stdout
    assert _lint_imports().returncode == 0
