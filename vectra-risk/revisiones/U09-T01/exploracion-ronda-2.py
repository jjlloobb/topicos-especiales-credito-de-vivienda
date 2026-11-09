"""Exploracion de la ronda 2 de U09-T01: ninguna regla de BR-U9-11 cumple a la vez las tres condiciones del arbitraje.

Verdad de la simulacion: tasas de celda de `bias-monitoring/tests/doubles/u5_counts.json` (modelo base y variante proxy;
las celdas con < 30 casos toman la tasa agrupada de su banda). Numpy vectorizado, equivalente a la libreria con celdas de
igual tamano (las tres bandas pesan lo mismo); el error de Wald en lugar del de Newcombe es una aproximacion.
Uso: uv run python revisiones/U09-T01/exploracion-ronda-2.py
"""

import json
import numpy as np
from scipy.stats import chi2, norm

rng = np.random.default_rng(20261109)
BANDS = ["lt_20", "20_30", "gt_30"]
REPS = 4000
raw = json.load(open("bias-monitoring/tests/doubles/u5_counts.json"))


def truth(variant):
    out = {}
    for a, cells in raw[variant].items():
        cells = [c for c in cells if c["group"] != "no_informado"]
        groups = sorted({c["group"] for c in cells})
        P = np.zeros((len(groups), 3))
        for bi, b in enumerate(BANDS):
            cs = [c for c in cells if c["band"] == b]
            pooled = sum(c["favorable"] for c in cs) / sum(c["total"] for c in cs)
            for c in cs:
                P[groups.index(c["group"]), bi] = c["favorable"] / c["total"] if c["total"] >= 30 else pooled
        out[a] = P
    return out


null = {a: np.full((g, 3), 0.5) for a, g in dict(sexo=2, rango_edad=6, region=6, estrato=6).items()}
base, prox = truth("base"), truth("proxy")
stratified = lambda g: max(30, 1500 // (3 * g))  # ~1 500 casos, >= 30 por celda


def simulate(P, nfun):
    """Por corrida: la agregada del modelo, y para el atributo disparador su se, su chi2 y sus grados de libertad."""
    A, SE, P2, PHI = [], [], [], []
    for a, Pa in P.items():
        g = Pa.shape[0]; n = nfun(g)
        X = rng.binomial(n, np.broadcast_to(Pa, (REPS,) + Pa.shape)); r = X / n
        hi, lo = r.max(1), r.min(1)
        d = hi - lo
        agg = d.mean(1)
        v = (hi * (1 - hi) + lo * (1 - lo)) / n
        se = np.sqrt(v.sum(1)) / 3  # w_b = 1/3
        pbar = X.mean(1, keepdims=True) / n
        var = np.where((pbar > 0) & (pbar < 1), n * pbar * (1 - pbar), np.inf)
        c2 = ((X - n * pbar) ** 2 / var).sum((1, 2))
        df = 3 * (g - 1)
        A.append(agg); SE.append(se); P2.append(chi2.sf(c2, df)); PHI.append((c2 - df) / (3 * g * n))
    A, SE, P2, PHI = map(np.array, (A, SE, P2, PHI))
    i, k = A.argmax(0), np.arange(REPS)
    return A.max(0), SE[i, k], P2[i, k], PHI[i, k]


Z_BONF = norm.isf(0.05 / 60)  # 15 pares x 4 atributos
RULES = {
    "R0 vigente: agregada>5pp y limite inf (z=1,96)>0": lambda a, se, p, f: (a > .05) & (a - 1.96 * se > 0),
    f"R1 Bonferroni 60 comparaciones (z={Z_BONF:.2f}), limite inf>0": lambda a, se, p, f: (a > .05) & (a - Z_BONF * se > 0),
    "R2 omnibus chi2 por atributo, alfa=0,05/4": lambda a, se, p, f: (a > .05) & (p < .0125),
    "R3 limite inf (z=1,96)>5pp (H0: D<=5pp)": lambda a, se, p, f: a - 1.96 * se > .05,
    f"R4 limite inf (z={Z_BONF:.2f})>5pp (H0: D<=5pp)": lambda a, se, p, f: a - Z_BONF * se > .05,
    "R5 agregada>5pp y phi2=(chi2-gl)/N>0,012": lambda a, se, p, f: (a > .05) & (f > .012),
}
scen = {}
for n in (30, 100, 500, 2000): scen[f"nula {n}"] = simulate(null, lambda g, n=n: n)
for n in (30, 50, 100): scen[f"base {n}"] = simulate(base, lambda g, n=n: n)
scen["proxy estrat."] = simulate(prox, stratified)
for n in (150, 250, 400): scen[f"proxy {n}/celda"] = simulate(prox, lambda g, n=n: n)
print(f"{'regla':62s}" + "".join(f"{k:>13s}" for k in scen))
for name, rule in RULES.items():
    print(f"{name:62s}" + "".join(f"{rule(*v).mean():13.3f}" for v in scen.values()))
