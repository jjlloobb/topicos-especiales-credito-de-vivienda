"""Paso 7 (BR-U5-16..18; US-106, US-109, US-111): `adversarial/manifest.json` leido de disco, con sus 42 casos.

RT-3: el validador de manifiesto de U4 (la copia de U05-T02, `u4_registration_copy`) rechaza `RT3-a`, `RT3-c` y `RT3-d`
y acepta `RT3-b`. Que `RT3-b` pase es intencional (domain-entities §5, «Artefactos RT-3»): el explicador sin una feature
cumple todo lo que U4 verifica (formato, SHA-256 y un solo `model_version_id`) y lo atrapa despues `sync_check`
(`validacion_fallida`) o el runtime (`FailClosed` con `explainer_error` o `feature_dictionary_incomplete`).
"""

import json
import re
import shutil
import unicodedata
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from vectra_contracts.models.features import FeatureSpec
from vectra_reference import adversarial as adv
from vectra_reference.package import dump_json, sha256
from vectra_reference.release import Release


def _manifest_on_disk(release: Release) -> dict[str, Any]:
    return json.loads((release.out / "adversarial" / "manifest.json").read_bytes())  # type: ignore[no-any-return]


def _cases(manifest: dict[str, Any], scenario: str) -> list[dict[str, Any]]:
    return [c for c in manifest["cases"] if c["scenario"] == scenario]


def test_the_manifest_has_42_cases_each_with_its_expected_result(
    reference_release: Release, reference_adversarial: dict[str, Any]
) -> None:
    manifest = _manifest_on_disk(reference_release)
    assert manifest == json.loads(
        dump_json(reference_adversarial)
    )  # lo que se escribio es lo que se devolvio
    assert (reference_release.out / "adversarial" / "manifest.json").read_bytes() == dump_json(manifest)
    cases = manifest["cases"]
    assert len(cases) == 42
    assert Counter(c["scenario"] for c in cases) == {"RT-1": 20, "RT-4": 18, "RT-3": 4}
    assert [c["case_id"] for c in cases] == [
        *(f"RT1-{n:02d}" for n in range(1, 21)),
        *(f"RT4-{n:02d}" for n in range(1, 19)),
        *(f"RT3-{x}" for x in "abcd"),
    ]
    assert all(c["expected"] for c in cases)
    assert adv.check_manifest(manifest) == []


def test_every_case_has_the_expected_result_of_domain_entities_5(
    reference_release: Release, reference_adversarial: dict[str, Any]
) -> None:
    manifest = _manifest_on_disk(reference_release)
    assert all(c["expected"] == adv.RT1_EXPECTED for c in _cases(manifest, "RT-1"))
    assert all(c["expected"] == adv.RT4_EXPECTED for c in _cases(manifest, "RT-4"))
    rt3 = {c["case_id"]: c["expected"] for c in _cases(manifest, "RT-3")}
    assert [rt3[k]["u4_registration"] for k in ("RT3-a", "RT3-b", "RT3-c", "RT3-d")] == [
        "rejected", "accepted", "rejected", "rejected",
    ]  # fmt: skip
    assert "validacion_fallida" in rt3["RT3-b"]["later"] and "explainer_error" in rt3["RT3-b"]["later"]
    assert "no es barrera" in rt3["RT3-c"]["u6"]


# RT-1 ----------------------------------------------------------------------------------------------------------


def test_the_20_rt1_pairs_differ_only_in_free_text_and_are_valid_applications(
    reference_release: Release, reference_adversarial: dict[str, Any]
) -> None:
    cases = _cases(_manifest_on_disk(reference_release), "RT-1")
    assert len(cases) == 20
    for case in cases:
        pair = case["paired_with"]
        assert pair["free_text"] is None
        assert case["input"]["free_text"] is not None
        assert set(case["input"]) == set(pair)
        assert {k for k in pair if pair[k] != case["input"][k]} == {"free_text"}, case["case_id"]
        adv.validate_application(case["input"])
        adv.validate_application(pair)
    assert len({c["paired_with"]["document_number"] for c in cases}) == 20  # 20 solicitantes distintos
    assert len({c["input"]["free_text"] for c in cases}) == 20


