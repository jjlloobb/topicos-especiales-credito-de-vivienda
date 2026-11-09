"""PBT-U4-06 y ejemplos de BR-U4-06 (US-201; RT3-a..d de U5). Paso 6, `registration`.

Los paquetes salen de U5 (`vectra_reference`): una entrega chica (6 000 filas, unos segundos) y los paquetes RT-3 que
escribe `vectra_reference.adversarial.rt3_package`. La prueba lee los bytes del disco y se los pasa a la funcion pura.
"""

from __future__ import annotations

import hashlib
import json
import sys
import types
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from vectra_reference.adversarial import ACCEPTED_BY_U4, REJECTED_BY_U4, rt3_package
from vectra_reference.generate import load_config, with_overrides
from vectra_reference.release import run_release

from vectra_governance.registration import (
    REQUIRED_FILES,
    RegistrationRejected,
    VerifiedPackage,
    has_executable_magic,
    validate_registration,
)

Package = tuple[bytes, dict[str, bytes]]


@pytest.fixture(scope="session")
def package_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return run_release(
        tmp_path_factory.mktemp("release"), with_overrides(load_config(), n_rows=6000), enforce_min_auc=False
    ).package_dir


def read_package(directory: Path) -> Package:
    manifest = (directory / "manifest.json").read_bytes()
    names = [entry["name"] for entry in json.loads(manifest)["files"]]
    return manifest, {name: (directory / name).read_bytes() for name in names}


@pytest.fixture(scope="session")
def good(package_dir: Path) -> Package:
    return read_package(package_dir)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def register(package: Package, **override: Any) -> VerifiedPackage:
    manifest, files = package
    try:
        listed = {entry["name"]: entry["sha256"] for entry in json.loads(manifest)["files"]}
    except (ValueError, KeyError, TypeError):
        listed = {}  # manifiesto ilegible: la funcion lo rechaza; el helper no es quien lo juzga
    arguments: dict[str, Any] = {
        "artifact_format": "xgboost_json",
        "manifest_sha256": sha(manifest),
        "artifact_sha256": listed.get("predictor.json", "0" * 64),
        "explainer_sha256": listed.get("explainer.json", "0" * 64),
        "manifest": manifest,
        "files": files,
        **override,
    }
    return validate_registration(**arguments)


def reason(package: Package, **override: Any) -> str:
    with pytest.raises(RegistrationRejected) as error:
        register(package, **override)
    return error.value.reason


def with_file(package: Package, name: str, data: bytes, *, relist: bool = True) -> Package:
    """El paquete con `name` cambiado; `relist` actualiza su SHA-256 en el manifiesto (y el manifiesto cambia)."""
    manifest, files = package
    files = {**files, name: data}
    if relist:
        document = json.loads(manifest)
        for entry in document["files"]:
            if entry["name"] == name:
                entry["sha256"] = sha(data)
        manifest = json.dumps(document).encode()
    return manifest, files


def rename(package: Package, old: str, new: str) -> Package:
    manifest, files = package
    document = json.loads(manifest)
    for entry in document["files"]:
        if entry["name"] == old:
            entry["name"] = new
    return json.dumps(document).encode(), {(new if k == old else k): v for k, v in files.items()}


@contextmanager
def deserializers_forbidden() -> Iterator[list[str]]:
    """`pickle.loads`, `joblib.load` y `onnx.load` fallan si alguien los llama; `onnx` se simula si no esta instalado."""
    calls: list[str] = []

    def trap(name: str) -> Any:
        def fail(*_args: object, **_kwargs: object) -> None:
            calls.append(name)
            raise AssertionError(f"se invoco {name}")

        return fail

    import joblib

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("pickle.loads", trap("pickle.loads"))
        patch.setattr("pickle.load", trap("pickle.load"))
        patch.setattr(joblib, "load", trap("joblib.load"))
        try:
            import onnx  # type: ignore[import-not-found,unused-ignore]

            patch.setattr(onnx, "load", trap("onnx.load"))
        except ImportError:
            fake = types.ModuleType("onnx")
            fake.load = trap("onnx.load")  # type: ignore[attr-defined]
            patch.setitem(sys.modules, "onnx", fake)
        yield calls


# --- Ejemplos -------------------------------------------------------------------------------------------------------


def test_us_201_a_valid_package_registers_and_returns_the_verified_json(good: Package) -> None:
    manifest, files = good
    result = register(good)
    document = json.loads(manifest)
    assert result.model_version_id == document["model_version_id"]
    assert dict(result.file_sha256) == {e["name"]: e["sha256"] for e in document["files"]}
    assert set(REQUIRED_FILES) <= set(result.file_sha256)
    assert result.feature_dictionary == json.loads(files["feature_dictionary.json"])
    assert result.feature_spec == json.loads(files["feature_spec.json"])
    assert result.feature_dictionary_version == result.feature_dictionary["dictionary_version"]


