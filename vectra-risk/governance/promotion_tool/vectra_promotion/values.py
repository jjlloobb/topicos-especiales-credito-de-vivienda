"""El esquema de `vectra-risk-gitops/values/<env>/model-serving.yaml` que edita `promotion-tool`, en un solo modulo.

Origen de cada campo (U06-T02: `model-serving/docs/values.md` y `model-serving/chart/values.schema.json`; no se inventa ninguno):

- clave de raiz editable: solo `inferenceServices` (lista; el esquema cierra el objeto con `additionalProperties: false`);
- entrada: `modelVersionId` (`mv-<aaaa>-<mm>-<dd>-<8 hex>`), `storageUri` (`s3://model-store/<ruta>/`, el directorio del paquete) y
  `profile` (`prod`, `inactive` o `staging`); nada mas. El nombre `isvc-<8 hex>`, el namespace, las replicas, la prioridad, el HPA y el
  PDB los deduce el chart del perfil;
- promocion: agregar al final una entrada `prod`; post-activacion: `prod` -> `inactive` de la anterior; rollback: `inactive` -> `prod`;
- el retiro (quitar la entrada `inactive`) esta diferido por la demo (enmienda §3 U4, Paso 12) y no existe aqui.

`helm template` valida el resultado contra `values.schema.json`; este modulo solo lo arma. Las funciones son puras.
"""

import re
from collections.abc import Sequence
from typing import Any

import yaml

from vectra_promotion.errors import PromotionError

ROOT_KEY = "inferenceServices"
MODEL_STORE = "s3://model-store/"
VERSION_ID = re.compile(r"^mv-\d{4}-\d{2}-\d{2}-[0-9a-f]{8}$")
Entry = dict[str, str]


def isvc_name(model_version_id: str) -> str:
    """`isvc-<8 hex>`: los 8 hex finales de la version (es el `inference_service` que guarda `serving-config`)."""
    _check_version(model_version_id)
    return "isvc-" + model_version_id[-8:]


def storage_uri(manifest_uri: str) -> str:
    """El directorio del paquete: `dirname(manifest_uri) + "/"`, como governance (`manifest_uri.rsplit("/", 1)[0]`)."""
    if not manifest_uri.startswith(MODEL_STORE) or "/" not in manifest_uri[len(MODEL_STORE) :]:
        raise PromotionError("manifest_uri_invalid")
    return manifest_uri.rsplit("/", 1)[0] + "/"


def _check_version(model_version_id: str) -> None:
    if not VERSION_ID.match(model_version_id):
        raise PromotionError("model_version_id_invalid")


def parse(text: str) -> list[Entry]:
    """La lista `inferenceServices` del archivo (vacia si el archivo no la declara)."""
    data: Any = yaml.safe_load(text) or {}
    if not isinstance(data, dict) or not isinstance(data.get(ROOT_KEY, []), list):
        raise PromotionError("values_unreadable")
    return [dict(e) for e in data.get(ROOT_KEY, [])]


def _only(entries: Sequence[Entry], model_version_id: str, profile: str) -> Entry:
    found = [e for e in entries if e.get("modelVersionId") == model_version_id and e.get("profile") == profile]
    if len(found) != 1:
        raise PromotionError(f"entry_not_found:{profile}")
    return found[0]


def has_entry(entries: Sequence[Entry], model_version_id: str, profile: str) -> bool:
    return any(e.get("modelVersionId") == model_version_id and e.get("profile") == profile for e in entries)


def promote(entries: Sequence[Entry], model_version_id: str, uri: str) -> list[Entry]:
    """PR 1: agrega AL FINAL la version con el perfil `prod`; no reordena ni toca las demas (diff minimo)."""
    _check_version(model_version_id)
    if any(e.get("modelVersionId") == model_version_id and e.get("profile") in ("prod", "inactive") for e in entries):
        raise PromotionError("already_declared")
    return [*(dict(e) for e in entries), {"modelVersionId": model_version_id, "storageUri": uri, "profile": "prod"}]


def _switch(entries: Sequence[Entry], model_version_id: str, source: str, target: str) -> list[Entry]:
    _check_version(model_version_id)
    out = [dict(e) for e in entries]
    _only(out, model_version_id, source)["profile"] = target
    return out


def demote(entries: Sequence[Entry], model_version_id: str) -> list[Entry]:
    """PR 2 (post-activacion): `prod` -> `inactive` en la entrada de la version anterior."""
    return _switch(entries, model_version_id, "prod", "inactive")


def restore(entries: Sequence[Entry], model_version_id: str) -> list[Entry]:
    """Rollback: `inactive` -> `prod` en la entrada de la version que se restaura."""
    return _switch(entries, model_version_id, "inactive", "prod")


def render_block(entries: Sequence[Entry]) -> str:
    if not entries:
        return f"{ROOT_KEY}: []\n"
    lines = [f"{ROOT_KEY}:"]
    for e in entries:
        first = True
        for key in ("modelVersionId", "storageUri", "profile"):
            lines.append(("  - " if first else "    ") + f"{key}: {e[key]}")
            first = False
    return "\n".join(lines) + "\n"


_KEY_LINE = re.compile(rf"^{ROOT_KEY}:")
_TOP_LEVEL = re.compile(r"^[^\s-]")


def edit(text: str, entries: Sequence[Entry]) -> str:
    """Reemplaza solo el bloque `inferenceServices`; los comentarios y las demas claves del archivo quedan como estaban."""
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if _KEY_LINE.match(line)), None)
    block = render_block(entries)
    if start is None:
        return text + ("" if text.endswith("\n") or not text else "\n") + block
    end = next((i for i in range(start + 1, len(lines)) if _TOP_LEVEL.match(lines[i])), len(lines))
    return "".join(lines[:start]) + block + "".join(lines[end:])
