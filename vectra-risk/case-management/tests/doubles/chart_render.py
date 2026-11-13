"""El render del chart de U8 con los values que usa Argo CD (para `test_image.py`): `components.yaml`, `generate.value_files` y `helm template`.

Patron de `bias-monitoring/tests/doubles/chart_render.py`; ninguna unidad importa las pruebas de otra.
"""

import importlib.util
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
GITOPS = ROOT / "vectra-risk-gitops"
BIN = ROOT / "platform" / ".tools" / "bin"
Doc = dict[str, Any]


def _generate() -> Any:
    spec = importlib.util.spec_from_file_location("gitops_generate", GITOPS / "generate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render(env: str = "kind", *extra: str) -> list[Doc]:
    """`helm template` de `case-management/chart` con los values del entorno, en el orden en que los pasa Argo CD."""
    helm = BIN / "helm"
    assert helm.is_file(), f"falta {helm}: corre platform/install-tools.sh"
    components = yaml.safe_load((GITOPS / "components.yaml").read_text(encoding="utf-8"))["components"]
    component = next(c for c in components if c["name"] == "case-management")
    command = [
        str(helm),
        "template",
        "case-management",
        str(ROOT / "case-management" / "chart"),
        "-n",
        "vectra-app",
    ]
    for path in [
        GITOPS / "envs" / env / "values.yaml",
        *(ROOT / f for f in _generate().value_files(component, env)),
    ]:
        command += ["-f", str(path)]
    out = subprocess.run([*command, *extra], check=True, capture_output=True, text=True).stdout  # noqa: S603
    return [d for d in yaml.safe_load_all(out) if d]
