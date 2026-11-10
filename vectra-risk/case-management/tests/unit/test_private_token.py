"""F-01 (ronda 1 de U08-T02), cerrado por U00-T03: `vectra_case` no toca el token de construccion de `Recommendation` (P-U0-03, capa 3).

`views.case_detail` anida la instancia ya construida de `CaseRow.recommendation`; el token no sale de `outcome`. La prueba de AST de
U0 (`contracts/tests/unit/test_token_privado_workspace.py`) cubre todo el workspace; aqui se comprueba lo propio de U8.
"""

import configparser
import subprocess
from pathlib import Path

from vectra_case import views

ROOT = Path(__file__).resolve().parents[3]  # vectra-risk/


def test_no_name_of_the_views_module_holds_the_token():
    assert not [name for name, value in vars(views).items() if type(value).__name__ == "_Token"]
    assert not hasattr(views, "_CONTEXT")


def test_private_token_contract_has_no_exceptions():
    config = configparser.ConfigParser()
    config.read(ROOT / "case-management" / ".importlinter")
    contract = config["importlinter:contract:private-token"]
    assert "ignore_imports" not in contract
    assert contract["source_modules"].split() == ["vectra_case"]


def test_lint_imports_keeps_every_contract():
    run = subprocess.run(
        ["uv", "run", "lint-imports", "--config", "case-management/.importlinter"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout
    assert "BROKEN" not in run.stdout
