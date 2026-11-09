#!/usr/bin/env python3
"""Cada identificador de diseno de una unidad tiene codigo que lo implementa (Paso 18).

- `--unit <dir>`: la unidad de `aidlc-docs/construction/<dir>/`. Sin codigo todavia, falla con "sin codigo".
- `--all`: junto a `--unit` no cambia nada (lo usan los planes, `--unit X --all`). Solo, revisa cada unidad y omite
  las que aun no tienen codigo.
- Sin argumentos: `platform-foundation`.

El prefijo (`U1`) se detecta de los documentos. Las raices de codigo son `<dir>/` y la linea `Raíces de código:` del
`code/README.md` de la unidad. Un identificador que solo aparece en ese README debe nombrar, en su fila, un archivo
existente: una carpeta no dice donde esta el codigo.

Lista de «diferido por la demo» (P-4, `demo-recorte-funcional.md` §2.4): la seccion `## Diferido por la demo` de
`aidlc-docs/construction/<unidad>/evidence/cierre-demo.md`, con una fila `| <id> | <paso del plan> | <cita del recorte> | ... |`
por identificador. Un identificador de la lista no necesita codigo; si ya lo tiene, o si la fila no nombra el paso y la
cita, la prueba falla: la lista no encubre trabajo hecho ni recortes sin fuente.
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
CONSTRUCTION = ROOT / "aidlc-docs/construction"
DESIGN_FOLDERS = ("nfr-requirements", "nfr-design", "infrastructure-design", "functional-design")
#: `plans` no es una unidad.
NOT_UNITS = {"plans"}
DEFINITION = re.compile(r"^(?:\|\s*\*{0,2}|#+\s+\*{0,2})((?:BR|NFR|P|INF)-(U\d+)-\d+)\b", re.M)
SUFFIXES = {".py", ".yaml", ".yml", ".md", ".sh", ".rego", ".json", ".ts", ".tsx", ".tpl", ".toml", ".js"}
NAMES = {"Makefile", "Dockerfile"}
SKIPPED_PARTS = {".tools", ".charts", "rendered", "generated", "__pycache__", "node_modules", ".venv", "dist"}
#: Una fila que difiere a otra unidad en vez de nombrar codigo; se comprueba contra el plan de esa unidad.
DEFERRED = re.compile(r"Diferid[ao] a `([a-z-]+)`")


def definitions(unit: str) -> dict[str, set[str]]:
    """prefijo -> identificadores definidos en los documentos de la unidad."""
    found: dict[str, set[str]] = {}
    for folder in DESIGN_FOLDERS:
        for path in sorted((CONSTRUCTION / unit / folder).glob("*.md")):
            for identifier, prefix in DEFINITION.findall(path.read_text(encoding="utf-8")):
                found.setdefault(prefix, set()).add(identifier)
    return found


DEFERRED_SECTION = "## Diferido por la demo"
IDENTIFIER = re.compile(r"^(?:BR|NFR|P|INF)-U\d+-\d+[a-z]?$")


def deferred_rows(unit: str) -> dict[str, list[str]]:
    """identificador -> celdas de su fila en la seccion «Diferido por la demo» de `evidence/cierre-demo.md`."""
    path = CONSTRUCTION / unit / "evidence/cierre-demo.md"
    if not path.is_file():
        return {}
    rows: dict[str, list[str]] = {}
    inside = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.strip() == DEFERRED_SECTION
            continue
        if inside and line.startswith("|"):
            cells = [cell.strip().strip("`*") for cell in line.strip().strip("|").split("|")]
            if IDENTIFIER.match(cells[0]):
                rows[cells[0]] = cells[1:]
    return rows


def own_identifiers(unit: str) -> set[str]:
    """Los identificadores de la unidad: un documento tambien define filas que citan a otras unidades."""
    found = definitions(unit)
    if not found:
        return set()
    counts = Counter({prefix: len(ids) for prefix, ids in found.items()})
    return found[counts.most_common(1)[0][0]]


def summary_of(unit: str) -> Path:
    return CONSTRUCTION / unit / "code/README.md"


def code_roots(unit: str) -> list[Path]:
    roots = [ROOT / unit] if (ROOT / unit).is_dir() else []
    summary = summary_of(unit)
    if summary.is_file():
        line = re.search(r"^Raíces de código:(.*)$", summary.read_text(encoding="utf-8"), flags=re.M)
        for name in re.findall(r"`([^`]+)`", line.group(1)) if line else []:
            path = existing(name)
            if path:
                roots.append(path)
    return roots


def existing(name: str) -> Path | None:
    """La ruta de un README, relativa a `vectra-risk/` o a la raiz del repositorio."""
    for base in (ROOT, REPO):
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


def code_files(roots: list[Path]) -> list[Path]:
    """Este mismo archivo se omite: nombra identificadores solo como ejemplo."""
    files: list[Path] = []
    for root in roots:
        for path in [root] if root.is_file() else root.rglob("*"):
            if path.is_file() and (path.suffix in SUFFIXES or path.name in NAMES) and not SKIPPED_PARTS & set(path.parts) and path != Path(__file__).resolve():
                files.append(path)
    return files


def backed_by_a_row(unit: str) -> set[str]:
    """Identificadores con una fila del README que nombra un archivo real o difiere a una unidad cuyo plan lo cita."""
    summary = summary_of(unit)
    backed: set[str] = set()
    if not summary.is_file():
        return backed
    for line in summary.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        identifiers = set(re.findall(r"\b(?:BR|NFR|P|INF)-U\d+-\d+\b", line))
        if any(real_file(name) for name in re.findall(r"`([^`]+)`", line)):
            backed |= identifiers
        deferred = DEFERRED.search(line)
        if deferred:
            backed |= {i for i in identifiers if i in plan_text(deferred.group(1))}
    return backed


def real_file(name: str) -> bool:
    path = existing(name)
    return bool(path) and path.is_file() and path.stat().st_size > 0 and "aidlc-docs" not in path.parts


def plan_text(unit: str) -> str:
    path = CONSTRUCTION / "plans" / f"{unit}-code-generation-plan.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def with_ranges(text: str) -> str:
    """Agrega los identificadores que se citan en rango: `NFR-U0-01..03` y `br_u0_20_22` (nombre de una prueba)."""
    cited: list[str] = []
    for kind, unit, start, end in re.findall(r"\b(BR|NFR|P|INF)-(U\d+)-(\d+)\.\.(\d+)\b", text):
        cited += [f"{kind}-{unit}-{n:02d}" for n in range(int(start), int(end) + 1)]
    for unit, start, end in re.findall(r"\bbr_u(\d+)_(\d+)(?:_(\d+))?", text):
        cited += [f"BR-U{unit}-{n:02d}" for n in range(int(start), int(end or start) + 1)]
    return "\n".join([text, *cited])


def check_unit(unit: str) -> list[str]:
    """Problemas de una unidad; `sin código` si todavia no tiene."""
    if not (CONSTRUCTION / unit).is_dir():
        return [f"{unit}: la unidad no existe en aidlc-docs/construction/"]
    roots = code_roots(unit)
    files = code_files(roots)
    if not files:
        return [f"{unit}: sin código"]
    wanted = own_identifiers(unit)
    if not wanted:
        return [f"{unit}: sin identificadores en sus documentos de diseno"]
    blob = with_ranges("\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files))
    summary = summary_of(unit).read_text(encoding="utf-8") if summary_of(unit).is_file() else ""
    backed = backed_by_a_row(unit)
    deferred = deferred_rows(unit)
    problems: list[str] = []
    for identifier, cells in sorted(deferred.items()):
        if len(cells) < 2 or not cells[0] or not cells[1]:
            problems.append(f"{identifier}: la fila de «Diferido por la demo» no nombra el paso del plan y la cita del recorte")
        elif identifier in wanted and (re.search(rf"\b{re.escape(identifier)}\b", blob) or identifier in backed):
            problems.append(f"{identifier}: esta en «Diferido por la demo» pero ya tiene codigo o prueba: se quita de la lista")
    for identifier in sorted(wanted):
        if re.search(rf"\b{re.escape(identifier)}\b", blob) or identifier in backed or identifier in deferred:
            continue
        if re.search(rf"\b{re.escape(identifier)}\b", summary):
            problems.append(f"{identifier}: solo en code/README.md, y su fila no nombra un archivo existente")
        else:
            problems.append(f"{identifier}: sin trazabilidad")
    return problems


def all_units() -> list[str]:
    return sorted(p.name for p in CONSTRUCTION.iterdir() if p.is_dir() and p.name not in NOT_UNITS)


def section_identifiers(unit: str, section: str) -> set[str]:
    """`BR-U4-01, 02, 05..07` en la linea de aceptacion que pide `--section <section>`."""
    plan = CONSTRUCTION / "plans" / f"{unit}-code-generation-plan.md"
    found: set[str] = set()
    for line in plan.read_text(encoding="utf-8").splitlines():
        if f"--section {section}" not in line:
            continue
        for prefix, rest in re.findall(r"\b((?:BR|NFR|P|INF)-U\d+-)(\d+(?:(?:, |\.\.)\d+)*)", line):
            for part in rest.split(", "):
                first, _, last = part.partition("..")
                width = len(first)
                found |= {f"{prefix}{n:0{width}d}" for n in range(int(first), int(last or first) + 1)}
    return found


def report(unit: str, only: set[str] | None = None) -> int:
    problems = check_unit(unit)
    if only is not None:
        problems = [p for p in problems if p.split(":")[0] in only or p.endswith("sin código")]
    if problems:
        print("\n".join(problems))
        return 1
    print(f"{unit}: {len(own_identifiers(unit))} identificadores con trazabilidad")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit")
    parser.add_argument("--all", action="store_true")
    # Los planes piden el avance por bloque: se comprueban solo los identificadores de esa linea del plan.
    parser.add_argument("--section", choices=["logic", "api"])
    args = parser.parse_args(argv)
    if args.unit and args.section:
        return report(args.unit, section_identifiers(args.unit, args.section))
    if args.unit:
        return report(args.unit)
    if not args.all:
        return report("platform-foundation")
    failures = 0
    for unit in all_units():
        if check_unit(unit) == [f"{unit}: sin código"]:
            print(f"{unit}: sin código, se omite")
            continue
        failures += report(unit)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
