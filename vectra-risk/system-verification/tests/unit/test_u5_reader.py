"""CA-10: lectura de la entrega de U5 (U12 Paso 6; BR-U12-01; NFR-U12-10, 11). El `test.parquet` lo produce el generador real de U5."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
from fake_clock import FakeClock
from vault_double import CountingTransport
from vectra_contracts.models.application import ApplicationIn
from vectra_reference.proxy import monitoring_labels

from vectra_verification import guard
from vectra_verification.clients._api import RunTag
from vectra_verification.clients.gateway import GatewayClient
from vectra_verification.simulator import Simulator, SimulatorError, read_delivery

EVALUATED = datetime(2026, 11, 13, 10, tzinfo=UTC)


def test_every_row_validates_as_application_in_and_default_never_reaches_the_request(
    u5_delivery: Path,
) -> None:
    population = read_delivery(u5_delivery, EVALUATED)
    assert population.test_rows == len(population.applications) == len(population.rows) > 100
    assert all(isinstance(a, ApplicationIn) for a in population.applications)
    columns = pq.read_table(u5_delivery / "datasets" / "test.parquet").column_names
    assert "default" in columns and "synthetic_id" in columns  # el Parquet las trae; la solicitud no
    assert set(population.applications[0].model_dump()) == set(ApplicationIn.model_fields)
    assert (
        "default" not in population.applications[0].model_dump()
        and "synthetic_id" not in population.applications[0].model_dump()
    )


def test_generator_version_and_seed_come_from_the_manifest_with_the_size_and_the_sha256(
    u5_delivery: Path,
) -> None:
    manifest = json.loads((u5_delivery / "adversarial" / "manifest.json").read_text())
    population = read_delivery(u5_delivery, EVALUATED)
    assert (
        (population.generator_version, population.seed)
        == (manifest["generator_version"], manifest["seed"])
        == ("1.0.0", 20261101)
    )
    assert (
        population.parquet_sha256
        == hashlib.sha256((u5_delivery / "datasets" / "test.parquet").read_bytes()).hexdigest()
    )


def test_the_labels_of_each_row_are_those_u5_used_to_measure_the_freeze_and_the_id_is_the_position(
    u5_delivery: Path,
) -> None:
    population = read_delivery(u5_delivery, EVALUATED)
    records = pq.read_table(u5_delivery / "datasets" / "test.parquet").to_pylist()
    for position, (row, record) in enumerate(zip(population.rows, records, strict=True)):
        expected = monitoring_labels(record, EVALUATED.date())
        assert row.id == str(position)
        assert (
            dict(row.groups) == {k: expected[k] for k in ("sexo", "rango_edad", "region", "estrato")}
            and row.band == expected["banda"]
        )
        assert str(record["document_number"]) not in row.id


def test_a_missing_folder_or_file_is_a_clear_error_that_says_how_to_generate_it(
    tmp_path: Path, u5_delivery: Path
) -> None:
    with pytest.raises(
        SimulatorError, match=r"u5_delivery_missing:test.parquet.*make -C reference-model release"
    ):
        read_delivery(tmp_path / "no-existe", EVALUATED)
    (tmp_path / "datasets").mkdir()
    (tmp_path / "adversarial").mkdir()
    with pytest.raises(SimulatorError, match="u5_delivery_missing:test.parquet"):
        read_delivery(tmp_path, EVALUATED)
    (tmp_path / "datasets" / "test.parquet").write_bytes(
        (u5_delivery / "datasets" / "test.parquet").read_bytes()
    )
    with pytest.raises(
        SimulatorError, match=r"u5_delivery_missing:manifest.json.*make -C reference-model release"
    ):
        read_delivery(tmp_path, EVALUATED)
    (tmp_path / "adversarial" / "manifest.json").write_text("{}")
    with pytest.raises(SimulatorError, match="u5_manifest_invalid"):
        read_delivery(tmp_path, EVALUATED)


@pytest.mark.parametrize("scenario", ["rt1", "rt4"])
def test_the_deferred_scenarios_are_a_clear_error_with_zero_requests(
    u5_delivery: Path, dynamic_environment: guard.Environment, scenario: str
) -> None:
    counting = CountingTransport()
    clock = FakeClock()
    simulator = Simulator(
        dynamic_environment,
        GatewayClient(dynamic_environment, lambda: "t", RunTag(scenario, "3fa9c2d1"), transport=counting),
        clock,
        read_delivery(u5_delivery, EVALUATED),
        "3fa9c2d1",
    )
    with pytest.raises(SimulatorError, match=f"scenario_deferred:{scenario}"):
        simulator.run(scenario, 10, 1, section="rt1")
    assert counting.count == 0 and httpx is not None
