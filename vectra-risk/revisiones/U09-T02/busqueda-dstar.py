"""Re-medicion de U09-T02 (F-03 opcion (b), 2026-11-10) y busqueda de D*, con la libreria real y `vectra_bias.freeze_rule`.

Compara dos reglas con la misma semilla y las mismas muestras:
  disparador  la regla de R4 de U09-T01: limite R4 solo del atributo disparador (BR-U9-05)  [el rojo: la regla anterior]
  todos       la regla vigente (b): algun atributo con limite R4 > umbral                    [`freeze_rule`]

Modos (primer argumento):
  condiciones [repeticiones]       condiciones 1 y 2 de BR-U9-11 con las dos reglas
  dstar [repeticiones] [regla] [t ...]   congelamiento con el lote `stratified` por cada t; sin t, una rejilla de 0,3 a 1,6

D* es la disparidad minima de una variante proxy con la que se congela >= 95 % con el lote `stratified` (~1 500 casos, BR-U12-06).
La variante `t` interpola entre el modelo base (t = 0) y el proxy de U5 (t = 1) y extrapola mas alla (tasas en [0, 1]). Se
informan dos medidas: la real de la simulacion (media por banda de max - min de las tasas reales del atributo disparador) y la
`agregada` de la libreria sobre los conteos esperados de U5 (la cifra que U5 puede medir; 25,41 pp en el proxy actual).
Uso: uv run python revisiones/U09-T02/busqueda-dstar.py condiciones 10000
     uv run python revisiones/U09-T02/busqueda-dstar.py dstar 3000 todos
"""

import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
from vectra_disparity import (
    ATTRIBUTES,
    BANDS,
    CountCell,
    CountTable,
    aggregate_lower_limit,
    disparity_by_band,
    model_aggregate,
)

spec = importlib.util.spec_from_file_location(
    "sim", Path("bias-monitoring/tests/simulation/test_statistical_validation.py")
)
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)

THRESHOLD_PP = Decimal(5)
all_attributes_rule = sim._freezes  # `vectra_bias.freeze_rule` (regla vigente (b))


def trigger_only_rule(counts: dict[str, CountTable]) -> bool:
    """La regla de R4 de U09-T01: el limite R4 solo del atributo disparador."""
    best = model_aggregate(disparity_by_band(counts, a, sim.N_MIN) for a in ATTRIBUTES)
    if best is None:
        return False
    limit = aggregate_lower_limit(counts, best[0], sim.N_MIN)
    return limit is not None and limit > THRESHOLD_PP / 100


RULES = {"disparador": trigger_only_rule, "todos": all_attributes_rule}
raw = json.loads(sim.U5_COUNTS.read_text())["proxy"]


def library_aggregate(truth) -> float:
    """Agregada de la libreria sobre los conteos esperados con los totales reales del proxy de U5."""
    counts = {}
    for attribute, rates in truth.items():
        groups = sorted({c["group"] for c in raw[attribute] if c["group"] != "no_informado"})
        cells = [c for c in raw[attribute] if c["group"] != "no_informado"]
        out = [
            CountCell(c["group"], c["band"], round(rates[groups.index(c["group"]), BANDS.index(c["band"])] * c["total"]), c["total"])
            for c in cells
        ]
        counts[attribute] = CountTable(attribute, tuple(out))
    best = model_aggregate(disparity_by_band(counts, a, sim.N_MIN) for a in sim.GROUPS)
    return float(best[1])


def conditions(reps: int) -> None:
    for name, rule in RULES.items():
        sim._freezes = rule
        rng = np.random.default_rng(sim.SEED + 1)
        false = {n: sim.freeze_rate(sim.NULL_TRUTH, lambda _g, n=n: n, reps, rng) for n in sim.CELL_SIZES}
        rng = np.random.default_rng(sim.SEED + 2)
        base = {n: sim.freeze_rate(sim._truth("base"), lambda _g, n=n: n, reps, rng) for n in sim.BASE_CELL_SIZES}
        print(f"regla={name} repeticiones={reps}")
        print("  condicion 1 (falsos, disparidad real 0): " + json.dumps({str(n): r for n, r in false.items()}))
        print("  condicion 2 (modelo base 4,61 pp):       " + json.dumps({str(n): r for n, r in base.items()}), flush=True)


def dstar(reps: int, rule_name: str, ts: list[float]) -> None:
    sim._freezes = RULES[rule_name]
    print(f"regla={rule_name} repeticiones={reps}")
    print(f"{'t':>5} {'D real (pp)':>12} {'agregada lib (pp)':>18} {'congela':>9}")
    for t in ts or [round(0.05 * k, 2) for k in range(6, 33)]:
        truth = sim.synthetic_variant(t)
        rate = sim.freeze_rate(truth, sim._stratified_cell, reps, np.random.default_rng(sim.SEED + 3))
        print(f"{t:5.2f} {100 * sim.true_model_disparity(truth):12.2f} {100 * library_aggregate(truth):18.2f} {rate:9.4f}", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "condiciones"
    repetitions = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    if mode == "condiciones":
        conditions(repetitions)
    else:
        dstar(repetitions, sys.argv[3] if len(sys.argv) > 3 else "todos", [float(x) for x in sys.argv[4:]])
