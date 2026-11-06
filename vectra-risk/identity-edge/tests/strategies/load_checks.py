"""Comprobaciones de la especificacion de carga (U02-T15, Paso 14) sobre la salida de `k6 inspect`.

`k6 inspect` (v2.3.0) ejecuta el init context del script e imprime las `options` como JSON; `thresholds` y `scenarios` salen en el
primer nivel de ese JSON, no dentro de `options` (`thresholds`: metrica con su filtro -> lista de expresiones).
Cada funcion devuelve la lista de fallos (vacia si el script corresponde al diseno); los identificadores de fallo son
prefijos estables que las pruebas buscan en las copias mutadas.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import load_design as ld

SCENARIOS = ("users", "services", "jwks", "console-burst", "overhead")
SERVICES_RULE = "J6"


def run_inspect(script: Path, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    """`k6 inspect <script>` con un entorno vacio (solo PATH), como CA-2; falla si k6 no sale en 0."""
    assert ld.K6.exists(), f"falta {ld.K6}: corre platform/install-tools.sh"
    env = {"PATH": os.environ["PATH"], **(extra_env or {})}
    done = subprocess.run([str(ld.K6), "inspect", str(script)], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    assert done.returncode == 0, f"k6 inspect termino en {done.returncode}: {done.stderr[-800:]}"
    return dict(json.loads(done.stdout))


def seconds(duration: str) -> float:
    """«2m0s», «15m», «300s», «1m30s», «250ms» -> segundos."""
    units = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
    parts = re.findall(r"(\d+(?:\.\d+)?)(ms|h|m|s)", duration)
    assert parts and "".join(f"{n}{u}" for n, u in parts) == duration, f"duracion ilegible: {duration!r}"
    return sum(float(n) * units[u] for n, u in parts)


def _env(scenario: dict[str, Any]) -> dict[str, str]:
    return dict(scenario.get("env") or {})


def _stage_seconds(stages: list[dict[str, Any]]) -> float:
    return sum(seconds(s["duration"]) for s in stages)


def _max_stage_rate_per_second(scenario: dict[str, Any]) -> float:
    return max(float(s["target"]) for s in scenario["stages"]) / seconds(scenario["timeUnit"])


def _max_vu_growth_per_second(scenario: dict[str, Any]) -> float:
    """El mayor aumento de VUs por segundo entre dos etapas: cada VU nuevo hace un login."""
    previous, growth = float(scenario.get("startVUs") or 0), 0.0
    for stage in scenario["stages"]:
        target, length = float(stage["target"]), seconds(stage["duration"])
        growth = max(growth, (target - previous) / length)
        previous = target
    return growth


def threshold_problems(options: dict[str, Any]) -> list[str]:
    expected = ld.thresholds()
    found = options.get("thresholds") or {}
    problems = []
    for name, selector, limit in (
        ("login", "http_req_duration{flow:login}", expected.login_p95_ms),
        ("token", "http_req_duration{flow:token}", expected.token_p95_ms),
        ("jwks", "http_req_duration{flow:jwks}", expected.jwks_p95_ms),
    ):
        if f"p(95)<{limit}" not in (found.get(selector) or []):
            problems.append(f"umbral:{name}: {selector} debe llevar p(95)<{limit}, lleva {found.get(selector)}")
    wanted = f"rate<{expected.failed_rate:g}"
    if wanted not in (found.get("http_req_failed") or []):
        problems.append(f"umbral:failed: http_req_failed debe llevar {wanted}, lleva {found.get('http_req_failed')}")
    # J5: un 429 de los logins falla con `checks` y con `http_req_failed`; los dos con la misma tolerancia de J7 (la fraccion de aciertos).
    wanted_checks = f"rate>{round(1 - expected.failed_rate, 10):g}"
    if wanted_checks not in (found.get("checks") or []):
        problems.append(f"umbral:checks: checks debe llevar {wanted_checks} (1 - J7), lleva {found.get('checks')}")
    return problems


def scenario_problems(options: dict[str, Any]) -> list[str]:
    scenarios = options.get("scenarios") or {}
    if set(scenarios) != set(SCENARIOS):
        return [f"escenarios: deben ser {sorted(SCENARIOS)}, son {sorted(scenarios)}"]
    problems = []
    ramp, sustain = ld.ramp_and_sustain_seconds()
    prefix, first, last = ld.load_users()

    users = scenarios["users"]
    stages = users.get("stages") or []
    if users.get("executor") != "ramping-vus" or not stages:
        problems.append("users:ejecutor: debe ser ramping-vus con etapas")
    else:
        if max(int(s["target"]) for s in stages) != ld.concurrent_users():
            problems.append(f"users:vus: el maximo de VUs debe ser {ld.concurrent_users()}")
        if [seconds(s["duration"]) for s in stages] != [ramp, sustain] or stages[0]["target"] != stages[1]["target"]:
            problems.append(f"perfil:users: debe subir {ramp} s y sostener {sustain} s con los mismos VUs")
        if _max_vu_growth_per_second(users) >= ld.login_rate_ceiling():
            problems.append(f"users:logins: {_max_vu_growth_per_second(users):.2f}/s, el techo es {ld.login_rate_ceiling()}/s (J5)")
    env = _env(users)
    if (env.get("USER_PREFIX"), env.get("USER_FIRST"), env.get("USER_LAST")) != (prefix, str(first), str(last)):
        problems.append(f"users:nombres: USER_PREFIX/FIRST/LAST deben ser {prefix!r}/{first}/{last} (J1)")

    services = scenarios["services"]
    clients = [c for c in _env(services).get("CLIENTS", "").split(",") if c]
    if set(clients) != ld.service_clients() or len(clients) != len(set(clients)):
        problems.append(
            f"services:clientes: deben ser exactamente {sorted(ld.service_clients())} ({SERVICES_RULE}), son {sorted(clients)}"
        )
    if len(clients) != ld.service_identities():
        problems.append(f"services:cuenta: NFR-U2-10 fija {ld.service_identities()} identidades, el script tiene {len(clients)}")
    if services.get("executor") != "constant-arrival-rate":
        problems.append("services:ejecutor: debe ser constant-arrival-rate")
    else:
        period = seconds(services["timeUnit"]) * len(clients) / float(services["rate"])
        if abs(period - ld.renew_seconds()) > 1e-6:
            problems.append(f"services:renovacion: cada cliente se renueva cada {period:g} s, NFR-U2-10 fija {ld.renew_seconds()} s")
        if seconds(services["duration"]) != ramp + sustain:
            problems.append("perfil:services: la duracion debe ser la subida mas lo sostenido")

    jwks = scenarios["jwks"]
    if jwks.get("executor") != "constant-arrival-rate" or float(jwks.get("rate") or 0) <= 0:
        problems.append("jwks:ejecutor: lecturas del JWKS a tasa constante")
    elif seconds(jwks["duration"]) != ramp + sustain:
        problems.append("perfil:jwks: la duracion debe ser la subida mas lo sostenido")

    burst = scenarios["console-burst"]
    if burst.get("executor") != "ramping-arrival-rate" or not burst.get("stages"):
        problems.append("console-burst:ejecutor: debe ser ramping-arrival-rate con etapas")
    else:
        if _max_stage_rate_per_second(burst) <= ld.console_limit_per_second():
            problems.append(
                f"console-burst:tasa: {_max_stage_rate_per_second(burst):g}/s no supera el limite {ld.console_limit_per_second():g}/s"
            )
        if _stage_seconds(burst["stages"]) != ramp + sustain:
            problems.append("perfil:console-burst: las etapas deben sumar la subida mas lo sostenido")
    if _env(burst).get("RETRY_AFTER") != ld.console_retry_after():
        problems.append(f"console-burst:retry-after: debe esperar {ld.console_retry_after()!r} (routes.yaml)")

    overhead = scenarios["overhead"]
    if _env(overhead).get("MAX_DIFF_P95_MS") != str(ld.thresholds().overhead_p95_ms):
        problems.append(f"overhead:umbral: MAX_DIFF_P95_MS debe ser {ld.thresholds().overhead_p95_ms} (NFR-U2-11)")
    if overhead.get("executor") != "constant-arrival-rate":
        problems.append("overhead:ejecutor: debe ser constant-arrival-rate")
    else:
        if float(overhead["rate"]) / seconds(overhead["timeUnit"]) >= ld.console_limit_per_second():
            problems.append("overhead:tasa: por el gateway debe quedar por debajo del limite de la consola")
        if seconds(overhead["duration"]) != ramp + sustain:
            problems.append("perfil:overhead: la duracion debe ser la subida mas lo sostenido")
    return problems


def spec_problems(options: dict[str, Any]) -> list[str]:
    return threshold_problems(options) + scenario_problems(options)


def inspect_problems(script: Path) -> list[str]:
    return spec_problems(run_inspect(script))


def verdict_problems(verdict: dict[str, Any]) -> list[str]:
    """El veredicto de `handleSummary` (`overhead-verdict.json`): NFR-U2-11 (J3) y que las rafagas dieran 429."""
    problems = []
    overhead = verdict["overhead"]
    if not overhead["ok"]:
        problems.append(
            f"NFR-U2-11: la diferencia de p95 es {overhead['diff_p95_ms']} ms; el maximo es {overhead['budget_ms']} ms"
        )
    if not verdict["console"]["ok"]:
        problems.append("consola: las rafagas por encima del limite no dieron ningun 429")
    return problems


if __name__ == "__main__":
    # `make load-inspect` (sin argumentos) compara el script con el diseno; `make load` pasa el veredicto de la corrida.
    if len(sys.argv) == 3 and sys.argv[1] == "--verdict":
        found = verdict_problems(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
    else:
        found = inspect_problems(ld.SCRIPT)
    for line in found:
        print(line)  # noqa: T201
    raise SystemExit(1 if found else 0)
