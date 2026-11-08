"""Generador de datos sinteticos de U5 (BR-U5-01..05; NFR-U5-11, 34; US-202).

Determinista: el mismo `generator_version` y la misma `seed` producen los mismos Parquet byte a byte (BR-U5-02).
Sin reloj, sin rutas ni nombres de maquina dentro de los archivos. Ningun dato real (BR-U5-01).
"""

from __future__ import annotations

import argparse
import copy
import math
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from vectra_contracts.dane import DEPARTMENT_REGION, MUNICIPALITY_DEPARTMENT
from vectra_contracts.finance import installment, installment_to_income, loan_to_value
from vectra_contracts.models.application import ApplicationIn

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "generator.yaml"
CATALOG_PATH = Path(__file__).resolve().parents[2] / "config" / "catalog" / "names.yaml"
COP_MAX = 10**12  # tope de `COP` en U0
PARTITIONS = ("train", "validation", "test")
ID_PREFIX = "SYN-"
# Los CC se toman de un bloque reservado de 10 digitos que no se asigna a personas (prefijo 999); los demas documentos
# llevan el prefijo `SYN` (el patron de U0 no admite guiones). Ver NFR-U5-34.
CC_RESERVED_PREFIX = "999"
DOC_SYN_PREFIX = "SYN"
BROKER_PREFIX = "SYN-BRK-"
EMAIL_DOMAIN = "example.com"  # RFC 2606: dominio reservado para documentacion
SEX = ("F", "M", "no_informado")
STRATA = ("1", "2", "3", "4", "5", "6", "no_informado")

# Orden fijo de columnas (BR-U5-02). Las de `ApplicationIn` van en el orden del modelo de U0; luego `default`.
APPLICATION_COLUMNS = (
    "full_name",
    "document_type",
    "document_number",
    "birth_date",
    "phone",
    "email",
    "address",
    "municipality_code",
    "department_code",
    "monthly_income",
    "other_income",
    "employment_type",
    "employment_months",
    "monthly_obligations",
    "max_days_past_due_12m",
    "property_value",
    "requested_amount",
    "term_months",
    "proposed_rate_ea",
    "property_condition",
    "channel",
    "broker_id",
    "free_text",
    "sex",
    "socioeconomic_stratum",
)
COLUMNS = ("synthetic_id", *APPLICATION_COLUMNS, "default")
_INT_COLUMNS = {
    "monthly_income",
    "other_income",
    "employment_months",
    "monthly_obligations",
    "max_days_past_due_12m",
    "property_value",
    "requested_amount",
    "term_months",
}


class GeneratorError(Exception):
    """Una fila generada es invalida: error del generador, no se descarta en silencio (BR-U5-03)."""


def load_config(path: Path | None = None) -> dict[str, Any]:
    with (path or CONFIG_PATH).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)  # type: ignore[no-any-return]


def load_catalog(path: Path | None = None) -> dict[str, list[str]]:
    with (path or CATALOG_PATH).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)  # type: ignore[no-any-return]


