"""Escenarios de BreakGlassLogin (B11 de P-U2-09) y su generador de casos de promtool (U02-T13, ronda 3).

Uso:
  python b11_scenarios.py gen   <salida.yaml>            escribe el archivo de casos de promtool (un eval por minuto)
  python b11_scenarios.py probe <reglas.yaml> <promtool>  mide en que minutos dispara cada escenario, sin expectativas

Cada escenario dice las series (con `_`/`stale` de promtool) y los minutos en que la alerta debe estar activa. A, A2, B, C y D
son los del revisor de la ronda 2 (`revisiones/U02-T13/ronda-2.md`).
"""

import subprocess
import sys
import tempfile
from pathlib import Path

X = 'keycloak_user_events_total{event="login",client_id="security-admin-console",error="",realm="vectra",namespace="vectra-identity",pod="keycloak-0"}'
UP = 'up{job="keycloak",namespace="vectra-identity",pod="keycloak-0"}'
UP_OTHER_POD = 'up{job="keycloak",namespace="vectra-identity",pod="keycloak-1"}'
UP_OTHER_NS = 'up{job="keycloak",namespace="vectra-edge",pod="keycloak-0"}'
UP_OTHER_JOB = 'up{job="envoy-data-plane",namespace="vectra-identity",pod="keycloak-0"}'
XERR = X.replace('error=""', 'error="invalid_user_credentials"')
R = range(0, 25)
R5 = range(5, 25)  # sin los 5 primeros minutos: una serie que existe desde el minuto 0 es el caso B (primer scrape)
R_LONG = range(70, 100)
R_GAP = range(5, 35)

XR = "3x4 stale _x3 1x15"  # contador que se reinicia (3 a 1) con un hueco de la serie, sin hueco de scrape

# nombre: (comentario, [(serie, valores)], minutos a evaluar, minutos en que debe disparar)
SCENARIOS = {
    "A": ("pod nuevo con up desde el minuto 0; el login aparece en el minuto 2", [(X, "_x2 1x22"), (UP, "1x25")], R, set(range(2, 7))),
    "A2": ("lo mismo con el login en el minuto 4", [(X, "_x4 1x20"), (UP, "1x25")], R, set(range(4, 9))),
    "B": ("el login ya esta en el primer scrape (serie y up empiezan juntos)", [(X, "1x25"), (UP, "1x25")], R, set(range(0, 5))),
    "C": ("primer login real durante un hueco con up=0", [(X, "_x14 1x10"), (UP, "1x5 0x8 1x10")], R, set(range(14, 19))),
    "D": ("login real durante el hueco, con un contador que ya existia", [(X, "1x5 stale _x8 2x10"), (UP, "1x5 0x8 1x10")], R5, set(range(15, 20))),
    "G1": ("hueco con up=0 y la serie vuelve con el mismo valor: sin login", [(X, "1x5 stale _x7 1x12"), (UP, "1x5 0x8 1x10")], R5, set()),
    "G2": ("limite medido, modelo X con stale y up sin stale: hueco de 8 min de up (las muestras de X ya tenian marca de stale) y la serie vuelve igual: falso positivo de 1 min. Duracion por tamano de hueco en LIMITES (probe)", [(X, "1x5 stale _x7 1x12"), (UP, "1x5 _x8 1x10")], R5, {14}),
    "G3": ("Prometheus caido 15 min (mas que el lookback) y la serie vuelve igual: sin login", [(X, "1x5 stale _x14 1x12"), (UP, "1x5 _x15 1x12")], R_GAP, set()),
    "E": ("limite aceptado, modelo X con stale y up sin stale: el pod se reinicia durante un hueco de 15 min y luego hay un login (contador de 3 a 1): omision. Desde que hueco empieza, por modelo, en LIMITES (probe)", [(X, "3x5 stale _x14 1x12"), (UP, "1x5 _x15 1x12")], R_GAP, set()),
    "L": ("limite aceptado: hueco de mas de 1 h (la serie no se vio en la ultima hora) y vuelve con el mismo valor: falso positivo de 5 min", [(X, "1x5 stale _x70 1x25"), (UP, "1x5 _x71 1x25")], R_LONG, set(range(77, 82))),
    "L2": ("hueco de 45 min (dentro de la hora) y la serie vuelve con el mismo valor: sin login (la ventana de last_over_time es de 1 h)", [(X, "1x5 stale _x45 1x20"), (UP, "1x5 _x46 1x20")], range(5, 80), set()),
    "R": ("el contador se reinicio antes del hueco (3 a 1) y vuelve con 2 tras el hueco: login real, last_over_time toma el ultimo valor (1), no el maximo (3)", [(X, "3x2 1x3 stale _x8 2x10"), (UP, "1x5 0x8 1x10")], range(8, 25), set(range(16, 21))),
    "Rr": ("el contador se reinicia dentro de un hueco y vuelve con un valor menor que el ultimo y mayor que uno anterior (1, 5, hueco, 3): no es un login; last_over_time[offset 5m] toma el 5, con offset 10m tomaria el 1", [(X, "1x2 5 stale _x7 3x12")], range(8, 25), set()),
    "Z": ("una serie nueva con valor 0 no es un login", [(X, "_x3 0x20"), (UP, "1x25")], R5, set()),
    "I": ("login sobre una serie vieja (0 a 1, sin hueco): solo lo ve la rama increase, durante la ventana de 5 min", [(X, "0x8 1x16"), (UP, "1x25")], range(0, 25), {9, 10, 11, 12}),
    "Zf": ("un login fallido (error distinto de \"\") sobre una serie nueva no es un login con exito: la rama 3 exige error=\"\" en N", [(XERR, "_x3 1x20"), (UP, "1x25")], R5, set()),
    "H": ("la serie reaparece por reinicio (3 a 1) sin hueco de scrape: solo la tercera rama (up a 1 hace 5 min)", [(X, XR), (UP, "1x25")], R5, {10, 11, 12, 13}),
    "H_ns": ("idem, pero el unico up es del mismo pod en otro namespace: no cuenta (on(namespace, pod))", [(X, XR), (UP_OTHER_NS, "1x25")], R5, set()),
    "H_job": ("idem, pero el unico up es de otro job sobre el mismo pod: no cuenta (job=\"keycloak\")", [(X, XR), (UP_OTHER_JOB, "1x25")], R5, set()),
    "H_pod": ("idem, pero el unico up es de otro pod del mismo namespace: no cuenta", [(X, XR), (UP_OTHER_POD, "1x25")], R5, set()),
    "H_noup": ("idem, sin ningun up: no cuenta", [(X, XR)], R5, set()),
}


