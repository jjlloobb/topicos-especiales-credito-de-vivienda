"""Paso 2: los presupuestos de U7 son constantes del codigo con el valor del diseno (INF-U7-04)."""

import re
from pathlib import Path

import explainability.config as xcfg
import scoring.config as scfg
from vectra_common.deps import BreakerConfig

SRC = Path(__file__).resolve().parents[2]
CONFIGS = [SRC / "scoring/src/scoring/config.py", SRC / "explainability/src/explainability/config.py"]


def test_fail_closed_cabe_en_un_segundo() -> None:
    assert scfg.PRE_REGISTRY_BUDGET_MS + scfg.FAIL_CLOSED_APPEND_TIMEOUT_MS + scfg.PROCESS_MARGIN_MS <= 1000
    assert 700 + 250 + 50 <= scfg.RESPONSE_CEILING_MS


def test_la_gracia_de_terminacion_cubre_el_peor_append() -> None:
    worst_ms = (
        scfg.PRE_REGISTRY_BUDGET_MS
        + scfg.APPEND_ATTEMPTS * scfg.APPEND_TIMEOUT_MS
        + scfg.APPEND_JITTER_MAX_MS
    )
    assert worst_ms == 5_800
    assert scfg.TERMINATION_GRACE_S * 1000 > worst_ms


def test_ningun_presupuesto_se_lee_del_entorno() -> None:
    for path in CONFIGS:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"os\.environ|getenv|environ\b", text), path


def test_timeouts_de_nfr_u7_10() -> None:
    assert scfg.PRE_REGISTRY_BUDGET_MS == 700
    assert scfg.SERVING_CONFIG_TIMEOUT_MS == 500
    assert scfg.PREDICT_TIMEOUT_MS == 300
    assert scfg.EXPLAINABILITY_TIMEOUT_MS == 800
    assert scfg.REGISTRY_TIMEOUT_MS == 2_500
    assert xcfg.EXPLAIN_TIMEOUT_MS == 500
    assert xcfg.DICTIONARY_TIMEOUT_MS == 500


def test_append_y_fail_closed_de_p_u7_02() -> None:
    assert (scfg.APPEND_ATTEMPTS, scfg.APPEND_TIMEOUT_MS) == (2, 2_500)
    assert (scfg.APPEND_JITTER_MIN_MS, scfg.APPEND_JITTER_MAX_MS) == (0, 100)
    assert (scfg.FAIL_CLOSED_APPEND_ATTEMPTS, scfg.FAIL_CLOSED_APPEND_TIMEOUT_MS) == (1, 250)


def test_tope_propio_de_explainability() -> None:
    assert xcfg.OWN_CEILING_MS == 700
    assert xcfg.DEADLINE_MARGIN_MS == 50


def test_pools_de_p_u7_04() -> None:
    assert (scfg.PREDICT_POOL, scfg.EXPLAINABILITY_POOL, scfg.REGISTRY_POOL, scfg.SERVING_CONFIG_POOL) == (
        20,
        20,
        10,
        5,
    )
    assert (xcfg.EXPLAIN_POOL, xcfg.DICTIONARY_POOL, xcfg.REGISTRY_POOL) == (20, 5, 5)


def test_breaker_de_nfr_u7_11() -> None:
    for cfg in (scfg.BREAKER, xcfg.BREAKER):
        assert isinstance(cfg, BreakerConfig)
        assert (cfg.window_size, cfg.failure_ratio, cfg.window_seconds, cfg.open_for) == (20, 0.5, 30.0, 10.0)
        assert cfg.consecutive_failures is None


def test_caches_de_p_u7_05() -> None:
    assert scfg.SERVING_CONFIG_CACHE_TTL_MS <= 5_000
    assert xcfg.SERVING_CONFIG_CACHE_TTL_MS <= 5_000
    assert xcfg.DICTIONARY_LRU_VERSIONS == 4
