"""`helm template` del chart de U9 con los values de cada entorno (U09-T04): lo comparten `test_chart.py` y `test_image.py`.

Necesita `platform/install-tools.sh` (helm en `platform/.tools/bin`): si falta, las pruebas **fallan**.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / "bias-monitoring" / "chart"
POLICY_FILE = CHART / "values-monitoring-policy.yaml"
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
    """Lo que Argo CD renderiza: los values del entorno y `values-monitoring-policy.yaml`."""
    out = subprocess.run(  # noqa: S603
        [
            tool("helm"),
            "template",
            "bias-monitoring",
            str(chart),
            "-f",
            str(env_values(env)),
            "-f",
            str(policy),
            *extra,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [d for d in yaml.safe_load_all(out) if d]
