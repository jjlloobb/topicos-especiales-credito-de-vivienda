#!/usr/bin/env python3
"""Arma el parche de una entrada `staging` en `values/kind/model-serving.yaml` (D1 y D2), sobre el archivo **tal como esta**.

Una plantilla de parche fija no sirve: su contexto trae `inferenceServices: []` (o la entrada que ya hubiera), y deja de aplicar en cuanto `promotion-tool` promueve el modelo de referencia.
Este guion lee el archivo, agrega **al final** del bloque `inferenceServices` una entrada `{ modelVersionId, storageUri, profile: staging }` (como `vectra_promotion.values.promote`: el diff es minimo
y no reordena nada) e imprime el diff unificado, para `git apply` desde la raiz del repositorio. Solo la biblioteca estandar. No escribe ningun archivo.

Uso (desde `vectra-risk/`): `python3 system-verification/demos/prs/entrada.py --version mv-... --storage-uri s3://model-store/<ruta>/ > entrada.patch`
"""

import argparse
import difflib
import re
import sys
from pathlib import Path

VERSION = re.compile(r"^mv-\d{4}-\d{2}-\d{2}-[0-9a-f]{8}$")
STORAGE = re.compile(r"^s3://model-store/[A-Za-z0-9._/-]+/$")
KEY_LINE = re.compile(r"^inferenceServices:")
TOP_LEVEL = re.compile(r"^[^\s-]")
DEFAULT_VALUES = "vectra-risk-gitops/values/kind/model-serving.yaml"


def add_entry(text: str, version: str, uri: str) -> str:
    """El archivo con la entrada `staging` al final de `inferenceServices` (el bloque termina en la primera linea de raiz: un comentario o otra clave)."""
    if not VERSION.match(version):
        raise ValueError("model_version_id_invalid")
    if not STORAGE.match(uri):
        raise ValueError("storage_uri_invalid")
    entry = f'  - {{ modelVersionId: {version}, storageUri: "{uri}", profile: staging }}\n'
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if KEY_LINE.match(line)), None)
    if start is None:
        raise ValueError("inferenceServices_ausente")
    if entry in lines:
        raise ValueError("entrada_repetida")
    end = next((i for i in range(start + 1, len(lines)) if TOP_LEVEL.match(lines[i])), len(lines))
    if lines[start].strip() == "inferenceServices: []":
        return "".join([*lines[:start], "inferenceServices:\n", entry, *lines[start + 1 :]])
    last = max(i for i in range(start, end) if lines[i].strip())
    return "".join([*lines[: last + 1], entry, *lines[last + 1 :]])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--values", default=DEFAULT_VALUES, help="el archivo de values (relativo al directorio actual)"
    )
    parser.add_argument("--version", required=True, help="el model_version_id (mv-aaaa-mm-dd-<8 hex>)")
    parser.add_argument(
        "--storage-uri",
        required=True,
        help="el directorio del paquete en el model-store (s3://model-store/<ruta>/)",
    )
    parser.add_argument(
        "--label",
        default="vectra-risk/" + DEFAULT_VALUES,
        help="la ruta del archivo desde la raiz del repositorio",
    )
    args = parser.parse_args(argv)
    before = Path(args.values).read_text(encoding="utf-8")
    try:
        after = add_entry(before, args.version, args.storage_uri)
    except ValueError as error:
        sys.stderr.write(f"entrada.py: {error}\n")
        return 2
    sys.stdout.writelines(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            f"a/{args.label}",
            f"b/{args.label}",
            n=3,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
