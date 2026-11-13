"""Informe de verificacion (U12 Paso 3; BR-U12-11, BR-U12-13; NFR-U12-20, NFR-U12-21). Logica pura: sin E/S.

Recibe en memoria las evidencias, los hashes declarados del manifiesto y los observados; leer archivos y `manifest.json` es de `manifest` y `cli` (Paso 13).

Reglas de una evidencia: sin hash declarado u observado, o con hashes distintos, no es integra y vale `no ejecutado` (NFR-U12-20); si es integra, `expected != obtained`
o `result = falla` valen `falla`; si no, `pasa`. Reglas de un elemento (P-1, recomendacion (a)): gana lo peor: `falla` si alguna de sus evidencias falla; si
ninguna falla y alguna no es integra, `no ejecutado`; `pasa` solo si todas son integras y pasan; sin evidencias, `no ejecutado`. Reglas de una historia (BR-U12-13):
`pasa` si pasan todas las evidencias de su fila del mapa, `falla` si alguna falla y `no ejecutado` en otro caso. Las historias de demos (US-304, 503, 504, 505) se marcan
`demostrada`: el informe no las presenta como verificadas y su resultado no reemplaza el de la unidad dueña.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Literal

PASA: Final = "pasa"
FALLA: Final = "falla"
NO_EJECUTADO: Final = "no ejecutado"

Result = Literal["pasa", "falla", "no ejecutado"]
Kind = Literal["elemento", "historia", "demostrada"]

# Los 26 identificadores de evidencia (domain-entities §3, §4 y §4.1). `US-609` no es uno: su evidencia es `LOAD` (§4.2).
RT_IDS: Final = ("RT-1", "RT-2", "RT-3", "RT-4", "RT-5")
X_IDS: Final = tuple(f"X{n:02d}" for n in range(1, 11))
DEMO_IDS: Final = ("journey-7-3", "journey-7-4", "rt-5", "dashboard")
EXTRA_IDS: Final = (
    "SIM-NORMAL",
    "RT2-LATENCY",
    "LOGS-NO-PII",
    "LOAD",
    "RESTORE-DRILL",
    "READINESS",
    "CASE-SIZE",
)
ELEMENT_IDS: Final = RT_IDS + X_IDS + DEMO_IDS + EXTRA_IDS

# Las historias de domain-entities §4 y las cuatro de demos (§4.2).
STORY_IDS: Final = (
    "US-101", "US-106", "US-109", "US-111", "US-303", "US-305", "US-603", "US-604", "US-608", "US-609", "US-610",
)  # fmt: skip
DEMO_STORY_IDS: Final = ("US-304", "US-503", "US-504", "US-505")

# NFR-U12-21: el informe lo dice en su encabezado.
MANIFEST_LIMIT: Final = (
    "El manifiesto (`manifest.json`) detecta alteraciones accidentales y archivos faltantes, pero no a quien edite la evidencia y el "
    "manifiesto a la vez. Esa protección la da la revisión del PR de verificación, con `CODEOWNERS` del directorio de evidencias."
)


@dataclass(frozen=True)
class Evidence:
    """Una evidencia (domain-entities §3). `output` es el archivo de la salida, tal como lo nombra el manifiesto."""

    id: str
    command: str
    output: str
    expected: str
    obtained: str
    result: Literal["pasa", "falla"]
    commit: str
    images: Mapping[str, str]
    executed_at: datetime
    operator: str

    def __post_init__(self) -> None:
        if self.id not in ELEMENT_IDS:
            raise ValueError(f"evidence_id_unknown:{self.id}")
        if self.result not in (PASA, FALLA):
            raise ValueError(f"evidence_result_unknown:{self.result}")


@dataclass(frozen=True)
class StoryRow:
    """Una fila del mapa historia -> evidencias (domain-entities §4.2)."""

    evidence: tuple[str, ...]
    demonstrated: bool = False


@dataclass(frozen=True)
class ReportRow:
    id: str
    kind: Kind
    result: Result
    evidence: tuple[
        str, ...
    ]  # elemento: los archivos de sus evidencias; historia: los identificadores de su fila del mapa
    commit: str
    images: Mapping[str, str]
    date: datetime | None


@dataclass(frozen=True)
class VerificationReport:
    rows: tuple[ReportRow, ...]
    header: str = field(default=MANIFEST_LIMIT)


def _intact(evidence: Evidence, declared: Mapping[str, str], observed: Mapping[str, str]) -> bool:
    return (
        evidence.output in declared
        and evidence.output in observed
        and declared[evidence.output] == observed[evidence.output]
    )


def _evidence_result(evidence: Evidence, declared: Mapping[str, str], observed: Mapping[str, str]) -> Result:
    if not _intact(evidence, declared, observed):
        return NO_EJECUTADO
    if evidence.expected != evidence.obtained or evidence.result == FALLA:
        return FALLA
    return PASA


def _worst(results: Sequence[Result]) -> Result:
    if FALLA in results:
        return FALLA
    if not results or NO_EJECUTADO in results:
        return NO_EJECUTADO
    return PASA


def _latest(evidences: Sequence[Evidence]) -> Evidence | None:
    latest: Evidence | None = None
    for evidence in evidences:
        if latest is None or evidence.executed_at >= latest.executed_at:
            latest = evidence
    return latest


def build(
    evidences: Sequence[Evidence],
    declared_hashes: Mapping[str, str],
    observed_hashes: Mapping[str, str],
    story_map: Mapping[str, StoryRow],
) -> VerificationReport:
    """El informe: una fila por cada uno de los 26 elementos y por cada historia del mapa (BR-U12-11)."""
    by_id: dict[str, list[Evidence]] = {element: [] for element in ELEMENT_IDS}
    for evidence in evidences:
        by_id[evidence.id].append(evidence)
    element_results: dict[str, Result] = {
        element: _worst([_evidence_result(e, declared_hashes, observed_hashes) for e in found])
        for element, found in by_id.items()
    }
    rows: list[ReportRow] = []
    for element in ELEMENT_IDS:
        latest = _latest(by_id[element])
        rows.append(
            ReportRow(
                id=element,
                kind="elemento",
                result=element_results[element],
                evidence=tuple(e.output for e in by_id[element]),
                commit=latest.commit if latest else "",
                images=dict(latest.images) if latest else {},
                date=latest.executed_at if latest else None,
            )
        )
    for story, row in story_map.items():
        results = [element_results.get(required, NO_EJECUTADO) for required in row.evidence]
        required_evidences = [e for required in row.evidence for e in by_id.get(required, [])]
        latest = _latest(required_evidences)
        rows.append(
            ReportRow(
                id=story,
                kind="demostrada" if row.demonstrated else "historia",
                result=_worst(results),
                evidence=row.evidence,
                commit=latest.commit if latest else "",
                images=dict(latest.images) if latest else {},
                date=latest.executed_at if latest else None,
            )
        )
    return VerificationReport(rows=tuple(rows))


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render(report: VerificationReport) -> str:
    """El Markdown del informe, con el encabezado de NFR-U12-21."""
    lines = [
        "# Informe de verificación",
        "",
        f"> {report.header}",
        "",
        "| Elemento | Tipo | Resultado | Evidencia | Commit | Imágenes | Fecha |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report.rows:
        evidence = (
            ", ".join(row.evidence)
            if row.kind != "elemento"
            else ", ".join(f"[{e}]({e})" for e in row.evidence)
        )
        images = ", ".join(f"{name}={digest}" for name, digest in sorted(row.images.items()))
        date = row.date.isoformat() if row.date else ""
        cells = [row.id, row.kind, row.result, evidence or "-", row.commit or "-", images or "-", date or "-"]
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return "\n".join(lines) + "\n"
