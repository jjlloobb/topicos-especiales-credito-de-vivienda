"""Paso 6 (BR-U5-06, BR-U5-14, BR-U5-15; US-303): la variante proxy de RT-2, leida de disco.

Los 5 paquetes se generan una vez por sesion (`reference_proxy`) y las pruebas los leen como los leeria U4: con sus
archivos y su `manifest.json`, no con los objetos en memoria.
"""

import copy
import csv
import json
import shutil
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import xgboost as xgb
from vectra_contracts.labels import derive
from vectra_contracts.models.application import ApplicationIn
from vectra_contracts.models.features import FeatureDictionary, FeatureSpec
from vectra_contracts.models.governance import PolicyDraft
from vectra_reference import generate as gen
from vectra_reference import proxy as px
from vectra_reference.envelope.confidence import confidence
from vectra_reference.features import NUMERIC_FEATURES, read_rows, validate_feature_spec
from vectra_reference.package import (
    PURPOSE_RT2,
    build_package,
    dump_json,
    feature_dictionary,
    sha256,
    verify_package,
)
from vectra_reference.release import ProxyRelease, Release
from vectra_reference.train import encode

CONFIG = gen.load_config()
CATALOG = px.load_proxy_catalog()
RUNS = range(1, 6)
STATS = (
    "sizes",
    "default_rates",
    "auc_validation",
    "disparity_pp",
    "disparity_trigger_attribute",
    "base_disparity_pp",
    "validation_review_rate",
)


def _application(row: dict[str, Any]) -> ApplicationIn:
    fields = gen.application_fields(row)
    return ApplicationIn.model_validate({**fields, "birth_date": date.fromisoformat(fields["birth_date"])})


def _package(reference_release: Release, run: int) -> Path:
    return reference_release.out / "proxy" / f"run-{run}"


def _manifest(directory: Path) -> dict[str, Any]:
    return json.loads((directory / "manifest.json").read_bytes())  # type: ignore[no-any-return]


def _file_sha(manifest: dict[str, Any], name: str) -> str:
    return next(e["sha256"] for e in manifest["files"] if e["name"] == name)


# Disparidad (BR-U5-06, BR-U5-14) --------------------------------------------------------------------------------


def test_the_base_disparity_is_below_5_pp_and_the_variants_are_at_least_10_pp(
    reference_release: Release, reference_proxy: ProxyRelease
) -> None:
    base = _manifest(reference_release.package_dir)
    assert base["purpose"] == "base"
    assert base["disparity_pp"] < 5.0
    for run in RUNS:
        manifest = _manifest(_package(reference_release, run))
        assert manifest["disparity_pp"] >= 10.0, run
        assert manifest["purpose"] == PURPOSE_RT2 == "rt2-demo"
        assert manifest["base_disparity_pp"] == base["disparity_pp"]
        assert (
            manifest["disparity_trigger_attribute"] == "region"
        )  # el proxy de la region (la zona sigue a la region)
    assert reference_proxy.disparity_pp == _manifest(_package(reference_release, 1))["disparity_pp"]


def _recompute_disparity(reference_release: Release, directory: Path) -> float:
    """Mide la disparidad del paquete en disco: predictor.json y `validation.parquet`, sin pasar por `run_*`."""
    spec = FeatureSpec.model_validate_json((directory / "feature_spec.json").read_bytes())
    explainer = json.loads((directory / "explainer.json").read_bytes())
    booster = xgb.Booster()
    booster.load_model(bytearray((directory / "predictor.json").read_bytes()))
    rows = read_rows(reference_release.datasets["validation"])
    values = [
        px.with_lookups(v, r, spec)
        for v, r in zip(reference_release.splits["validation"].values, rows, strict=True)
    ]
    order = explainer["feature_order"]
    matrix = encode(values, order, explainer["categorical_encoding"])
    probabilities = np.asarray(booster.predict(xgb.DMatrix(matrix, feature_names=order)))
    envelope = json.loads((directory / "domain_envelope.json").read_bytes())
    policy = PolicyDraft.model_validate_json((reference_release.out / "reference-policy.json").read_bytes())
    evaluated_on = date.fromisoformat(CONFIG["reference_date"])
    outcomes = px.outcomes_of(
        rows, probabilities, [confidence(envelope, v) for v in values], policy, evaluated_on
    )
    return px.disparity_pp(rows, outcomes, evaluated_on)[1]


