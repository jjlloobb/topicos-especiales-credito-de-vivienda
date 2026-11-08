"""Los contratos de import-linter de U5 (NFR-U5-30..32) se rompen cuando deben, y `confidence` solo importa numpy."""

import ast
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[2] / "src" / "vectra_reference"
CONFIG = Path(__file__).resolve().parents[2] / ".importlinter"
LINT = Path(sys.executable).parent / "lint-imports"


def _lint(src_root: Path) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": str(src_root), "PATH": str(LINT.parent)}
    return subprocess.run(  # noqa: S603
        [str(LINT), "--config", str(CONFIG)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=src_root,
    )


def test_the_three_contracts_are_kept_on_the_real_tree() -> None:
    result = _lint(PKG.parent)
    assert result.returncode == 0, result.stdout
    assert result.stdout.count("KEPT") == 3, result.stdout


@pytest.mark.parametrize(
    ("module", "statement", "broken"),
    [
        ("envelope/confidence.py", "import sklearn", "envelope.confidence importa solo numpy"),
        ("envelope/confidence.py", "import xgboost", "envelope.confidence importa solo numpy"),
        ("generate.py", "import sklearn", "solo envelope.fit importa sklearn"),
        ("train.py", "import shap", "solo la validacion del explicador importa shap"),
    ],
)
def test_a_forbidden_import_breaks_its_contract(
    tmp_path: Path, module: str, statement: str, broken: str
) -> None:
    copy = tmp_path / "src"
    shutil.copytree(PKG, copy / "vectra_reference")
    target = copy / "vectra_reference" / module
    target.write_text(target.read_text() + f"\n{statement}\n")
    result = _lint(copy)
    assert result.returncode != 0, result.stdout
    assert f"{broken}" in result.stdout and "BROKEN" in result.stdout, result.stdout


def test_envelope_fit_may_import_sklearn(tmp_path: Path) -> None:
    copy = tmp_path / "src"
    shutil.copytree(PKG, copy / "vectra_reference")
    target = copy / "vectra_reference" / "envelope" / "fit.py"
    target.write_text(target.read_text() + "\nimport sklearn\n")
    assert _lint(copy).returncode == 0


def test_confidence_imports_only_numpy_and_the_standard_library() -> None:
    tree = ast.parse((PKG / "envelope" / "confidence.py").read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    assert roots <= {"numpy", "__future__"} | set(sys.stdlib_module_names), roots
