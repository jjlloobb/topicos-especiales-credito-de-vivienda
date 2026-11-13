"""Paso 2: las constantes del ciclo, una por una (BR-U11-09, 11; NFR-U11-04, 09; P-U11-01, 02)."""

import ast
import importlib
import os
from datetime import time, timedelta
from pathlib import Path

import pytest
from vectra_common import deps, process
from vectra_product import config

SRC = Path(config.__file__).parent


def test_cycle_and_daily_schedule() -> None:
    assert config.CYCLE_SECONDS == 300
    assert config.FULL_PASS_AT_UTC == time(2, 30)
    assert config.FULL_PASS_JITTER_MAX_SECONDS == 600


def test_full_pass_deadline_and_retries() -> None:
    assert config.FULL_PASS_DEADLINE_SECONDS == 75 * 60
    assert config.FULL_PASS_RETRY_SECONDS == 15 * 60
    assert config.FULL_PASS_RETRIES == 6


def test_page_read_limits() -> None:
    assert config.PAGE_TIMEOUT_SECONDS == 5
    assert config.PAGE_SIZE == 1000
    assert config.MAX_CONNECTIONS == 1


def test_windows() -> None:
    assert config.STATE_WINDOW_DAYS == 35
    assert config.CLOSED_MONTHS == 6
    assert config.FULL_PASS_MARGIN_DAYS == 1
    assert config.PERIOD_30D_DAYS == 30
    assert config.VIEW_WINDOW_DAYS == 7


def test_data_quality_constants() -> None:
    assert config.MAX_DECIDED_AHEAD == timedelta(minutes=5)
    assert config.DEGRADED_RATIO == 0.01


def test_breaker_parameters() -> None:
    assert config.BREAKER_CONSECUTIVE_FAILURES == 3
    assert config.BREAKER_OPEN_FOR_SECONDS == 60
    assert config.BREAKER_CLOSE_AFTER == 1


def test_breaker_builds_with_vectra_common_deps_in_consecutive_failures_mode() -> None:
    process.init("service")
    breaker = deps.BreakerConfig(
        open_for=config.BREAKER_OPEN_FOR_SECONDS,
        consecutive_failures=config.BREAKER_CONSECUTIVE_FAILURES,
        close_after=config.BREAKER_CLOSE_AFTER,
    )
    # Modo `consecutive_failures` excluye la ventana deslizante (U0 NFR-U0-23 (i)).
    assert (breaker.window_size, breaker.failure_ratio, breaker.window_seconds) == (None, None, None)
    client = deps.DependencyClient(
        config.BREAKER_DEPENDENCY, "http://registry.invalid", breaker, config.MAX_CONNECTIONS
    )
    assert client.breaker is not None
    assert client.breaker.state is deps.CircuitState.CLOSED


def test_single_read_scope_and_client() -> None:
    assert config.SCOPES == ("registry:read:metrics",)
    assert config.CLIENT_ID == "product-metrics"


@pytest.mark.parametrize("name", ["config.py", "params.py"])
def test_no_environment_access_in_source(name: str) -> None:
    tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"environ", "getenv", "environb"}, f"{name}:{node.lineno}"
        if isinstance(node, ast.Name):
            assert node.id not in {"environ", "getenv"}, f"{name}:{node.lineno}"
        if isinstance(node, ast.Import | ast.ImportFrom):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            assert "os" not in names, f"{name}:{node.lineno}"


def test_constants_ignore_the_environment() -> None:
    """Con el entorno cambiado, al importar de nuevo ninguna constante cambia."""
    before = {k: v for k, v in vars(config).items() if k.isupper()}
    keys = [*before, *(f"VECTRA_{k}" for k in before), *(k.lower() for k in before)]
    saved = {k: os.environ.get(k) for k in keys}
    try:
        for key in keys:
            os.environ[key] = "1"
        reloaded = importlib.reload(config)
        after = {k: v for k, v in vars(reloaded).items() if k.isupper()}
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(config)
    assert after == before
