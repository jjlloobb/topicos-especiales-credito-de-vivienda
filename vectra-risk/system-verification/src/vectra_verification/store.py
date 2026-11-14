"""El **unico** escritor de la carpeta de la verificacion (U12-T04, Paso 13; NFR-U12-05, NFR-U12-20; P-5).

Todo lo que la herramienta deja en disco (evidencias, `manifest.json`, el informe, el parche de `prepare` y el estado de retoma) pasa por `Store.write`: filtra con `evidence.prepare` y los secretos cargados
**antes** de crear nada, escribe en un temporal de la misma carpeta y lo renombra. Si el filtro falla (un JWT, un secreto), no queda archivo ni temporal. Un archivo que supera el tope (50 MB) se sustituye
por un resumen con el tamano y el SHA-256 del original (NFR-U12-20). Una prueba estatica (`test_store.py`) comprueba que ningun otro modulo de `src/` abre un archivo para escribir.

`secrets` es una funcion: las credenciales se cargan de a poco y el filtro tiene que ver lo que haya en memoria en el momento de escribir.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from vectra_verification import evidence

FILE_LIMIT: Final = 50 * 1024 * 1024
_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class StoreError(Exception):
    """Un nombre invalido o un archivo que ya existe; el mensaje empieza por un codigo estable y no lleva contenido."""


@dataclass(frozen=True)
class Stored:
    name: str
    sha256: str
    size: int
    summarized: bool


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Store:
    def __init__(
        self,
        directory: Path,
        secrets: Callable[[], Iterable[str]] = lambda: (),
        *,
        limit: int = FILE_LIMIT,
    ) -> None:
        self.directory = directory
        self._secrets = secrets
        self._limit = limit

    def _path(self, name: str) -> Path:
        if not _NAME.fullmatch(name) or ".." in name:
            raise StoreError(f"store_name_invalid:{name[:40]}")
        return self.directory / name

    def exists(self, name: str) -> bool:
        return self._path(name).is_file()

    def read_text(self, name: str) -> str:
        return self._path(name).read_text(encoding="utf-8")

    def names(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        return sorted(p.name for p in self.directory.iterdir() if p.is_file())

    def sha256(self, name: str) -> str | None:
        path = self._path(name)
        return sha256_of(path.read_bytes()) if path.is_file() else None

    def write(self, name: str, text: str, *, new: bool = False) -> Stored:
        """Filtra, escribe en un temporal y renombra. `new=True`: falla si el archivo ya existe (el manifiesto de `prepare`)."""
        path = self._path(name)
        if new and path.exists():
            raise StoreError(f"store_exists:{name}")
        size = len(text.encode("utf-8"))
        summarized = size > self._limit
        if summarized:
            text = json.dumps(
                {
                    "summary": f"el archivo supera el tope de {self._limit} bytes y se sustituyo por este resumen",
                    "original_bytes": size,
                    "original_sha256": sha256_of(text.encode("utf-8")),
                },
                indent=2,
                sort_keys=True,
            )
        cleaned = evidence.prepare(text, self._secrets())  # falla cerrado: aun no existe ningun archivo
        data = cleaned.encode("utf-8")
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{name}.{os.getpid()}.tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return Stored(name, sha256_of(data), size, summarized)
