"""`helm template` del chart de U11 con los values de cada entorno (U11-T03): lo comparten `test_chart.py`, `test_dashboards.py`, `test_gen_rules.py` y
`test_image.py`. Es lo que Argo CD renderiza: los values del entorno, `values-product-metrics-policy.yaml` y, solo en kind, `values-kind.yaml` (P-1 = b).

Necesita `platform/install-tools.sh` (helm en `platform/.tools/bin`): si falta, las pruebas **fallan**.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / "product-metrics" / "chart"
POLICY_FILE = CHART / "values-product-metrics-policy.yaml"
KIND_VALUES = CHART / "values-kind.yaml"
BIN = ROOT / "platform" / ".tools" / "bin"
ENVS = ("kind", "staging", "prod")
Doc = dict[str, Any]


def tool(name: str) -> str:
    path = BIN / name
    assert path.is_file(), f"falta {path}: corre platform/install-tools.sh"
    return str(path)


def env_values(env: str) -> Path:
    return ROOT / "vectra-risk-gitops" / "envs" / env / "values.yaml"


def render(env: str = "kind", chart: Path = CHART, policy: Path = POLICY_FILE, *extra: str) -> list[Doc]:
    """Lo que Argo CD renderiza (`components.yaml`: los values del entorno, el archivo de parametros y, en kind, `kind_values`)."""
    command = [
        tool("helm"),
        "template",
        "product-metrics",
        str(chart),
        "-f",
        str(env_values(env)),
        "-f",
        str(policy),
    ]
    if env == "kind":
        command += ["-f", str(KIND_VALUES)]
    out = subprocess.run([*command, *extra], check=True, capture_output=True, text=True).stdout  # noqa: S603
    return [d for d in yaml.safe_load_all(out) if d]
