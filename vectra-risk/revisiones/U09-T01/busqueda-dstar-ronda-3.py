"""Busqueda de D* (ronda 3 de U09-T01, condicion 3 reformulada del arbitraje de la ronda 2), con la libreria real.

D* es la disparidad real minima de una variante proxy con la que BR-U9-11 (regla R4) congela >= 95 % con el lote `stratified`
(~1 500 casos, BR-U12-06). La variante `t` interpola entre el modelo base (t = 0) y el proxy de U5 (t = 1) y extrapola mas
alla (tasas en [0, 1]). Se informan dos medidas de la disparidad: la real de la simulacion (media por banda de max - min de
las tasas reales del atributo disparador) y la `agregada` de la libreria sobre los conteos esperados de U5 (los totales
reales de `u5_counts.json`, ponderada por banda, la cifra que U5 puede medir: 11,66 pp en el proxy actual).
Uso: uv run python revisiones/U09-T01/busqueda-dstar-ronda-3.py [repeticiones]
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
from vectra_disparity import BANDS, CountCell, CountTable, disparity_by_band, model_aggregate

spec = importlib.util.spec_from_file_location(
    "sim", Path("bias-monitoring/tests/simulation/test_statistical_validation.py")
)
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)
import json  # noqa: E402

reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
raw = json.loads(sim.U5_COUNTS.read_text())["proxy"]


def library_aggregate(truth) -> float:
    """Agregada de la libreria sobre los conteos esperados con los totales reales del proxy de U5."""
    counts = {}
    for attribute, rates in truth.items():
        groups = sorted({c["group"] for c in raw[attribute] if c["group"] != "no_informado"})
        cells = [c for c in raw[attribute] if c["group"] != "no_informado"]
        out = []
        for c in cells:
            r = rates[groups.index(c["group"]), BANDS.index(c["band"])]
            out.append(CountCell(c["group"], c["band"], round(r * c["total"]), c["total"]))
        counts[attribute] = CountTable(attribute, tuple(out))
    best = model_aggregate(disparity_by_band(counts, a, sim.N_MIN) for a in sim.GROUPS)
    return float(best[1])


print(f"{'t':>5} {'D real (pp)':>12} {'agregada lib (pp)':>18} {'congela':>9}   (repeticiones={reps})")
for t in [float(x) for x in sys.argv[2:]] or [round(0.1 * k, 1) for k in range(8, 26)]:
    truth = sim.synthetic_variant(t)
    rate = sim.freeze_rate(truth, sim._stratified_cell, reps, np.random.default_rng(sim.SEED + 3))
    print(f"{t:5.2f} {100 * sim.true_model_disparity(truth):12.2f} {100 * library_aggregate(truth):18.2f} {rate:9.4f}", flush=True)