def test_the_disparity_in_the_manifests_is_what_the_packages_on_disk_produce(
    reference_release: Release, reference_proxy: ProxyRelease
) -> None:
    assert _recompute_disparity(reference_release, _package(reference_release, 3)) == pytest.approx(
        _manifest(_package(reference_release, 3))["disparity_pp"], abs=1e-9
    )
    assert _recompute_disparity(reference_release, reference_release.package_dir) == pytest.approx(
        _manifest(reference_release.package_dir)["disparity_pp"], abs=1e-9
    )


# Zonas (BR-U5-15, BR-U0-34) --------------------------------------------------------------------------------------


def test_no_zone_of_any_package_has_fewer_than_5_municipalities(
    reference_release: Release, reference_proxy: ProxyRelease
) -> None:
    for run in RUNS:
        spec = FeatureSpec.model_validate_json(
            (_package(reference_release, run) / "feature_spec.json").read_bytes()
        )
        zone = next(i for i in spec.features if i.feature_id == px.ZONE_FEATURE)
        assert zone.source_fields == ["municipality_code"]
        counts = Counter((zone.table or {}).values())
        assert set(counts) == set(CATALOG["zonas"]), run
        assert min(counts.values()) >= 5, (run, counts)
        assert sum(counts.values()) == 1122  # cada municipio de U0 esta en una zona
    assert px.zone_table(CATALOG) == zone.table


def test_a_zone_with_4_municipalities_is_rejected() -> None:
    """Mutacion: 'zona_1' queda solo con el departamento 95 (Guaviare, 4 municipios)."""
    catalog = copy.deepcopy(CATALOG)
    catalog["zonas"]["zona_2"] = [*catalog["zonas"]["zona_2"], *catalog["zonas"]["zona_1"]]
    catalog["zonas"]["zona_1"] = ["95"]
    catalog["zonas"]["zona_6"] = [d for d in catalog["zonas"]["zona_6"] if d != "95"]
    with pytest.raises(px.ProxyError, match=r"zone_too_small:zona_1:4<5"):
        px.zone_table(catalog)


def test_a_zone_table_with_a_zone_of_4_municipalities_is_rejected_by_the_package_check() -> None:
    catalog = copy.deepcopy(CATALOG)
    spec = px.proxy_feature_spec(CATALOG, CONFIG, "mv-x")
    zone = next(i for i in spec.features if i.feature_id == px.ZONE_FEATURE)
    assert zone.table is not None
    first_zone = next(iter(CATALOG["zonas"]))
    keep = [m for m, z in zone.table.items() if z == first_zone][:4]
    small = zone.model_copy(
        update={"table": {m: z for m, z in zone.table.items() if z != first_zone or m in keep}}
    )
    spec = spec.model_copy(update={"features": [small if i is zone else i for i in spec.features]})
    dictionary = feature_dictionary(spec, "1.0.0", not_applicant_safe=px.PROXY_FEATURES)
    assert px.check_proxy_spec(spec, dictionary, catalog) == [f"zone_too_small:{first_zone}:4<5"]


def test_a_department_in_two_zones_or_without_zone_is_rejected() -> None:
    twice = copy.deepcopy(CATALOG)
    twice["zonas"]["zona_2"] = [*twice["zonas"]["zona_2"], "05"]
    with pytest.raises(px.ProxyError, match="department_in_two_zones:05"):
        px.zone_table(twice)
    missing = copy.deepcopy(CATALOG)
    missing["zonas"]["zona_2"] = [d for d in missing["zonas"]["zona_2"] if d != "11"]
    with pytest.raises(px.ProxyError, match="department_without_zone:11"):
        px.zone_table(missing)


