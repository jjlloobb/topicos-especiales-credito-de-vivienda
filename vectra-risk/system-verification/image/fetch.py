"""Descarga con SHA-256 comprobado (Paso 15, P-8): lo usa el `Dockerfile` en la etapa `fetch`; no se instala en la imagen final.

    fetch.py get [--mode 0755] <sha256> <destino> <url>   descarga, comprueba la suma y solo entonces escribe el destino
    fetch.py unzip <zip> <destino>                         extrae respetando los permisos del zip (el `zipfile` de Python los pierde)

Una suma que no coincide termina con codigo 1 y sin dejar archivo: la construccion se detiene.
"""

from __future__ import annotations

import hashlib
import stat
import sys
import urllib.request
import zipfile
from pathlib import Path

CHUNK = 1 << 20


def get(url: str, expected: str, dest: Path, mode: int) -> int:
    digest = hashlib.sha256()
    temporary = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as out:  # noqa: S310 - https fijo
        while chunk := response.read(CHUNK):
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != expected.lower():
        temporary.unlink()
        sys.stderr.write(
            f"SHA-256 distinto para {url}: esperado {expected}, calculado {digest.hexdigest()}\n"
        )
        return 1
    temporary.chmod(mode)
    temporary.rename(dest)
    sys.stdout.write(f"ok {dest} sha256={digest.hexdigest()}\n")
    return 0


def unzip(source: Path, dest: Path) -> int:
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            target = dest / info.filename
            if not target.resolve().is_relative_to(dest.resolve()):
                sys.stderr.write(f"ruta fuera del destino: {info.filename}\n")
                return 1
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("wb") as out:
                out.write(src.read())
            target.chmod(stat.S_IMODE(info.external_attr >> 16) or 0o644)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 4 and argv[0] == "get":
        rest = argv[1:]
        mode = 0o644
        if rest[0] == "--mode":
            mode, rest = int(rest[1], 8), rest[2:]
        if len(rest) == 3:
            return get(rest[2], rest[0], Path(rest[1]), mode)
    if len(argv) == 3 and argv[0] == "unzip":
        return unzip(Path(argv[1]), Path(argv[2]))
    sys.stderr.write(f"{__doc__}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
