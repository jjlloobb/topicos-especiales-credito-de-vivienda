"""Paso 2 (NFR-U6-03, 40; P-U6-03): el cargador verifica el paquete y, si algo no coincide, no hay listo y se emite el evento."""

import hashlib
import json
import logging
from collections.abc import Callable
from pathlib import Path

import pytest
from vectra_common.metrics import REGISTRY
from vectra_serving_common.package_loader import (
    EXPLAINER_FILES,
    PREDICTOR_FILES,
    ModelPackageIntegrityFailed,
    load_package,
)
from vectra_serving_common.service import try_load

from serving_helpers import version_of


def _failures(component: str) -> float:
    return (
        REGISTRY.get_sample_value("vectra_serving_package_integrity_failed_total", {"component": component})
        or 0.0
    )


def test_the_base_package_loads_for_both_components(package_dir: Path) -> None:
    version = version_of(package_dir)
    for files, component in ((PREDICTOR_FILES, "predictor"), (EXPLAINER_FILES, "explainer")):
        package = load_package(package_dir, version, files, component)
        assert package.model_version_id == version
        assert set(package.files) == set(files)


def test_rt3_a_explainer_of_another_version_is_not_ready(rt3_dirs: dict[str, Path]) -> None:
    directory = rt3_dirs["RT3-a"]
    before = _failures("explainer")
    with pytest.raises(ModelPackageIntegrityFailed, match="embedded_version_mismatch:explainer.json"):
        load_package(directory, version_of(directory), EXPLAINER_FILES, "explainer")
    assert _failures("explainer") == before + 1


def test_rt3_d_manifest_with_different_versions_is_not_ready(rt3_dirs: dict[str, Path]) -> None:
    directory = rt3_dirs["RT3-d"]
    before = _failures("explainer")
    with pytest.raises(ModelPackageIntegrityFailed, match="entry_version_mismatch:explainer.json"):
        load_package(directory, version_of(directory), EXPLAINER_FILES, "explainer")
    assert _failures("explainer") == before + 1


def test_rt3_b_with_coherent_versions_is_ready(rt3_dirs: dict[str, Path]) -> None:
    """Cuarta revision de coherencia: (b) lleva versiones y SHA-256 coherentes y pasa."""
    directory = rt3_dirs["RT3-b"]
    for files, component in ((PREDICTOR_FILES, "predictor"), (EXPLAINER_FILES, "explainer")):
        assert load_package(directory, version_of(directory), files, component).files


def test_rt3_c_alters_the_dictionary_which_u6_does_not_read(rt3_dirs: dict[str, Path]) -> None:
    """Quinta revision de coherencia: (c) altera el diccionario, que U6 no usa; no es barrera aqui."""
    directory = rt3_dirs["RT3-c"]
    assert load_package(directory, version_of(directory), EXPLAINER_FILES, "explainer").files