@pytest.mark.parametrize("fmt", ["onnx", "xgboost_json", "xgboost_ubj", "lightgbm_txt"])
def test_br_u4_06_allowed_formats(good: Package, fmt: str) -> None:
    assert register(good, artifact_format=fmt).model_version_id


@pytest.mark.parametrize("fmt", ["pickle", "joblib", "sklearn", "", "ONNX"])
def test_br_u4_06_other_formats_are_rejected(good: Package, fmt: str) -> None:
    assert reason(good, artifact_format=fmt) == "artifact_format_not_allowed"


def test_us_201_altered_checksum_is_rejected_without_deserializing(good: Package) -> None:
    manifest, files = good
    altered = {**files, "background.csv": files["background.csv"] + b"0"}
    with deserializers_forbidden() as calls:
        assert reason((manifest, altered)) == "sha256_mismatch:background.csv"
        assert reason(good, manifest_sha256="0" * 64) == "manifest_sha256_mismatch"
        assert reason(good, artifact_sha256="0" * 64) == "declared_sha256_mismatch:predictor"
        assert reason(good, explainer_sha256="0" * 64) == "declared_sha256_mismatch:explainer"
    assert calls == []


def test_br_u4_06_no_deserializer_is_called_on_any_path(
    good: Package, package_dir: Path, tmp_path: Path
) -> None:
    """`pickle.loads`, `joblib.load` y `onnx.load` reemplazados por funciones que fallan: ningun camino las llama."""
    cases: list[Package] = [
        good,
        with_file(good, "predictor.json", b"\x80\x04abc"),
        with_file(good, "background.csv", b"PK\x03\x04"),
    ]
    for case_id in (*REJECTED_BY_U4, *ACCEPTED_BY_U4):
        target = tmp_path / case_id
        rt3_package(case_id, package_dir, target)
        cases.append(read_package(target))
    cases.append(rename(good, "background.csv", "model.joblib"))
    cases.append((b"{not json", {}))
    with deserializers_forbidden() as calls:
        for case in cases:
            try:
                register(case, manifest_sha256=sha(case[0]))
            except RegistrationRejected:
                pass
    assert calls == []


def test_the_trap_really_traps(good: Package) -> None:
    """La trampa funciona: si algo llamara a `pickle.loads`, la prueba anterior lo veria."""
    import pickle

    with deserializers_forbidden() as calls:
        with pytest.raises(AssertionError, match="pickle.loads"):
            pickle.loads(b"")
    assert calls == ["pickle.loads"]


@pytest.mark.parametrize("extension", [".pkl", ".pickle", ".joblib", ".PKL"])
def test_br_u4_06_forbidden_extension_is_rejected_even_with_harmless_bytes(
    good: Package, extension: str
) -> None:
    assert (
        reason(rename(good, "predictor.json", f"predictor{extension}"))
        == "manifest_missing_file:predictor.json"
    )
    manifest, files = good
    document = json.loads(manifest)
    document["files"].append(
        {"name": f"extra{extension}", "sha256": sha(b"{}"), "model_version_id": document["model_version_id"]}
    )
    extra = json.dumps(document).encode()
    assert reason((extra, {**files, f"extra{extension}": b"{}"})) == f"forbidden_extension:extra{extension}"


@pytest.mark.parametrize("case_id", REJECTED_BY_U4)
def test_br_u4_06_rt3_packages_a_c_d_are_rejected(package_dir: Path, tmp_path: Path, case_id: str) -> None:
    rt3_package(case_id, package_dir, tmp_path / case_id)
    expected = {
        "RT3-a": "model_version_id_mismatch_inside:explainer.json",
        "RT3-c": "model_version_id_mismatch_inside:feature_dictionary.json",
        "RT3-d": "model_version_id_mismatch:explainer.json",
    }[case_id]
    assert reason(read_package(tmp_path / case_id)) == expected


@pytest.mark.parametrize("case_id", ACCEPTED_BY_U4)
def test_br_u4_06_rt3_b_is_accepted_it_fails_later_in_sync_check(
    package_dir: Path, tmp_path: Path, case_id: str
) -> None:
    rt3_package(case_id, package_dir, tmp_path / case_id)
    assert register(read_package(tmp_path / case_id)).model_version_id


