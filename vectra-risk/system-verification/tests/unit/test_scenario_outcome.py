"""CA-3 (U12-T03): el resultado de tres valores, «que falto» y la conversion a `report.Evidence` (BR-U12-11; NFR-U12-42)."""

from datetime import UTC, datetime

import pytest
from vectra_verification import report
from vectra_verification.scenarios import outcome as o

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=UTC)


def ok(outcome_id: str = "RT-5") -> o.Outcome:
    return o.Outcome(outcome_id, "pasa", "E", "E")


def bad(result: str, outcome_id: str = "RT-5") -> o.Outcome:
    return o.Outcome(outcome_id, result, "E", "O", ("codigo_estable",))  # type: ignore[arg-type]


def evidence(outcome: o.Outcome) -> report.Evidence | None:
    return o.to_evidence(outcome, command="c", output="out.txt", commit="abc", images={}, executed_at=NOW, operator="op")


def test_pasa_with_missing_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="pasa_with_missing"):
        o.Outcome("RT-5", "pasa", "E", "E", ("algo",))


@pytest.mark.parametrize("result", ["falla", "no ejecutado"])
def test_falla_and_no_ejecutado_need_missing(result: str) -> None:
    with pytest.raises(ValueError, match="without_missing"):
        o.Outcome("RT-5", result, "E", "O")  # type: ignore[arg-type]


def test_unknown_result_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="result_unknown"):
        o.Outcome("RT-5", "quizas", "E", "O", ("x",))  # type: ignore[arg-type]


def test_expected_equals_obtained_if_and_only_if_pasa() -> None:
    with pytest.raises(ValueError, match="expected_obtained_mismatch"):
        o.Outcome("RT-5", "pasa", "E", "otra cosa")
    with pytest.raises(ValueError, match="expected_obtained_mismatch"):
        o.Outcome("RT-5", "falla", "E", "E", ("x",))


@pytest.mark.parametrize("outcome_id", ["RT-2", "RT2-LATENCY", "RT-3", "RT-5", "SIM-NORMAL"])
def test_conversion_pasa_and_falla_give_a_valid_evidence_with_the_right_id(outcome_id: str) -> None:
    passed, failed = evidence(ok(outcome_id)), evidence(bad("falla", outcome_id))
    assert passed is not None and passed.id == outcome_id and passed.result == "pasa"
    assert failed is not None and failed.id == outcome_id and failed.result == "falla"
    assert failed.expected != failed.obtained


def test_conversion_no_ejecutado_gives_no_evidence() -> None:
    assert evidence(bad("no ejecutado")) is None


def test_report_marks_no_ejecutado_without_evidence_and_falla_with_a_mismatch() -> None:
    missing = report.build([], {}, {}, {})
    assert next(r for r in missing.rows if r.id == "RT-5").result == "no ejecutado"
    failed = evidence(bad("falla"))
    assert failed is not None
    built = report.build([failed], {"out.txt": "h"}, {"out.txt": "h"}, {})
    assert next(r for r in built.rows if r.id == "RT-5").result == "falla"
    passed = evidence(ok())
    assert passed is not None
    built = report.build([passed], {"out.txt": "h"}, {"out.txt": "h"}, {})
    assert next(r for r in built.rows if r.id == "RT-5").result == "pasa"


def sub(name: str, result: str, mandatory: bool = True) -> o.SubOutcome:
    return o.SubOutcome(name, result, () if result == "pasa" else (f"{name}_codigo",), mandatory=mandatory)  # type: ignore[arg-type]


def test_combine_a_mandatory_falla_gives_falla() -> None:
    assert o.combine([sub("a", "pasa"), sub("b", "falla")]) == ("falla", ("b_codigo",))


def test_combine_a_mandatory_no_ejecutado_without_falla_gives_no_ejecutado() -> None:
    assert o.combine([sub("a", "pasa"), sub("b", "no ejecutado")]) == ("no ejecutado", ("b_codigo",))
    assert o.combine([sub("a", "falla"), sub("b", "no ejecutado")])[0] == "falla"


def test_combine_an_optional_no_ejecutado_does_not_lower_the_result() -> None:
    assert o.combine([sub("a", "pasa"), sub("b", "no ejecutado", mandatory=False)]) == ("pasa", ())


def test_combine_an_optional_falla_lowers_the_result() -> None:
    assert o.combine([sub("a", "pasa"), sub("b", "falla", mandatory=False)]) == ("falla", ("b_codigo",))


def test_from_subresults_builds_a_consistent_outcome() -> None:
    passed = o.from_subresults("RT-3", "todo", [sub("a", "pasa")])
    assert passed.result == "pasa" and passed.expected == passed.obtained and passed.missing == ()
    failed = o.from_subresults("RT-3", "todo", [sub("a", "pasa"), sub("b", "falla")])
    assert failed.result == "falla" and failed.missing == ("b_codigo",) and "b=falla" in failed.obtained


def test_to_text_is_json_with_the_subresults_and_no_secret_shaped_value() -> None:
    text = o.to_text(o.from_subresults("RT-3", "todo", [sub("a", "pasa")]))
    assert '"subresults"' in text and '"id": "RT-3"' in text
