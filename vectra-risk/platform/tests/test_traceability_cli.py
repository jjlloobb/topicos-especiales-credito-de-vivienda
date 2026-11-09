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


DEFERRED_LIST = """# Cierre

## Comprobado

| NFR-U9-99 | no es de la lista |

## Diferido por la demo

| Identificador | Paso | Cita | Motivo |
|---|---|---|---|
| NFR-U9-02 | 14 | T2 | alertas |
"""


def unit_with_deferred(tmp_path, monkeypatch, listed: str, code: str = "# NFR-U9-01\n"):
    """Una unidad `demo` con NFR-U9-01 y 02 en su diseno, el codigo `code` y la lista `listed`."""
    design = tmp_path / "construction/demo/nfr-requirements"
    design.mkdir(parents=True)
    (design / "nfr.md").write_text("| NFR-U9-01 | a |\n| NFR-U9-02 | b |\n", encoding="utf-8")
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo/code.py").write_text(code, encoding="utf-8")
    evidence = tmp_path / "construction/demo/evidence"
    evidence.mkdir()
    (evidence / "cierre-demo.md").write_text(listed, encoding="utf-8")
    monkeypatch.setattr(t, "CONSTRUCTION", tmp_path / "construction")
    monkeypatch.setattr(t, "ROOT", tmp_path)
    monkeypatch.setattr(t, "REPO", tmp_path)


def test_un_diferido_de_la_lista_pasa_sin_codigo(tmp_path, monkeypatch):
    unit_with_deferred(tmp_path, monkeypatch, DEFERRED_LIST)
    assert t.check_unit("demo") == []


def test_un_identificador_sin_codigo_y_fuera_de_la_lista_falla(tmp_path, monkeypatch):
    unit_with_deferred(tmp_path, monkeypatch, DEFERRED_LIST.replace("NFR-U9-02 | 14", "NFR-U9-77 | 14"))
    assert t.check_unit("demo") == ["NFR-U9-02: sin trazabilidad"]


def test_la_lista_solo_cuenta_en_su_seccion(tmp_path, monkeypatch):
    unit_with_deferred(tmp_path, monkeypatch, DEFERRED_LIST.replace("## Diferido por la demo", "## Otra seccion"))
    assert t.check_unit("demo") == ["NFR-U9-02: sin trazabilidad"]


def test_un_diferido_que_ya_tiene_codigo_falla(tmp_path, monkeypatch):
    unit_with_deferred(tmp_path, monkeypatch, DEFERRED_LIST, code="# NFR-U9-01 y NFR-U9-02\n")
    assert t.check_unit("demo") == ["NFR-U9-02: esta en «Diferido por la demo» pero ya tiene codigo o prueba: se quita de la lista"]


def test_una_fila_sin_paso_o_sin_cita_falla(tmp_path, monkeypatch):
    unit_with_deferred(tmp_path, monkeypatch, DEFERRED_LIST.replace("| 14 | T2 |", "| 14 |  |"))
    assert t.check_unit("demo") == ["NFR-U9-02: la fila de «Diferido por la demo» no nombra el paso del plan y la cita del recorte"]
