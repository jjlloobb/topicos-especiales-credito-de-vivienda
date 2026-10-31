"""Cada BR-U0-xx aparece en las pruebas (NFR-U0-35)."""

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "aidlc-docs/construction/contracts/functional-design/business-rules.md"
TESTS = ROOT / "contracts/tests"
SECTIONS = {
    "logic": lambda n: 1 <= n <= 43 or 80 <= n <= 81 or n == 95,
    "api": lambda n: 50 <= n <= 73,
    "versioning": lambda n: 90 <= n <= 93,
    "all": lambda n: True,
}


def defined_rules() -> set[int]:
    return {int(m) for m in re.findall(r"BR-U0-(\d\d)\b", RULES.read_text(encoding="utf-8"))}


def tested_rules() -> set[int]:
    found: set[int] = set()
    for path in TESTS.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        found |= {int(m) for m in re.findall(r"(?:BR-U0-|br_u0_)(\d\d)", text)}
        for start, end in re.findall(r"br_u0_(\d\d)_(\d\d)", text):
            found |= {int(start), int(end)}
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=sorted(SECTIONS))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    section = "all" if args.all or not args.section else args.section
    wanted = {n for n in defined_rules() if SECTIONS[section](n)}
    missing = sorted(wanted - tested_rules())
    if missing:
        print("Sin prueba:", ", ".join(f"BR-U0-{n:02d}" for n in missing))
        return 1
    print(f"{len(wanted)} reglas con prueba en la seccion {section}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
