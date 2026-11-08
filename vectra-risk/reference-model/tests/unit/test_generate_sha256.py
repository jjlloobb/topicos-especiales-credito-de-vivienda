"""Determinismo byte a byte con la semilla de referencia (BR-U5-02, BR-U5-04, NFR-U5-10)."""

import hashlib
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from vectra_reference import generate as gen


def _sha256(path: Path) -> str:
    # Se lee el archivo escrito en disco, no lo que devolvio `generate`.
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Path], dict[str, Path]]:
    cfg = gen.load_config()
    root = tmp_path_factory.mktemp("sha256")
    return gen.generate(root / "uno", cfg), gen.generate(root / "dos", cfg)


def test_sha256_of_the_three_parquets_matches_across_two_runs(two_runs) -> None:
    first, second = two_runs
    assert set(first) == set(gen.PARTITIONS) == {"train", "validation", "test"}
    for name in gen.PARTITIONS:
        assert first[name] != second[name]
        digest = _sha256(first[name])
        assert len(digest) == 64
        assert digest == _sha256(second[name]), name


def test_reference_seed_gives_a_70_15_15_stratified_split(two_runs) -> None:
    sizes = {name: pq.read_metadata(path).num_rows for name, path in two_runs[0].items()}
    assert sizes == {"train": 84_000, "validation": 18_000, "test": 18_000}
    rates = {
        name: pq.read_table(path, columns=["default"]).column("default").to_pylist()
        for name, path in two_runs[0].items()
    }
    shares = {name: sum(v) / len(v) for name, v in rates.items()}
    assert max(shares.values()) - min(shares.values()) < 1e-3  # estratificada por `default`
    assert 0.03 < shares["train"] < 0.05  # ~4 % [VERIFICAR]


def test_partitions_do_not_overlap_and_rows_are_ordered(two_runs) -> None:
    ids = {
        name: pq.read_table(path, columns=["synthetic_id"]).column("synthetic_id").to_pylist()
        for name, path in two_runs[0].items()
    }
    for name, values in ids.items():
        assert values == sorted(values), name  # orden de filas fijo
    all_ids = [i for values in ids.values() for i in values]
    assert len(all_ids) == len(set(all_ids)) == 120_000  # BR-U5-04: ningun solapamiento


def test_a_different_seed_changes_the_bytes(tmp_path: Path) -> None:
    cfg = gen.with_overrides(gen.load_config(), n_rows=200)
    a = gen.generate(tmp_path / "a", cfg)
    b = gen.generate(tmp_path / "b", gen.with_overrides(cfg, seed=cfg["seed"] + 1))
    assert _sha256(a["train"]) != _sha256(b["train"])
