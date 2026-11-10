"""F-01 (ronda 1 de U08-T02), cerrado por U00-T03: `vectra_case` no toca el token de construccion de `Recommendation` (P-U0-03, capa 3).

`views.case_detail` anida la instancia ya construida de `CaseRow.recommendation`; el token no sale de `outcome`. La prueba de AST de
U0 (`contracts/tests/unit/test_token_privado_workspace.py`) cubre todo el workspace; aqui se comprueba lo propio de U8. Ninguna prueba
escribe en `src/`: la negativa usa un paquete y una configuracion temporales (F-03 de la ronda 1 de U00-T03).
"""

import configparser
import os
import subprocess
from pathlib import Path
from typing import Any

from vectra_case import views

ROOT = Path(__file__).resolve().parents[3]  # vectra-risk/
CONFIG = ROOT / "case-management" / ".importlinter"


def _holds_token(value: Any, depth: int = 0) -> bool:
    if type(value).__name__ == "_Token":
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
    assert not hasattr(views, "CONSTRUCTION" + "_TOKEN")


def test_the_container_search_finds_a_token_inside_containers():
    class _Token:  # mismo nombre de tipo que el token real; la prueba no lo importa
        pass

    token = _Token()
    assert _holds_token({"a": [token]})
    assert not _holds_token({"a": [1, "x"]})


def test_private_token_contract_has_no_exceptions():
    config = configparser.ConfigParser()
    config.read(CONFIG)
    contract = config["importlinter:contract:private-token"]
    assert "ignore_imports" not in contract
    assert contract["source_modules"].split() == ["vectra_case"]


def _lint(config: Path, cwd: Path, extra_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ}
    if extra_path is not None:
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(extra_path), env.get("PYTHONPATH")]))
    return subprocess.run(
        ["uv", "run", "--project", str(ROOT), "lint-imports", "--config", str(config)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_lint_imports_keeps_every_contract():
    run = _lint(CONFIG, ROOT)
    assert run.returncode == 0, run.stdout
    assert "BROKEN" not in run.stdout


def test_another_module_importing_the_token_breaks_the_private_token_contract(tmp_path: Path):
    """Negativa: se copia el contrato real a una configuracion temporal y un paquete temporal (fuera de `src/`) que importa el token."""
    real = configparser.ConfigParser()
    real.read(CONFIG)
    section = real["importlinter:contract:private-token"]
    pkg = tmp_path / "probe_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("from vectra_contracts.outcome import _internal  # noqa: F401\n")
    cfg = tmp_path / ".importlinter"
    cfg.write_text(
        "[importlinter]\nroot_packages =\n    probe_pkg\n    vectra_contracts\ninclude_external_packages = True\n"
        "[importlinter:contract:private-token]\nname = token privado\ntype = forbidden\nsource_modules =\n    probe_pkg\n"
        f"forbidden_modules =\n    {section['forbidden_modules'].strip()}\nallow_indirect_imports = True\n"
    )
    broken = _lint(cfg, tmp_path, extra_path=tmp_path)
    assert broken.returncode != 0, broken.stdout
    assert "BROKEN" in broken.stdout
    (pkg / "mod.py").write_text("x = 1\n")
    assert _lint(cfg, tmp_path, extra_path=tmp_path).returncode == 0
