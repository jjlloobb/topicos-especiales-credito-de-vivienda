"""PBT-U5-05 y PBT-U5-06 (paquete y diccionario) y la aceptacion del validador de registro de U4 (BR-U5-09, 10)."""

import hashlib
import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from vectra_contracts.models.features import FeatureDictionary, FeatureSpec, FeatureSpecItem
from vectra_reference.features import (
    BASE_FEATURES,
    EXCLUDED_FEATURES,
    FeatureSpecError,
    base_feature_spec,
    validate_feature_spec,
)
from vectra_reference.package import (
    ID_CARRIERS,
    PACKAGE_FILES,
    PackageError,
    check_dictionary_coverage,
    dump_json,
    feature_dictionary,
    has_executable_magic,
    verify_package,
)
from vectra_reference.release import Release

RANDOM_FEATURES = st.sampled_from(["sex", "age_years", "x_extra", "zona_vivienda", "free_text", "stratum_x"])


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _copy(package_dir: Path) -> Path:
    target = Path(tempfile.mkdtemp()) / "pkg"
    shutil.copytree(package_dir, target)
    return target


def _rewrite_manifest(directory: Path, change: Callable[[dict[str, Any]], None]) -> None:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    change(manifest)
    (directory / "manifest.json").write_bytes(dump_json(manifest))


def _refresh_sha(directory: Path, name: str) -> None:
    sha = _sha((directory / name).read_bytes())
    _rewrite_manifest(directory, lambda m: [e.update(sha256=sha) for e in m["files"] if e["name"] == name])


# PBT-U5-05 ------------------------------------------------------------------------------------------------------


def test_pbt_u5_05_an_unaltered_package_passes(small_release: Release) -> None:
    assert verify_package(small_release.package_dir) == []
    manifest = small_release.manifest
    assert {e["name"] for e in manifest["files"]} == set(PACKAGE_FILES)
    assert {e["model_version_id"] for e in manifest["files"]} == {manifest["model_version_id"]}
    assert manifest["model_version_id"].startswith("mv-2026-01-01-")


@given(data=st.data())
def test_pbt_u5_05_any_random_alteration_makes_the_package_fail(
    small_release: Release, data: st.DataObject
) -> None:
    package = _copy(small_release.package_dir)
    try:
        name = data.draw(st.sampled_from(PACKAGE_FILES))
        kind = data.draw(
            st.sampled_from(
                [
                    "flip_byte",
                    "delete",
                    "pickle_magic",
                    "zip_magic",
                    "other_id_in_manifest",
                    "other_id_inside",
                ]
            )
        )
        path = package / name
        raw = path.read_bytes()
        if kind == "flip_byte":
            index = data.draw(st.integers(0, len(raw) - 1))
            path.write_bytes(raw[:index] + bytes([raw[index] ^ 0x01]) + raw[index + 1 :])
        elif kind == "delete":
            path.unlink()
        elif kind in {"pickle_magic", "zip_magic"}:
            magic = b"\x80\x04" if kind == "pickle_magic" else b"PK\x03\x04"
            path.write_bytes(magic + raw)
            _refresh_sha(package, name)  # el SHA-256 coincide: solo los bytes magicos lo delatan
        elif kind == "other_id_in_manifest":
            _rewrite_manifest(
                package,
                lambda m: [
                    e.update(model_version_id="mv-2026-01-01-deadbeef")
                    for e in m["files"]
                    if e["name"] == name
                ],
            )
        else:  # el id dentro del archivo (solo los JSON que lo llevan), con el SHA-256 al dia
            assume(name in ID_CARRIERS)
            text = raw.decode().replace(small_release.manifest["model_version_id"], "mv-2026-01-01-deadbeef")
            path.write_text(text, encoding="utf-8")
            _refresh_sha(package, name)
        assert verify_package(package) != []
    finally:
        shutil.rmtree(package.parent)


