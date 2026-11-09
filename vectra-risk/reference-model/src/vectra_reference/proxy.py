"""Variante proxy de RT-2 y medicion de disparidad (BR-U5-06, BR-U5-14, BR-U5-15; US-303).

La variante agrega dos features a las del modelo base, ambas como busquedas del `feature_spec` que `derive` (U0)
aplica sobre campos de `ApplicationIn`:

- `zona_vivienda`: `municipality_code -> zona` (cada zona con al menos 5 municipios; el municipio nunca llega al
  `FeatureVector`, BR-U0-34);
- `canal_originacion_detalle`: `channel|broker_id -> detalle` (el corredor nunca llega al vector).

La etiqueta de la variante depende de forma PARCIAL de las dos busquedas (`generator.yaml`, seccion `proxy`), asi que el
modelo aprende una dependencia de la region que ninguna feature declara. La disparidad se mide como la mide U9.

**Libreria de U9.** La disparidad se mide con `vectra_disparity` (`counts_from_records`, `disparity_by_band`,
`model_aggregate`) sobre el `outcome` de BR-U7-04/05: solo `favorable` cuenta como favorable y `revision_requerida` no
(BR-U9-01). `n_min = 30` (BR-U9-02). BR-U5-14 (enmendada en U05-T05): la variante debe pasar de 18 pp por `region`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import numpy as np
import yaml
from vectra_contracts.dane import DEPARTMENT_REGION, MUNICIPALITY_DEPARTMENT
from vectra_contracts.finance import installment, installment_to_income
from vectra_contracts.labels import age_range, payment_band, region_of
from vectra_contracts.models.features import FeatureDictionary, FeatureSpec, FeatureSpecItem
from vectra_contracts.models.governance import PolicyDraft
from vectra_contracts.validation import age_at
from vectra_disparity import (
    ATTRIBUTES,
    CountTable,
    counts_from_records,
    disparity_by_band,
    model_aggregate,
)

from vectra_reference.features import Value, base_feature_spec

CATALOG_PATH: Final = Path(__file__).resolve().parents[2] / "config" / "catalog" / "proxy.yaml"
ZONE_FEATURE: Final = "zona_vivienda"
DETAIL_FEATURE: Final = "canal_originacion_detalle"
PROXY_FEATURES: Final = (ZONE_FEATURE, DETAIL_FEATURE)
LOOKUP_SEPARATOR: Final = "|"  # el mismo que usa `derive` de U0 al armar la clave de la busqueda
N_MIN: Final = 30  # BR-U9-02


class ProxyError(Exception):
    """La variante proxy no cumple BR-U5-14/15 o el modelo base no cumple BR-U5-06: la entrega falla."""


def load_proxy_catalog(path: Path | None = None) -> dict[str, Any]:
    with (path or CATALOG_PATH).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)  # type: ignore[no-any-return]


# Busquedas --------------------------------------------------------------------------------------------------------


def zone_table(catalog: Mapping[str, Any]) -> dict[str, str]:
    """`municipality_code -> zona`. Falla si un departamento queda sin zona, si esta en dos, o si una zona tiene
    menos de `min_municipios_por_zona` municipios (BR-U5-15: el municipio no debe poder recuperarse de la zona)."""
    zone_of_department: dict[str, str] = {}
    for zone, departments in catalog["zonas"].items():
        for department in departments:
            if department in zone_of_department:
                raise ProxyError(f"department_in_two_zones:{department}")
            if department not in DEPARTMENT_REGION:
                raise ProxyError(f"department_unknown:{department}")
            zone_of_department[department] = zone
    table: dict[str, str] = {}
    for municipality, department in sorted(MUNICIPALITY_DEPARTMENT.items()):
        if department not in zone_of_department:
            raise ProxyError(f"department_without_zone:{department}")
        table[municipality] = zone_of_department[department]
    minimum = int(catalog["min_municipios_por_zona"])
    counts = Counter(table.values())
    for zone in catalog["zonas"]:
        if counts[zone] < minimum:
            raise ProxyError(f"zone_too_small:{zone}:{counts[zone]}<{minimum}")
    return table


def check_proxy_spec(
    spec: FeatureSpec, dictionary: FeatureDictionary, catalog: Mapping[str, Any]
) -> list[str]:
    """BR-U5-15 sobre un paquete en disco: las dos busquedas existen, cada zona de la tabla tiene al menos
    `min_municipios_por_zona` municipios y el diccionario marca ambas features con `applicant_safe = false`."""
    items = {item.feature_id: item for item in spec.features}
    errors = [f"proxy_feature_missing:{f}" for f in PROXY_FEATURES if f not in items]
    zone = items.get(ZONE_FEATURE)
    if zone is not None:
        counts = Counter((zone.table or {}).values())
        minimum = int(catalog["min_municipios_por_zona"])
        errors += [f"zone_too_small:{z}:{n}<{minimum}" for z, n in sorted(counts.items()) if n < minimum]
    safe = {e.feature_id: e.applicant_safe for e in dictionary.entries}
    errors += [f"proxy_feature_applicant_safe:{f}" for f in PROXY_FEATURES if safe.get(f, False)]
    return errors


def broker_ids(config: Mapping[str, Any]) -> list[str]:
    from vectra_reference.generate import BROKER_PREFIX  # noqa: PLC0415  (evita un ciclo de importacion)

    return [f"{BROKER_PREFIX}{n:03d}" for n in range(1, int(config["marginals"]["brokers"]) + 1)]


def detail_table(catalog: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, str]:
    """`channel|broker_id -> detalle`. Un canal sin corredor es su propio detalle; un corredor, el grupo de su numero."""
    groups = catalog["grupos_de_corredores"]
    per_group = int(catalog["corredores_por_grupo"])
    table = {f"{channel}{LOOKUP_SEPARATOR}": channel for channel in config["marginals"]["channel_weights"]}
    table["aliado_inmobiliario" + LOOKUP_SEPARATOR] = str(catalog["canal_sin_corredor"])
    for n, broker in enumerate(broker_ids(config)):
        table[f"aliado_inmobiliario{LOOKUP_SEPARATOR}{broker}"] = groups[min(n // per_group, len(groups) - 1)]
    return table


def proxy_vocabulary(catalog: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, list[str]]:
    """Valores de las dos categoricas nuevas, en orden fijo (la codificacion ordinal es la posicion)."""
    zones = [*catalog["zonas"], str(catalog["zona_sin_dato"])]
    details = list(config["marginals"]["channel_weights"])
    details = [d for d in details if d != "aliado_inmobiliario"]
    details += [
        str(catalog["canal_sin_corredor"]),
        *catalog["grupos_de_corredores"],
        str(catalog["canal_sin_dato"]),
    ]
    return {ZONE_FEATURE: zones, DETAIL_FEATURE: details}


def proxy_feature_spec(
    catalog: Mapping[str, Any], config: Mapping[str, Any], model_version_id: str
) -> FeatureSpec:
    """El `feature_spec` del modelo base mas las dos busquedas (`origin = "lookup"`, con `table` y `default`)."""
    base = base_feature_spec(model_version_id)
    lookups = [
        FeatureSpecItem(
            feature_id=ZONE_FEATURE,
            origin="lookup",
            source_fields=["municipality_code"],
            table=zone_table(catalog),
            default=str(catalog["zona_sin_dato"]),
        ),
        FeatureSpecItem(
            feature_id=DETAIL_FEATURE,
            origin="lookup",
            source_fields=["channel", "broker_id"],
            table=detail_table(catalog, config),
            default=str(catalog["canal_sin_dato"]),
        ),
    ]
    return FeatureSpec(model_version_id=model_version_id, features=[*base.features, *lookups])


def lookup_value(item: FeatureSpecItem, row: Mapping[str, Any]) -> str:
    """La misma busqueda que `derive` de U0 (clave `campo|campo`, `None` como cadena vacia, `default` si no esta)."""
    key = LOOKUP_SEPARATOR.join(str(row.get(f) or "") for f in item.source_fields)
    value = (item.table or {}).get(key, item.default)
    if value is None:
        raise ProxyError("lookup_without_value")
    return value


def with_lookups(values: Mapping[str, Value], row: Mapping[str, Any], spec: FeatureSpec) -> dict[str, Value]:
    """Los valores del modelo base mas las dos features de busqueda de una fila, en el orden del `feature_spec`."""
    out: dict[str, Value] = dict(values)
    for item in spec.features:
        if item.origin == "lookup":
            out[item.feature_id] = lookup_value(item, row)
    return {item.feature_id: out[item.feature_id] for item in spec.features}


# Etiqueta con dependencia parcial ---------------------------------------------------------------------------------


def proxy_labels(
    rows: Sequence[Mapping[str, Any]],
    base_default: Sequence[int],
    spec: FeatureSpec,
    config: Mapping[str, Any],
    partition: int,
) -> np.ndarray:
    """Etiqueta de la variante: la del dataset base, mas incumplimientos extra segun la zona y el detalle de canal.

    La semilla es `[seed, label_seed_stream, particion]`, asi que cada particion es determinista e independiente.
    """
    cfg = config["proxy"]
    zone_extra, detail_extra = cfg["zone_extra_default"], cfg["detail_extra_default"]
    zone_item, detail_item = (next(i for i in spec.features if i.feature_id == f) for f in PROXY_FEATURES)
    rng = np.random.default_rng([int(config["seed"]), int(cfg["label_seed_stream"]), partition])
    draws = rng.random(len(rows))
    out = np.array(base_default, dtype=np.int64)
    for i, row in enumerate(rows):
        a = float(zone_extra.get(lookup_value(zone_item, row), 0.0))
        b = float(detail_extra.get(lookup_value(detail_item, row), 0.0))
        if draws[i] < 1.0 - (1.0 - a) * (1.0 - b):
            out[i] = 1
    return out


# Disparidad con la libreria de U9 (BR-U9-01..05) -------------------------------------------------------------------------


def monitoring_labels(row: Mapping[str, Any], evaluated_on: date) -> dict[str, str]:
    """Etiquetas de monitoreo de una fila (BR-U0-40..43), calculadas con las funciones de U0."""
    cuota = installment(row["requested_amount"], Decimal(row["proposed_rate_ea"]), row["term_months"])
    birth = row["birth_date"]
    birth_date = date.fromisoformat(birth) if isinstance(birth, str) else birth
    return {
        "sexo": str(row["sex"]),
        "rango_edad": age_range(age_at(birth_date, evaluated_on)),
        "region": region_of(str(row["department_code"])),
        "estrato": str(row["socioeconomic_stratum"]),
        "banda": payment_band(installment_to_income(cuota, row["monthly_income"], row["other_income"])),
    }


FAVORABLE: Final = "favorable"
UNFAVORABLE: Final = "desfavorable"
REVIEW: Final = "revision_requerida"


def outcome_of(
    probability: float, confidence: str, proposed_rate_ea: str, policy: PolicyDraft, evaluated_on: date
) -> str:
    """`outcome` de la recomendacion (BR-U7-04 y BR-U7-05), con la politica de referencia.

    `revision_requerida` si `normative` es nulo (ninguna vigencia cubre `evaluated_on`), si la tasa supera la usura
    (igual no es sobre) o si `confidence < low_confidence_threshold`; si no, `favorable` cuando `score < cutoff` y
    `desfavorable` en otro caso. La politica de este paquete no tiene reglas por canal (`channel_rules` vacio).
    """
    normative = next(
        (
            n
            for n in policy.normative
            if n.effective_from <= evaluated_on and (n.effective_to is None or evaluated_on <= n.effective_to)
        ),
        None,
    )
    if normative is None:
        return REVIEW
    if Decimal(proposed_rate_ea) > Decimal(normative.usury_cap_ea):
        return REVIEW
    if Decimal(confidence) < Decimal(policy.low_confidence_threshold):
        return REVIEW
    return FAVORABLE if probability < float(Decimal(policy.cutoff)) else UNFAVORABLE


def outcomes_of(
    rows: Sequence[Mapping[str, Any]],
    probabilities: Sequence[float],
    confidences: Sequence[str],
    policy: PolicyDraft,
    evaluated_on: date,
) -> list[str]:
    return [
        outcome_of(float(p), c, str(row["proposed_rate_ea"]), policy, evaluated_on)
        for row, p, c in zip(rows, probabilities, confidences, strict=True)
    ]


def counts_of(
    rows: Sequence[Mapping[str, Any]], outcomes: Sequence[str], evaluated_on: date
) -> dict[str, CountTable]:
    """`CountTable` por atributo (U9) de las filas con su `outcome` de BR-U7-04/05."""
    return counts_from_records(
        {**monitoring_labels(row, evaluated_on), "outcome": outcome}
        for row, outcome in zip(rows, outcomes, strict=True)
    )


def model_trigger(counts: Mapping[str, CountTable]) -> tuple[str, float]:
    """Atributo disparador y su agregada (proporcion), con `disparity_by_band` y `model_aggregate` de U9 (BR-U9-05)."""
    result = model_aggregate(disparity_by_band(counts, attribute, N_MIN) for attribute in ATTRIBUTES)
    if result is None:
        raise ProxyError("disparity_insufficient_sample")
    return result[0], float(result[1])


def disparity_pp(
    rows: Sequence[Mapping[str, Any]], outcomes: Sequence[str], evaluated_on: date
) -> tuple[str, float]:
    """Disparidad agregada del modelo en puntos porcentuales y su atributo disparador (libreria de U9).

    `outcomes` son los de `outcomes_of` (BR-U7-04/05). Solo `favorable` cuenta como favorable: `revision_requerida` y
    `desfavorable` no (BR-U9-01).
    """
    trigger, aggregate = model_trigger(counts_of(rows, outcomes, evaluated_on))
    return trigger, round(aggregate * 100.0, 4)


def check_base_disparity(measured_pp: float, config: Mapping[str, Any]) -> None:
    """BR-U5-06: la disparidad del modelo base debe quedar por debajo de 5 pp."""
    limit = float(config["proxy"]["max_base_disparity_pp"])
    if not measured_pp < limit:
        raise ProxyError(f"base_disparity_not_below:{measured_pp:.2f}>={limit}")


def check_proxy_disparity(measured_pp: float, config: Mapping[str, Any]) -> None:
    """BR-U5-14 (enmendada en U05-T05): la disparidad de la variante debe ser al menos de `min_disparity_pp` (18 pp)."""
    limit = float(config["proxy"]["min_disparity_pp"])
    if not measured_pp >= limit:
        raise ProxyError(f"proxy_disparity_below:{measured_pp:.2f}<{limit}")
