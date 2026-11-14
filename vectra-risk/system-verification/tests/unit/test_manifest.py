"""El manifiesto (U12-T04, CA-10; NFR-U12-10, 11, 20, 31): campos, `runId`, parche, secciones, tiempos, solicitudes repetidas y las razones de «no ejecutado»."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from vectra_verification import manifest as mf
from vectra_verification import report
from vectra_verification.store import Store

T0 = datetime(2026, 10, 12, 14, 7, 31, tzinfo=UTC)


def fresh() -> mf.Manifest:
    return mf.Manifest.new(started_at=T0, commit="abc", operator="op", environment="kind")


def test_run_id_is_the_utc_minute_of_started_at_and_needs_a_timezone() -> None:
    assert (
        mf.run_id_from(T0) == "20261012-1407" and mf.expected_job("20261012-1407") == "rt5-demo-20261012-1407"
    )
    assert (
        mf.run_id_from(datetime(2026, 10, 12, 21, 7, tzinfo=UTC).astimezone(timezone_minus_5()))
        == "20261012-2107"
    )
    with pytest.raises(mf.ManifestError, match="started_at_without_timezone"):
        mf.run_id_from(T0.replace(tzinfo=None))


def timezone_minus_5():  # type: ignore[no-untyped-def]
    from datetime import timezone

    return timezone(timedelta(hours=-5))


def test_a_new_manifest_has_every_field_and_no_digest(tmp_path: Path) -> None:
    manifest = fresh()
    for field in (
        "started_at",
        "run_id",
        "expected_jobs",
        "commit",
        "operator",
        "seeds",
        "generator_version",
        "test_rows",
        "sections",
        "operator_waits",
        "digests",
        "repeated_requests",
        "files",
    ):
        assert field in manifest.data
    assert manifest.data["digests"] == {} and manifest.started_at == T0.replace(microsecond=0)
    store = Store(tmp_path, lambda: ())
    manifest.save(store, new=True)
    again = mf.Manifest.load(store)
    assert (
        again is not None
        and again.run_id == "20261012-1407"
        and again.commit == "abc"
        and again.operator == "op"
    )
    assert mf.Manifest.load(Store(tmp_path / "otra", lambda: ())) is None


def test_a_manifest_that_is_not_json_or_has_another_shape_is_an_error(tmp_path: Path) -> None:
    store = Store(tmp_path, lambda: ())
    store.write("manifest.json", "{no")
    with pytest.raises(mf.ManifestError, match="manifest_not_json"):
        mf.Manifest.load(store)
    store.write("manifest.json", json.dumps({"schema": 9}))
    with pytest.raises(mf.ManifestError, match="manifest_shape"):
        mf.Manifest.load(store)


def test_the_patch_adds_only_the_run_id_line_under_probes_and_refuses_a_second_one() -> None:
    values = "a: 1\nprobes:\n  enabled: true\nb: 2\n"
    patch = mf.runid_patch(values, "20261012-1407", path="x/values.yaml")
    assert (
        patch.splitlines()[:2] == ["--- a/x/values.yaml", "+++ b/x/values.yaml"]
        and '+  runId: "20261012-1407"' in patch
    )
    assert [ln for ln in patch.splitlines() if ln[:1] in "+-" and ln[:3] not in ("+++", "---")] == [
        '+  runId: "20261012-1407"'
    ]
    with pytest.raises(mf.ManifestError, match="values_already_have_runid"):
        mf.runid_patch(values + "", "20261012-1407", path="x") if False else mf.runid_patch(
            "probes:\n  enabled: true\n  runId: x\n", "20261012-1407", path="x"
        )
    with pytest.raises(mf.ManifestError, match="values_without_probes"):
        mf.runid_patch("a: 1\n", "20261012-1407", path="x")


def test_sections_track_start_finish_interruption_and_deferral() -> None:
    manifest = fresh()
    manifest.start_section("decisions", T0)
    manifest.finish_section("decisions", T0 + timedelta(seconds=90), result="pasa", exit_code=0)
    assert (
        manifest.is_done("decisions")
        and manifest.sections["decisions"]["seconds"] == 90.0
        and manifest.pending_of("decisions") is None
    )
    manifest.start_section("rt2", T0 + timedelta(minutes=10))
    manifest.finish_section(
        "rt2", T0 + timedelta(minutes=12), result="no ejecutado", exit_code=2, pending="reactivacion"
    )
    assert not manifest.is_done("rt2") and manifest.pending_of("rt2") == "reactivacion"
    manifest.start_section(
        "rt2", T0 + timedelta(minutes=20)
    )  # la retoma conserva `started_at` y suma el tiempo
    manifest.finish_section("rt2", T0 + timedelta(minutes=21), result="pasa", exit_code=0)
    assert (
        manifest.sections["rt2"]["started_at"] == "2026-10-12T14:17:31Z"
        and manifest.sections["rt2"]["seconds"] == 180.0
        and manifest.is_done("rt2")
    )
    manifest.start_section("rt5", T0 + timedelta(minutes=30))
    manifest.interrupt_section("rt5", T0 + timedelta(minutes=31), "se cayo")
    assert (
        manifest.sections["rt5"]["state"] == "interrumpida" and manifest.sections["rt5"]["note"] == "se cayo"
    )
    manifest.finish_section("rt5", T0 + timedelta(minutes=32), result="no ejecutado", exit_code=2)
    assert not manifest.is_done("rt5")  # un `no ejecutado` se retoma
    manifest.defer_section("network", T0)
    assert (
        manifest.sections["network"]["exit_code"] == 2
        and "enmienda §3 U12" in manifest.sections["network"]["note"]
    )


def test_the_durations_and_the_operator_waits_are_apart() -> None:
    manifest = fresh()
    manifest.start_section("decisions", T0)
    manifest.finish_section("decisions", T0 + timedelta(seconds=100), result="pasa", exit_code=0)
    manifest.add_wait("antes de rt5", T0 + timedelta(seconds=100), T0 + timedelta(seconds=1900))
    per, total, waits = manifest.durations()
    assert per == {"decisions": 100.0} and total == 100.0 and waits == 1800.0
    assert manifest.last_finished() == T0 + timedelta(seconds=100)
    manifest.defer_section("pii", T0 + timedelta(days=1))
    assert manifest.last_finished() == T0 + timedelta(seconds=100)  # las diferidas no cuentan


def test_repeated_requests_group_the_positions_by_the_sections_that_sent_them() -> None:
    manifest = fresh()
    manifest.record_rows("decisions", [1, 2, 3, 4])
    manifest.record_rows("rt3", [3, 4, 9])
    manifest.record_rows("rt2", [4, 10])
    assert manifest.data["repeated_requests"] == [
        {"sections": ["decisions", "rt2", "rt3"], "count": 1, "positions": [4]},
        {"sections": ["decisions", "rt3"], "count": 1, "positions": [3]},
    ]
    manifest.record_rows("rt3", [3])  # volver a registrar no duplica
    assert manifest.data["rows_sent"]["rt3"] == [3, 4, 9]


def test_digests_files_seeds_population_and_decisions_are_plain_data() -> None:
    manifest = fresh()
    manifest.set_digests("rt5", {"b/x": "sha256:2", "a/y": "sha256:1"})
    manifest.set_file("a.json", "00")
    manifest.set_seed("decisions", 7)
    manifest.set_population("g1", 18000, "ab" * 32)
    manifest.set_decisions(sent=5, accepted=5, decided=4)
    assert (
        list(manifest.digests_of("rt5")) == ["a/y", "b/x"]
        and manifest.digests_of("rt3") == {}
        and manifest.files == {"a.json": "00"}
    )
    assert (
        manifest.data["seeds"] == {"decisions": 7}
        and manifest.data["test_rows"] == 18000
        and manifest.data["decisions"] == {"sent": 5, "accepted": 5, "decided": 4}
    )


def test_evidence_file_names_do_not_collide_on_a_case_insensitive_file_system() -> None:
    names = [mf.evidence_file(e) for e in report.ELEMENT_IDS]
    assert (
        len({n.lower() for n in names}) == len(names)
        and mf.evidence_file("rt-5") == "demo-rt-5.json"
        and mf.evidence_file("RT-5") == "RT-5.json"
    )
    assert mf.prefix_of("20261012-1407") == mf.prefix_of("20261012-1407") and len(mf.prefix_of("x")) == 8


def row(id_: str, kind: str, result: str, evidence: tuple[str, ...] = ()) -> report.ReportRow:
    return report.ReportRow(id_, kind, result, evidence, "", {}, None)  # type: ignore[arg-type]


def test_every_not_executed_row_gets_a_reason() -> None:
    manifest = fresh()
    manifest.start_section("rt5", T0)
    manifest.finish_section("rt5", T0, result="no ejecutado", exit_code=2, note="rt5_job_inexistente")
    rows = [
        row("RT-1", "elemento", "no ejecutado"),
        row("RT-5", "elemento", "no ejecutado"),
        row("RT-2", "elemento", "no ejecutado"),
        row("RT-3", "elemento", "no ejecutado", ("RT-3.json",)),
        row("US-106", "historia", "no ejecutado", ("RT-4",)),
        row("US-111", "historia", "no ejecutado", ("RT-3", "journey-7-3")),
        row("US-101", "historia", "pasa", ("SIM-NORMAL",)),
    ]
    reasons = dict(mf.reasons_not_executed(rows, manifest))
    assert set(reasons) == {"RT-1", "RT-5", "RT-2", "RT-3", "US-106", "US-111"}
    assert (
        "diferida por la demo" in reasons["RT-1"]
        and "rt5_job_inexistente" in reasons["RT-5"]
        and "`rt2` no se corrio" in reasons["RT-2"]
    )
    assert (
        "no es integra" in reasons["RT-3"]
        and "RT-4 (diferida por la demo)" in reasons["US-106"]
        and "prerrequisito" in reasons["US-111"]
    )


def test_render_full_has_the_sections_the_durations_the_notes_and_the_reasons() -> None:
    manifest = fresh()
    manifest.start_section("decisions", T0)
    manifest.finish_section(
        "decisions", T0 + timedelta(hours=1, minutes=2, seconds=3), result="pasa", exit_code=0
    )
    manifest.add_wait("antes de rt5", T0, T0 + timedelta(minutes=5))
    built = report.build([], {}, {}, {})
    text = mf.render_full(built, manifest, {"RT2-LATENCY": "1 medicion(es)"})
    assert "1 h 02 min 03 s" in text and "Esperas del operador" in text and "antes de rt5: 5 min 00 s" in text
    assert (
        "## Notas de las evidencias" in text
        and "- **RT2-LATENCY**: 1 medicion(es)" in text
        and "## No ejecutado y por qué" in text
    )
    empty = mf.render_full(report.VerificationReport(rows=()), manifest)
    assert "## Notas de las evidencias" not in empty and "Ninguno." in empty
