"""Valores del diseno del controlador de Envoy Gateway (U02-T10, Paso 8), leidos de los documentos."""

import re
from pathlib import Path

from design_values import INFRASTRUCTURE, section, table_rows

_ROOT = Path(__file__).resolve().parents[3]
_FD = _ROOT / "aidlc-docs" / "construction" / "identity-edge"
NFR_REQUIREMENTS = (_FD / "nfr-requirements" / "nfr-requirements.md").read_text(encoding="utf-8")
NFR_PATTERNS = (_FD / "nfr-design" / "nfr-design-patterns.md").read_text(encoding="utf-8")
LOGICAL = (_FD / "nfr-design" / "logical-components.md").read_text(encoding="utf-8")
PLAN = (_ROOT / "aidlc-docs" / "construction" / "plans" / "identity-edge-code-generation-plan.md").read_text(encoding="utf-8")
DEPENDENCY = (_ROOT / "aidlc-docs" / "inception" / "application-design" / "component-dependency.md").read_text(encoding="utf-8")


def controller_replicas() -> int:
    row = next(r for r in table_rows(NFR_REQUIREMENTS) if r[0] == "NFR-U2-03")
    return int(re.search(r"Controlador de Envoy Gateway: (\d+) r", row[1]).group(1))  # type: ignore[union-attr]


def controller_priority() -> str:
    row = next(r for r in table_rows(LOGICAL) if r[0].startswith("Envoy Gateway (controlador)"))
    return row[-1].strip("`")


def _quantity(text: str) -> str:
    cpu, mem = (p.strip() for p in text.split("/"))
    return cpu, mem.replace(" MiB", "Mi").replace(" GiB", "Gi")  # type: ignore[return-value]


def controller_resources() -> dict[str, dict[str, str]]:
    row = next(r for r in table_rows(section(INFRASTRUCTURE, "### INF-U2-06")) if r[0] == "Controlador de Envoy Gateway")
    out = {}
    for key, cell in (("requests", row[1]), ("limits", row[2])):
        cpu, mem = _quantity(cell)
        out[key] = {"cpu": cpu, "memory": mem}
    return out


def patch_policy_key() -> str:
    body = section(NFR_PATTERNS, "### P-U2-01")
    return re.search(r"`extensionApis\.(\w+)`", body).group(1)  # type: ignore[union-attr]


def deploy_type() -> str:
    return re.search(r"`deploy\.type: (\w+)`", PLAN).group(1)  # type: ignore[union-attr]


def k14_row() -> str:
    return next(r for r in table_rows(DEPENDENCY) if r[0] == "K14")[3]


def shutdown_manager_image() -> str:
    """X3: el espejo de la imagen del controlador para el `shutdown-manager` (staging y prod; kind lleva `kind-registry`)."""
    text = section(INFRASTRUCTURE, "### INF-U2-02")
    line = next(ln for ln in text.splitlines() if ln.startswith("  - **Imagen del data plane**"))
    found = re.search(r"Es `(registro[\w./-]+)` \(`kind-registry[\w.:/-]+` en kind\).*digest de upstream `(sha256:[0-9a-f]{64})`", line)
    assert found, "INF-U2-02 sin la imagen del shutdown-manager"
    return f"{found.group(1)}@{found.group(2)}"
