"""Empaquetado del modelo (BR-U5-09, BR-U5-10; US-201).

Sin codigo ejecutable: predictor en XGBoost JSON, explicador, envolvente, diccionario y especificacion en JSON,
fondo en CSV; nada de pickle ni joblib. `manifest.json` lista cada archivo con su SHA-256 y su `model_version_id`.

`model_version_id = mv-<fecha>-<8 hex>` (domain-entities §3). Los archivos JSON llevan el id dentro, y el id sale
del hash del manifiesto, asi que el calculo es en dos pasadas: (1) se renderizan los archivos con el marcador
`mv-pending`; (2) el hash de esa lista (nombre + SHA-256 de cada archivo con marcador, mas los metadatos, sin el
id) da los 8 hex; (3) se renderizan de nuevo con el id y el manifiesto final lista los SHA-256 reales. La fecha
sale de `reference_date` de la configuracion (la entrega no lee el reloj, NFR-U5-11).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from vectra_contracts.models.features import (
    FeatureDictionary,
    FeatureDictionaryEntry,
    FeatureSpec,
)

from vectra_reference.features import PLACEHOLDER_ID, Value, base_feature_spec, validate_feature_spec
from vectra_reference.proxy import (
    DETAIL_FEATURE,
    PROXY_FEATURES,
    ZONE_FEATURE,
    check_proxy_spec,
    load_proxy_catalog,
)
from vectra_reference.train import TrainedModel, predictor_bytes

MANIFEST = "manifest.json"
PACKAGE_FILES: Final = (
    "predictor.json",
    "explainer.json",
    "background.csv",
    "domain_envelope.json",
    "feature_dictionary.json",
    "feature_spec.json",
)
PURPOSE_BASE: Final = "base"
PURPOSE_RT2: Final = "rt2-demo"  # BR-U5-15: la variante proxy solo sirve para la demostracion de RT-2
FORBIDDEN_SUFFIXES: Final = (".pkl", ".pickle", ".joblib")
ZIP_MAGIC: Final = b"PK\x03\x04"
PICKLE_PROTOCOLS: Final = tuple(range(2, 6))
ID_CARRIERS: Final = (
    "explainer.json",
    "domain_envelope.json",
    "feature_dictionary.json",
    "feature_spec.json",
)

# Diccionario en espanol (BR-U5-10): etiqueta, unidad y frases de direccion de cada feature del modelo base.
_DICTIONARY: Final[dict[str, tuple[str, str | None, str, str]]] = {
    "installment_to_income": (
        "Relación cuota-ingreso",
        "razón",
        "La cuota pesa más sobre el ingreso, lo que aumenta el riesgo.",
        "La cuota pesa menos sobre el ingreso, lo que reduce el riesgo.",
    ),
    "loan_to_value": (
        "Relación préstamo-valor",
        "razón",
        "El préstamo es una parte mayor del valor de la vivienda, lo que aumenta el riesgo.",
        "El préstamo es una parte menor del valor de la vivienda, lo que reduce el riesgo.",
    ),
    "monthly_income": (
        "Ingreso mensual",
        "COP",
        "Un ingreso mensual mayor aumenta el riesgo estimado.",
        "Un ingreso mensual mayor reduce el riesgo estimado.",
    ),
    "other_income": (
        "Otros ingresos",
        "COP",
        "Los otros ingresos declarados aumentan el riesgo estimado.",
        "Los otros ingresos declarados reducen el riesgo estimado.",
    ),
    "monthly_obligations": (
        "Obligaciones mensuales",
        "COP",
        "Las obligaciones mensuales declaradas aumentan el riesgo.",
        "Las obligaciones mensuales declaradas reducen el riesgo.",
    ),
    "employment_type": (
        "Tipo de empleo",
        None,
        "El tipo de empleo declarado se asocia con un riesgo mayor.",
        "El tipo de empleo declarado se asocia con un riesgo menor.",
    ),
    "employment_months": (
        "Antigüedad laboral",
        "meses",
        "Una antigüedad laboral mayor aumenta el riesgo estimado.",
        "Una antigüedad laboral mayor reduce el riesgo estimado.",
    ),
    "max_days_past_due_12m": (
        "Mora máxima en 12 meses",
        "días",
        "Una mora máxima mayor en los últimos 12 meses aumenta el riesgo.",
        "Una mora máxima menor en los últimos 12 meses reduce el riesgo.",
    ),
    "term_months": (
        "Plazo del crédito",
        "meses",
        "Un plazo mayor aumenta el riesgo estimado.",
        "Un plazo mayor reduce el riesgo estimado.",
    ),
    "proposed_rate_ea": (
        "Tasa propuesta efectiva anual",
        "% E.A.",
        "Una tasa propuesta mayor aumenta el riesgo estimado.",
        "Una tasa propuesta menor reduce el riesgo estimado.",
    ),
    "property_condition": (
        "Condición de la vivienda",
        None,
        "La condición de la vivienda (nueva o usada) se asocia con un riesgo mayor.",
        "La condición de la vivienda (nueva o usada) se asocia con un riesgo menor.",
    ),
    "channel": (
        "Canal de originación",
        None,
        "El canal por el que llegó la solicitud se asocia con un riesgo mayor.",
        "El canal por el que llegó la solicitud se asocia con un riesgo menor.",
    ),
    # Solo la variante proxy (RT-2): ambas se marcan `applicant_safe = false` (no se muestran al solicitante).
    ZONE_FEATURE: (
        "Zona de la vivienda",
        None,
        "La zona de la vivienda se asocia con un riesgo mayor.",
        "La zona de la vivienda se asocia con un riesgo menor.",
    ),
    DETAIL_FEATURE: (
        "Detalle del canal de originación",
        None,
        "El detalle del canal por el que llegó la solicitud se asocia con un riesgo mayor.",
        "El detalle del canal por el que llegó la solicitud se asocia con un riesgo menor.",
    ),
}


class PackageError(Exception):
    """El paquete no cumple BR-U5-09 o BR-U5-10: la entrega falla."""


def dump_json(value: Any) -> bytes:
    """JSON canonico: claves ordenadas, UTF-8, salto de linea final. Determinista."""
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def feature_dictionary(
    spec: FeatureSpec, dictionary_version: str, *, not_applicant_safe: Sequence[str] = ()
) -> FeatureDictionary:
    """BR-U5-10: una entrada por feature del `feature_spec`, en espanol y con `applicant_safe`.

    En el modelo base todas son seguras de mostrar al solicitante; la variante proxy marca
    `zona_vivienda` y `canal_originacion_detalle` con `applicant_safe = false` (`not_applicant_safe`).
    """
    entries = []
    for item in spec.features:
        label, unit, up, down = _DICTIONARY[item.feature_id]
        entries.append(
            FeatureDictionaryEntry(
                feature_id=item.feature_id,
                label_es=label,
                unit=unit,
                increases_risk_phrase_es=up,
                decreases_risk_phrase_es=down,
                applicant_safe=item.feature_id not in not_applicant_safe,
            )
        )
    return FeatureDictionary(
        dictionary_version=dictionary_version, model_version_id=spec.model_version_id, entries=entries
    )


def check_dictionary_coverage(spec: FeatureSpec, dictionary: FeatureDictionary) -> None:
    """BR-U5-10 (PBT-U5-06): el diccionario cubre todas las features del `feature_spec` y viceversa."""
    in_spec = {item.feature_id for item in spec.features}
    in_dictionary = {entry.feature_id for entry in dictionary.entries}
    if in_spec - in_dictionary:
        raise PackageError(f"dictionary_incomplete:{sorted(in_spec - in_dictionary)[0]}")
    if in_dictionary - in_spec:
        raise PackageError(f"dictionary_extra:{sorted(in_dictionary - in_spec)[0]}")


def _background_csv(feature_order: Sequence[str], rows: Sequence[Mapping[str, Value]]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(feature_order)
    for row in rows:
        writer.writerow([row[name] for name in feature_order])
    return out.getvalue().encode("utf-8")


def _render(
    model_version_id: str,
    model: TrainedModel,
    envelope: Mapping[str, Any],
    background: Sequence[Mapping[str, Value]],
    base_value: float,
    dictionary_version: str,
    spec_for: Callable[[str], FeatureSpec] = base_feature_spec,
    not_applicant_safe: Sequence[str] = (),
) -> dict[str, bytes]:
    spec = spec_for(model_version_id)
    if tuple(item.feature_id for item in spec.features) != model.feature_order:
        raise PackageError("feature_order_differs_from_spec")
    return {
        "predictor.json": predictor_bytes(model.booster),
        "explainer.json": dump_json(
            {
                "model_version_id": model_version_id,
                "mode": "tree_path_dependent",
                "runtime": "xgboost pred_contribs=True",
                "feature_order": list(model.feature_order),
                "categorical_encoding": model.vocabulary,
                "base_value": base_value,
            }
        ),
        "background.csv": _background_csv(model.feature_order, background),
        "domain_envelope.json": dump_json({**envelope, "model_version_id": model_version_id}),
        "feature_dictionary.json": dump_json(
            feature_dictionary(spec, dictionary_version, not_applicant_safe=not_applicant_safe).model_dump(
                mode="json"
            )
        ),
        "feature_spec.json": dump_json(spec.model_dump(mode="json")),
    }


def build_package(
    out_dir: Path,
    model: TrainedModel,
    envelope: Mapping[str, Any],
    background: Sequence[Mapping[str, Value]],
    base_value: float,
    config: Mapping[str, Any],
    stats: Mapping[str, Any],
    *,
    spec_for: Callable[[str], FeatureSpec] = base_feature_spec,
    purpose: str = PURPOSE_BASE,
    not_applicant_safe: Sequence[str] = (),
    extra_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Escribe el paquete en `out_dir` y devuelve el manifiesto. Verifica el resultado antes de devolverlo.

    La variante proxy (BR-U5-15) pasa su `spec_for`, `purpose = rt2-demo` y `extra_meta = {"rt2_run": n}`; los metadatos
    entran en el hash del `model_version_id`, asi que cada corrida tiene un id distinto con el mismo predictor.
    """
    dictionary_version = str(config["generator_version"])

    def render(version: str) -> dict[str, bytes]:
        return _render(
            version, model, envelope, background, base_value, dictionary_version, spec_for, not_applicant_safe
        )

    pending = render(PLACEHOLDER_ID)
    meta: dict[str, Any] = {
        "manifest_version": 1,
        "generator_version": config["generator_version"],
        "seed": config["seed"],
        "purpose": purpose,
        **(extra_meta or {}),
        **stats,
    }
    digest = sha256(
        dump_json({**meta, "files": [{"name": n, "sha256": sha256(pending[n])} for n in sorted(pending)]})
    )[:8]
    model_version_id = f"mv-{config['reference_date']}-{digest}"
    files = render(model_version_id)
    manifest = {
        **meta,
        "model_version_id": model_version_id,
        "files": [
            {"name": name, "sha256": sha256(files[name]), "model_version_id": model_version_id}
            for name in sorted(files)
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out_dir / name).write_bytes(data)
    (out_dir / MANIFEST).write_bytes(dump_json(manifest))
    errors = verify_package(out_dir)
    if errors:
        raise PackageError("; ".join(errors))
    return manifest


def has_executable_magic(data: bytes) -> bool:
    """Bytes magicos de pickle (`\\x80` + protocolo 2 a 5) o de la cabecera zip de joblib."""
    return data.startswith(ZIP_MAGIC) or (len(data) > 1 and data[0] == 0x80 and data[1] in PICKLE_PROTOCOLS)


def verify_package(directory: Path) -> list[str]:
    """BR-U5-09 y BR-U5-10 sobre un paquete en disco (PBT-U5-05, PBT-U5-06). Devuelve los errores; vacio = valido.

    Cada archivo listado existe, su SHA-256 coincide, todos llevan el mismo `model_version_id` (en el manifiesto y
    dentro de los JSON que lo llevan), ninguno es pickle/joblib, el `feature_spec` solo tiene features permitidas y
    el diccionario las cubre.
    """
    try:
        manifest = json.loads((directory / MANIFEST).read_bytes())
        listed = {entry["name"]: entry for entry in manifest["files"]}
        version = manifest["model_version_id"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"manifest_unreadable:{exc.__class__.__name__}"]
    errors = [f"file_not_listed:{name}" for name in PACKAGE_FILES if name not in listed]
    for name, entry in listed.items():
        if name.lower().endswith(FORBIDDEN_SUFFIXES):
            errors.append(f"forbidden_extension:{name}")
        path = directory / name
        if not path.is_file():
            errors.append(f"file_missing:{name}")
            continue
        data = path.read_bytes()
        if has_executable_magic(data):
            errors.append(f"executable_magic:{name}")
        if sha256(data) != entry.get("sha256"):
            errors.append(f"sha256_mismatch:{name}")
        if entry.get("model_version_id") != version:
            errors.append(f"model_version_id_mismatch:{name}")
        if name in ID_CARRIERS:
            try:
                if json.loads(data).get("model_version_id") != version:
                    errors.append(f"model_version_id_inside_mismatch:{name}")
            except (ValueError, AttributeError):
                errors.append(f"json_unreadable:{name}")
    extra = PROXY_FEATURES if manifest.get("purpose") == PURPOSE_RT2 else ()
    return errors + _verify_features(directory, extra)


def _verify_features(directory: Path, extra_allowed: Sequence[str] = ()) -> list[str]:
    try:
        spec = FeatureSpec.model_validate_json((directory / "feature_spec.json").read_bytes())
        dictionary = FeatureDictionary.model_validate_json(
            (directory / "feature_dictionary.json").read_bytes()
        )
    except (OSError, ValueError):
        return ["feature_files_unreadable"]
    errors: list[str] = []
    try:
        validate_feature_spec(spec, extra_allowed)
    except ValueError as exc:
        errors.append(str(exc))
    try:
        check_dictionary_coverage(spec, dictionary)
    except PackageError as exc:
        errors.append(str(exc))
    if (
        extra_allowed
    ):  # variante proxy: BR-U5-15, cada zona con al menos 5 municipios; y `applicant_safe = false`
        errors += check_proxy_spec(spec, dictionary, load_proxy_catalog())
    return errors
