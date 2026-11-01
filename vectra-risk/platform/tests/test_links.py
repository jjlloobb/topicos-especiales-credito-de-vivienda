#!/usr/bin/env python3
"""Cada enlace relativo de los Markdown de una raiz apunta a un archivo que existe.

Sin argumentos revisa el codigo de `vectra-risk/` (no `aidlc-docs/` ni `entradas/`, que son documentos de trabajo).
`--root X`, repetible, revisa una carpeta o un archivo relativos a `vectra-risk/`.
"""

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIPPED_PARTS = {".tools", ".charts", "__pycache__", "node_modules", ".venv", "dist"}
DEFAULT_EXCLUDED = {"aidlc-docs", "entradas"}
#: `[texto](destino "titulo")` e imagenes. No un enlace dentro de `codigo`.
LINK = re.compile(r"(?<!\\)\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
FENCE = re.compile(r"^(```|~~~).*?^\1\s*$", re.M | re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", re.I)


def relative_targets(text: str) -> list[str]:
    visible = INLINE_CODE.sub("", FENCE.sub("", text))
    return [t for t in LINK.findall(visible) if not EXTERNAL.match(t)]


def broken_links(path: Path) -> list[str]:
    broken = []
    for target in relative_targets(path.read_text(encoding="utf-8")):
        plain = target.split("#", 1)[0].split("?", 1)[0]
        if plain and not Path(os.path.normpath(path.parent / plain)).exists():
            broken.append(target)
    return broken


def markdown_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        candidates = [root] if root.is_file() else sorted(root.rglob("*.md"))
        files += [p for p in candidates if not SKIPPED_PARTS & set(p.parts)]
    return files


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", action="append", default=[], help="carpeta o archivo relativo a vectra-risk/")
    args = parser.parse_args(argv)
    if args.root:
        roots = [ROOT / name for name in args.root]
        missing = [str(p) for p in roots if not p.exists()]
        if missing:
            print("No existe:", ", ".join(missing))
            return 1
    else:
        roots = [p for p in sorted(ROOT.iterdir()) if p.is_dir() and p.name not in DEFAULT_EXCLUDED | SKIPPED_PARTS]
    files = markdown_files(roots)
    if not files:
        print("Sin Markdown que revisar")
        return 1
    problems = [f"{path.relative_to(ROOT)}: {target}" for path in files for target in broken_links(path)]
    print("\n".join(problems) if problems else f"{len(files)} archivos Markdown sin enlaces rotos")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
