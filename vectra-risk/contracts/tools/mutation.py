"""Mutacion con mutmut (NFR-U0-41) en un directorio temporal con layout `src/`.

mutmut 3 solo reconoce los modulos de `src/`; este monorepo los tiene mas adentro.
Uso: `uv run python contracts/tools/mutation.py [--workdir DIR]`.
"""

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST = ROOT / "contracts/tests/mutmut-allowlist.txt"
CONFIG = """[mutmut]
paths_to_mutate=
    src/
tests_dir=tests/
also_copy=
    src/vectra_contracts/data
do_not_mutate=
    src/vectra_contracts/catalog.py
    src/vectra_contracts/canonical.py
    src/vectra_contracts/dane.py
    src/vectra_contracts/decimal_ctx.py
    src/vectra_contracts/dictionary.py
    src/vectra_contracts/errors.py
    src/vectra_contracts/finance.py
    src/vectra_contracts/labels.py
    src/vectra_contracts/validation.py
    src/vectra_contracts/__init__.py
    src/vectra_contracts/models/*
    src/vectra_contracts/routes/*
    src/vectra_contracts/data/*
    src/vectra_contracts/outcome/_internal.py
    src/vectra_common/__init__.py
    src/vectra_common/app_factory.py
    src/vectra_common/authn.py
    src/vectra_common/decimal_ctx.py
    src/vectra_common/errors.py
    src/vectra_common/jwks_cache.py
    src/vectra_common/logging.py
    src/vectra_common/metrics.py
    src/vectra_common/ops_server.py
    src/vectra_common/process.py
    src/vectra_common/telemetry.py
"""
TESTS = {
    "unit/test_outcome.py",
    "unit/test_authz.py",
    "unit/test_deps.py",
    "unit/test_deps_extra.py",
    "unit/test_deps_tokens.py",
    "unit/test_service_token.py",
    "unit/test_deadline.py",
    "unit/test_require_app.py",
    "examples/test_logic_examples.py",
    "examples/test_api_examples.py",
    "property/test_common.py",
    "property/test_deps_stateful.py",
}
PYTEST = """[tool.pytest.ini_options]
pythonpath = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
markers = ["common: a", "logic: b", "api: c", "benchmark: d"]
"""


def prepare(work: Path) -> None:
    shutil.copytree(
        ROOT / "contracts/python/vectra_contracts/src/vectra_contracts", work / "src/vectra_contracts"
    )
    shutil.copytree(ROOT / "contracts/python/vectra_common/src/vectra_common", work / "src/vectra_common")
    shutil.copytree(
        ROOT / "contracts/tests", work / "tests", ignore=shutil.ignore_patterns("bench", "__pycache__")
    )
    for path in (work / "tests").rglob("test_*.py"):
        if path.relative_to(work / "tests").as_posix() not in TESTS:
            path.unlink()
    (work / "setup.cfg").write_text(CONFIG, encoding="utf-8")
    (work / "pyproject.toml").write_text(PYTEST, encoding="utf-8")


def status_of(code: int | None) -> str:
    """Estado de un mutante segun su codigo de salida; lo desconocido nunca cuenta como eliminado."""
    if code is None:
        return "not checked"
    if code in (1, 3):
        return "killed"
    if code == 0:
        return "survived"
    if code == 5:
        return "no tests"
    if code in (24, -24, 36, 152, 255):
        return "timeout"
    return "not checked"


def results(work: Path) -> dict[str, list[str]]:
    """Lee los metadatos: `mutmut results` no imprime nada cuando no hay sobrevivientes."""
    grouped: dict[str, list[str]] = {}
    for meta in (work / "mutants").rglob("*.meta"):
        for name, code in json.loads(meta.read_text(encoding="utf-8"))["exit_code_by_key"].items():
            grouped.setdefault(status_of(code), []).append(name)
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir")
    args = parser.parse_args()
    work = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="vectra-mut-"))
    if not (work / "setup.cfg").exists():
        work.mkdir(parents=True, exist_ok=True)
        prepare(work)
    env = {**os.environ, "HYPOTHESIS_PROFILE": "dev"}
    run = subprocess.run(
        [sys.executable, "-m", "mutmut", "run", "--max-children", str(os.cpu_count() or 2)],
        cwd=work,
        env=env,
        check=False,
    )
    grouped = results(work)
    allowed = [line.split("#")[0].strip() for line in ALLOWLIST.read_text(encoding="utf-8").splitlines()]
    left = [
        n
        for n in grouped.get("survived", []) + grouped.get("no tests", [])
        if not any(p and fnmatch.fnmatch(n, p) for p in allowed)
    ]
    print(f"workdir: {work}")
    print("estados:", {status: len(names) for status, names in sorted(grouped.items())})
    print(f"sobrevivientes sin justificar: {len(left)}")
    for name in left:
        print(" ", name)
    # Una corrida fallida, o con mutantes sin comprobar, nunca es un resultado aprobado.
    incomplete = run.returncode != 0 or not grouped or "not checked" in grouped
    if incomplete:
        print("corrida incompleta")
    return 1 if left or incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
