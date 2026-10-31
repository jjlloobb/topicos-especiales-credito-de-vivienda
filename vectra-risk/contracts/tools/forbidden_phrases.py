"""Aplica la lista unica de frases prohibidas (BR-U0-94). Falla con archivo, linea y frase."""

import re
import sys
import unicodedata
from pathlib import Path

import yaml

LIST_PATH = Path(__file__).resolve().parents[1] / "forbidden-phrases.yaml"


def normalize(text: str) -> str:
    """Sin tildes (NFD) y en minusculas."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn").lower()


def load_patterns(path: Path = LIST_PATH) -> list[tuple[str, re.Pattern[str]]]:
    phrases: list[str] = yaml.safe_load(path.read_text(encoding="utf-8"))["phrases"]
    return [(phrase, re.compile(rf"\b{re.escape(normalize(phrase))}\b")) for phrase in phrases]


def find_violations(text: str, patterns: list[tuple[str, re.Pattern[str]]]) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        normalized = normalize(line)
        found.extend((number, phrase) for phrase, pattern in patterns if pattern.search(normalized))
    return found


def main(argv: list[str]) -> int:
    patterns = load_patterns()
    failed = False
    for name in argv:
        for number, phrase in find_violations(Path(name).read_text(encoding="utf-8"), patterns):
            print(f"{name}:{number}: frase prohibida: {phrase}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
