#!/usr/bin/env python3
"""Verifica el SHA-256 de cada archivo de un paquete de U5 contra su `manifest.json` (NFR-U5-03).

Solo usa la biblioteca estandar: el operador lo corre antes de subir el paquete al model-store y no depende del codigo
que se esta verificando.

    verify_release.py PAQUETE [PAQUETE ...]        cada directorio con su manifest.json
    verify_release.py --out reference-model/.out   el paquete base y los 5 de la variante proxy (proxy/run-1..5)

Falla (codigo 1) si falta el manifiesto, si un archivo listado falta o difiere, si el directorio tiene un archivo que el
manifiesto no lista, o si un nombre sale del directorio. Con `--out` falla ademas si no hay exactamente 5 corridas proxy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

MANIFEST = "manifest.json"
PROXY_RUNS = 5


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_directory(directory: Path) -> list[str]:
    """Problemas de un paquete; lista vacia si cada SHA-256 del manifiesto coincide."""
    try:
        manifest = json.loads((directory / MANIFEST).read_bytes())
        entries = {entry["name"]: entry["sha256"] for entry in manifest["files"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"{directory}: manifiesto ilegible ({exc.__class__.__name__})"]
    problems: list[str] = []
    for name, expected in sorted(entries.items()):
        path = directory / name
        if Path(name).name != name:
            problems.append(f"{directory}: nombre fuera del directorio: {name}")
        elif not path.is_file():
            problems.append(f"{directory}: falta {name}")
        elif sha256_of(path) != expected:
            problems.append(f"{directory}: sha256 distinto en {name}")
    present = {p.name for p in directory.iterdir() if p.is_file()} - {MANIFEST}
    problems += [f"{directory}: {name} no esta en el manifiesto" for name in sorted(present - set(entries))]
    return problems


def release_directories(out: Path) -> list[Path]:
    return [out / "package", *sorted((out / "proxy").glob("run-*"))]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("packages", nargs="*", type=Path)
    parser.add_argument("--out", type=Path, help="directorio de `make release`")
    args = parser.parse_args(argv)
    directories = list(args.packages)
    problems: list[str] = []
    if args.out:
        found = release_directories(args.out)
        if len(found) != 1 + PROXY_RUNS:
            problems.append(
                f"{args.out}: se esperaban package y {PROXY_RUNS} corridas proxy, hay {len(found)}"
            )
        directories += found
    if not directories:
        parser.error("indica al menos un paquete o --out")
    for directory in directories:
        errors = verify_directory(directory)
        problems += errors
        if not errors:
            print(f"ok {directory}")  # noqa: T201
    for problem in problems:
        print(f"FALLA {problem}", file=sys.stderr)  # noqa: T201
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
