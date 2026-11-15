"""El inventario unico de kind y las plantillas de evidencia (U12-T06, CA-4 y CA-7).

El inventario (`docs/kind/inventario.yaml`) es la lista de lo que solo se puede comprobar en kind. Esta prueba lo ata a las fuentes de las que sale (los cierres de las
unidades, `CANDIDATAS.md`) y a la guia, a las plantillas y a `cierre-demo.md`, que salen de el. No demuestra que algo funcione en kind: demuestra que nada se perdio ni se inventó.
"""

from __future__ import annotations

import re
from typing import Any

import kind_docs as kd
import pytest
import yaml

K_ID = re.compile(r"^K-(\d{2})$")
READ_PREFIXES = (
    "kubectl --context kind-vectra get ",
    "kubectl --context kind-vectra logs ",
    "kubectl --context kind-vectra auth can-i ",
    "kubectl --context kind-vectra port-forward ",
    "free ", "docker stats ", "git log ", "grep ", "ls ", "date ", "make -C case-management policy-chart",
)  # fmt: skip
PENDING_SECTIONS = {
    "aidlc-docs/construction/decision-registry/evidence/cierre-demo.md": "Pendiente en U12",
    "aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md": "Pendiente en U12",
    "aidlc-docs/construction/case-management/evidence/cierre-demo.md": "Pendiente en U12",
    "aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md": "Pendiente en U12",
    "aidlc-docs/construction/console/evidence/cierre-demo.md": "Pendiente en U12",
    "aidlc-docs/construction/product-metrics/evidence/cierre-demo.md": "Pendiente en U12",
}
ACOTADO = "aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md"
MIN_ENTRIES = 66


def covered(data: dict[str, Any]) -> set[tuple[str, int]]:
    abbreviations = data["abreviaturas"]
    return {
        (s.path, n)
        for entry in data["entradas"]
        for s in kd.sources(entry, abbreviations)
        for n in range(s.first, s.last + 1)
    }


def problems(data: dict[str, Any]) -> list[str]:
    """Lo que esta mal en un inventario: identificadores, campos, fuentes, comprobaciones y cobertura de las fuentes que debe reunir."""
    found: list[str] = []
    abbreviations = data["abreviaturas"]
    listed = data["entradas"]
    ids = [e["id"] for e in listed]
    if len(ids) != len(set(ids)):
        found.append("identificadores repetidos")
    numbers = sorted(int(m.group(1)) for i in ids if (m := K_ID.match(i)))
    if numbers != list(range(1, len(ids) + 1)):
        found.append(f"los identificadores no son K-01..K-{len(ids):02d} seguidos")
    if len(ids) < MIN_ENTRIES:
        found.append(f"hay {len(ids)} entradas y el minimo es {MIN_ENTRIES}")
    for entry in listed:
        name = entry.get("id", "?")
        for field in ("id", "fase", "que", "fuentes", "comprobacion", "plantilla", "demo"):
            if field not in entry or entry[field] in (None, "") and field != "demo":
                found.append(f"{name}: falta `{field}`")
        if entry.get("fase") not in kd.PHASES + ("F11",):
            found.append(f"{name}: fase `{entry.get('fase')}` desconocida")
        if not entry.get("fuentes"):
            found.append(f"{name}: sin fuentes")
        for source in kd.sources(entry, abbreviations) if entry.get("fuentes") else []:
            if not (kd.VECTRA / source.path).is_file():
                found.append(f"{name}: la fuente {source.path} no existe")
            elif not 1 <= source.first <= source.last <= kd.line_count(source.path):
                found.append(f"{name}: la linea {source.first}-{source.last} cae fuera de {source.path}")
        found += check_checks(entry)
        if not set(entry.get("demo") or []) <= {"Base", "D1", "D2", "D3", "D4"}:
            found.append(f"{name}: demo `{entry.get('demo')}` desconocida")
        if not (kd.TEMPLATES / str(entry.get("plantilla"))).is_file():
            found.append(f"{name}: la plantilla {entry.get('plantilla')} no existe")
    have = covered(data)
    for path, heading in PENDING_SECTIONS.items():
        for number in kd.section_lines(path, heading):
            if (path, number) not in have:
                found.append(f"sin entrada: {path}:{number} («{heading}»)")
    for number in kd.acotado_rows_for_u12():
        if (ACOTADO, number) not in have:
            found.append(f"sin entrada: {ACOTADO}:{number} (destino U12)")
    for number in kd.task_candidate_lines():
        if ("CANDIDATAS.md", number) not in have:
            found.append(f"sin entrada: CANDIDATAS.md:{number} («Se atienden aqui»)")
    return found


