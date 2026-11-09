"""Verificacion del paquete del modelo al arrancar (P-U6-03, NFR-U6-03, 40; SECURITY-11, 13; US-111).

Cada componente lee `manifest.json`, verifica el SHA-256 de **cada archivo que usa** y que todo lleve el mismo
`model_version_id` que la anotacion del `InferenceService`. Si algo no coincide, `load_package` lanza
`ModelPackageIntegrityFailed` (no hay paquete, no hay listo), cuenta
`vectra_serving_package_integrity_failed_total{component}` y deja un log con la causa (la alerta es del Paso 9).

Los bytes se leen una sola vez: lo que se verifica es lo que se usa (sin ventana entre verificar y leer).
"""

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from vectra_serving_common.metrics import INTEGRITY_FAILED

MANIFEST: Final = "manifest.json"
EVENT: Final = "ModelPackageIntegrityFailed"
# Archivos que lleva el `model_version_id` dentro (el resto, como `predictor.json` o `background.csv`, no).
JSON_WITH_ID: Final = (
    "explainer.json",
    "domain_envelope.json",
    "feature_dictionary.json",
    "feature_spec.json",
)

PREDICTOR_FILES: Final = ("predictor.json", "feature_spec.json", "domain_envelope.json", "explainer.json")
EXPLAINER_FILES: Final = ("predictor.json", "explainer.json", "feature_spec.json")

_log = logging.getLogger("vectra_serving.package_loader")


class ModelPackageIntegrityFailed(Exception):  # noqa: N818 - el nombre es el de la alerta (P-U6-06)
    """El paquete no es el que dice la anotacion o fue alterado: el componente no pasa a listo."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class LoadedPackage:
    """Paquete verificado: sus bytes (solo los archivos usados) y el `model_version_id` del manifiesto."""

    model_version_id: str
    files: Mapping[str, bytes]

    def json(self, name: str) -> Any:
        return json.loads(self.files[name])


def _fail(component: str, reason: str) -> ModelPackageIntegrityFailed:
    INTEGRITY_FAILED.labels(component=component).inc()
    _log.error("%s component=%s reason=%s", EVENT, component, reason)
    return ModelPackageIntegrityFailed(reason)


def _read_manifest(directory: Path, component: str) -> dict[str, Any]:
    try:
        manifest = json.loads((directory / MANIFEST).read_bytes())
    except (OSError, ValueError) as error:
        raise _fail(component, f"manifest_unreadable:{type(error).__name__}") from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise _fail(component, "manifest_malformed")
    return manifest


def load_package(
    directory: Path, expected_version_id: str, files: Sequence[str], component: str
) -> LoadedPackage:
    """Verifica `files` de `directory` contra `manifest.json` y `expected_version_id` (la anotacion)."""
    manifest = _read_manifest(directory, component)
    if manifest.get("model_version_id") != expected_version_id:
        raise _fail(component, "manifest_version_mismatch")
    entries: dict[str, Mapping[str, Any]] = {}
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise _fail(component, "manifest_malformed")
        if entry.get("model_version_id") != expected_version_id:
            raise _fail(component, f"entry_version_mismatch:{entry['name']}")
        entries[entry["name"]] = entry
    loaded: dict[str, bytes] = {}
    for name in files:
        entry = entries.get(name)
        if entry is None:
            raise _fail(component, f"file_not_in_manifest:{name}")
        try:
            data = (directory / name).read_bytes()
        except OSError as error:
            raise _fail(component, f"file_unreadable:{name}") from error
        if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise _fail(component, f"sha256_mismatch:{name}")
        loaded[name] = data
    package = LoadedPackage(expected_version_id, loaded)
    for name in files:
        if name in JSON_WITH_ID and _embedded_version(package, name, component) != expected_version_id:
            raise _fail(component, f"embedded_version_mismatch:{name}")
    return package


def _embedded_version(package: LoadedPackage, name: str, component: str) -> object:
    try:
        document = package.json(name)
    except ValueError as error:
        raise _fail(component, f"file_malformed:{name}") from error
    return document.get("model_version_id") if isinstance(document, dict) else None
