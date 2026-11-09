"""Validacion del registro de paquetes de modelo (BR-U4-06). Pura, sin E/S (Bloque C, Paso 6).

Funcion pura sobre **bytes**: `validate_registration` recibe el formato declarado, los SHA-256 declarados (manifiesto,
predictor y explicador), los bytes de `manifest.json` y los de cada archivo que lista. Leer del model-store (F47) es del
Paso 10. El formato del manifiesto es el de U5 (`vectra_reference.package`): `files = [{name, sha256,
model_version_id}]`, con los seis archivos de `REQUIRED_FILES`.

Nunca deserializa un modelo: no llama a `pickle`, `joblib`, `onnx.load`, `xgboost` ni `lightgbm`. Solo calcula SHA-256,
compara bytes y lee con `json.loads` el manifiesto y los JSON de metadatos (diccionario y especificacion de features),
que no son un modelo.

Orden de las comprobaciones (el primer fallo gana, para que el motivo sea estable): 1) formato; 2) bytes magicos del
manifiesto; 3) SHA-256 del manifiesto contra el declarado; 4) estructura del manifiesto y los seis archivos listados;
5) por cada archivo listado: extension prohibida, bytes presentes, bytes magicos, SHA-256 contra el manifiesto y
`model_version_id` del manifiesto; 6) SHA-256 declarados del predictor y del explicador; 7) `model_version_id` dentro de
los JSON que lo llevan (RT3-a, RT3-c); 8) diccionario y especificacion de features legibles con los tipos de U0.
Cualquier fallo es `RegistrationRejected` con un motivo estable (el Paso 10 lo traduce a `422 validation_error`).
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from vectra_contracts.models.features import FeatureDictionary, FeatureSpec
from vectra_contracts.models.governance import ArtifactFormat

ALLOWED_FORMATS: Final[tuple[ArtifactFormat, ...]] = ("onnx", "xgboost_json", "xgboost_ubj", "lightgbm_txt")
REQUIRED_FILES: Final = (
    "predictor.json",
    "explainer.json",
    "background.csv",
    "domain_envelope.json",
    "feature_dictionary.json",
    "feature_spec.json",
)
FORBIDDEN_SUFFIXES: Final = (".pkl", ".pickle", ".joblib")
ZIP_MAGIC: Final = b"PK\x03\x04"  # cabecera zip (joblib)
PICKLE_MARK: Final = 0x80  # pickle: `\x80` + version de protocolo
PICKLE_PROTOCOLS: Final = tuple(range(2, 6))
#: Archivos del paquete que llevan su propio `model_version_id` dentro.
ID_CARRIERS: Final = (
    "explainer.json",
    "domain_envelope.json",
    "feature_dictionary.json",
    "feature_spec.json",
)
PREDICTOR: Final = "predictor.json"
EXPLAINER: Final = "explainer.json"
DICTIONARY: Final = "feature_dictionary.json"
SPEC: Final = "feature_spec.json"


class RegistrationRejected(Exception):
    """El paquete no se registra (`422 validation_error`, BR-U4-06). `reason` es estable (`codigo` o `codigo:archivo`)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class VerifiedPackage:
    """Lo que el Paso 10 guarda en la version: el id, el SHA-256 de cada archivo y los dos JSON verificados."""

    model_version_id: str
    file_sha256: Mapping[str, str]
    feature_dictionary_version: str
    feature_dictionary: dict[str, Any]
    feature_spec: dict[str, Any]


def has_executable_magic(data: bytes) -> bool:
    """Bytes magicos de pickle (`\\x80` + protocolo 2 a 5) o cabecera zip de joblib, sea cual sea la extension."""
    if data.startswith(ZIP_MAGIC):
        return True
    return len(data) > 1 and data[0] == PICKLE_MARK and data[1] in PICKLE_PROTOCOLS


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_manifest(manifest: bytes) -> tuple[str, list[dict[str, str]]]:
    try:
        document = json.loads(manifest)
        version = document["model_version_id"]
        entries = document["files"]
        if not isinstance(version, str) or not isinstance(entries, list):
            raise TypeError
        for entry in entries:
            if not all(isinstance(entry[key], str) for key in ("name", "sha256", "model_version_id")):
                raise TypeError
    except (ValueError, KeyError, TypeError) as error:
        raise RegistrationRejected("manifest_unreadable") from error
    return version, entries


def validate_registration(
    *,
    artifact_format: str,
    manifest_sha256: str,
    artifact_sha256: str,
    explainer_sha256: str,
    manifest: bytes,
    files: Mapping[str, bytes],
) -> VerifiedPackage:
    """Verifica el paquete (BR-U4-06, puntos 1 a 5) o lanza `RegistrationRejected`. Orden: ver el modulo."""
    if artifact_format not in ALLOWED_FORMATS:
        raise RegistrationRejected("artifact_format_not_allowed")
    if has_executable_magic(manifest):
        raise RegistrationRejected("forbidden_magic_bytes:manifest.json")
    if _sha256(manifest) != manifest_sha256:
        raise RegistrationRejected("manifest_sha256_mismatch")
    version, entries = _read_manifest(manifest)
    names = [entry["name"] for entry in entries]
    if len(set(names)) != len(names):
        raise RegistrationRejected("manifest_unreadable")
    for required in REQUIRED_FILES:
        if required not in names:
            raise RegistrationRejected(f"manifest_missing_file:{required}")
    for entry in entries:
        name = entry["name"]
        if name.lower().endswith(FORBIDDEN_SUFFIXES):
            raise RegistrationRejected(f"forbidden_extension:{name}")
        data = files.get(name)
        if data is None:
            raise RegistrationRejected(f"file_bytes_missing:{name}")
        if has_executable_magic(data):
            raise RegistrationRejected(f"forbidden_magic_bytes:{name}")
        if _sha256(data) != entry["sha256"]:
            raise RegistrationRejected(f"sha256_mismatch:{name}")
        if entry["model_version_id"] != version:
            raise RegistrationRejected(f"model_version_id_mismatch:{name}")
    listed = {entry["name"]: entry["sha256"] for entry in entries}
    if listed[PREDICTOR] != artifact_sha256:
        raise RegistrationRejected("declared_sha256_mismatch:predictor")
    if listed[EXPLAINER] != explainer_sha256:
        raise RegistrationRejected("declared_sha256_mismatch:explainer")
    for name in ID_CARRIERS:
        try:
            inside = json.loads(files[name]).get("model_version_id")
        except (ValueError, AttributeError) as error:
            raise RegistrationRejected(f"json_unreadable:{name}") from error
        if inside != version:
            raise RegistrationRejected(f"model_version_id_mismatch_inside:{name}")
    try:
        dictionary = FeatureDictionary.model_validate_json(files[DICTIONARY])
        FeatureSpec.model_validate_json(files[SPEC])
    except ValueError as error:
        raise RegistrationRejected("feature_files_unreadable") from error
    return VerifiedPackage(
        model_version_id=version,
        file_sha256=listed,
        feature_dictionary_version=dictionary.dictionary_version,
        feature_dictionary=json.loads(files[DICTIONARY]),
        feature_spec=json.loads(files[SPEC]),
    )