def check_checks(entry: dict[str, Any]) -> list[str]:
    name = entry.get("id", "?")
    found: list[str] = []
    real = [c for c in entry.get("comprobacion") or [] if not str(c).startswith("manual:")]
    if not real:
        return [f"{name}: sin comprobacion que no sea manual"]
    for check in real:
        kind, _, value = str(check).partition(":")
        if kind == "guion":
            script = value.split()[0]
            if not (kd.KIND_DOCS / script).is_file():
                found.append(f"{name}: el guion {script} no existe en docs/kind")
        elif kind == "seccion":
            if value in kd.DEFERRED_SECTIONS:
                found.append(f"{name}: comprueba con la seccion diferida {value}")
            elif value not in kd.CLI_SECTIONS:
                found.append(f"{name}: la seccion {value} no es de la CLI")
        elif kind == "verify":
            if not (kd.SYSTEM / "demos/verify" / value).is_file():
                found.append(f"{name}: el verify {value} no existe")
        elif kind == "lectura":
            if not value.startswith(READ_PREFIXES):
                found.append(f"{name}: la lectura `{value}` no es de solo lectura")
        else:
            found.append(f"{name}: comprobacion `{check}` de un tipo desconocido")
    return found


@pytest.fixture(scope="module")
def inventory() -> dict[str, Any]:
    return kd.load_inventory()


def test_the_inventory_has_no_problems(inventory: dict[str, Any]) -> None:
    assert problems(inventory) == []


def test_the_inventory_counts_what_the_task_says(inventory: dict[str, Any]) -> None:
    listed = inventory["entradas"]
    assert len(listed) == 66
    counts = {tag: sum(tag in e["demo"] for e in listed) for tag in ("Base", "D1", "D2", "D3", "D4")}
    counts["ninguna"] = sum(not e["demo"] for e in listed)
    assert counts == {"Base": 29, "D1": 10, "D2": 16, "D3": 9, "D4": 9, "ninguna": 3}


def test_red_the_source_that_the_u11_closing_needs_cannot_be_dropped(inventory: dict[str, Any]) -> None:
    """Rojo de CA-4: quitar C-U11:54 (el orden de arranque de la wave 5) hace fallar la prueba y dice cual."""
    mutated = yaml.safe_load(yaml.safe_dump(inventory))
    for entry in mutated["entradas"]:
        entry["fuentes"] = [s for s in entry["fuentes"] if s != "C-U11:54"]
    assert any("product-metrics/evidence/cierre-demo.md:54" in p for p in problems(mutated))


def test_red_an_entry_without_a_check_fails(inventory: dict[str, Any]) -> None:
    mutated = yaml.safe_load(yaml.safe_dump(inventory))
    mutated["entradas"][5]["comprobacion"] = ["manual:mirar"]
    assert any("sin comprobacion" in p for p in problems(mutated))


def test_red_a_line_outside_the_file_a_deferred_section_and_a_write_command_fail(
    inventory: dict[str, Any],
) -> None:
    mutated = yaml.safe_load(yaml.safe_dump(inventory))
    mutated["entradas"][0]["fuentes"].append("INST:9999")
    mutated["entradas"][1]["comprobacion"].append("seccion:network")
    mutated["entradas"][2]["comprobacion"].append("lectura:kubectl --context kind-vectra delete pod x")
    mutated["entradas"][3]["id"] = "K-01"
    found = problems(mutated)
    assert any("cae fuera" in p for p in found)
    assert any("seccion diferida network" in p for p in found)
    assert any("no es de solo lectura" in p for p in found)
    assert any("repetidos" in p for p in found)


def test_the_candidate_lines_of_the_task_are_read(inventory: dict[str, Any]) -> None:
    assert {701, 288, 484, 640, 673, 678, 647, 671, 719, 712, 715, 254, 641} <= set(kd.task_candidate_lines())


# --- la guia, las plantillas y cierre-demo salen del inventario -------------------------------------------------------------------------------------------


def test_every_entry_is_in_the_guide_in_one_template_and_in_the_closing_table(
    inventory: dict[str, Any],
) -> None:
    guide = kd.GUIDE.read_text(encoding="utf-8")
    closing = kd.CLOSURE.read_text(encoding="utf-8")
    templates = {p.name: p.read_text(encoding="utf-8") for p in sorted(kd.TEMPLATES.glob("*.md"))}
    missing: list[str] = []
    for entry in inventory["entradas"]:
        ident = entry["id"]
        if not re.search(rf"\b{ident}\b", guide):
            missing.append(f"{ident}: no esta en la guia")
        if len(re.findall(rf"^\| {ident} \|", closing, re.M)) != 1:
            missing.append(f"{ident}: no esta una sola vez en la tabla de cierre-demo.md")
        homes = [n for n, text in templates.items() if re.search(rf"^### {ident}\b", text, re.M)]
        if homes != [entry["plantilla"]]:
            missing.append(f"{ident}: esta en {homes} y debia estar solo en {entry['plantilla']}")
    assert missing == []


EXPECTED_TEMPLATES = (
    "00-prerrequisitos.md", "01-imagenes.md", "02-sync-y-arranque.md", "03-identidad-y-acceso.md", "04-flujo-base.md", "05-prepare-y-d3.md",
    "06-decisions-d4.md", "07-d1-rt3.md", "08-d2-rt2.md", "09-d4-u11-y-grafana.md", "10-informe-y-estado-final.md", "11-opcionales.md",
    "12-duraciones-y-memoria.md",
)  # fmt: skip


