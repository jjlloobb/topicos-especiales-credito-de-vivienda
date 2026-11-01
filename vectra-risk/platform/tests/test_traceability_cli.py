"""`--section` comprueba solo lo que nombra la linea de aceptacion del plan."""

import test_traceability as t


def test_section_expands_lists_and_ranges(tmp_path, monkeypatch):
    plans = tmp_path / "plans"
    plans.mkdir()
    (plans / "demo-code-generation-plan.md").write_text(
        "`x --unit demo --section logic` (BR-U4-01, 02, 05..07)\n`x --unit demo --section api` (BR-U4-09)\n", encoding="utf-8"
    )
    monkeypatch.setattr(t, "CONSTRUCTION", tmp_path)
    assert t.section_identifiers("demo", "logic") == {"BR-U4-01", "BR-U4-02", "BR-U4-05", "BR-U4-06", "BR-U4-07"}
    assert t.section_identifiers("demo", "api") == {"BR-U4-09"}
