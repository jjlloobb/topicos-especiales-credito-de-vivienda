"""Tablas DANE empaquetadas, verificadas al importar (NFR-U0-20, BR-U0-25, BR-U0-41)."""

import csv
import hashlib
import io
import json
from importlib import resources
from types import MappingProxyType
from typing import Final

from vectra_contracts.errors import DataIntegrityError


def _read_verified(name: str, manifest: dict[str, dict[str, object]]) -> str:
    raw = resources.files("vectra_contracts.data").joinpath(name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest[name]["sha256"]:
        raise DataIntegrityError(f"checksum de {name} no coincide con MANIFEST.json")
    return raw.decode("utf-8")


_MANIFEST: Final[dict[str, dict[str, object]]] = json.loads(
    resources.files("vectra_contracts.data").joinpath("MANIFEST.json").read_bytes()
)
_divipola = list(csv.DictReader(io.StringIO(_read_verified("divipola.csv", _MANIFEST))))
_regions = list(csv.DictReader(io.StringIO(_read_verified("regions.csv", _MANIFEST))))

MUNICIPALITY_DEPARTMENT: Final = MappingProxyType(
    {row["municipality_code"]: row["department_code"] for row in _divipola}
)
DEPARTMENT_REGION: Final = MappingProxyType({row["department_code"]: row["region"] for row in _regions})
DEPARTMENTS: Final = frozenset(DEPARTMENT_REGION)
if DEPARTMENTS != frozenset(MUNICIPALITY_DEPARTMENT.values()) or len(DEPARTMENTS) != 33:
    raise DataIntegrityError("los departamentos de DIVIPOLA y de regiones no coinciden")