def with_overrides(config: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Copia de la configuracion con claves de primer nivel reemplazadas (p. ej. `seed`, `n_rows`)."""
    out = copy.deepcopy(config)
    out.update(overrides)
    return out


def _choice(rng: np.random.Generator, weights: list[float] | np.ndarray, size: int) -> np.ndarray:
    p = np.asarray(weights, dtype=float)
    p = p / p.sum()
    return np.searchsorted(np.cumsum(p), rng.random(size) * 0.999999999999, side="right").clip(0, len(p) - 1)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50.0, 50.0)))


def _round_to(values: np.ndarray, step: int) -> np.ndarray:
    return (np.round(values / step) * step).astype(np.int64)


def _annuity(amount: np.ndarray, rate_ea: np.ndarray, term: np.ndarray) -> np.ndarray:
    i_m = (1.0 + rate_ea) ** (1.0 / 12.0) - 1.0
    return amount * i_m / (1.0 - (1.0 + i_m) ** (-term.astype(float)))


def _solve_intercept(base: np.ndarray, target: float) -> float:
    """Biseccion de b0 para que la media de sigmoid(b0 + base) sea la tasa objetivo (determinista)."""
    lo, hi = -60.0, 60.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if float(_sigmoid(base + mid).mean()) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _sample_numeric(config: dict[str, Any], rng: np.random.Generator, n: int) -> dict[str, np.ndarray]:
    m = config["marginals"]
    regions = list(m["region_weights"])
    region_idx = _choice(rng, [m["region_weights"][r] for r in regions], n)
    stratum_idx = np.zeros(n, dtype=np.int64)
    for k, region in enumerate(regions):
        mask = region_idx == k
        stratum_idx[mask] = _choice(rng, m["stratum_weights"][region], int(mask.sum()))
    sex_idx = _choice(rng, [m["sex_weights"][s] for s in SEX], n)

    age_cfg = m["age"]
    age = np.clip(np.round(rng.normal(age_cfg["mean"], age_cfg["sd"], n)), age_cfg["min"], age_cfg["max"])
    age_days = rng.integers(0, 365, n)

    inc = m["income"]
    adjust = np.array([inc["region_adjust"][r] for r in regions])[region_idx]
    stratum_level = np.where(stratum_idx < 6, stratum_idx, 2)  # "no_informado" se comporta como estrato 3
    mu = math.log(inc["base_cop"]) + inc["stratum_slope"] * stratum_level + adjust
    income = _round_to(np.clip(np.exp(rng.normal(mu, inc["sigma"])), inc["min_cop"], inc["max_cop"]), 1000)

    oi = m["other_income"]
    has_other = rng.random(n) < oi["p_has"]
    other = np.where(has_other, _round_to(income * rng.exponential(oi["fraction_mean"], n), 1000), 0)
    other = np.minimum(other, income)
    total_income = income + other

    employment_idx = _choice(rng, list(m["employment_weights"].values()), n)
    max_months = np.minimum(720, np.maximum(0, (age - 18) * 12))
    employment_months = np.minimum(max_months, np.round(rng.exponential(72.0, n))).astype(np.int64)

    ob = m["obligations"]
    obl_fraction = rng.beta(ob["fraction_alpha"], ob["fraction_beta"], n)
    obligations = np.where(rng.random(n) < ob["p_zero"], 0, _round_to(total_income * obl_fraction, 1000))

    dq = m["delinquency"]
    dpd = np.where(
        rng.random(n) < dq["p_clean"], 0, np.clip(np.ceil(rng.exponential(dq["scale_days"], n)), 1, 365)
    ).astype(np.int64)

    prop = m["property"]
    p_vis = np.array(m["p_vis_by_stratum"])[stratum_idx]
    is_vis = rng.random(n) < p_vis
    value = total_income * np.exp(rng.normal(prop["multiple_mu"], prop["multiple_sigma"], n))
    cap = float(config["vis_cap_cop"])
    value = np.where(is_vis, np.minimum(value, cap * 0.98), np.maximum(value, cap * 1.02))
    value = _round_to(np.clip(value, prop["min_cop"], COP_MAX), 1000)
    nueva = rng.random(n) < np.where(is_vis, prop["p_nueva_vis"], prop["p_nueva"])

    ltv_cfg = m["ltv"]
    ltv = np.clip(rng.normal(ltv_cfg["mean"], ltv_cfg["sd"], n), ltv_cfg["min"], ltv_cfg["max"])
    amount = np.maximum(1000, np.minimum(_round_to(value * ltv, 1000), value))

    term_cfg = m["term_months"]
    term = np.array(term_cfg["values"], dtype=np.int64)[_choice(rng, term_cfg["weights"], n)]
    rate_cfg = m["rate_ea"]
    rate = rng.normal(rate_cfg["base"], rate_cfg["sd"], n) - np.where(is_vis, rate_cfg["vis_discount"], 0.0)
    rate = np.round(np.clip(rate, rate_cfg["min"], rate_cfg["max"]), 4)

    channels = list(m["channel_weights"])
    channel_idx = _choice(rng, [m["channel_weights"][c] for c in channels], n)
    doc_types = list(m["document_type_weights"])
    doc_idx = _choice(rng, [m["document_type_weights"][d] for d in doc_types], n)

    return {
        "region_idx": region_idx,
        "stratum_idx": stratum_idx,
        "sex_idx": sex_idx,
        "age": age.astype(np.int64),
        "age_days": age_days,
        "income": income,
        "other": other,
        "employment_idx": employment_idx,
        "employment_months": employment_months,
        "obligations": obligations,
        "dpd": dpd,
        "value": value,
        "nueva": nueva,
        "amount": amount,
        "term": term,
        "rate": rate,
        "channel_idx": channel_idx,
        "doc_idx": doc_idx,
        "_regions": np.array(regions),
        "_channels": np.array(channels),
        "_doc_types": np.array(doc_types),
    }


def _latent_default(config: dict[str, Any], rng: np.random.Generator, x: dict[str, np.ndarray]) -> np.ndarray:
    """BR-U5-05: `default` ~ Bernoulli(sigmoid(b0 + ...)), con b0 resuelto para la tasa objetivo."""
    lab = config["label"]
    coef = lab["coefficients"]
    total_income = (x["income"] + x["other"]).astype(float)
    iti = _annuity(x["amount"].astype(float), x["rate"], x["term"]) / total_income
    ltv = x["amount"] / x["value"]
    emp_effect = np.array(list(coef["employment_type"].values()))[x["employment_idx"]]
    base = (
        coef["installment_to_income"] * iti
        + coef["loan_to_value"] * ltv
        + coef["days_past_due_per_30"] * (x["dpd"] / 30.0)
        + coef["employment_years"] * (x["employment_months"] / 12.0)
        + emp_effect
        + coef["obligations_to_income"] * (x["obligations"] / total_income)
        + rng.normal(0.0, lab["noise_sd"], len(total_income))
    )
    b0 = _solve_intercept(base, float(lab["target_default_rate"]))
    return (rng.random(len(base)) < _sigmoid(base + b0)).astype(np.int64)


def _doc_number(rng: np.random.Generator, doc_type: str) -> str:
    if doc_type == "CC":
        return CC_RESERVED_PREFIX + f"{int(rng.integers(0, 10**7)):07d}"
    return DOC_SYN_PREFIX + f"{int(rng.integers(0, 10**9)):09d}"


def build_rows(config: dict[str, Any], catalog: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """Filas completas (`synthetic_id`, campos de `ApplicationIn`, `default`) en el orden de generacion.

    Toda fila se valida con `ApplicationIn` de U0; una fila invalida lanza `GeneratorError` (BR-U5-03).
    """
    catalog = catalog or load_catalog()
    n = int(config["n_rows"])
    rng = np.random.default_rng(int(config["seed"]))
    x = _sample_numeric(config, rng, n)
    default = _latent_default(config, rng, x)

    departments_by_region: dict[str, list[str]] = {}
    for dep, region in sorted(DEPARTMENT_REGION.items()):
        departments_by_region.setdefault(region, []).append(dep)
    municipalities_by_dep: dict[str, list[str]] = {}
    for mun, dep in sorted(MUNICIPALITY_DEPARTMENT.items()):
        municipalities_by_dep.setdefault(dep, []).append(mun)

    given, surnames = catalog["given_names"], catalog["surnames"]
    reference = date.fromisoformat(str(config["reference_date"]))
    # Un bloque de enteros aleatorios por fila para los campos textuales (orden fijo => determinismo).
    draws = rng.integers(0, 2**31 - 1, size=(n, 8))
    jobs = ("asalariado", "independiente", "pensionado")
    conditions = ("usada", "nueva")
    rows: list[dict[str, Any]] = []
    for i in range(n):
        region = str(x["_regions"][x["region_idx"][i]])
        deps = departments_by_region[region]
        dep = deps[int(draws[i, 0]) % len(deps)]
        muns = municipalities_by_dep[dep]
        mun = muns[int(draws[i, 1]) % len(muns)]
        doc_type = str(x["_doc_types"][x["doc_idx"][i]])
        channel = str(x["_channels"][x["channel_idx"][i]])
        birth = reference - timedelta(days=int(x["age"][i]) * 365 + int(x["age_days"][i]) + 1)
        sid = f"{ID_PREFIX}{i + 1:07d}"
        number = _doc_number(np.random.default_rng([int(config["seed"]), i]), doc_type)
        row: dict[str, Any] = {
            "synthetic_id": sid,
            "full_name": (
                f"{given[int(draws[i, 2]) % len(given)]} {surnames[int(draws[i, 3]) % len(surnames)]} "
                f"{surnames[int(draws[i, 4]) % len(surnames)]}"
            ),
            "document_type": doc_type,
            "document_number": number,
            "birth_date": birth,
            "phone": f"0000{i + 1:06d}"[-10:],
            "email": f"{sid.lower()}@{EMAIL_DOMAIN}",
            "address": f"Calle {1 + int(draws[i, 5]) % 150} # {1 + int(draws[i, 6]) % 99}-{1 + int(draws[i, 7]) % 99} (sintetico)",
            "municipality_code": mun,
            "department_code": dep,
            "monthly_income": int(x["income"][i]),
            "other_income": int(x["other"][i]),
            "employment_type": jobs[int(x["employment_idx"][i])],
            "employment_months": int(x["employment_months"][i]),
            "monthly_obligations": int(x["obligations"][i]),
            "max_days_past_due_12m": int(x["dpd"][i]),
            "property_value": int(x["value"][i]),
            "requested_amount": int(x["amount"][i]),
            "term_months": int(x["term"][i]),
            "proposed_rate_ea": f"{float(x['rate'][i]):.4f}",
            "property_condition": conditions[int(x["nueva"][i])],
            "channel": channel,
            "broker_id": f"{BROKER_PREFIX}{1 + int(draws[i, 5]) % 40:03d}"
            if channel == "aliado_inmobiliario"
            else None,
            "free_text": None,
            "sex": SEX[int(x["sex_idx"][i])],
            "socioeconomic_stratum": STRATA[int(x["stratum_idx"][i])],
            "default": int(default[i]),
        }
        _validate(row)
        rows.append(row)
    return rows


def application_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row[k] for k in APPLICATION_COLUMNS}


def _validate(row: dict[str, Any]) -> ApplicationIn:
    try:
        return ApplicationIn.model_validate(application_fields(row))
    except ValueError as exc:
        raise GeneratorError(f"fila {row['synthetic_id']} invalida segun ApplicationIn: {exc}") from exc


def derived_features(row: dict[str, Any]) -> tuple[Decimal, Decimal]:
    """`installment_to_income` y `loan_to_value` de U0 para una fila (los usa la etiqueta y las pruebas)."""
    cuota = installment(row["requested_amount"], Decimal(row["proposed_rate_ea"]), row["term_months"])
    return (
        installment_to_income(cuota, row["monthly_income"], row["other_income"]),
        loan_to_value(row["requested_amount"], row["property_value"]),
    )


def split_indices(default: np.ndarray, config: dict[str, Any]) -> dict[str, np.ndarray]:
    """BR-U5-04: 70/15/15 estratificada por `default`, con la semilla fija; sin solapamiento."""
    rng = np.random.default_rng([int(config["seed"]), 1])
    shares = config["split"]
    parts: dict[str, list[np.ndarray]] = {name: [] for name in PARTITIONS}
    for cls in (0, 1):
        idx = rng.permutation(np.flatnonzero(default == cls))
        n_train = int(round(len(idx) * shares["train"]))
        n_val = int(round(len(idx) * shares["validation"]))
        parts["train"].append(idx[:n_train])
        parts["validation"].append(idx[n_train : n_train + n_val])
        parts["test"].append(idx[n_train + n_val :])
    # Orden de filas fijo: por `synthetic_id` (indice original) dentro de cada particion.
    return {name: np.sort(np.concatenate(chunks)) for name, chunks in parts.items()}


def _table(rows: list[dict[str, Any]]) -> pa.Table:
    arrays = []
    for col in COLUMNS:
        values = [r[col] for r in rows]
        if col == "birth_date":
            values = [v.isoformat() for v in values]
        if col in _INT_COLUMNS:
            arrays.append(pa.array(values, type=pa.int64()))
        elif col == "default":
            arrays.append(pa.array(values, type=pa.int8()))
        else:
            arrays.append(pa.array(values, type=pa.string()))
    return pa.Table.from_arrays(arrays, names=list(COLUMNS))


def generate(
    out_dir: Path, config: dict[str, Any] | None = None, catalog: dict[str, list[str]] | None = None
) -> dict[str, Path]:
    """Escribe `train.parquet`, `validation.parquet` y `test.parquet` en `out_dir` y devuelve sus rutas.

    Parquet sin marcas de tiempo ni metadatos de pandas (BR-U5-02, NFR-U5-11).
    """
    config = config or load_config()
    rows = build_rows(config, catalog)
    default = np.array([r["default"] for r in rows], dtype=np.int64)
    parts = split_indices(default, config)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name in PARTITIONS:
        path = out_dir / f"{name}.parquet"
        pq.write_table(
            _table([rows[int(j)] for j in parts[name]]),
            path,
            compression="zstd",
            use_dictionary=False,
            write_statistics=False,
            store_schema=False,
        )
        paths[name] = path
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera los Parquet sinteticos de U5")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    paths = generate(args.out, load_config(args.config))
    for name, path in paths.items():
        print(f"{name}: {path}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