# El municipio no llega al FeatureVector (BR-U0-34) ---------------------------------------------------------------


def test_municipality_code_never_appears_in_the_feature_vector_that_derive_produces(
    reference_release: Release, reference_proxy: ProxyRelease
) -> None:
    rows = read_rows(reference_release.datasets["test"])[:300]
    for run in RUNS:
        spec = FeatureSpec.model_validate_json(
            (_package(reference_release, run) / "feature_spec.json").read_bytes()
        )
        for row in rows:
            application = _application(row)
            vector = derive(application, date(2026, 1, 1), spec)
            keys = set(vector.features)
            assert {"municipality_code", "department_code", "broker_id"}.isdisjoint(keys)
            assert {px.ZONE_FEATURE, px.DETAIL_FEATURE} <= keys
            zone = vector.features[px.ZONE_FEATURE].value
            assert zone in CATALOG["zonas"]
            values = {str(f.value) for f in vector.features.values() if f.type == "category"}
            assert {row["municipality_code"], row["department_code"], str(row["broker_id"])}.isdisjoint(
                values
            )


def test_the_lookup_of_u5_is_the_lookup_of_derive(reference_release: Release) -> None:
    """`with_lookups` (que usa el entrenamiento) da lo mismo que `derive` (que usa la inferencia): 500 filas."""
    spec = px.proxy_feature_spec(CATALOG, CONFIG, "mv-x")
    for row in read_rows(reference_release.datasets["validation"])[:500]:
        vector = derive(_application(row), date(2026, 1, 1), spec)
        for item in spec.features:
            if item.origin == "lookup":
                assert vector.features[item.feature_id].value == px.lookup_value(item, row)


def test_an_unknown_municipality_and_an_unknown_broker_fall_to_the_default_value() -> None:
    spec = px.proxy_feature_spec(CATALOG, CONFIG, "mv-x")
    zone, detail = (next(i for i in spec.features if i.feature_id == f) for f in px.PROXY_FEATURES)
    assert px.lookup_value(zone, {"municipality_code": "00000"}) == CATALOG["zona_sin_dato"]
    assert px.lookup_value(detail, {"channel": "digital", "broker_id": None}) == "digital"
    assert (
        px.lookup_value(detail, {"channel": "digital", "broker_id": "SYN-BRK-999"})
        == CATALOG["canal_sin_dato"]
    )
    assert (
        px.lookup_value(detail, {"channel": "aliado_inmobiliario", "broker_id": "SYN-BRK-015"})
        == "aliado_grupo_b"
    )


# 5 versiones, un solo predictor (BR-U5-15) -----------------------------------------------------------------------


def test_the_5_packages_have_distinct_versions_and_the_same_predictor(
    reference_release: Release, reference_proxy: ProxyRelease
) -> None:
    manifests = [_manifest(_package(reference_release, run)) for run in RUNS]
    ids = [m["model_version_id"] for m in manifests]
    assert len(set(ids)) == 5
    assert reference_release.manifest["model_version_id"] not in ids
    assert [m["rt2_run"] for m in manifests] == [1, 2, 3, 4, 5]
    assert len({_file_sha(m, "predictor.json") for m in manifests}) == 1
    assert len({(_package(reference_release, r) / "predictor.json").read_bytes() for r in RUNS}) == 1
    assert len({_file_sha(m, "background.csv") for m in manifests}) == 1  # mismo modelo y mismo fondo
    for run, manifest in zip(RUNS, manifests, strict=True):
        directory = _package(reference_release, run)
        assert {e["model_version_id"] for e in manifest["files"]} == {manifest["model_version_id"]}
        assert sha256((directory / "predictor.json").read_bytes()) == _file_sha(manifest, "predictor.json")
        for name in (
            "explainer.json",
            "domain_envelope.json",
            "feature_dictionary.json",
            "feature_spec.json",
        ):
            assert (
                json.loads((directory / name).read_bytes())["model_version_id"]
                == manifest["model_version_id"]
            )