def _series(model, gap, kind):
    """Series de un hueco de `gap` minutos de `up` tras 5 muestras (idx 0-4). `model` dice quien lleva marca de stale al empezar el hueco:
    none (ninguna), x (solo X), up (solo up), both (las dos). kind: fp (vuelve el mismo valor) u omision (el pod se reinicio: 3 antes, 1 despues)."""
    before, after = ("1x4", "1x25") if kind == "fp" else ("3x4", "1x25")
    xs = model in ("x", "both")
    ups = model in ("up", "both")
    # `gap` = muestras que faltan (minutos sin raspar). `_xN` son N muestras vacias; la marca `stale` ocupa 1 de las `gap`
    blanks = lambda stale: ("stale " + (f"_x{gap - 1} " if gap > 1 else "")) if stale else f"_x{gap} "
    xv = f"{before} " + blanks(xs) + after
    uv = "1x4 " + blanks(ups) + "1x25"
    return [(X, xv), (UP, uv)]


MODELOS = {"none": "ninguna serie lleva marca de stale", "x": "solo X lleva marca de stale", "up": "solo up lleva marca de stale", "both": "X y up llevan marca de stale"}
# LIMITES: barridos de F-05. Cada cifra de break-glass-login.md sale de aqui (`probe`). nombre: (comentario, series, minutos)
LIMITES = {}
for _m in MODELOS:
    for _g in range(2, 16):
        LIMITES[f"FP_{_m}_{_g}"] = (f"falso positivo: hueco de {_g} min sin raspar, {MODELOS[_m]}, la serie vuelve con el mismo valor", _series(_m, _g, "fp"), range(5, 5 + _g + 30))
        LIMITES[f"OM_{_m}_{_g}"] = (f"omision: hueco de {_g} min con reinicio del pod (3 a 1), {MODELOS[_m]}", _series(_m, _g, "om"), range(5, 5 + _g + 30))
# reinicio normal: up=0 durante 3 evals (idx 5-7), X con marca de stale (el scrape fallido la escribe), el pod vuelve en idx 8 y su contador empieza en 1
for _k in range(0, 7):
    LIMITES[f"RN_{_k}"] = (f"reinicio normal del pod (up=0 3 min, X con stale, contador previo 1); el login cae {_k} min despues de volver el scrape",
                          [(X, f"1x4 stale _x{2 + _k} 1x25"), (UP, "1x4 0x2 1x30")], range(5, 35))


def series_block(series):
    return "".join(f"  - series: '{s}'\n    values: '{v}'\n" for s, v in series)


def case(name, comment, series, minutes, firing):
    out = f"# {name}: {comment}\n- interval: 1m\n  input_series:\n{series_block(series)}  alert_rule_test:\n"
    for m in minutes:
        out += f"  - eval_time: {m}m\n    alertname: BreakGlassLogin\n"
        if m in firing:
            out += (
                "    exp_alerts:\n    - exp_labels:\n        severity: SEV1\n        event: login\n        client_id: security-admin-console\n"
                "        realm: vectra\n        namespace: vectra-identity\n        pod: keycloak-0\n      exp_annotations:\n"
                "        summary: BreakGlassLogin\n        runbook_url: identity-edge/runbooks/break-glass-login.md\n"
            )
        else:
            out += "    exp_alerts: []\n"
    return out


def gen(path):
    head = "rule_files:\n- ../identity-edge-rules.yaml\nevaluation_interval: 1m\ntests:\n"
    Path(path).write_text(head + "".join(case(n, *s) for n, s in SCENARIOS.items()), encoding="utf-8")


def probe(rules, promtool):
    """Dispara en que minutos: corre promtool con `exp_alerts: []` y lee los FAILED."""
    import re

    todos = dict(SCENARIOS)
    todos.update({n: (c, sr, mi, set()) for n, (c, sr, mi) in LIMITES.items()})
    for name, (comment, series, minutes, _) in todos.items():
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "rules.yaml").write_text(Path(rules).read_text(encoding="utf-8"), encoding="utf-8")
            body = "rule_files: [rules.yaml]\nevaluation_interval: 1m\ntests:\n" + case(name, comment, series, minutes, set())
            (Path(d) / "t.yaml").write_text(body, encoding="utf-8")
            r = subprocess.run([promtool, "test", "rules", "t.yaml"], capture_output=True, text=True, cwd=d)
            fired = sorted({int(h or 0) * 60 + int(m or 0) for h, m in re.findall(r"time: (?:(\d+)h)?(?:(\d+)m)?(?:0s)?,", r.stdout + r.stderr)})
            print(f"{name:3} dispara en {fired}")


if __name__ == "__main__":
    if sys.argv[1] == "gen":
        gen(sys.argv[2])
    else:
        probe(sys.argv[2], sys.argv[3])
