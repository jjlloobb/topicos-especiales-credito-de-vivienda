"""Paso 2 (CA-4): las constantes del BFF coinciden con la tabla de P-U10-04; ningun timeout >= 9 s; nada del entorno.

Tabla transcrita una sola vez de `aidlc-docs/construction/console/nfr-design/nfr-design-patterns.md`, P-U10-04
(«Timeouts, presupuesto y conexiones»), columnas «Timeout del BFF» y «Conexiones por réplica».
"""

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from console_bff import config

# (destino.operacion) -> timeout en segundos, fila de P-U10-04 entre parentesis.
TABLE_TIMEOUTS = {
    "case.list_cases": 1.5,  # fila 1: case lecturas
    "case.get_case": 1.5,
    "case.get_case_identifiers": 1.5,  # P-1 (a) de U10-T02: lectura de una fila, igual que las de la fila 1
    "case.list_persistent_failures": 1.5,
    "case.record_decision": 4.0,  # fila 2: case escrituras (antes 3 s)
    "case.create_manual_application": 4.0,
    "case.record_explanation_view": 4.0,
    "case.retry_case": 4.0,
    "governance.read": 1.5,  # fila 3: governance lecturas
    "governance.transition": 4.0,  # fila 4: governance transiciones con firma
    "registry.get_case_dossier": 5.0,  # fila 5
    "registry.run_integrity_check": 3.0,  # fila 6
    "registry.get_integrity_check": 3.0,
    "explainability.applicant_summary": 2.0,  # fila 7
    "bias.get_dashboard": 5.0,  # fila 8
    "bias.list_freezes": 1.5,  # fila 9
    "bias.get_context_package": 1.5,
}
# Conexiones por replica (columna «Conexiones por réplica»), compartidas entre las operaciones del destino.
TABLE_CONNECTIONS = {"case": 20, "governance": 10, "registry": 5, "explainability": 5, "bias": 5}
# «Conexiones con 6 réplicas»: 120 hacia case, 60 hacia governance y 30 hacia cada uno de los demas.
TABLE_TOTAL_CONNECTIONS = {"case": 120, "governance": 60, "registry": 30, "explainability": 30, "bias": 30}


def test_operation_timeouts_match_p_u10_04() -> None:
    assert dict(config.OPERATION_TIMEOUT_SECONDS) == TABLE_TIMEOUTS


def test_get_case_identifiers_has_the_case_read_timeout_and_shares_its_connections() -> None:
    """P-1 (a): 1,5 s y las mismas 20 conexiones (no hay un pool aparte, P-1 (c) descartada)."""
    assert (
        config.OPERATION_TIMEOUT_SECONDS["case.get_case_identifiers"]
        == config.CASE_READ_TIMEOUT_SECONDS
        == 1.5
    )
    assert config.CONNECTIONS_PER_REPLICA["case"] == 20
    assert not any(d.startswith("case.") and d != "case" for d in config.CONNECTIONS_PER_REPLICA)


def test_breaker_thresholds_are_the_ones_of_u7() -> None:
    """NFR-U10-30: 20 llamadas, 50 %, 30 s de ventana y 10 s abierto."""
    assert (
        config.BREAKER_WINDOW_SIZE,
        config.BREAKER_FAILURE_RATIO,
        config.BREAKER_WINDOW_SECONDS,
        config.BREAKER_OPEN_FOR_SECONDS,
    ) == (20, 0.5, 30, 10)


def test_case_and_governance_writes_are_four_seconds() -> None:
    assert config.CASE_WRITE_TIMEOUT_SECONDS == 4.0
    assert config.GOVERNANCE_WRITE_TIMEOUT_SECONDS == 4.0
    for op in ("record_decision", "create_manual_application", "record_explanation_view", "retry_case"):
        assert config.OPERATION_TIMEOUT_SECONDS[f"case.{op}"] == 4.0
    assert config.OPERATION_TIMEOUT_SECONDS["governance.transition"] == 4.0


def test_connections_per_replica_match_p_u10_04() -> None:
    assert dict(config.CONNECTIONS_PER_REPLICA) == TABLE_CONNECTIONS


def test_connections_with_six_replicas() -> None:
    assert config.REPLICAS == 6
    assert {d: config.total_connections(d) for d in TABLE_CONNECTIONS} == TABLE_TOTAL_CONNECTIONS


def test_budget_is_nine_seconds_and_below_the_spa_timeout() -> None:
    assert config.DEADLINE_BUDGET_SECONDS == 9.0
    assert config.SPA_API_TIMEOUT_SECONDS == 10.0
    assert config.DEADLINE_BUDGET_SECONDS < config.SPA_API_TIMEOUT_SECONDS


def test_every_timeout_of_the_module_is_below_the_budget() -> None:
    """«Ningun timeout >= 9 s» sobre **todas** las constantes `*_TIMEOUT_SECONDS` del modulo y las del mapa."""
    named = {
        n: v
        for n, v in vars(config).items()
        if n.endswith("_TIMEOUT_SECONDS") and isinstance(v, float) and n != "SPA_API_TIMEOUT_SECONDS"
    }
    assert len(named) == 9
    for name, value in {**named, **config.OPERATION_TIMEOUT_SECONDS}.items():
        assert 0 < value < 9, name


def test_every_mapped_operation_uses_a_named_constant() -> None:
    named = {v for n, v in vars(config).items() if n.endswith("_TIMEOUT_SECONDS") and isinstance(v, float)}
    assert set(config.OPERATION_TIMEOUT_SECONDS.values()) <= named


def test_config_source_never_touches_the_environment() -> None:
    tree = ast.parse(Path(inspect.getfile(config)).read_text(encoding="utf-8"))
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert "os" not in imported
    assert not {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} & {"environ", "getenv"}


def test_environment_variables_do_not_change_any_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    before = {n: v for n, v in vars(config).items() if n.isupper()}
    for name in before:
        monkeypatch.setenv(name, "1")
    after = {n: v for n, v in vars(importlib.reload(config)).items() if n.isupper()}
    assert after == before