def _background_of(directory: Path) -> list[dict[str, Any]]:
    with (directory / "background.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    numeric = set(NUMERIC_FEATURES)
    return [{k: (float(v) if k in numeric else v) for k, v in row.items()} for row in rows]


def test_the_version_id_depends_on_rt2_run_and_on_nothing_else_that_varies(
    reference_release: Release, reference_proxy: ProxyRelease, tmp_path: Path
) -> None:
    """Mutacion: dos corridas con el mismo `rt2_run` dan el mismo id y los mismos bytes; con otro, otro id."""
    run_dir = _package(reference_release, 1)
    background = _background_of(run_dir)

    def build(name: str, run: int) -> dict[str, Any]:
        return build_package(
            tmp_path / name, reference_proxy.model, reference_proxy.envelope, background,
            reference_proxy.explainer.base_value, CONFIG,
            {k: v for k, v in _manifest(run_dir).items() if k in STATS},
            spec_for=lambda version: px.proxy_feature_spec(CATALOG, CONFIG, version),
            purpose=PURPOSE_RT2, not_applicant_safe=px.PROXY_FEATURES, extra_meta={"rt2_run": run},
        )  # fmt: skip

    same_a, same_b, other = build("a", 1), build("b", 1), build("c", 6)
    assert same_a["model_version_id"] == same_b["model_version_id"] == _manifest(run_dir)["model_version_id"]
    assert (tmp_path / "a" / "manifest.json").read_bytes() == (tmp_path / "b" / "manifest.json").read_bytes()
    assert other["model_version_id"] != same_a["model_version_id"]
    assert (tmp_path / "c" / "predictor.json").read_bytes() == (run_dir / "predictor.json").read_bytes()


def test_every_proxy_package_is_a_valid_package_for_u5_and_u4(
    reference_release: Release, reference_proxy: ProxyRelease, u4_validate: Any
) -> None:
    for run in RUNS:
        directory = _package(reference_release, run)
        assert verify_package(directory) == []
        u4_validate(directory, sha256((directory / "manifest.json").read_bytes()))


def test_the_dictionary_marks_both_proxy_features_as_not_safe_for_the_applicant(
    reference_release: Release, reference_proxy: ProxyRelease
) -> None:
    for run in RUNS:
        dictionary = FeatureDictionary.model_validate_json(
            (_package(reference_release, run) / "feature_dictionary.json").read_bytes()
        )
        safe = {e.feature_id: e.applicant_safe for e in dictionary.entries}
        assert safe[px.ZONE_FEATURE] is False
        assert safe[px.DETAIL_FEATURE] is False
        assert all(v for k, v in safe.items() if k not in px.PROXY_FEATURES)


def test_a_proxy_package_whose_features_are_marked_safe_for_the_applicant_fails_verification(
    reference_release: Release, reference_proxy: ProxyRelease, tmp_path: Path
) -> None:
    target = tmp_path / "pkg"
    shutil.copytree(_package(reference_release, 1), target)
    dictionary = json.loads((target / "feature_dictionary.json").read_bytes())
    for entry in dictionary["entries"]:
        entry["applicant_safe"] = True
    data = dump_json(dictionary)
    (target / "feature_dictionary.json").write_bytes(data)
    manifest = _manifest(target)
    for entry in manifest["files"]:
        if entry["name"] == "feature_dictionary.json":
            entry["sha256"] = sha256(data)
    (target / "manifest.json").write_bytes(dump_json(manifest))
    assert verify_package(target) == [f"proxy_feature_applicant_safe:{f}" for f in px.PROXY_FEATURES]


def test_a_base_package_cannot_carry_the_proxy_features(reference_release: Release) -> None:
    """Sin `purpose = rt2-demo` el `feature_spec` solo admite las features de §3.1 (BR-U5-07)."""
    assert verify_package(reference_release.package_dir) == []
    with pytest.raises(Exception, match="excluded_source_field:municipality_code"):
        validate_feature_spec(px.proxy_feature_spec(CATALOG, CONFIG, "mv-x"))


# La etiqueta depende de forma parcial de las busquedas (BR-U5-14) ------------------------------------------------


def test_the_label_depends_partially_on_the_zone_and_the_channel_detail(
    reference_release: Release, reference_proxy: ProxyRelease
) -> None:
    rows = read_rows(reference_release.datasets["train"])
    base_y = reference_release.splits["train"].y
    spec = px.proxy_feature_spec(CATALOG, CONFIG, "mv-x")
    proxy_y = px.proxy_labels(rows, base_y, spec, CONFIG, 0)
    zone_item = next(i for i in spec.features if i.feature_id == px.ZONE_FEATURE)
    by_zone: dict[str, list[int]] = {}
    for row, base, new in zip(rows, base_y, proxy_y, strict=True):
        assert new >= base  # la etiqueta solo suma incumplimientos extra
        by_zone.setdefault(px.lookup_value(zone_item, row), []).append(int(new) - int(base))
    extra = {zone: sum(v) / len(v) for zone, v in by_zone.items()}
    assert extra["zona_1"] > 0 or CONFIG["proxy"]["zone_extra_default"].get("zona_1", 0) == 0
    assert extra["zona_5"] > extra["zona_4"] > 0  # parcial: no todas las zonas, ni todas con el mismo peso
    assert extra["zona_5"] > 10 * extra["zona_2"] + 0.01  # zona_2 no tiene efecto de zona (solo el del canal)
    assert (proxy_y == px.proxy_labels(rows, base_y, spec, CONFIG, 0)).all()  # determinista


# Doble de la libreria de U9 (BR-U9-01..05) ----------------------------------------------------------------------


def _record(group: str, band: str, favorable: bool, attribute: str = "region") -> tuple[dict[str, str], bool]:
    labels = {"sexo": "F", "rango_edad": "26-35", "region": "andina", "estrato": "3", "banda": band}
    labels[attribute] = group
    return labels, favorable


def _cell(group: str, band: str, n: int, favorable: int) -> list[tuple[dict[str, str], bool]]:
    return [_record(group, band, i < favorable) for i in range(n)]


def test_the_disparity_double_follows_br_u9_01_to_05() -> None:
    # Banda lt_20: andina 100 casos con 90 % favorables, caribe 100 con 70 %: d = 0,20 (n_b = 200).
    # Banda 20_30: andina 50 con 80 %, caribe 50 con 76 %: d = 0,04 (n_b = 100).
    records = (
        _cell("andina", "lt_20", 100, 90)
        + _cell("caribe", "lt_20", 100, 70)
        + _cell("andina", "20_30", 50, 40)
        + _cell("caribe", "20_30", 50, 38)
    )
    expected = (200 * 0.20 + 100 * 0.04) / 300
    assert px.disparity_by_attribute(records, "region") == pytest.approx(expected)
    aggregate = px.model_aggregate(records)
    assert aggregate is not None
    assert aggregate[0] == "region"
    assert aggregate[1] == pytest.approx(expected)


def test_the_disparity_double_ignores_small_cells_and_no_informado_and_single_group_bands() -> None:
    records = (
        _cell("andina", "lt_20", 100, 90)
        + _cell("caribe", "lt_20", 100, 70)
        + _cell("pacifica", "lt_20", 29, 0)  # < 30: no entra (BR-U9-02)
        + _cell("no_informado", "lt_20", 100, 0)  # no es extremo (BR-U9-02)
        + _cell("andina", "gt_30", 100, 10)  # una sola celda suficiente: no hay diferencia (BR-U9-02)
        + _cell("caribe", "gt_30", 29, 29)
    )
    assert px.disparity_by_attribute(records, "region") == pytest.approx(0.20)
    assert px.disparity_by_attribute(_cell("andina", "lt_20", 100, 50), "region") is None


def _policy() -> PolicyDraft:
    return PolicyDraft.model_validate_json(
        json.dumps(
            {
                "cutoff": "0.0800",
                "low_confidence_threshold": "0.0300",
                "channel_rules": [],
                "normative": [
                    {
                        "effective_from": "2026-01-01",
                        "effective_to": None,
                        "usury_cap_ea": "0.2800",
                        "vis_max_property_value": 200000000,
                        "source_ref": "sintetico",
                    }
                ],
            }
        )
    )


EVALUATED_ON = date(2026, 1, 1)


def test_outcome_follows_br_u7_04_and_05() -> None:
    policy = _policy()
    assert px.outcome_of(0.05, "0.5000", "0.1250", policy, EVALUATED_ON) == "favorable"
    assert (
        px.outcome_of(0.08, "0.5000", "0.1250", policy, EVALUATED_ON) == "desfavorable"
    )  # score < corte, estricto
    assert (
        px.outcome_of(0.05, "0.0299", "0.1250", policy, EVALUATED_ON) == "revision_requerida"
    )  # baja confianza
    assert (
        px.outcome_of(0.05, "0.0300", "0.1250", policy, EVALUATED_ON) == "favorable"
    )  # igual al umbral no es baja
    assert (
        px.outcome_of(0.05, "0.5000", "0.2800", policy, EVALUATED_ON) == "favorable"
    )  # igual a la usura no es sobre
    assert (
        px.outcome_of(0.05, "0.5000", "0.2801", policy, EVALUATED_ON) == "revision_requerida"
    )  # sobre usura
    assert (
        px.outcome_of(0.05, "0.5000", "0.1250", policy, date(2025, 12, 31)) == "revision_requerida"
    )  # sin vigencia


def test_a_cell_of_cases_under_the_cutoff_with_low_confidence_is_not_favorable() -> None:
    """BR-U9-01: `revision_requerida` es NO favorable aunque `p < cutoff`. El doble de la ronda 1 (`p < cutoff`) da 0."""
    template = gen.build_rows(gen.with_overrides(CONFIG, n_rows=1))[0]
    rows = [{**template, "department_code": "05"} for _ in range(100)] + [
        {**template, "department_code": "08"} for _ in range(100)
    ]  # 05 es andina y 08 es caribe; el resto de los campos (y la banda de pago) es el mismo
    probabilities = [0.01] * 200  # todos bajo el corte
    confidences = ["0.5000"] * 100 + ["0.0100"] * 100  # los de la region caribe, con baja confianza
    outcomes = px.outcomes_of(rows, probabilities, confidences, _policy(), EVALUATED_ON)
    assert outcomes == ["favorable"] * 100 + ["revision_requerida"] * 100
    trigger, pp = px.disparity_pp(rows, outcomes, EVALUATED_ON)
    assert (trigger, pp) == ("region", 100.0)
    # con confianza alta en todos no hay disparidad
    same = px.outcomes_of(rows, probabilities, ["0.5000"] * 200, _policy(), EVALUATED_ON)
    assert px.disparity_pp(rows, same, EVALUATED_ON)[1] == 0.0


def test_the_aggregate_of_the_model_is_the_largest_attribute() -> None:
    records = [
        *_cell("andina", "lt_20", 100, 90),
        *_cell("caribe", "lt_20", 100, 70),
    ]
    other = [({**labels, "sexo": "F" if i % 2 else "M"}, fav) for i, (labels, fav) in enumerate(records)]
    result = px.model_aggregate(other)
    assert result is not None and result[0] == "region" and result[1] == pytest.approx(0.20)


def test_the_quality_gates_fail_when_the_disparity_is_out_of_range() -> None:
    px.check_base_disparity(4.99, CONFIG)
    px.check_proxy_disparity(10.0, CONFIG)
    with pytest.raises(px.ProxyError, match="base_disparity_not_below"):
        px.check_base_disparity(5.0, CONFIG)
    with pytest.raises(px.ProxyError, match="proxy_disparity_below"):
        px.check_proxy_disparity(9.99, CONFIG)


def test_the_proxy_manifest_is_deterministic_json(
    reference_release: Release, reference_proxy: ProxyRelease
) -> None:
    for run in RUNS:
        directory = _package(reference_release, run)
        manifest = json.loads((directory / "manifest.json").read_bytes())
        assert (directory / "manifest.json").read_bytes() == dump_json(manifest)
