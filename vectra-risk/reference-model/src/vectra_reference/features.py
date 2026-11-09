"""Features del modelo base y su especificacion (domain-entities §3.1; BR-U5-07, BR-U5-10).

Unica fuente de la lista de features: `train`, `envelope`, `package` y las pruebas la comparten.
Los valores de una fila se calculan con las mismas funciones de U0 que usa `derive` (una prueba compara
ambos caminos); no se llama a `derive` fila a fila porque construye un `FeatureVector` por fila (1 ms) y la
entrega recorre 120 000 filas.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import pyarrow.parquet as pq
from vectra_contracts.finance import installment, installment_to_income, loan_to_value, to_decimal4_str
from vectra_contracts.models.features import FeatureSpec, FeatureSpecItem

Value = float | str

# Orden fijo de las features del modelo base (domain-entities §3.1). `monthly_income` entra sin log (§3.1 lo pide con
# log): `derive` de U0 no ofrece una feature `monthly_income_log`. Los arboles no notan la diferencia, pero la
# envolvente SI: la distancia de Mahalanobis se calcula sobre el ingreso crudo y sesgado. `proposed_rate_ea` se trata
# como numerica aunque `derive` la entregue como categoria (defecto de U0, ver CANDIDATAS.md).
BASE_SPEC: Final[tuple[tuple[str, str, bool], ...]] = (
    # (feature_id, origin, numerica)
    ("installment_to_income", "derived", True),
    ("loan_to_value", "derived", True),
    ("monthly_income", "field", True),
    ("other_income", "field", True),
    ("monthly_obligations", "field", True),
    ("employment_type", "field", False),
    ("employment_months", "field", True),
    ("max_days_past_due_12m", "field", True),
    ("term_months", "field", True),
    ("proposed_rate_ea", "field", True),
    ("property_condition", "field", False),
    ("channel", "field", False),
)
BASE_FEATURES: Final[tuple[str, ...]] = tuple(f for f, _, _ in BASE_SPEC)
NUMERIC_FEATURES: Final[tuple[str, ...]] = tuple(f for f, _, numeric in BASE_SPEC if numeric)
CATEGORICAL_FEATURES: Final[tuple[str, ...]] = tuple(f for f, _, numeric in BASE_SPEC if not numeric)

# Excluidas (domain-entities §3.1): protegidas, identificadores y texto libre. Las protegidas quedan solo
# como `MonitoringLabels`. `age_years`, `installment_cop` y `region` son salidas de `derive`/`MonitoringLabels`.
EXCLUDED_FEATURES: Final[frozenset[str]] = frozenset(
    {
        "sex",
        "socioeconomic_stratum",
        "region",
        "department_code",
        "municipality_code",
        "age_years",
        "birth_date",
        "free_text",
        "broker_id",
        "full_name",
        "document_type",
        "document_number",
        "phone",
        "email",
        "address",
        "synthetic_id",
    }
)

PLACEHOLDER_ID: Final = "mv-pending"


class FeatureSpecError(ValueError):
    """El `feature_spec` contiene una feature excluida o ajena al modelo (BR-U5-07)."""


def base_feature_spec(model_version_id: str = PLACEHOLDER_ID) -> FeatureSpec:
    return FeatureSpec(
        model_version_id=model_version_id,
        features=[
            FeatureSpecItem(
                feature_id=feature_id,
                origin=origin,  # type: ignore[arg-type]
                source_fields=[] if origin == "derived" else [feature_id],
            )
            for feature_id, origin, _ in BASE_SPEC
        ],
    )


def validate_feature_spec(spec: FeatureSpec, extra_allowed: Iterable[str] = ()) -> None:
    """BR-U5-07: el `feature_spec` solo contiene las features de §3.1 (mas `extra_allowed`, para la variante proxy).

    Una feature excluida, o un campo excluido como origen, lanza `FeatureSpecError`.
    """
    allowed = set(BASE_FEATURES) | set(extra_allowed)
    for item in spec.features:
        if item.feature_id in EXCLUDED_FEATURES:
            raise FeatureSpecError(f"excluded_feature:{item.feature_id}")
        bad = EXCLUDED_FEATURES & set(item.source_fields)
        if bad and item.feature_id not in set(extra_allowed):
            raise FeatureSpecError(f"excluded_source_field:{sorted(bad)[0]}")
        if item.feature_id not in allowed:
            raise FeatureSpecError(f"feature_not_allowed:{item.feature_id}")
    ids = [item.feature_id for item in spec.features]
    if len(set(ids)) != len(ids):
        raise FeatureSpecError("feature_repeated")


def categorical_vocabulary(config: Mapping[str, Any]) -> dict[str, list[str]]:
    """Codificacion ordinal de las categoricas: el codigo de un valor es su posicion; fuera de la lista = -1."""
    m = config["marginals"]
    return {
        "employment_type": list(m["employment_weights"]),
        "property_condition": ["nueva", "usada"],
        "channel": list(m["channel_weights"]),
    }


def row_values(row: Mapping[str, Any]) -> dict[str, Value]:
    """Valores de las features de una fila (o `ApplicationIn` como diccionario) con las funciones de U0."""
    cuota = installment(row["requested_amount"], Decimal(row["proposed_rate_ea"]), row["term_months"])
    values: dict[str, Value] = {
        "installment_to_income": float(
            to_decimal4_str(installment_to_income(cuota, row["monthly_income"], row["other_income"]))
        ),
        "loan_to_value": float(
            to_decimal4_str(loan_to_value(row["requested_amount"], row["property_value"]))
        ),
    }
    for feature_id, origin, numeric in BASE_SPEC:
        if origin == "field":
            values[feature_id] = float(row[feature_id]) if numeric else str(row[feature_id])
    return {f: values[f] for f in BASE_FEATURES}


def read_rows(path: Path) -> list[dict[str, Any]]:
    return pq.read_table(path).to_pylist()


def split_values(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Value]]:
    return [row_values(r) for r in rows]
