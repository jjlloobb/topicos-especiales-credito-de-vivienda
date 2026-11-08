"""Copia, para las pruebas de U5, de la validacion del manifiesto al registrar un modelo en U4 (BR-U4-06).

U4 (governance) todavia no existe. El plan de U5 (Paso 5) pide usar la misma logica copiada en una prueba. Cada regla
cita su origen en `aidlc-docs/construction/governance/functional-design/business-rules.md` (BR-U4-06, items 1 a 5) y,
para los tres paquetes que debe rechazar, en `reference-model/functional-design/domain-entities.md` §5 (RT3-a, c, d).
Es una copia deliberadamente independiente de `vectra_reference.package.verify_package`: solo usa la biblioteca
estandar, para que un error en el verificador de U5 no se repita aqui. Cuando exista U4, esta prueba se reemplaza por
`vectra_governance.registration`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# BR-U4-06 item 1: formatos de artefacto permitidos.
ALLOWED_ARTIFACT_FORMATS = ("onnx", "xgboost_json", "xgboost_ubj", "lightgbm_txt")
# BR-U4-06 item 2: el manifiesto lista predictor, explicador, fondo, envolvente, diccionario y especificacion.
REQUIRED_FILES = (
    "predictor.json",
    "explainer.json",
    "background.csv",
    "domain_envelope.json",
    "feature_dictionary.json",
    "feature_spec.json",
)
# BR-U4-06 item 3: pickle y joblib por extension y por bytes magicos.
FORBIDDEN_EXTENSIONS = (".pkl", ".pickle", ".joblib")
JOINT_ID_FILES = ("explainer.json", "domain_envelope.json", "feature_dictionary.json", "feature_spec.json")


class RegistrationRejected(Exception):
    """`422 validation_error`: no se crea la version (BR-U4-06, ultimo parrafo)."""


def _is_pickle(data: bytes) -> bool:
    return len(data) > 1 and data[0] == 0x80 and 2 <= data[1] <= 5  # `\x80` + version de protocolo


def _is_joblib_zip(data: bytes) -> bool:
    return data.startswith(b"PK\x03\x04")  # cabecera zip


def validate_registration(
    directory: Path, declared_manifest_sha256: str, artifact_format: str = "xgboost_json"
) -> None:
    """Acepta (retorna) o rechaza (`RegistrationRejected`) un paquete, leyendo solo bytes: nunca carga el modelo."""
    if artifact_format not in ALLOWED_ARTIFACT_FORMATS:  # item 1
        raise RegistrationRejected("artifact_format_not_allowed")
    try:
        manifest_bytes = (directory / "manifest.json").read_bytes()  # item 2
    except OSError as exc:
        raise RegistrationRejected("manifest_missing") from exc
    if (
        hashlib.sha256(manifest_bytes).hexdigest() != declared_manifest_sha256
    ):  # item 4: manifiesto vs declarado
        raise RegistrationRejected("manifest_sha256_mismatch")
    manifest = json.loads(manifest_bytes)
    entries = {entry["name"]: entry for entry in manifest["files"]}
    for required in REQUIRED_FILES:  # item 2
        if required not in entries:
            raise RegistrationRejected(f"manifest_missing_file:{required}")
    version = manifest["model_version_id"]
    for name, entry in entries.items():
        if name.lower().endswith(FORBIDDEN_EXTENSIONS):  # item 3: extension
            raise RegistrationRejected(f"forbidden_extension:{name}")
        try:
            data = (directory / name).read_bytes()  # item 2: los bytes de cada archivo listado
        except OSError as exc:  # cualquier fallo -> 422, tambien un archivo listado que no esta
            raise RegistrationRejected(f"file_missing:{name}") from exc
        if _is_pickle(data) or _is_joblib_zip(data):  # item 3: bytes magicos
            raise RegistrationRejected(f"forbidden_magic_bytes:{name}")
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:  # item 4: cada archivo vs manifiesto
            raise RegistrationRejected(f"sha256_mismatch:{name}")
        if entry.get("model_version_id") != version:  # item 5 (RT3-d: el manifiesto con ids distintos)
            raise RegistrationRejected(f"model_version_id_mismatch:{name}")
        if (
            name in JOINT_ID_FILES and json.loads(data).get("model_version_id") != version
        ):  # item 5 (RT3-a, RT3-c)
            raise RegistrationRejected(f"model_version_id_mismatch_inside:{name}")