def test_pbt_u5_05_a_forbidden_extension_in_the_manifest_fails(small_release: Release) -> None:
    package = _copy(small_release.package_dir)
    try:
        (package / "model.pkl").write_bytes(b"plain")
        _rewrite_manifest(
            package,
            lambda m: m["files"].append(
                {"name": "model.pkl", "sha256": _sha(b"plain"), "model_version_id": m["model_version_id"]}
            ),
        )
        assert "forbidden_extension:model.pkl" in verify_package(package)
    finally:
        shutil.rmtree(package.parent)


def test_a_missing_or_broken_manifest_is_reported(tmp_path: Path) -> None:
    assert verify_package(tmp_path)[0].startswith("manifest_unreadable")
    (tmp_path / "manifest.json").write_text("[]")
    assert verify_package(tmp_path)[0].startswith("manifest_unreadable")


def test_a_json_file_that_cannot_be_read_or_a_dictionary_that_cannot_be_parsed_fails(
    small_release: Release,
) -> None:
    package = _copy(small_release.package_dir)
    try:
        (package / "explainer.json").write_bytes(b"not json")
        _refresh_sha(package, "explainer.json")
        assert "json_unreadable:explainer.json" in verify_package(package)
        (package / "feature_dictionary.json").write_bytes(b"{}")
        _refresh_sha(package, "feature_dictionary.json")
        assert "feature_files_unreadable" in verify_package(package)
    finally:
        shutil.rmtree(package.parent)


def test_magic_bytes_detection() -> None:
    assert has_executable_magic(b"\x80\x05rest") and has_executable_magic(b"PK\x03\x04rest")
    assert (
        not has_executable_magic(b"{}")
        and not has_executable_magic(b"\x80")
        and not has_executable_magic(b"")
    )


def test_no_file_of_the_package_is_executable_code(small_release: Release) -> None:
    for entry in small_release.manifest["files"]:
        assert not entry["name"].lower().endswith((".pkl", ".pickle", ".joblib"))
        assert not has_executable_magic((small_release.package_dir / entry["name"]).read_bytes())


def test_the_background_has_200_rows_and_no_identifiers(small_release: Release) -> None:
    lines = (small_release.package_dir / "background.csv").read_text().splitlines()
    assert lines[0].split(",") == list(BASE_FEATURES)
    assert len(lines) == 1 + 200
    assert not EXCLUDED_FEATURES & set(lines[0].split(","))
    assert "SYN" not in "\n".join(lines)


def test_the_model_version_id_has_the_date_and_8_hex_of_the_design(small_release: Release) -> None:
    mid = small_release.manifest["model_version_id"]
    assert mid.startswith("mv-2026-01-01-") and len(mid.split("-")[-1]) == 8
    int(mid.split("-")[-1], 16)


# PBT-U5-06 ------------------------------------------------------------------------------------------------------


def _spec(ids: list[str]) -> FeatureSpec:
    base = {item.feature_id: item for item in base_feature_spec().features}
    return FeatureSpec(
        model_version_id="mv-x",
        features=[
            base.get(i) or FeatureSpecItem(feature_id=i, origin="field", source_fields=[i]) for i in ids
        ],
    )


@given(removed=st.sets(st.sampled_from(BASE_FEATURES)), added=st.sets(RANDOM_FEATURES))
def test_pbt_u5_06_the_dictionary_covers_the_spec_and_the_base_spec_has_no_excluded_feature(
    removed: set[str], added: set[str]
) -> None:
    ids = [f for f in BASE_FEATURES if f not in removed]
    dictionary = feature_dictionary(base_feature_spec(), "1.0.0")
    spec = _spec([*ids, *sorted(added)])
    # El diccionario del modelo base cubre el spec solo si el spec es un subconjunto de las features base.
    if added:
        with pytest.raises(FeatureSpecError):
            validate_feature_spec(spec)
    else:
        validate_feature_spec(spec)
    if removed and not added:
        with pytest.raises(PackageError, match="dictionary_extra"):
            check_dictionary_coverage(spec, dictionary)
    elif not added:
        check_dictionary_coverage(spec, dictionary)