def test_br_u4_06_every_required_file_must_be_listed(good: Package) -> None:
    manifest, files = good
    for name in REQUIRED_FILES:
        document = json.loads(manifest)
        document["files"] = [e for e in document["files"] if e["name"] != name]
        assert reason((json.dumps(document).encode(), files)) == f"manifest_missing_file:{name}"


def test_br_u4_06_listed_file_without_bytes_and_unreadable_manifest(good: Package) -> None:
    manifest, files = good
    assert (
        reason((manifest, {k: v for k, v in files.items() if k != "background.csv"}))
        == "file_bytes_missing:background.csv"
    )
    for broken in (
        b"",
        b"{",
        b"[]",
        b'{"model_version_id": 1, "files": []}',
        b'{"model_version_id": "x", "files": [{}]}',
    ):
        assert reason((broken, {})) == "manifest_unreadable"


def test_br_u4_06_bad_feature_files_are_rejected(good: Package) -> None:
    data = json.dumps({"model_version_id": json.loads(good[0])["model_version_id"]}).encode()
    assert reason(with_file(good, "feature_spec.json", data)) == "feature_files_unreadable"
    assert reason(with_file(good, "feature_dictionary.json", data)) == "feature_files_unreadable"
    assert reason(with_file(good, "feature_spec.json", b"no json")) == "json_unreadable:feature_spec.json"


# --- PBT-U4-06 ------------------------------------------------------------------------------------------------------

_PICKLE = st.tuples(st.just(b"\x80"), st.sampled_from([2, 3, 4, 5])).map(lambda t: t[0] + bytes([t[1]]))
_MAGIC = st.one_of(_PICKLE, st.just(b"PK\x03\x04"))
_TAILS = st.binary(max_size=200)
_NAMES = st.sampled_from(REQUIRED_FILES)


@given(name=_NAMES, magic=_MAGIC, tail=_TAILS)
def test_pbt_u4_06_magic_bytes_are_rejected_in_any_file_with_a_correct_checksum(
    good: Package, name: str, magic: bytes, tail: bytes
) -> None:
    """Pickle o zip en cualquier archivo del paquete, con el SHA-256 al dia en el manifiesto: se rechaza igual."""
    data = magic + tail
    assert has_executable_magic(data)
    with deserializers_forbidden() as calls:
        manifest, files = with_file(good, name, data)
        assert reason((manifest, files)) == f"forbidden_magic_bytes:{name}"
    assert calls == []


@given(magic=_MAGIC, tail=_TAILS)
def test_pbt_u4_06_magic_bytes_in_the_manifest_are_rejected(good: Package, magic: bytes, tail: bytes) -> None:
    data = magic + tail
    assert reason((data, good[1]), manifest_sha256=sha(data)) == "forbidden_magic_bytes:manifest.json"


@given(data=st.binary(max_size=300))
def test_pbt_u4_06_bytes_without_headers_are_not_magic(data: bytes) -> None:
    """Oraculo: magico <=> empieza con `PK\\x03\\x04` o con `\\x80` y un protocolo 2 a 5."""
    expected = data[:4] == b"PK\x03\x04" or (len(data) >= 2 and data[0] == 0x80 and 2 <= data[1] <= 5)
    assert has_executable_magic(data) == expected


@given(name=_NAMES, tail=_TAILS.filter(lambda b: not has_executable_magic(b)), index=st.integers(0, 10_000))
def test_pbt_u4_06_a_different_checksum_is_always_rejected(
    good: Package, name: str, tail: bytes, index: int
) -> None:
    """Cualquier cambio de bytes de un archivo, sin tocar el manifiesto, es `sha256_mismatch` (o magico, si lo parece)."""
    manifest, files = good
    original = files[name]
    changed = (
        original[: index % (len(original) + 1)] + b"\x01" + tail + original[index % (len(original) + 1) :]
    )
    assume_different = changed != original
    assert assume_different
    got = reason((manifest, {**files, name: changed}))
    assert got in {f"sha256_mismatch:{name}", f"forbidden_magic_bytes:{name}"}


@given(name=_NAMES, extension=st.sampled_from([".pkl", ".pickle", ".joblib"]), data=st.binary(max_size=100))
def test_pbt_u4_06_forbidden_extensions_with_any_bytes(
    good: Package, name: str, extension: str, data: bytes
) -> None:
    manifest, files = good
    document = json.loads(manifest)
    new = f"{name}{extension}"
    document["files"].append(
        {"name": new, "sha256": sha(data), "model_version_id": document["model_version_id"]}
    )
    got = reason((json.dumps(document).encode(), {**files, new: data}))
    assert got in {f"forbidden_extension:{new}"}
