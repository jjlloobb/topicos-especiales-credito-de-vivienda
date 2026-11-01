#!/usr/bin/env python3
"""Cada regla de conftest aprueba su caso bueno y niega el malo, con el mensaje esperado (Paso 23).

Una regla es un comentario `# regla: nombre` en un `.rego`; sus casos estan en `tests/nombre/{pass,fail}.yaml`, y cada
`# espera: texto` de `fail.yaml` tiene que aparecer en algun mensaje. Una regla sin casos o un caso sin regla es un error.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGO = ROOT / "platform/policies/rego"
CONFTEST = ROOT / "platform/.tools/bin/conftest"


def declared_rules() -> dict[str, str]:
    """regla -> package donde vive."""
    rules: dict[str, str] = {}
    for path in REGO.glob("*.rego"):
        text = path.read_text(encoding="utf-8")
        package = re.search(r"^package (\S+)", text, flags=re.M)
        for rule in re.findall(r"^# regla: (\S+)", text, flags=re.M):
            rules[rule] = package.group(1) if package else "main"
    return rules


def run(fixture: Path, package: str) -> tuple[int, list[str], int]:
    """Codigo de conftest, mensajes de falla y numero de evaluaciones."""
    command = [str(CONFTEST), "test", "--output", "json", "--no-color", "--policy", str(REGO), "--namespace", package]
    if package != "main":
        command.append("--combine")
    result = subprocess.run([*command, str(fixture)], capture_output=True, text=True, check=False)
    if result.returncode > 1:
        return result.returncode, [result.stderr], 0
    reports = json.loads(result.stdout)
    failures = [f["msg"] for report in reports for f in report.get("failures") or []]
    evaluated = sum(report.get("successes", 0) + len(report.get("failures") or []) for report in reports)
    return result.returncode, failures, evaluated


def problems() -> list[str]:
    found: list[str] = []
    rules = declared_rules()
    cases = {p.name for p in (REGO / "tests").iterdir() if p.is_dir()}
    found += [f"{name}: caso sin regla" for name in sorted(cases - set(rules))]
    for rule, package in sorted(rules.items()):
        folder = REGO / "tests" / rule
        good, bad = folder / "pass.yaml", folder / "fail.yaml"
        if not good.is_file() or not bad.is_file():
            found.append(f"{rule}: faltan pass.yaml o fail.yaml")
            continue
        code, failures, evaluated = run(good, package)
        if code != 0 or not evaluated:
            found.append(f"{rule}: pass.yaml debio aprobar: {code} {failures} ({evaluated} evaluaciones)")
        code, failures, _ = run(bad, package)
        expected = re.findall(r"^# espera: (.+)$", bad.read_text(encoding="utf-8"), flags=re.M)
        if code != 1 or not expected:
            found.append(f"{rule}: fail.yaml debio negar (codigo {code}, {len(expected)} `# espera`)")
        found += [f"{rule}: falta el mensaje {text!r} en {failures}" for text in expected if not any(text in f for f in failures)]
    return found


def main() -> int:
    found = problems()
    print("\n".join(found) if found else f"{len(declared_rules())} reglas de conftest con su caso bueno y su caso malo")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