@given(drop=st.sets(st.sampled_from(BASE_FEATURES), min_size=1))
def test_pbt_u5_06_a_dictionary_missing_a_feature_of_the_spec_is_rejected(drop: set[str]) -> None:
    full = feature_dictionary(base_feature_spec(), "1.0.0")
    partial = FeatureDictionary(
        dictionary_version="1.0.0",
        model_version_id=full.model_version_id,
        entries=[e for e in full.entries if e.feature_id not in drop],
    )
    with pytest.raises(PackageError, match="dictionary_incomplete"):
        check_dictionary_coverage(base_feature_spec(), partial)


def test_the_dictionary_is_in_spanish_and_complete(small_release: Release) -> None:
    dictionary = FeatureDictionary.model_validate_json(
        (small_release.package_dir / "feature_dictionary.json").read_bytes()
    )
    assert [e.feature_id for e in dictionary.entries] == list(BASE_FEATURES)
    assert all(
        e.label_es and e.increases_risk_phrase_es and e.decreases_risk_phrase_es for e in dictionary.entries
    )
    assert all(e.applicant_safe for e in dictionary.entries)  # el modelo base no tiene proxies
    assert dictionary.model_version_id == small_release.manifest["model_version_id"]


def test_proxy_features_can_be_marked_not_applicant_safe() -> None:
    dictionary = feature_dictionary(base_feature_spec(), "1.0.0", not_applicant_safe=["channel"])
    assert {e.feature_id: e.applicant_safe for e in dictionary.entries}["channel"] is False


# Validador de registro de U4 (copia) ---------------------------------------------------------------------------


def test_the_u4_validator_accepts_the_package(
    small_release: Release, u4_validate: Callable[..., None]
) -> None:
    declared = _sha((small_release.package_dir / "manifest.json").read_bytes())
    u4_validate(small_release.package_dir, declared)


def test_the_u4_validator_rejects_a_package_with_an_altered_sha256(
    small_release: Release, u4_validate: Callable[..., None], u4_registration: Any
) -> None:
    package = _copy(small_release.package_dir)
    try:
        _rewrite_manifest(package, lambda m: m["files"][0].update(sha256="0" * 64))
        declared = _sha((package / "manifest.json").read_bytes())
        with pytest.raises(u4_registration.RegistrationRejected, match="sha256_mismatch"):
            u4_validate(package, declared)
    finally:
        shutil.rmtree(package.parent)


def test_the_u4_validator_rejects_other_alterations(
    small_release: Release, u4_validate: Callable[..., None], u4_registration: Any
) -> None:
    rejected = u4_registration.RegistrationRejected
    declared = _sha((small_release.package_dir / "manifest.json").read_bytes())
    with pytest.raises(rejected, match="manifest_sha256_mismatch"):
        u4_validate(small_release.package_dir, "0" * 64)
    with pytest.raises(rejected, match="artifact_format_not_allowed"):
        u4_validate(small_release.package_dir, declared, "pickle")
    package = _copy(small_release.package_dir)
    try:
        (package / "predictor.json").write_bytes(b"\x80\x04" + (package / "predictor.json").read_bytes())
        _refresh_sha(package, "predictor.json")
        with pytest.raises(rejected, match="forbidden_magic_bytes"):
            u4_validate(package, _sha((package / "manifest.json").read_bytes()))
    finally:
        shutil.rmtree(package.parent)
    package = _copy(small_release.package_dir)
    try:
        _rewrite_manifest(package, lambda m: m["files"][1].update(model_version_id="mv-2026-01-01-deadbeef"))
        with pytest.raises(rejected, match="model_version_id_mismatch"):
            u4_validate(package, _sha((package / "manifest.json").read_bytes()))
    finally:
        shutil.rmtree(package.parent)