def test_templates_are_the_thirteen_and_all_say_pending(inventory: dict[str, Any]) -> None:
    names = sorted(p.name for p in kd.TEMPLATES.glob("*.md"))
    assert names == list(EXPECTED_TEMPLATES)
    not_pending = [
        n
        for n in names
        if "Estado: pendiente del operador" not in (kd.TEMPLATES / n).read_text(encoding="utf-8")
    ]
    assert not_pending == []


def template_findings(name: str, text: str, entries_here: list[dict[str, Any]]) -> list[str]:
    """Lo que le falta a una plantilla del formato de governance (`03-arranque-politica.md`) y todo lo que ya trae un valor donde debe decir _pendiente_."""
    found: list[str] = []
    for label in ("Guía y fase", "Fecha", "Operador", "Commit", "## Hallazgos"):
        if label not in text:
            found.append(f"{name}: falta «{label}»")
    if "unidad" not in text.split("## Hallazgos", 1)[-1]:
        found.append(f"{name}: «Hallazgos» no dice a que unidad apunta cada uno")
    for label in ("Fecha", "Operador", "Commit de `main` desplegado"):
        if re.search(rf"^- {label}: (?!_pendiente_)", text, re.M):
            found.append(f"{name}: «{label}» ya trae un valor")
    for entry in entries_here:
        block = re.search(rf"^### {entry['id']}\b(.*?)(?=^### |^## |\Z)", text, re.M | re.S)
        if block is None:
            found.append(f"{entry['id']}: no esta en {name}")
            continue
        body = block.group(1)
        for label in ("Resultado esperado", "Comando", "Salida", "| Esperado | Obtenido | Cumple |"):
            if label not in body:
                found.append(f"{entry['id']}: falta «{label}»")
        if re.search(r"^\| .* \| _pendiente_ \| _pendiente_ \|$", body, re.M) is None:
            found.append(f"{entry['id']}: «Obtenido» y «Cumple» no dicen _pendiente_")
        for fenced in re.findall(r"```(?:bash|text)\n(.*?)\n```", body, re.S):
            if not fenced.startswith("_pendiente"):
                found.append(f"{entry['id']}: un comando o una salida ya escrita ({fenced[:30]!r})")
    return found


def test_templates_have_the_fields_of_the_governance_format_and_no_invented_output(
    inventory: dict[str, Any],
) -> None:
    found: list[str] = []
    for name in EXPECTED_TEMPLATES:
        text = (kd.TEMPLATES / name).read_text(encoding="utf-8")
        found += template_findings(name, text, [e for e in inventory["entradas"] if e["plantilla"] == name])
    assert found == []


def test_red_a_template_with_an_invented_output_a_missing_row_or_a_filled_header_fails(
    inventory: dict[str, Any],
) -> None:
    """Rojo de CA-7: «Obtenido» con un valor, una salida ya escrita, un campo sin la tabla y la fecha ya llena hacen fallar `template_findings`."""
    entries_here = [e for e in inventory["entradas"] if e["plantilla"] == "04-flujo-base.md"]
    text = (kd.TEMPLATES / "04-flujo-base.md").read_text(encoding="utf-8")
    assert template_findings("04", text, entries_here) == []
    invented = text.replace("| _pendiente_ | _pendiente_ |", "| listo | si |", 1)
    assert any("«Obtenido» y «Cumple»" in f for f in template_findings("04", invented, entries_here))
    printed = text.replace("_pendiente: la salida real, sin tokens_", "caso listo 200", 1)
    assert any("ya escrita" in f for f in template_findings("04", printed, entries_here))
    no_table = text.replace("| Esperado | Obtenido | Cumple |", "", 1)
    assert any(
        "falta «| Esperado | Obtenido | Cumple |»" in f
        for f in template_findings("04", no_table, entries_here)
    )
    dated = text.replace("- Fecha: _pendiente_.", "- Fecha: 2026-11-14.", 1)
    assert any("«Fecha» ya trae un valor" in f for f in template_findings("04", dated, entries_here))


def test_humo_flujo_always_carries_the_delivery_in_the_inventory_and_its_copies() -> None:
    """F-06: `humo flujo` sin `--delivery` usa una ruta relativa que no existe en la imagen (código 2); el inventario y las 13 plantillas lo llevan siempre."""
    delivery = "--delivery /verification/reference-model/.out"
    texts = {"inventario.yaml": kd.INVENTORY.read_text(encoding="utf-8")}
    texts |= {p.name: p.read_text(encoding="utf-8") for p in sorted(kd.TEMPLATES.glob("*.md"))}
    bare = [
        f"{name}: {m.group(0)}"
        for name, text in texts.items()
        for m in re.finditer(rf"humo(?:\.py)? flujo(?! {re.escape(delivery)})", text)
    ]
    assert bare == []
    assert any("humo.py flujo " + delivery in text for text in texts.values())