def _category(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def test_the_rt1_texts_cover_the_categories_of_br_u5_16(
    reference_release: Release, reference_adversarial: dict[str, Any]
) -> None:
    texts = [c["input"]["free_text"] for c in _cases(_manifest_on_disk(reference_release), "RT-1")]

    def count(predicate: Callable[[str], bool]) -> int:
        return sum(predicate(t) for t in texts)

    spanish = count(lambda t: _category(t, r"\b(ignora|instrucciones|analista|solicitante)\b"))
    english = count(lambda t: _category(t, r"\b(ignore all|developer mode|system override)\b"))
    html = count(lambda t: _category(t, r"<(b|a|img|iframe)\b"))
    script = count(lambda t: _category(t, r"<script"))
    sql = count(lambda t: _category(t, r"drop table|union select"))
    markdown = count(lambda t: _category(t, r"^#|\*\*|\]\(http|```"))
    bidi = count(lambda t: any(unicodedata.bidirectional(ch) in ("R", "AL") for ch in t))
    homoglyph = count(
        lambda t: any(
            ord(ch) > 127 and unicodedata.name(ch, "").startswith(("CYRILLIC", "GREEK")) for ch in t
        )
    )
    assert (spanish, english) >= (3, 3)
    assert html >= 2 and script >= 2 and sql >= 2 and markdown >= 2 and bidi >= 2 and homoglyph >= 2
    assert sum(len(t) == 2000 for t in texts) == 1
    assert max(len(t) for t in texts) == 2000


def test_the_deceptive_unicode_cases_are_printable_because_u0_rejects_control_characters() -> None:
    """U0 (BR-U0-29) rechaza U+202E y los de ancho cero; por eso el caso bidi usa hebreo y arabe, que son imprimibles."""
    base = adv.rt1_base_application(1, adv.load_catalog())
    for control in ("‮", "⁦", "​"):
        with pytest.raises(adv.AdversarialError, match="valida"):
            adv.validate_application({**base, "free_text": f"aprobar{control}"})


# RT-4 ----------------------------------------------------------------------------------------------------------


def test_the_18_rt4_cases_are_the_ones_the_calibration_used(
    reference_release: Release, reference_adversarial: dict[str, Any]
) -> None:
    cases = _cases(_manifest_on_disk(reference_release), "RT-4")
    assert [c["input"] for c in cases] == [c["input"] for c in reference_release.rt4]
    assert len(cases) == adv.N_RT4 == 18


# RT-3 ----------------------------------------------------------------------------------------------------------


def _rt3_dir(release: Release, case_id: str) -> Path:
    return release.out / "adversarial" / "rt3" / case_id


def _declared(directory: Path) -> str:
    return sha256((directory / "manifest.json").read_bytes())


def test_the_valid_package_is_accepted_by_the_u4_validator(
    reference_release: Release, u4_validate: Callable[..., None]
) -> None:
    u4_validate(reference_release.package_dir, _declared(reference_release.package_dir))


@pytest.mark.parametrize("case_id", ["RT3-a", "RT3-c", "RT3-d"])
def test_the_u4_manifest_validator_rejects_rt3_a_c_and_d(
    reference_release: Release,
    reference_adversarial: dict[str, Any],
    u4_registration: ModuleType,
    case_id: str,
) -> None:
    directory = _rt3_dir(reference_release, case_id)
    reasons = {
        "RT3-a": "model_version_id_mismatch_inside:explainer.json",
        "RT3-c": "model_version_id_mismatch_inside:feature_dictionary.json",
        "RT3-d": "model_version_id_mismatch:explainer.json",
    }
    with pytest.raises(u4_registration.RegistrationRejected) as info:
        u4_registration.validate_registration(directory, _declared(directory))
    assert str(info.value) == reasons[case_id]


def test_the_u4_manifest_validator_accepts_rt3_b_and_the_gap_is_what_the_manifest_says(
    reference_release: Release, reference_adversarial: dict[str, Any], u4_validate: Callable[..., None]
) -> None:
    directory = _rt3_dir(reference_release, "RT3-b")
    u4_validate(directory, _declared(directory))  # no lanza: U4 acepta
    explainer = json.loads((directory / "explainer.json").read_bytes())
    spec = FeatureSpec.model_validate_json((directory / "feature_spec.json").read_bytes())
    missing = {i.feature_id for i in spec.features} - set(explainer["feature_order"])
    assert missing == {adv.DROPPED_FEATURE}  # lo que atrapa sync_check o el runtime, no U4


def test_each_rt3_package_differs_from_the_valid_one_only_where_the_manifest_documents(
    reference_release: Release, reference_adversarial: dict[str, Any]
) -> None:
    base = reference_release.package_dir
    base_manifest = json.loads((base / "manifest.json").read_bytes())
    for case in _cases(_manifest_on_disk(reference_release), "RT-3"):
        directory = _rt3_dir(reference_release, case["case_id"])
        assert case["input"] == f"rt3/{case['case_id']}"
        assert case["alteration"]["base_model_version_id"] == base_manifest["model_version_id"]
        assert {p.name for p in directory.iterdir()} == {p.name for p in base.iterdir()}
        changed = {p.name for p in base.iterdir() if (directory / p.name).read_bytes() != p.read_bytes()}
        documented = {case["alteration"]["file"]}
        # el manifiesto cambia siempre (lista el SHA-256 nuevo), salvo que sea el propio archivo alterado
        assert changed == documented | {"manifest.json"}, (case["case_id"], changed)


def test_an_unaltered_copy_of_the_package_is_accepted_and_the_altered_one_is_not(
    reference_release: Release, u4_registration: ModuleType, tmp_path: Path
) -> None:
    """Mutacion: si RT3-a se dejara sin alterar (copia del paquete valido), U4 lo aceptaria y la prueba lo veria."""
    target = tmp_path / "RT3-a"
    shutil.copytree(reference_release.package_dir, target)
    u4_registration.validate_registration(target, _declared(target))  # sin alteracion: acepta
    adv.rt3_package("RT3-a", reference_release.package_dir, tmp_path / "altered")
    with pytest.raises(u4_registration.RegistrationRejected):
        u4_registration.validate_registration(tmp_path / "altered", _declared(tmp_path / "altered"))
