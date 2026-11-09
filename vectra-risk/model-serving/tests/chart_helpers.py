"""Render del chart de U6 y `conftest` sobre el resultado (Pasos 6 y 7). Necesita `platform/install-tools.sh` (helm y conftest)."""

import copy
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "model-serving" / "chart"
POLICY = ROOT / "model-serving" / "policies" / "conftest"
FIXTURES = ROOT / "model-serving" / "tests" / "fixtures"
BIN = ROOT / "platform" / ".tools" / "bin"
Doc = dict[str, Any]


def tool(name: str) -> str:
    path = BIN / name
    assert path.is_file(), f"falta {path}: corre platform/install-tools.sh"
    return str(path)


def helm(values: Path | None = None, *extra: str) -> subprocess.CompletedProcess[str]:
    args = [tool("helm"), "template", "ms", str(CHART), *extra]
    if values is not None:
        args += ["-f", str(values)]
    return subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603


def render(values: Path | None = None, *extra: str) -> list[Doc]:
    result = helm(values, *extra)
    assert result.returncode == 0, result.stderr
    return [d for d in yaml.safe_load_all(result.stdout) if d]


def render_profile(profile: str) -> list[Doc]:
    return render(FIXTURES / f"values-{profile}.yaml")


def conftest(docs: list[Doc], *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [tool("conftest"), "test", "--policy", str(POLICY), *extra, "-"],
        input=yaml.safe_dump_all(docs, sort_keys=False),
        capture_output=True,
        text=True,
        check=False,
    )


def failures(docs: list[Doc]) -> str:
    """Los mensajes de las dos pasadas: por documento (`main`) y con todos juntos (`chart_set`)."""
    single = conftest(docs)
    combined = conftest(docs, "--combine", "--namespace", "chart_set")
    return single.stdout + single.stderr + combined.stdout + combined.stderr


def passes(docs: list[Doc]) -> bool:
    return (
        conftest(docs).returncode == 0
        and conftest(docs, "--combine", "--namespace", "chart_set").returncode == 0
    )


def of_kind(docs: list[Doc], kind: str) -> list[Doc]:
    return [d for d in docs if d["kind"] == kind]


def isvcs(docs: list[Doc]) -> list[Doc]:
    return of_kind(docs, "InferenceService")


def edit(docs: list[Doc], change: Callable[[list[Doc]], None]) -> list[Doc]:
    copied = copy.deepcopy(docs)
    change(copied)
    return copied
