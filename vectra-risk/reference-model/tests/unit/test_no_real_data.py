"""Sin datos reales (BR-U5-01, NFR-U5-34) y sin marcas de tiempo, rutas ni maquinas en los archivos (NFR-U5-11)."""

import re
import socket
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from vectra_reference import generate as gen


@pytest.fixture(scope="module")
def parquets(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    cfg = gen.with_overrides(gen.load_config(), n_rows=3000)
    return gen.generate(tmp_path_factory.mktemp("nrd"), cfg)


def _column(path: Path, name: str) -> list:
    return pq.read_table(path, columns=[name]).column(name).to_pylist()


def test_ids_have_the_syn_prefix_in_every_parquet(parquets: dict[str, Path]) -> None:
    for path in parquets.values():
        ids = _column(path, "synthetic_id")
        assert ids and all(i.startswith("SYN-") for i in ids)
        brokers = [b for b in _column(path, "broker_id") if b is not None]
        assert all(b.startswith("SYN-") for b in brokers)


def test_names_come_only_from_the_fictitious_catalog(parquets: dict[str, Path]) -> None:
    catalog = gen.load_catalog()
    given, surnames = set(catalog["given_names"]), set(catalog["surnames"])
    for path in parquets.values():
        for full_name in _column(path, "full_name"):
            first, s1, s2 = full_name.split(" ")
            assert first in given and s1 in surnames and s2 in surnames, full_name


def test_other_identifiers_are_in_reserved_synthetic_ranges(parquets: dict[str, Path]) -> None:
    # Literales y patrones fijados aqui, no las constantes del modulo bajo prueba (U05-T01, F-01).
    cc = re.compile(r"^999\d{7}$")
    other = re.compile(r"^SYN\d{9}$")
    for path in parquets.values():
        table = pq.read_table(path).to_pydict()
        for doc_type, number in zip(table["document_type"], table["document_number"], strict=True):
            pattern = cc if doc_type == "CC" else other
            assert pattern.fullmatch(number), (doc_type, number)
        assert all(re.fullmatch(r"SYN-\d{7}@example\.com", e) for e in table["email"])  # dominio RFC 2606
        assert all(re.fullmatch(r"0000\d{6}", p) for p in table["phone"])  # no es un telefono asignable


def test_the_catalog_has_no_duplicates_and_no_overlap() -> None:
    catalog = gen.load_catalog()
    for key in ("given_names", "surnames"):
        assert len(catalog[key]) == len(set(catalog[key])) >= 30
    assert not set(catalog["given_names"]) & set(catalog["surnames"])


def test_parquet_files_carry_no_timestamps_paths_or_hostnames(parquets: dict[str, Path]) -> None:
    host = socket.gethostname().encode()
    for path in parquets.values():
        meta = pq.read_metadata(path)
        assert meta.metadata is None  # sin metadatos de pandas ni clave-valor
        assert not re.search(r"\d{4}-\d{2}-\d{2}", meta.created_by), meta.created_by
        raw = path.read_bytes()
        assert str(path.parent).encode() not in raw
        assert host not in raw
        schema_types = {str(t) for t in pq.read_schema(path).types}
        assert not any(t.startswith(("timestamp", "date")) for t in schema_types)
