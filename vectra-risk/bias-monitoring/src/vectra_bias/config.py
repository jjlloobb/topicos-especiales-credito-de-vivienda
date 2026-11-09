"""Constantes y parametros de cumplimiento de U9 (INF-U9-03; P-U9-02, P-U9-03; NFR-U9-03; BR-U9-13).

Las constantes del codigo (timeouts, reintentos, cache, razon de invalidas, atraso del agregador) estan aqui y no se
leen de variables de entorno. Los cinco parametros de cumplimiento (umbral, `n_min`, ventana, horario y W) viven en
`chart/values-monitoring-policy.yaml`; la app los lee de un `ConfigMap` que el chart genera de ese archivo y
`load_policy` falla al arrancar si un valor sale de rango. El horario solo lo usa el chart (`schedule` del CronJob) y W
solo la `PrometheusRule`; la app los lee para informarlos en el paquete y en el dashboard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import yaml

# --- P-U9-02: timeouts por intento y reintentos (segundos) -------------------------------------------------------
TOKEN_TIMEOUT_S: Final = 2
TOKEN_ATTEMPTS: Final = 2  # un intento y 1 reintento inmediato
FREEZES_TIMEOUT_S: Final = 3
QUERY_TIMEOUT_S: Final = 5  # por solicitud de rangos
FREEZE_TIMEOUT_S: Final = 3
FREEZE_RETRY_DELAYS_S: Final = (1, 2, 4)  # 3 reintentos: 4 llamadas por version y corrida
PUSH_TIMEOUT_S: Final = 5
PUSH_GROUPS: Final = 2  # grupos `run` y `success`
GROUP_CALL_TIMEOUT_S: Final = 5  # lectura, PUT y DELETE de los grupos `freeze-<v>`
COMPUTE_BUDGET_S: Final = 2

# Forma del peor caso de una corrida (P-U9-02, revision del FD de U10, 2026-10-10, A6).
WORST_CASE_FAILING_VERSIONS: Final = 3
WORST_CASE_RANGE_REQUESTS: Final = 2
GROUP_LISTING_CALLS: Final = 1
GROUP_WRITES_PER_VERSION: Final = 1  # un PUT o DELETE por version evaluada
MAX_STALE_GROUP_DELETES: Final = (
    16  # DELETE de versiones que ya no se evaluan; el resto, en corridas siguientes
)
ACTIVE_DEADLINE_SECONDS: Final = 600  # `activeDeadlineSeconds` del CronJob con 15 min (INF-U9-03)

# --- P-U9-03: cache del dashboard ---------------------------------------------------------------------------------
CACHE_ENTRIES: Final = 64
CACHE_TTL_S: Final = 15 * 60

# --- BR-U9-09, BR-U9-10 -------------------------------------------------------------------------------------------
INVALID_FAIL_RATIO: Final = Decimal("0.01")
AGGREGATOR_MAX_LAG_S: Final = 30 * 60

# --- INF-U9-03: rangos validos de los cinco parametros de cumplimiento --------------------------------------------
THRESHOLD_PP_RANGE: Final = (Decimal(1), Decimal(20))
N_MIN_FLOOR: Final = 30
WINDOW_DAYS_RANGE: Final = (7, 90)
STALE_AFTER_FLOOR_S: Final = 30 * 60
ALLOWED_INTERVALS_MIN: Final = (5, 10, 15)
STALE_AFTER_MIN_INTERVALS: Final = 4  # W >= 4 x el intervalo entre corridas
POLICY_KEYS: Final = frozenset({"threshold_pp", "n_min", "window_days", "schedule", "stale_after"})
POLICY_PATH: Final = Path(
    "/etc/vectra/monitoring-policy/values-monitoring-policy.yaml"
)  # montaje del ConfigMap


def worst_case_run_seconds() -> int:
    """Peor caso de una corrida, calculado de las constantes (P-U9-02): ≈ 186 s con los valores de hoy."""
    attempts = len(FREEZE_RETRY_DELAYS_S) + 1
    per_version_freeze = attempts * FREEZE_TIMEOUT_S + sum(FREEZE_RETRY_DELAYS_S)
    groups = (
        GROUP_LISTING_CALLS + WORST_CASE_FAILING_VERSIONS * GROUP_WRITES_PER_VERSION + MAX_STALE_GROUP_DELETES
    ) * GROUP_CALL_TIMEOUT_S
    return (
        TOKEN_ATTEMPTS * TOKEN_TIMEOUT_S
        + FREEZES_TIMEOUT_S
        + WORST_CASE_RANGE_REQUESTS * QUERY_TIMEOUT_S
        + COMPUTE_BUDGET_S
        + WORST_CASE_FAILING_VERSIONS * per_version_freeze
        + PUSH_GROUPS * PUSH_TIMEOUT_S
        + groups
    )


class PolicyError(ValueError):
    """Un parametro de cumplimiento falta, sobra o esta fuera de rango: la app no arranca."""


@dataclass(frozen=True)
class MonitoringPolicy:
    threshold_pp: Decimal
    n_min: int
    window_days: int
    schedule: str
    stale_after_s: int

    @property
    def interval_minutes(self) -> int:
        return _interval_minutes(self.schedule)


_DURATION = re.compile(r"^(\d+)([smh])$")
_SECONDS = {"s": 1, "m": 60, "h": 3600}
_MINUTE_FIELDS = re.compile(r"^\d{1,2}(,\d{1,2})*$")


def _interval_minutes(schedule: str) -> int:
    """Intervalo fijo entre corridas de un `schedule` valido (5, 10 o 15 min, con desfase de 1 a 4 min)."""
    fields = schedule.split()
    if len(fields) != 5 or fields[1:] != ["*", "*", "*", "*"] or not _MINUTE_FIELDS.match(fields[0]):
        raise PolicyError("schedule_not_a_minute_list")
    minutes = [int(m) for m in fields[0].split(",")]
    if 60 % len(minutes):
        raise PolicyError("schedule_interval_not_allowed")
    interval = 60 // len(minutes)
    if interval not in ALLOWED_INTERVALS_MIN or minutes != [
        minutes[0] + k * interval for k in range(len(minutes))
    ]:
        raise PolicyError("schedule_interval_not_allowed")
    if minutes[-1] > 59 or any(not 1 <= m % 5 <= 4 for m in minutes):
        raise PolicyError("schedule_offset_not_allowed")
    return interval


def _number(value: Any, key: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise PolicyError(f"{key}_not_a_number")
    return Decimal(str(value))


def _integer(value: Any, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PolicyError(f"{key}_not_an_integer")
    return value


def _duration_s(value: Any) -> int:
    match = _DURATION.match(value) if isinstance(value, str) else None
    if match is None:
        raise PolicyError("stale_after_not_a_duration")
    return int(match.group(1)) * _SECONDS[match.group(2)]


def parse_policy(raw: Any) -> MonitoringPolicy:
    """Valida el contenido ya leido de `values-monitoring-policy.yaml` contra los rangos de INF-U9-03."""
    if not isinstance(raw, dict) or set(raw) != POLICY_KEYS:
        raise PolicyError("policy_keys_mismatch")
    threshold = _number(raw["threshold_pp"], "threshold_pp")
    if not THRESHOLD_PP_RANGE[0] <= threshold <= THRESHOLD_PP_RANGE[1]:
        raise PolicyError("threshold_pp_out_of_range")
    n_min = _integer(raw["n_min"], "n_min")
    if n_min < N_MIN_FLOOR:
        raise PolicyError("n_min_out_of_range")
    window = _integer(raw["window_days"], "window_days")
    if not WINDOW_DAYS_RANGE[0] <= window <= WINDOW_DAYS_RANGE[1]:
        raise PolicyError("window_days_out_of_range")
    schedule = raw["schedule"]
    if not isinstance(schedule, str):
        raise PolicyError("schedule_not_a_string")
    interval = _interval_minutes(schedule)
    stale = _duration_s(raw["stale_after"])
    if stale < STALE_AFTER_FLOOR_S or stale < STALE_AFTER_MIN_INTERVALS * interval * 60:
        raise PolicyError("stale_after_out_of_range")
    return MonitoringPolicy(threshold, n_min, window, schedule, stale)


def load_policy(path: Path = POLICY_PATH) -> MonitoringPolicy:
    """Lee y valida el archivo de parametros. Un error aqui detiene el arranque (no hay valores por omision)."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise PolicyError(f"policy_unreadable:{type(error).__name__}") from error
    return parse_policy(raw)
