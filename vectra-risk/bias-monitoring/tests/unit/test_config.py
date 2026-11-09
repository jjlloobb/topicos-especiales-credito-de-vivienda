"""Paso 2: constantes y parametros de cumplimiento (INF-U9-03; P-U9-02, 03; NFR-U9-03). CA-4."""

import ast
import os
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from vectra_bias import config
from vectra_bias.config import PolicyError, load_policy, parse_policy

BIAS = Path(__file__).resolve().parents[2]
REAL_POLICY = BIAS / "chart" / "values-monitoring-policy.yaml"
VALID = {
    "threshold_pp": 5,
    "n_min": 30,
    "window_days": 30,
    "schedule": "2,17,32,47 * * * *",
    "stale_after": "1h",
}


def test_worst_case_run_is_computed_from_constants_and_below_the_deadline():
    # P-U9-02: token 4 + freezes 3 + rangos 10 + calculo 2 + freeze 57 + run/success 10 + grupos 100 = 186 s.
    assert config.worst_case_run_seconds() == 186
    assert config.worst_case_run_seconds() < config.ACTIVE_DEADLINE_SECONDS == 600
    assert config.worst_case_run_seconds() < load_policy(REAL_POLICY).interval_minutes * 60


def test_constants_follow_p_u9_02_and_p_u9_03():
    assert config.FREEZE_RETRY_DELAYS_S == (1, 2, 4)
    assert (config.CACHE_ENTRIES, config.CACHE_TTL_S) == (64, 900)
    assert config.INVALID_FAIL_RATIO == Decimal("0.01")
    assert config.AGGREGATOR_MAX_LAG_S == 1800


def test_no_constant_is_read_from_the_environment(monkeypatch):
    source = (BIAS / "src" / "vectra_bias" / "config.py").read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "import os" not in source
    names = [n.id for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Name)]
    assert "environ" not in names
    before = {k: getattr(config, k) for k in dir(config) if k.isupper()}
    for key in list(before):
        monkeypatch.setenv(key, "1")
    monkeypatch.setenv("N_MIN", "1")
    monkeypatch.setenv("THRESHOLD_PP", "99")
    after_policy = load_policy(REAL_POLICY)
    assert {k: getattr(config, k) for k in dir(config) if k.isupper()} == before
    assert after_policy.n_min == 30 and after_policy.threshold_pp == Decimal(5)
    assert os.environ["N_MIN"] == "1"


def test_real_policy_file_loads_the_five_values():
    policy = load_policy(REAL_POLICY)
    assert policy.threshold_pp == Decimal(5)
    assert policy.n_min == 30
    assert policy.window_days == 30
    assert policy.schedule == "2,17,32,47 * * * *"
    assert policy.stale_after_s == 3600
    assert policy.interval_minutes == 15


def test_valid_variants_load():
    assert (
        parse_policy(
            {**VALID, "schedule": "1,6,11,16,21,26,31,36,41,46,51,56 * * * *", "stale_after": "30m"}
        ).interval_minutes
        == 5
    )
    assert (
        parse_policy(
            {**VALID, "schedule": "3,13,23,33,43,53 * * * *", "stale_after": "2400s"}
        ).interval_minutes
        == 10
    )
    assert parse_policy(
        {**VALID, "threshold_pp": 1.5, "window_days": 90, "n_min": 100}
    ).threshold_pp == Decimal("1.5")


@pytest.mark.parametrize(
    ("key", "value", "reason"),
    [
        ("threshold_pp", 0.5, "threshold_pp_out_of_range"),
        ("threshold_pp", 21, "threshold_pp_out_of_range"),
        ("threshold_pp", "5", "threshold_pp_not_a_number"),
        ("threshold_pp", True, "threshold_pp_not_a_number"),
        ("n_min", 20, "n_min_out_of_range"),
        ("n_min", 30.5, "n_min_not_an_integer"),
        ("window_days", 6, "window_days_out_of_range"),
        ("window_days", 91, "window_days_out_of_range"),
        ("window_days", True, "window_days_not_an_integer"),
        ("stale_after", "10m", "stale_after_out_of_range"),
        ("stale_after", "59m", "stale_after_out_of_range"),  # W >= 4 x 15 min = 60 min
        ("stale_after", 3600, "stale_after_not_a_duration"),
        ("stale_after", "1 hora", "stale_after_not_a_duration"),
        ("schedule", 15, "schedule_not_a_string"),
        ("schedule", "*/15 * * * *", "schedule_not_a_minute_list"),
        ("schedule", "2,17,32,47 1 * * *", "schedule_not_a_minute_list"),
        ("schedule", "2,17,32 * * * *", "schedule_interval_not_allowed"),  # 60 % 3 == 0 pero intervalo 20 min
        ("schedule", "2,17,32,48 * * * *", "schedule_interval_not_allowed"),
        ("schedule", "2,32 * * * *", "schedule_interval_not_allowed"),  # 30 min
        (
            "schedule",
            "2,8,14,20,26,32,38,44,50,56 * * * *",
            "schedule_interval_not_allowed",
        ),  # 6 min y 60 % 10
        ("schedule", "0,15,30,45 * * * *", "schedule_offset_not_allowed"),  # desfase 0
        ("schedule", "5,20,35,50 * * * *", "schedule_offset_not_allowed"),
        ("schedule", "2,17,32,47,62 * * * *", "schedule_interval_not_allowed"),
    ],
)
def test_out_of_range_values_fail_the_load(key, value, reason):
    with pytest.raises(PolicyError, match=reason):
        parse_policy({**VALID, key: value})


def test_missing_or_extra_keys_fail():
    with pytest.raises(PolicyError, match="policy_keys_mismatch"):
        parse_policy({k: v for k, v in VALID.items() if k != "n_min"})
    with pytest.raises(PolicyError, match="policy_keys_mismatch"):
        parse_policy({**VALID, "extra": 1})
    with pytest.raises(PolicyError, match="policy_keys_mismatch"):
        parse_policy(["not", "a", "mapping"])


def test_a_policy_file_with_n_min_20_fails_at_startup(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump({**VALID, "n_min": 20}), encoding="utf-8")
    with pytest.raises(PolicyError, match="n_min_out_of_range"):
        load_policy(path)


def test_unreadable_files_fail_at_startup(tmp_path):
    with pytest.raises(PolicyError, match="policy_unreadable:FileNotFoundError"):
        load_policy(tmp_path / "missing.yaml")
    broken = tmp_path / "broken.yaml"
    broken.write_text("a: [unclosed", encoding="utf-8")
    with pytest.raises(PolicyError, match="policy_unreadable:ParserError"):
        load_policy(broken)