@pytest.mark.parametrize(
    "name", ["predictor.json", "feature_spec.json", "explainer.json", "domain_envelope.json"]
)
def test_one_altered_byte_is_not_ready_and_emits_the_event(
    copy_package: Callable[[], Path], name: str, caplog: pytest.LogCaptureFixture
) -> None:
    directory = copy_package()
    data = bytearray((directory / name).read_bytes())
    data[len(data) // 2] ^= 0x01
    (directory / name).write_bytes(bytes(data))
    before = _failures("predictor")
    with caplog.at_level(logging.ERROR, logger="vectra_serving.package_loader"):
        with pytest.raises(ModelPackageIntegrityFailed, match=f"sha256_mismatch:{name}"):
            load_package(directory, version_of(directory), PREDICTOR_FILES, "predictor")
    assert _failures("predictor") == before + 1
    assert any(
        "ModelPackageIntegrityFailed" in r.getMessage() and name in r.getMessage() for r in caplog.records
    )


def test_a_file_the_component_does_not_use_does_not_block_it(copy_package: Callable[[], Path]) -> None:
    directory = copy_package()
    (directory / "background.csv").write_bytes(b"alterado")
    assert load_package(directory, version_of(directory), EXPLAINER_FILES, "explainer").files


def test_the_annotation_must_match_the_manifest(package_dir: Path) -> None:
    with pytest.raises(ModelPackageIntegrityFailed, match="manifest_version_mismatch"):
        load_package(package_dir, "mv-2026-01-01-00000000", PREDICTOR_FILES, "predictor")
    with pytest.raises(ModelPackageIntegrityFailed, match="manifest_version_mismatch"):
        load_package(package_dir, "", PREDICTOR_FILES, "predictor")


def test_a_missing_or_unlisted_file_is_not_ready(copy_package: Callable[[], Path]) -> None:
    directory = copy_package()
    version = version_of(directory)
    (directory / "predictor.json").unlink()
    with pytest.raises(ModelPackageIntegrityFailed, match="file_unreadable:predictor.json"):
        load_package(directory, version, PREDICTOR_FILES, "predictor")
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest["files"] = [e for e in manifest["files"] if e["name"] != "feature_spec.json"]
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ModelPackageIntegrityFailed, match="file_not_in_manifest:feature_spec.json"):
        load_package(directory, version, ["feature_spec.json"], "predictor")


@pytest.mark.parametrize("content", [None, b"no es json", b"[]", b'{"files": 3}', b'{"files": [3]}'])
def test_an_unreadable_or_malformed_manifest_is_not_ready(
    copy_package: Callable[[], Path], content: bytes | None
) -> None:
    directory = copy_package()
    version = version_of(directory)
    if content is None:
        (directory / "manifest.json").unlink()
    else:
        (directory / "manifest.json").write_bytes(content)
    with pytest.raises(ModelPackageIntegrityFailed, match="manifest_"):
        load_package(directory, version, PREDICTOR_FILES, "predictor")


@pytest.mark.parametrize("bad_entry", [3, {"name": 7}, {"sha256": "x"}])
def test_a_manifest_entry_that_is_not_an_object_with_a_name_is_not_ready(
    copy_package: Callable[[], Path], bad_entry: object
) -> None:
    """Cierra la rama de `load_package` que lee las entradas del manifiesto con la version correcta (100 % en el cargador, Paso 10)."""
    directory = copy_package()
    version = version_of(directory)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest["files"].append(bad_entry)
    (directory / "manifest.json").write_text(json.dumps(manifest))
    before = _failures("predictor")
    with pytest.raises(ModelPackageIntegrityFailed, match="manifest_malformed"):
        load_package(directory, version, PREDICTOR_FILES, "predictor")
    assert _failures("predictor") == before + 1


def test_a_malformed_json_with_a_valid_sha_is_not_ready(copy_package: Callable[[], Path]) -> None:
    directory = copy_package()
    version = version_of(directory)
    data = b"no es json"
    (directory / "feature_spec.json").write_bytes(data)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    for entry in manifest["files"]:
        if entry["name"] == "feature_spec.json":
            entry["sha256"] = hashlib.sha256(data).hexdigest()
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ModelPackageIntegrityFailed, match="file_malformed:feature_spec.json"):
        load_package(directory, version, PREDICTOR_FILES, "predictor")


def test_try_load_reads_the_annotation_and_the_directory_from_the_environment(
    package_dir: Path, rt3_dirs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODEL_DIR", str(package_dir))
    monkeypatch.setenv("MODEL_VERSION_ID", version_of(package_dir))
    assert try_load(EXPLAINER_FILES, "explainer") is not None
    monkeypatch.setenv("MODEL_DIR", str(rt3_dirs["RT3-a"]))
    assert try_load(EXPLAINER_FILES, "explainer") is None  # no listo
    monkeypatch.delenv("MODEL_VERSION_ID")
    monkeypatch.setenv("MODEL_DIR", str(package_dir))
    assert try_load(EXPLAINER_FILES, "explainer") is None
