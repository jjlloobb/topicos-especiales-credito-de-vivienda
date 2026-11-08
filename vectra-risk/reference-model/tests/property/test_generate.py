"""PBT-U5-01 (determinismo) y PBT-U5-02 (validez) del generador (BR-U5-02, BR-U5-03)."""

import json
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from vectra_contracts.models.application import ApplicationIn
from vectra_reference import generate as gen

BASE = gen.load_config()
SEEDS = st.integers(min_value=0, max_value=2**32 - 1)


@st.composite
def edge_configs(draw: st.DrawFn) -> dict:
    """Configuraciones con parametros en sus bordes: VIS 0 %/100 %, topes extremos, ruido nulo, tasas extremas."""
    cfg = gen.with_overrides(BASE, seed=draw(SEEDS), n_rows=draw(st.integers(1, 40)))
    cfg["vis_cap_cop"] = draw(st.sampled_from([1, 60_000_000, 200_000_000, 900_000_000_000]))
    p_vis = draw(st.sampled_from([0.0, 0.5, 1.0]))
    cfg["marginals"]["p_vis_by_stratum"] = [p_vis] * 7
    cfg["marginals"]["income"]["sigma"] = draw(st.sampled_from([0.0, 0.45, 1.5]))
    cfg["marginals"]["ltv"]["mean"] = draw(st.sampled_from([0.25, 0.68, 0.90]))
    cfg["marginals"]["other_income"]["p_has"] = draw(st.sampled_from([0.0, 1.0]))
    cfg["marginals"]["obligations"]["p_zero"] = draw(st.sampled_from([0.0, 1.0]))
    cfg["marginals"]["delinquency"]["p_clean"] = draw(st.sampled_from([0.0, 1.0]))
    cfg["label"]["target_default_rate"] = draw(st.sampled_from([0.0001, 0.04, 0.5, 0.9]))
    cfg["label"]["noise_sd"] = draw(st.sampled_from([0.0, 0.6, 5.0]))
    return cfg


@given(seed=SEEDS, n_rows=st.integers(min_value=2, max_value=60))
def test_pbt_u5_01_generate_is_deterministic(seed: int, n_rows: int) -> None:
    """PBT-U5-01: para toda semilla, generar dos veces da los mismos bytes en los tres Parquet."""
    cfg = gen.with_overrides(BASE, seed=seed, n_rows=n_rows)
    with tempfile.TemporaryDirectory() as tmp:
        a = gen.generate(Path(tmp) / "a", cfg)
        b = gen.generate(Path(tmp) / "b", cfg)
        for name in gen.PARTITIONS:
            assert a[name].read_bytes() == b[name].read_bytes(), name


@given(cfg=edge_configs())
def test_pbt_u5_02_every_row_is_a_valid_application(cfg: dict) -> None:
    """PBT-U5-02: toda fila pasa el validador de `ApplicationIn` de U0, tambien por la via JSON (la del contrato)."""
    rows = gen.build_rows(cfg)  # valida cada fila; una invalida lanza GeneratorError
    assert len(rows) == cfg["n_rows"]
    for row in rows:
        payload = {
            k: (v.isoformat() if k == "birth_date" else v) for k, v in gen.application_fields(row).items()
        }
        ApplicationIn.model_validate_json(json.dumps(payload))
        assert row["default"] in (0, 1)
        assert row["synthetic_id"].startswith(gen.ID_PREFIX)
