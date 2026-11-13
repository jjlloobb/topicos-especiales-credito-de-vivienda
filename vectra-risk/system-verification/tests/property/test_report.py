"""PBT-U12-02, `report` (U12 Paso 3; BR-U12-11, BR-U12-13; NFR-U12-20, NFR-U12-21) y los ejemplos del informe.

El oraculo aplica BR-U12-11 y BR-U12-13 por definicion sobre las evidencias generadas; no llama a `build`.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from vectra_verification import report, rt2_latency, story_map
from vectra_verification.report import ELEMENT_IDS, Evidence, StoryRow

REAL_MAP = story_map.load(Path(__file__).resolve().parents[2] / "report" / "story-map.yaml")
T0 = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def make(
    element: str,
    n: int = 0,
    *,
    expected: str = "ok",
    obtained: str = "ok",
    result: str = "pasa",
    minutes: int = 0,
) -> Evidence:
    return Evidence(
        id=element,
        command=f"verify {element}",
        output=f"{element}-{n}.txt",
        expected=expected,
        obtained=obtained,
        result=result,  # type: ignore[arg-type]
        commit="abc1234",
        images={"case-service": "sha256:" + "a" * 64},
        executed_at=T0 + timedelta(minutes=minutes),
        operator="op-1",
    )


def intact(evidences: list[Evidence]) -> tuple[dict[str, str], dict[str, str]]:
    hashes = {e.output: sha(e.output) for e in evidences}
    return dict(hashes), dict(hashes)


def row(rep: report.VerificationReport, identifier: str) -> report.ReportRow:
    return next(r for r in rep.rows if r.id == identifier)


# --- generadores ---

HASH_STATE = st.sampled_from(["igual", "distinto", "ausente_declarado", "ausente_observado", "ausente_ambos"])


@st.composite
def evidence_sets(draw):  # type: ignore[no-untyped-def]
    """Evidencias con faltantes, contradicciones (expected != obtained con result = pasa, y al reves) y duplicados, con su estado de hash."""
    count = draw(st.integers(0, 40))
    evidences, states = [], []
    for n in range(count):
        element = draw(st.sampled_from(ELEMENT_IDS))
        same = draw(st.booleans())
        evidences.append(
            make(
                element,
                n,
                expected="x",
                obtained="x" if same else "y",
                result=draw(st.sampled_from(["pasa", "falla"])),
                minutes=n,
            )
        )
        states.append(draw(HASH_STATE))
    declared: dict[str, str] = {}
    observed: dict[str, str] = {}
    for e, state in zip(evidences, states, strict=True):
        if state in ("igual", "ausente_observado"):
            declared[e.output] = sha(e.output)
        if state in ("igual", "ausente_declarado"):
            observed[e.output] = sha(e.output)
        if state == "distinto":
            declared[e.output], observed[e.output] = sha(e.output), sha(e.output + "x")
    return evidences, declared, observed


@st.composite
def story_maps(draw):  # type: ignore[no-untyped-def]
    generated = draw(
        st.dictionaries(
            st.from_regex(r"US-9[0-9]{2}", fullmatch=True),
            st.builds(
                StoryRow,
                st.lists(st.sampled_from(ELEMENT_IDS), min_size=1, max_size=4).map(tuple),
                st.booleans(),
            ),
            max_size=6,
        )
    )
    return draw(st.sampled_from([REAL_MAP, generated]))


# --- oraculo por definicion ---


def oracle_evidence(e: Evidence, declared: dict[str, str], observed: dict[str, str]) -> str:
    if e.output not in declared or e.output not in observed or declared[e.output] != observed[e.output]:
        return "no ejecutado"
    if e.expected != e.obtained:
        return "falla"
    return "falla" if e.result == "falla" else "pasa"


def oracle_element(evidences: list[Evidence], declared: dict[str, str], observed: dict[str, str]) -> str:
    results = [oracle_evidence(e, declared, observed) for e in evidences]
    if "falla" in results:
        return "falla"
    if results and all(r == "pasa" for r in results):
        return "pasa"
    return "no ejecutado"


def oracle_story(required: tuple[str, ...], element_results: dict[str, str]) -> str:
    results = [element_results[r] for r in required]
    if "falla" in results:
        return "falla"
    if results and all(r == "pasa" for r in results):
        return "pasa"
    return "no ejecutado"


# --- propiedades ---


@given(evidence_sets(), story_maps())
def test_an_element_without_evidence_is_no_ejecutado(data, mapping) -> None:  # type: ignore[no-untyped-def]
    evidences, declared, observed = data
    rep = report.build(evidences, declared, observed, mapping)
    with_evidence = {e.id for e in evidences}
    for element in ELEMENT_IDS:
        if element not in with_evidence:
            assert row(rep, element).result == "no ejecutado" and row(rep, element).evidence == ()


@given(evidence_sets(), story_maps())
def test_expected_different_from_obtained_is_falla_even_if_result_says_pasa(data, mapping) -> None:  # type: ignore[no-untyped-def]
    evidences, declared, observed = data
    rep = report.build(evidences, declared, observed, mapping)
    for e in evidences:
        intact_hash = (
            e.output in declared and e.output in observed and declared[e.output] == observed[e.output]
        )
        if intact_hash and e.expected != e.obtained:
            assert row(rep, e.id).result == "falla"


@given(evidence_sets(), story_maps())
def test_no_element_is_pasa_without_an_evidence_that_backs_it(data, mapping) -> None:  # type: ignore[no-untyped-def]
    evidences, declared, observed = data
    rep = report.build(evidences, declared, observed, mapping)
    for r in rep.rows:
        if r.kind == "elemento" and r.result == "pasa":
            backing = [e for e in evidences if e.id == r.id]
            assert backing
            for e in backing:
                assert (
                    e.output in declared and e.output in observed and declared[e.output] == observed[e.output]
                )
                assert e.expected == e.obtained and e.result == "pasa"


@given(evidence_sets(), story_maps())
def test_each_element_follows_br_u12_11_with_duplicates_as_the_worst_case(data, mapping) -> None:  # type: ignore[no-untyped-def]
    evidences, declared, observed = data
    rep = report.build(evidences, declared, observed, mapping)
    for element in ELEMENT_IDS:
        assert row(rep, element).result == oracle_element(
            [e for e in evidences if e.id == element], declared, observed
        )


@given(evidence_sets(), story_maps())
def test_a_story_is_pasa_only_if_all_its_evidences_pass_falla_if_any_fails(data, mapping) -> None:  # type: ignore[no-untyped-def]
    evidences, declared, observed = data
    rep = report.build(evidences, declared, observed, mapping)
    element_results = {r.id: r.result for r in rep.rows if r.kind == "elemento"}
    for story, definition in mapping.items():
        found = row(rep, story)
        assert found.result == oracle_story(definition.evidence, element_results)
        assert found.evidence == definition.evidence
        if found.result == "pasa":
            assert all(element_results[r] == "pasa" for r in definition.evidence)
        if any(element_results[r] == "falla" for r in definition.evidence):
            assert found.result == "falla"


@given(evidence_sets(), story_maps())
def test_one_row_per_element_and_per_story(data, mapping) -> None:  # type: ignore[no-untyped-def]
    evidences, declared, observed = data
    rep = report.build(evidences, declared, observed, mapping)
    assert [r.id for r in rep.rows] == [*ELEMENT_IDS, *mapping]
    assert all(
        r.kind == ("demostrada" if mapping[r.id].demonstrated else "historia")
        for r in rep.rows[len(ELEMENT_IDS) :]
    )
    assert report.render(rep).count("\n") >= len(rep.rows)


@given(evidence_sets())
def test_a_story_without_required_evidences_is_never_pasa(data) -> None:  # type: ignore[no-untyped-def]
    evidences, declared, observed = data
    rep = report.build(evidences, declared, observed, {"US-900": StoryRow(())})
    assert row(rep, "US-900").result == "no ejecutado"


# --- ejemplos de business-logic-model §3 ---


def test_without_any_evidence_there_are_41_rows_all_no_ejecutado() -> None:
    rep = report.build([], {}, {}, REAL_MAP)
    assert len(rep.rows) == 41 == len(ELEMENT_IDS) + len(REAL_MAP) == 26 + 15
    assert {r.result for r in rep.rows} == {"no ejecutado"}
    assert not [r for r in rep.rows if r.result == "pasa"]


def test_x07_without_evidence_is_no_ejecutado_while_others_pass() -> None:
    evidences = [make("X06")]
    declared, observed = intact(evidences)
    rep = report.build(evidences, declared, observed, REAL_MAP)
    assert row(rep, "X07").result == "no ejecutado" and row(rep, "X06").result == "pasa"


def test_us_111_with_rt3_pasa_and_journey_7_3_without_evidence_is_no_ejecutado() -> None:
    evidences = [make("RT-3")]
    declared, observed = intact(evidences)
    rep = report.build(evidences, declared, observed, REAL_MAP)
    assert row(rep, "RT-3").result == "pasa" and row(rep, "US-111").result == "no ejecutado"
    both = [make("RT-3"), make("journey-7-3")]
    declared, observed = intact(both)
    assert row(report.build(both, declared, observed, REAL_MAP), "US-111").result == "pasa"


def test_rt2_run_of_31_minutes_fails_rt2_latency_and_us_303_and_the_measurement_is_recorded() -> None:
    first = T0
    measurement = rt2_latency.measure(1, [first + timedelta(seconds=5), first], first + timedelta(minutes=31))
    assert measurement.passed is False and measurement.latency_seconds == 1860.0
    latency = make(
        "RT2-LATENCY",
        expected="latency_seconds <= 1800",
        obtained=f"latency_seconds = {measurement.latency_seconds}",
        result="pasa" if measurement.passed else "falla",
    )
    others = [make("RT-2"), make("journey-7-4")]
    evidences = [latency, *others]
    declared, observed = intact(evidences)
    rep = report.build(evidences, declared, observed, REAL_MAP)
    assert row(rep, "RT2-LATENCY").result == "falla" and row(rep, "US-303").result == "falla"
    assert row(rep, "RT-2").result == "pasa"
    assert row(rep, "RT2-LATENCY").evidence == ("RT2-LATENCY-0.txt",)
    assert "1860.0" in latency.obtained


def test_a_changed_byte_in_an_evidence_leaves_its_element_no_ejecutado() -> None:
    evidences = [make("RT-5"), make("X01"), make("rt-5")]
    declared, observed = intact(evidences)
    observed["X01-0.txt"] = sha("X01-0.txt" + "\x00")
    rep = report.build(evidences, declared, observed, REAL_MAP)
    assert row(rep, "X01").result == "no ejecutado"
    assert row(rep, "RT-5").result == "pasa" and row(rep, "US-603").result == "no ejecutado"


def test_a_missing_hash_in_the_manifest_or_on_disk_is_no_ejecutado() -> None:
    evidences = [make("X01"), make("X02")]
    declared, observed = intact(evidences)
    del declared["X01-0.txt"]
    del observed["X02-0.txt"]
    rep = report.build(evidences, declared, observed, REAL_MAP)
    assert row(rep, "X01").result == "no ejecutado" and row(rep, "X02").result == "no ejecutado"


def test_a_result_falla_with_expected_equal_obtained_is_falla_and_a_bad_hash_hides_the_contradiction() -> (
    None
):
    evidences = [make("X05", result="falla"), make("X06", expected="a", obtained="b")]
    declared, observed = intact(evidences)
    rep = report.build(evidences, declared, observed, REAL_MAP)
    assert row(rep, "X05").result == "falla" and row(rep, "X06").result == "falla"
    observed["X06-0.txt"] = "otro"
    assert row(report.build(evidences, declared, observed, REAL_MAP), "X06").result == "no ejecutado"


def test_duplicates_the_worst_wins_p1() -> None:
    passing, failing = make("RT-1", 0, minutes=0), make("RT-1", 1, result="falla", minutes=5)
    declared, observed = intact([passing, failing])
    assert row(report.build([passing, failing], declared, observed, REAL_MAP), "RT-1").result == "falla"
    assert row(report.build([failing, passing], declared, observed, REAL_MAP), "RT-1").result == "falla"
    observed[passing.output] = "otro"
    broken = report.build([passing, failing], declared, observed, REAL_MAP)
    assert row(broken, "RT-1").result == "falla"  # una falla integra gana sobre un hash roto
    observed[failing.output] = "otro"
    assert (
        row(report.build([passing, failing], declared, observed, REAL_MAP), "RT-1").result == "no ejecutado"
    )


def test_the_row_carries_commit_images_and_the_date_of_the_latest_evidence() -> None:
    older = make("RT-4", 0, minutes=0)
    newer = Evidence(
        **{
            **older.__dict__,
            "output": "RT-4-1.txt",
            "commit": "def5678",
            "executed_at": T0 + timedelta(hours=1),
        }
    )
    declared, observed = intact([older, newer])
    rep = report.build([newer, older], declared, observed, REAL_MAP)
    found = row(rep, "RT-4")
    assert (found.commit, found.date) == ("def5678", T0 + timedelta(hours=1)) and found.images == older.images
    story = row(rep, "US-106")
    assert (story.commit, story.date, story.evidence) == ("def5678", T0 + timedelta(hours=1), ("RT-4",))
    assert row(rep, "RT-1").commit == "" and row(rep, "RT-1").date is None and row(rep, "RT-1").images == {}


def test_demo_stories_are_demostrada_and_never_pasa_without_evidence() -> None:
    rep = report.build([], {}, {}, REAL_MAP)
    demos = [r for r in rep.rows if r.kind == "demostrada"]
    assert [r.id for r in demos] == ["US-304", "US-503", "US-504", "US-505"]
    assert {r.result for r in demos} == {"no ejecutado"}
    evidences = [make("dashboard")]
    declared, observed = intact(evidences)
    rep = report.build(evidences, declared, observed, REAL_MAP)
    assert (row(rep, "US-503").kind, row(rep, "US-503").result) == ("demostrada", "pasa")
    assert (row(rep, "US-304").kind, row(rep, "US-304").result) == ("demostrada", "no ejecutado")


def test_the_report_header_states_the_manifest_limit() -> None:
    text = report.render(report.build([], {}, {}, REAL_MAP))
    assert report.MANIFEST_LIMIT in text
    assert "no a quien edite la evidencia y el manifiesto a la vez" in text
    assert "CODEOWNERS" in text and "alteraciones accidentales y archivos faltantes" in text
    assert text.index("alteraciones accidentales") < text.index("| Elemento |")


def test_render_lists_every_row_with_its_result_and_escapes_the_separator() -> None:
    evidence = make("RT-1", 0)
    evidence = Evidence(**{**evidence.__dict__, "commit": "a|b"})
    declared, observed = intact([evidence])
    text = report.render(report.build([evidence], declared, observed, REAL_MAP))
    lines = [line for line in text.splitlines() if line.startswith("| ")]
    assert len(lines) == 41 + 1  # filas y encabezado de la tabla
    assert "| RT-1 | elemento | pasa | [RT-1-0.txt](RT-1-0.txt) | a\\|b |" in text
    assert "| US-109 | historia | pasa | RT-1 |" in text
    assert "| X07 | elemento | no ejecutado | - | - | - | - |" in text
    assert "case-service=sha256:" in text and "2026-11-12T10:00:00+00:00" in text


def test_an_evidence_with_an_unknown_id_or_result_is_refused() -> None:
    import pytest

    base = make("RT-1")
    with pytest.raises(ValueError, match="evidence_id_unknown:US-609"):
        Evidence(**{**base.__dict__, "id": "US-609"})
    with pytest.raises(ValueError, match="evidence_result_unknown"):
        Evidence(**{**base.__dict__, "result": "no ejecutado"})
