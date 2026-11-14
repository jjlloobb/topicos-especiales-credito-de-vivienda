"""La huella de todo lo que entra en la imagen (Paso 15): `make image` la pasa como `--build-arg SOURCE_DIGEST=` y el `Dockerfile` la deja en la etiqueta `org.vectra.system-verification.source-digest`.
`tests/image/test_image.py` la recalcula y compara: una imagen construida con fuentes anteriores (o sin reconstruir) hace fallar la prueba en vez de pasar con la imagen vieja.

Solo biblioteca estandar. Sin argumentos imprime la huella; la raiz de `vectra-risk/` es la del archivo (`../..`)."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INCLUDED = (
    "system-verification/Dockerfile",
    "system-verification/Dockerfile.dockerignore",
    "system-verification/pyproject.toml",
    "system-verification/image",
    "system-verification/src",
    "system-verification/demos",
    "system-verification/report",
    "system-verification/seccomp",
    "contracts/python/vectra_contracts",
)
SKIPPED = ("__pycache__", ".pyc")


def digest(root: Path = ROOT) -> str:
    files: list[Path] = []
    for item in INCLUDED:
        path = root / item
        files += [p for p in path.rglob("*") if p.is_file()] if path.is_dir() else [path]
    summary = hashlib.sha256()
    for path in sorted(p for p in files if not any(part in str(p) for part in SKIPPED)):
        summary.update(path.relative_to(root).as_posix().encode() + b"\0")
        summary.update(hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    return summary.hexdigest()


if __name__ == "__main__":
    sys.stdout.write(digest() + "\n")
    sys.exit(0)
