#!/usr/bin/env python3
"""Runbooks de una raiz.

- `--root X` (por omision `platform`): cada alerta de los charts y reglas bajo X tiene `severity` valida y un
  `runbook_url` hacia un archivo que sigue `platform/runbooks/_template.md`.
- `--operational`: los runbooks operativos de U1, o con `--root X` los documentos de X que usan la plantilla, siguen la
  plantilla y cada paso de verificacion nombra un comando.
"""

import argparse
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "platform/runbooks/_template.md"
OPERATIONAL = ("install", "zone-failover", "site-restore", "trust-anchor-rotation")
SEVERITIES = {"SEV1", "SEV2", "SEV3", "none"}
SKIPPED_PARTS = {".tools", ".charts", "rendered", "generated", "tests", "__pycache__", "node_modules", ".venv"}
ALERT_BLOCK = re.compile(r"^\s*-\s*alert:\s*(\S+)(.*?)(?=^\s*-\s*(?:alert|record):|\Z)", re.M | re.S)
Alert = dict[str, Any]


def template_sections(template: Path = TEMPLATE) -> list[str]:
    return re.findall(r"^## .+$", template.read_text(encoding="utf-8"), flags=re.M)


def missing_sections(text: str, sections: list[str]) -> list[str]:
    headings = {line.strip() for line in text.splitlines()}
    return [section for section in sections if section not in headings]


def alerts_in_documents(document: Any) -> Iterator[Alert]:
    if isinstance(document, dict):
        groups = document.get("groups") or (document.get("spec") or {}).get("groups") or []
        for group in groups:
            for rule in group.get("rules") or []:
                if "alert" in rule:
                    yield rule


def alerts_in_template(text: str) -> Iterator[Alert]:
    """Un chart no se puede leer como YAML: basta con encontrar cada bloque `- alert:`."""
    for name, body in ALERT_BLOCK.findall(text):
        severity = re.search(r"^\s*severity:\s*[\"']?([^\s\"']+)", body, flags=re.M)
        url = re.search(r"^\s*runbook_url:\s*[\"']?([^\s\"']+)", body, flags=re.M)
        yield {
            "alert": name,
            "labels": {"severity": severity.group(1)} if severity else {},
            "annotations": {"runbook_url": url.group(1)} if url else {},
        }


def alerts_under(root: Path) -> Iterator[tuple[Path, Alert]]:
    for path in sorted(root.rglob("*")):
        if path.suffix not in {".yaml", ".yml"} or SKIPPED_PARTS & set(path.relative_to(root).parts):
            continue
        text = path.read_text(encoding="utf-8")
        if "alert:" not in text:
            continue
        if "{{" in text:
            found: list[Alert] = list(alerts_in_template(text))
        else:
            found = [alert for document in yaml.safe_load_all(text) for alert in alerts_in_documents(document)]
        for alert in found:
            yield path, alert


def alert_problems(root: Path, base: Path = ROOT) -> tuple[list[str], int]:
    sections = template_sections()
    problems: list[str] = []
    checked = 0
    for path, alert in alerts_under(root):
        checked += 1
        where = f"{path.relative_to(base)}: {alert['alert']}"
        severity = (alert.get("labels") or {}).get("severity")
        if severity not in SEVERITIES:
            problems.append(f"{where}: severity invalida: {severity}")
        url = (alert.get("annotations") or {}).get("runbook_url")
        target = base / str(url)
        if not url or not target.is_file():
            problems.append(f"{where}: runbook_url sin archivo: {url}")
            continue
        missing = missing_sections(target.read_text(encoding="utf-8"), sections)
        if missing:
            problems.append(f"{where}: a {url} le faltan {missing}")
    return problems, checked


def verification_problems(text: str) -> list[str]:
    """Cada paso de `## Verificación` nombra un comando entre comillas invertidas."""
    if "## Verificación" not in text:
        return []
    body = re.split(r"^## ", text.split("## Verificación", 1)[1], maxsplit=1, flags=re.M)[0]
    steps = re.findall(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", body, flags=re.M)
    if not steps:
        return [] if "`" in body else ["## Verificación no nombra ningun comando"]
    return [f"el paso de verificacion no nombra un comando: {step}" for step in steps if "`" not in step]


def operational_problems(root: Path | None, base: Path = ROOT) -> tuple[list[str], int]:
    sections = template_sections()
    if root is None:
        documents = [base / f"platform/runbooks/{name}.md" for name in OPERATIONAL]
        problems = [f"{path}: no existe" for path in documents if not path.is_file()]
        documents = [path for path in documents if path.is_file()]
    else:
        # Un documento de la carpeta que no use ningun encabezado de la plantilla no es un runbook.
        documents = [p for p in sorted(root.rglob("*.md")) if not {*sections} .isdisjoint(line.strip() for line in p.read_text(encoding="utf-8").splitlines())]
        problems = []
    for path in documents:
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(base)
        problems += [f"{name}: falta {section}" for section in missing_sections(text, sections)]
        problems += [f"{name}: {problem}" for problem in verification_problems(text)]
    return problems, len(documents)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", help="carpeta relativa a vectra-risk/")
    parser.add_argument("--operational", action="store_true")
    args = parser.parse_args(argv)
    root = ROOT / args.root if args.root else None
    if root is not None and not root.is_dir():
        print(f"{args.root}: la carpeta no existe")
        return 1
    if args.operational:
        problems, checked = operational_problems(root)
        what = "runbooks operativos"
    else:
        problems, checked = alert_problems(root or ROOT / "platform")
        what = "alertas"
    if not checked:
        problems.append(f"{args.root or 'platform'}: sin {what} que revisar")
    print("\n".join(problems) if problems else f"{checked} {what} con su runbook en regla")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
