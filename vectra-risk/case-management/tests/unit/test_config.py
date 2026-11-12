"""Constantes tipadas de U8 (Paso 2; INF-U8-07; P-U8-01, 02; NFR-U8-30, 31): una prueba por viñeta de la aceptacion."""

import importlib
import re
from pathlib import Path

import pytest
from vectra_case import config

SOURCE = Path(config.__file__).read_text()


def test_worker_worst_case_is_below_the_lease() -> None:
    assert config.WORKER_WORST_CASE == 15.5
    assert config.WORKER_WORST_CASE < config.LEASE


def test_worker_worst_case_is_computed_from_the_timeouts() -> None:
    """No va escrito a mano: sale de los timeouts de NFR-U8-30 (con el reintento por 401, dos veces scoring)."""
    expected = (
        config.SERVING_CONFIG_TIMEOUT
        + config.FEATURE_SPEC_TIMEOUT
        + config.SCORING_TIMEOUT
        + config.SCORING_TIMEOUT
    )
    assert config.WORKER_WORST_CASE == expected
    assert not re.search(r"^WORKER_WORST_CASE[^=]*=\s*[\d.]+\s*$", SOURCE, re.M)


def test_shutdown_grace_is_between_the_worst_case_and_the_termination_grace() -> None:
    assert config.WORKER_WORST_CASE < config.WORKER_SHUTDOWN_GRACE < config.WORKER_TERMINATION_GRACE
    assert config.WORKER_SHUTDOWN_GRACE == 20
    assert config.WORKER_TERMINATION_GRACE == 30


def test_reconciler_concurrency_is_below_the_registry_pool() -> None:
    assert config.RECONCILER_CONCURRENCY == 4
    assert config.RECONCILER_CONCURRENCY < config.REGISTRY_POOL


def test_no_constant_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    before = _constants()
    for name in before:
        monkeypatch.setenv(name, "999")
        monkeypatch.setenv(f"CASE_{name}", "999")
    reloaded = importlib.reload(config)
    try:
        assert _constants(reloaded) == before
    finally:
        monkeypatch.undo()
        importlib.reload(config)
    assert "os.environ" not in SOURCE
    assert "getenv" not in SOURCE
    assert not re.search(r"^\s*(import os|from os\b)", SOURCE, re.M)


def test_every_named_value_of_step_2_matches_the_plan() -> None:
    expected: dict[str, float | int] = {
        # NFR-U8-30
        "SERVING_CONFIG_TIMEOUT": 0.5,
        "FEATURE_SPEC_TIMEOUT": 1.0,
        "SCORING_TIMEOUT": 7.0,
        "REGISTRY_TIMEOUT": 2.5,
        "CORE_TIMEOUT": 0.5,
        # P-U8-02
        "SCORING_POOL": 16,
        "GOVERNANCE_WORKER_POOL": 4,
        "GOVERNANCE_SERVICE_POOL": 2,
        "REGISTRY_POOL": 10,
        "CORE_POOL": 10,
        "RECONCILER_CONCURRENCY": 4,
        "CASE_DB_POOL_MAX": 5,
        # NFR-U8-31
        "BREAKER_FAILURE_RATIO": 0.5,
        "BREAKER_WINDOW_CALLS": 20,
        "BREAKER_WINDOW_SECONDS": 30,
        "BREAKER_HALF_OPEN_AFTER": 10,
        # BR-U8-07
        "BACKOFF_BASE": 30,
        "BACKOFF_FACTOR": 2,
        "BACKOFF_JITTER": 0.2,
        "MAX_ATTEMPTS": 6,
        # P-U8-01
        "LEASE": 30,
        "POLL_INTERVAL": 0.4,
        "POLL_JITTER": 0.1,
        "WORKER_CONCURRENCY": 16,
        # lotes
        "BATCH_SIZE": 100,
        "RETENTION_BATCH_SIZE": 500,
        # BR-U8-18, INF-U8-06
        "EVIDENCE_ABANDON_AFTER": 24 * 3600,
        "RECONCILER_BACKOFF_MIN": 1,
        "RECONCILER_BACKOFF_MAX": 300,
        "WORKER_SHUTDOWN_GRACE": 20,
    }
    for name, value in expected.items():
        assert getattr(config, name) == value, name
    assert config.CASE_DB_POOL_MAX <= 5
    assert config.POLL_INTERVAL + config.POLL_JITTER <= 0.5  # NFR-U8-04
    # BR-U8-07: las esperas 30 s, 1, 2, 4 y 8 min suman 930 s.
    assert (
        sum(config.BACKOFF_BASE * config.BACKOFF_FACTOR ** (n - 1) for n in range(1, config.MAX_ATTEMPTS))
        == 930
    )


def _constants(module: object = config) -> dict[str, object]:
    return {k: v for k, v in vars(module).items() if k.isupper()}


def test_reconciler_lease_covers_the_worst_batch_and_is_not_the_workers() -> None:
    """F-01 y F-05 (ronda 1 de U08-T03): el arrendamiento del reconciliador cubre un lote entero (con el reintento por 401)."""
    worst_batch = (config.BATCH_SIZE / config.RECONCILER_CONCURRENCY) * config.REGISTRY_TIMEOUT * 2
    assert config.RECONCILER_LEASE >= worst_batch and config.RECONCILER_LEASE == 125.0
    assert (
        config.RECONCILER_LEASE != config.LEASE and config.RECONCILER_BACKOFF_JITTER == config.BACKOFF_JITTER
    )


def test_case_service_modules_define_no_constant_of_their_own() -> None:
    """F-05: los tiempos y plazos de `case-service` viven en `config.py`, sin nombres repetidos."""
    src = Path(config.__file__).parent
    for name in ("evidence", "sweeps", "db_gauges", "governance_client", "db"):
        assert not re.search(
            r"^[A-Z_]+: Final\[(?:float|int)\] =\s*[\d.]+\s*$", (src / f"{name}.py").read_text(), re.M
        ), name
    names = re.findall(r"^([A-Z][A-Z0-9_]+)\b", SOURCE, re.M)
    assert len(names) == len(set(names))
