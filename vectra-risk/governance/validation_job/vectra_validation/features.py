"""Dataset de validacion (Parquet, F31) a matriz de features y etiquetas de monitoreo, con las funciones de U0 (`derive`)."""

import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pyarrow.parquet as pq
from numpy.typing import NDArray
from pydantic import ValidationError
from vectra_contracts.labels import derive, derive_monitoring_labels
from vectra_contracts.models.application import ApplicationIn
from vectra_contracts.models.features import CategoryFeature, FeatureSpec

from vectra_validation.errors import ValidationJobError

LABEL_COLUMN = "default"
NON_APPLICATION = ("synthetic_id", LABEL_COLUMN)


@dataclass(frozen=True)
class Dataset:
    matrix: NDArray[np.float64]
    defaults: list[int]
    monitoring: list[dict[str, str]]  # sexo, rango_edad, region, estrato y banda de cada fila, en el orden de las filas


def read_rows(parquet: bytes) -> list[dict[str, Any]]:
    return list(pq.read_table(io.BytesIO(parquet)).to_pylist())


def _application(row: Mapping[str, Any]) -> ApplicationIn:
    data = {k: v for k, v in row.items() if k not in NON_APPLICATION}
    if isinstance(data.get("birth_date"), str):
        data["birth_date"] = date.fromisoformat(data["birth_date"])
    try:
        return ApplicationIn.model_validate(data)
    except ValidationError as error:
        raise ValidationJobError("dataset_row_invalid") from error


def build_dataset(
    rows: Sequence[Mapping[str, Any]],
    spec: FeatureSpec,
    feature_order: Sequence[str],
    encoding: Mapping[str, Sequence[str]],
    evaluated_on: date,
) -> Dataset:
    """Matriz `(n, k)` en el orden del explicador (categoricas por su posicion, -1 si no estan), `default` y etiquetas.

    Es la misma derivacion que usa scoring (BR-U0-30..43): la AUC y la disparidad se miden sobre lo que el modelo veria.
    """
    if not rows:
        raise ValidationJobError("dataset_empty")
    matrix = np.empty((len(rows), len(feature_order)), dtype=np.float64)
    defaults: list[int] = []
    monitoring: list[dict[str, str]] = []
    for i, row in enumerate(rows):
        application = _application(row)
        features = derive(application, evaluated_on, spec).features
        for j, name in enumerate(feature_order):
            item = features.get(name)
            if item is None:
                raise ValidationJobError(f"feature_missing:{name}")
            if isinstance(item, CategoryFeature):
                values = list(encoding.get(name, ()))
                matrix[i, j] = values.index(item.value) if item.value in values else -1
            else:
                matrix[i, j] = float(item.value)
        labels = derive_monitoring_labels(application, evaluated_on)
        monitoring.append(
            {
                "sexo": labels.sexo,
                "rango_edad": labels.rango_edad,
                "region": labels.region,
                "estrato": labels.estrato,
                "banda": labels.banda_capacidad_pago,
            }
        )
        defaults.append(int(row[LABEL_COLUMN]))
    return Dataset(matrix, defaults, monitoring)
