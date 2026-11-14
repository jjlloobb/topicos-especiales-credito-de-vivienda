"""Lo que comparten las pruebas de la guia de kind (U12-T06): las rutas, el inventario y los documentos que lo atan al repositorio.

Nada de esto toca un cluster: solo lee archivos del repositorio. La guia (`docs/paso-18-kind.md`), el inventario (`docs/kind/inventario.yaml`) y las plantillas de
evidencia salen de la misma lista; las pruebas de `test_kind_inventory.py`, `test_kind_guide.py` y `test_kind_scripts.py` la recorren.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, NamedTuple

import yaml

SYSTEM = Path(__file__).resolve().parents[2]
VECTRA = SYSTEM.parent
DOCS = SYSTEM / "docs"
KIND_DOCS = DOCS / "kind"
GUIDE = DOCS / "paso-18-kind.md"
INVENTORY = KIND_DOCS / "inventario.yaml"
EVIDENCE = VECTRA / "aidlc-docs/construction/system-verification/evidence"
TEMPLATES = EVIDENCE / "kind"
CLOSURE = EVIDENCE / "cierre-demo.md"
TASK = VECTRA / "tareas/U12-T06-verificacion-en-kind-y-cierre.md"
PHASES = tuple(f"F{n}" for n in range(12))
DEFERRED_SECTIONS = ("network", "pii", "load", "resilience", "rt1", "rt4")
CLI_SECTIONS = ("prepare", "decisions", "rt5", "rt3", "rt2-setup", "rt2", "u11", "report")


class Source(NamedTuple):
    path: str
    first: int
    last: int


def load_inventory() -> dict[str, Any]:
    data = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def entries() -> list[dict[str, Any]]:
    return list(load_inventory()["entradas"])


def parse_source(text: str, abbreviations: dict[str, str]) -> Source:
    """`C-U7:41` o `T05:358-359` o una ruta desde `vectra-risk/`: la ruta y el rango de lineas."""
    head, _, tail = text.rpartition(":")
    first, _, last = tail.partition("-")
    return Source(abbreviations.get(head, head), int(first), int(last or first))


def sources(entry: dict[str, Any], abbreviations: dict[str, str]) -> list[Source]:
    return [parse_source(str(s), abbreviations) for s in entry["fuentes"]]


def line_count(path: str) -> int:
    return len((VECTRA / path).read_text(encoding="utf-8").splitlines())


def section_lines(path: str, heading: str, *, rows: bool = True) -> list[int]:
    """Los numeros de linea de las filas de tabla (sin el encabezado) y las vinietas de la seccion `## <heading>...` de un Markdown."""
    lines = (VECTRA / path).read_text(encoding="utf-8").splitlines()
    inside, found = False, []
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            inside = line.startswith(f"## {heading}")
            continue
        if not inside:
            continue
        following = lines[number] if number < len(lines) else ""
        if line.startswith("- ") or (
            rows and line.startswith("|") and not line.startswith("|---") and not following.startswith("|---")
        ):
            found.append(number)
    return found


def acotado_rows_for_u12() -> list[int]:
    """Las filas de `cierre-acotado.md`, seccion «No comprobado o incompleto», cuyo destino nombra a U12."""
    path = "aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md"
    found = []
    for number in section_lines(path, "No comprobado o incompleto"):
        cells = [
            c.strip() for c in (VECTRA / path).read_text(encoding="utf-8").splitlines()[number - 1].split("|")
        ]
        cells = [c for c in cells if c]
        if cells and "U12" in cells[-1]:
            found.append(number)
    return found


def task_candidate_lines() -> list[int]:
    """Los numeros de linea de `CANDIDATAS.md` de la tabla «Se atienden aqui» de la tarea U12-T06."""
    found: list[int] = []
    inside = False
    for line in TASK.read_text(encoding="utf-8").splitlines():
        if line.startswith("**Se atienden aqu"):
            inside = True
            continue
        if line.startswith("**Se quedan"):
            break
        if inside and line.startswith("|") and not line.startswith("|---"):
            first = line.split("|")[1]
            found += [int(n) for n in re.findall(r"\d+", first)]
    return found


# --- las fuentes del repositorio que la guia nombra --------------------------------------------------------------------------------------------------


def read(path: str) -> str:
    return (VECTRA / path).read_text(encoding="utf-8")


def applications() -> set[str]:
    return {p.stem for p in (VECTRA / "vectra-risk-gitops/apps/kind").glob("*.yaml")} - {
        "project",
        "root",
    } | {"root"}


def components() -> set[str]:
    return set(re.findall(r"\{ name: ([a-z0-9-]+),", read("vectra-risk-gitops/components.yaml")))


def namespaces() -> set[str]:
    flows = yaml.safe_load(read("platform/network/flows.yaml"))
    return set(flows["meshed_namespaces"]) | set(flows["system_namespaces"])


def realm_users() -> dict[str, set[str]]:
    realm = yaml.safe_load(read("identity-edge/keycloak/realm/realm.kind.yaml").replace("$(env:", "(env:"))
    return {u["username"]: set(u.get("realmRoles", [])) for u in realm["users"]}


def spa_routes() -> set[str]:
    return set(re.findall(r'path: "([^"]+)"', read("console/spa/src/views/shared/routes.ts")))


_SKIP = {
    ".venv", "node_modules", ".tools", ".charts", ".git", "system-verification", "tareas", "aidlc-docs", "bitacoras", "revisiones", "entradas", "__pycache__", "loop",
}  # fmt: skip
_corpus: list[str] = []


def corpus() -> str:
    """El texto de reglas, metricas, charts y codigo del repositorio (no de U12 ni de la documentacion): donde tiene que existir una serie, una alerta o un selector."""
    if not _corpus:
        chunks = []
        for path in VECTRA.rglob("*"):
            relative = path.relative_to(VECTRA)
            if (
                path.is_file()
                and path.suffix in {".py", ".yaml", ".yml", ".json", ".rego", ".ts", ".tpl"}
                and not _SKIP & set(relative.parts)
            ):
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
        for extra in ("src/vectra_verification/clients", "demos/verify"):
            for path in (SYSTEM / extra).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
        _corpus.append("\n".join(chunks))
    return _corpus[0]


# --- lo que sale del inventario: las tablas de cada fase de la guia -----------------------------------------------------------------------------------


def how(check: str) -> str:
    """La comprobacion de una entrada como se escribe en la guia."""
    kind, _, value = check.partition(":")
    if kind == "seccion":
        return f"`vectra-verification {value}`"
    if kind == "manual":
        return f"a mano: {value}"
    if kind == "guion" and value.startswith("humo.py"):
        return f"`humo {value.split(' ', 1)[1]}`" if " " in value else "`humo`"
    return f"`{value}`"


def render_phase_table(phase: str) -> str:
    """La tabla de entradas de una fase: la guia la repite tal cual y una prueba la compara con el inventario (una sola verdad)."""
    rows = ["| Id | Qué se mira | Cómo (solo lectura) | Demo |", "|---|---|---|---|"]
    for entry in entries():
        if entry["fase"] != phase:
            continue
        demo = ", ".join(entry["demo"]) if entry["demo"] else "—"
        cell = "; ".join(how(c) for c in entry["comprobacion"])
        rows.append(f"| {entry['id']} | {entry['que']} | {cell} | {demo} |")
    return "\n".join(rows)
