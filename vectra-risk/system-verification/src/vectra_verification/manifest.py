"""El manifiesto de la verificacion (U12-T04, Paso 13; NFR-U12-10, 11, 20, 31; INF-U12-02) y el informe completo.

`manifest.json` lo crea `prepare` (con el `runId` y `started_at`) y no se reinicia nunca: `prepare` se niega si ya existe. Guarda por archivo su SHA-256 (lo que `report.build` compara con lo observado en
disco), el `runId` y el nombre esperado del Job de RT-5, las semillas, `generator_version`, el tamano de `test`, las solicitudes repetidas entre secciones, el `commit`, el operador, por seccion su inicio, su fin
y su estado, las esperas del operador aparte, y los digests **leidos del cluster** al empezar cada seccion que lo toca (nunca en `prepare`). **No lleva** secretos ni datos del solicitante: solo `case_id`,
conteos y posiciones de fila. La escritura es de `store.Store` (el unico escritor).

`render_full` agrega al informe de `report.render` la duracion por seccion y total (con las esperas del operador aparte) y «No ejecutado y por que».
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Final

from vectra_verification import report
from vectra_verification.guard import SECTIONS
from vectra_verification.store import Store, Stored

NAME: Final = "manifest.json"
SCHEMA: Final = 1
RUN_ID_FORMAT: Final = "%Y%m%d-%H%M"
DEFERRED_NOTE: Final = "diferida por la demo"
DEFERRED_CITATION: Final = "enmienda §3 U12, fila «13»: «Secciones prepare, decisions, rt5, rt3, rt2-setup, rt2, u11 y report (sale pii)»; las demas quedan registradas como no ejecutado (BR-U12-11)"
DEFERRED: Final = ("network", "rt1", "rt4", "load", "pii", "resilience")
# Que elemento del informe depende de que seccion diferida (domain-entities §3 y business-logic-model §2.1).
DEFERRED_ELEMENTS: Final = {
    "RT-1": "rt1",
    "RT-4": "rt4",
    "X01": "network",
    "X02": "network",
    "X03": "network",
    "X04": "network",
    "X05": "network",
    "X06": "network",
    "X07": "network",
    "X08": "network",
    "X09": "network",
    "X10": "network",
    "LOGS-NO-PII": "pii",
    "CASE-SIZE": "load",
    "LOAD": "load",
    "RESTORE-DRILL": "resilience",
    "READINESS": "resilience",
}
STATE_RUNNING: Final = "en curso"
STATE_DONE: Final = "terminada"
STATE_INTERRUPTED: Final = "interrumpida"
STATE_DEFERRED: Final = DEFERRED_NOTE


class ManifestError(Exception):
    """El manifiesto no se puede leer o no tiene la forma esperada; el mensaje empieza por un codigo estable."""


def run_id_from(started_at: datetime) -> str:
    """`AAAAMMDD-HHMM` de `started_at` en UTC, truncado al minuto (lo que exige `rebuild-runid-check` de U3 y la plantilla de U8)."""
    if started_at.utcoffset() is None:
        raise ManifestError("started_at_without_timezone")
    return started_at.astimezone(UTC).strftime(RUN_ID_FORMAT)


def expected_job(run_id: str) -> str:
    return f"rt5-demo-{run_id}"


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


class Manifest:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    @classmethod
    def new(cls, *, started_at: datetime, commit: str, operator: str, environment: str) -> Manifest:
        run_id = run_id_from(started_at)
        return cls(
            {
                "schema": SCHEMA,
                "started_at": iso(started_at),
                "run_id": run_id,
                "expected_jobs": [expected_job(run_id)],
                "commit": commit,
                "operator": operator,
                "environment": environment,
                "generator_version": None,
                "test_rows": None,
                "parquet_sha256": None,
                "seeds": {},
                "decisions": None,
                "sections": {},
                "operator_waits": [],
                "digests": {},
                "rows_sent": {},
                "repeated_requests": [],
                "files": {},
            }
        )

    @classmethod
    def load(cls, store: Store) -> Manifest | None:
        if not store.exists(NAME):
            return None
        try:
            data = json.loads(store.read_text(NAME))
        except ValueError:
            raise ManifestError("manifest_not_json") from None
        if not isinstance(data, dict) or data.get("schema") != SCHEMA or "started_at" not in data:
            raise ManifestError("manifest_shape")
        return cls(data)

    def save(self, store: Store, *, new: bool = False) -> Stored:
        return store.write(NAME, json.dumps(self.data, indent=2, sort_keys=True, ensure_ascii=False), new=new)

    # --- campos simples ----------------------------------------------------------------------------------------------------------------
    @property
    def started_at(self) -> datetime:
        return parse_iso(str(self.data["started_at"]))

    @property
    def run_id(self) -> str:
        return str(self.data["run_id"])

    @property
    def commit(self) -> str:
        return str(self.data["commit"])

    @property
    def operator(self) -> str:
        return str(self.data["operator"])

    @property
    def sections(self) -> dict[str, dict[str, Any]]:
        sections: dict[str, dict[str, Any]] = self.data["sections"]
        return sections

    def set_seed(self, section: str, seed: int) -> None:
        self.data["seeds"][section] = seed

    def set_population(self, generator_version: str, test_rows: int, parquet_sha256: str) -> None:
        self.data["generator_version"] = generator_version
        self.data["test_rows"] = test_rows
        self.data["parquet_sha256"] = parquet_sha256

    def set_decisions(self, sent: int, accepted: int, decided: int) -> None:
        self.data["decisions"] = {"sent": sent, "accepted": accepted, "decided": decided}

    def set_digests(self, section: str, digests: Mapping[str, str]) -> None:
        self.data["digests"][section] = dict(sorted(digests.items()))

    def digests_of(self, section: str) -> dict[str, str]:
        found: dict[str, str] = self.data["digests"].get(section, {})
        return found

    def set_file(self, name: str, sha256: str) -> None:
        self.data["files"][name] = sha256

    @property
    def files(self) -> dict[str, str]:
        files: dict[str, str] = self.data["files"]
        return files

    # --- secciones y tiempos (NFR-U12-31) ------------------------------------------------------------------------------------------------
    def start_section(self, name: str, now: datetime) -> None:
        previous = self.sections.get(name, {})
        self.sections[name] = {
            "state": STATE_RUNNING,
            "started_at": previous.get("started_at") or iso(now),
            "finished_at": None,
            "result": None,
            "exit_code": None,
            "note": "",
            "pending": previous.get("pending"),
            "seconds": previous.get("seconds", 0.0),
            "resumed_at": iso(now),
        }

    def finish_section(
        self,
        name: str,
        now: datetime,
        *,
        result: str,
        exit_code: int,
        note: str = "",
        pending: str | None = None,
    ) -> None:
        record = self.sections[name]
        record["seconds"] = float(record["seconds"]) + (now - parse_iso(record["resumed_at"])).total_seconds()
        record.update(
            state=STATE_INTERRUPTED if pending is not None else STATE_DONE,
            finished_at=iso(now),
            result=result,
            exit_code=exit_code,
            note=note,
            pending=pending,
        )

    def interrupt_section(self, name: str, now: datetime, note: str) -> None:
        """Una seccion que se corto sin resultado (una excepcion): queda `interrumpida` para retomarla."""
        record = self.sections[name]
        record["seconds"] = float(record["seconds"]) + (now - parse_iso(record["resumed_at"])).total_seconds()
        record.update(state=STATE_INTERRUPTED, finished_at=iso(now), note=note)

    def defer_section(self, name: str, now: datetime) -> None:
        self.sections[name] = {
            "state": STATE_DEFERRED,
            "started_at": iso(now),
            "finished_at": iso(now),
            "result": report.NO_EJECUTADO,
            "exit_code": 2,
            "note": f"{DEFERRED_NOTE}: {DEFERRED_CITATION}",
            "pending": None,
            "seconds": 0.0,
            "resumed_at": iso(now),
        }

    def is_done(self, name: str) -> bool:
        return self.sections.get(name, {}).get("state") == STATE_DONE

    def pending_of(self, name: str) -> str | None:
        pending = self.sections.get(name, {}).get("pending")
        return str(pending) if pending else None

    def add_wait(self, name: str, started_at: datetime, finished_at: datetime) -> None:
        """Una espera del operador (un PR que se fusiona y se sincroniza): aparte del tiempo de las secciones."""
        self.data["operator_waits"].append(
            {
                "name": name,
                "started_at": iso(started_at),
                "finished_at": iso(finished_at),
                "seconds": (finished_at - started_at).total_seconds(),
            }
        )

    def durations(self) -> tuple[dict[str, float], float, float]:
        """Los segundos por seccion, el total de las secciones y el total de las esperas del operador."""
        per = {name: float(record.get("seconds", 0.0)) for name, record in self.sections.items()}
        waits = sum(float(w["seconds"]) for w in self.data["operator_waits"])
        return per, sum(per.values()), waits

    # --- solicitudes repetidas entre escenarios (NFR-U12-11) -------------------------------------------------------------------------
    def record_rows(self, section: str, positions: Sequence[int]) -> None:
        """Las posiciones de fila de la particion `test` que una seccion envio (ninguna otra cosa de la fila)."""
        merged = set(self.data["rows_sent"].get(section, [])) | {int(p) for p in positions}
        self.data["rows_sent"][section] = sorted(merged)
        by_position: dict[int, list[str]] = defaultdict(list)
        for name, rows in sorted(self.data["rows_sent"].items()):
            for position in rows:
                by_position[position].append(name)
        groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for position, names in sorted(by_position.items()):
            if len(names) > 1:
                groups[tuple(names)].append(position)
        self.data["repeated_requests"] = [
            {"sections": list(names), "count": len(rows), "positions": rows}
            for names, rows in sorted(groups.items())
        ]


def reasons_not_executed(rows: Sequence[report.ReportRow], manifest: Manifest) -> list[tuple[str, str]]:
    """Por cada fila `no ejecutado`, su motivo: una seccion diferida por la demo, una seccion que no se corrio o se interrumpio, o una evidencia que falta o cambio de hash."""
    reasons: list[tuple[str, str]] = []
    sections = manifest.sections
    for row in rows:
        if row.result != report.NO_EJECUTADO:
            continue
        if row.kind == "elemento":
            owner = DEFERRED_ELEMENTS.get(row.id)
            if owner is not None:
                reasons.append(
                    (row.id, f"diferida por la demo: seccion `{owner}` ({DEFERRED_CITATION.split(':')[0]})")
                )
            elif row.evidence:
                reasons.append(
                    (
                        row.id,
                        "la evidencia no es integra: su hash no coincide con el del manifiesto (NFR-U12-20)",
                    )
                )
            else:
                reasons.append((row.id, _section_reason(row.id, sections)))
        else:
            missing = [e for e in row.evidence if e in DEFERRED_ELEMENTS]
            if missing:
                reasons.append(
                    (
                        row.id,
                        "falta la evidencia de " + ", ".join(f"{e} (diferida por la demo)" for e in missing),
                    )
                )
            else:
                reasons.append(
                    (
                        row.id,
                        "falta la evidencia de "
                        + ", ".join(row.evidence)
                        + " (prerrequisito: corra la seccion que la produce)",
                    )
                )
    return reasons


_PRODUCER: Final = {
    "SIM-NORMAL": "decisions",
    "RT-5": "rt5",
    "rt-5": "rt5",
    "RT-3": "rt3",
    "journey-7-3": "rt3",
    "RT-2": "rt2",
    "RT2-LATENCY": "rt2",
    "journey-7-4": "rt2",
    "dashboard": "u11",
}


def _section_reason(element: str, sections: Mapping[str, Mapping[str, Any]]) -> str:
    producer = _PRODUCER.get(element, "?")
    record = sections.get(producer)
    if record is None:
        return f"prerrequisito: la seccion `{producer}` no se corrio"
    note = str(record.get("note") or "")
    return f"prerrequisito: la seccion `{producer}` quedo `{record.get('state')}`" + (
        f" ({note})" if note else ""
    )


def _duration(seconds: float) -> str:
    minutes, rest = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min {rest:02d} s" if hours else f"{minutes} min {rest:02d} s"


def render_full(verification: report.VerificationReport, manifest: Manifest) -> str:
    """El informe: `report.render`, la duracion por seccion y total (con las esperas del operador aparte) y «No ejecutado y por que»."""
    lines = [report.render(verification).rstrip("\n"), "", "## Duración por sección", ""]
    per, total, waits = manifest.durations()
    lines += ["| Sección | Estado | Resultado | Duración |", "|---|---|---|---|"]
    for name in SECTIONS:
        record = manifest.sections.get(name)
        if record is None:
            lines.append(f"| {name} | no se corrió | - | - |")
        else:
            lines.append(
                f"| {name} | {record['state']} | {record.get('result') or '-'} | {_duration(per.get(name, 0.0))} |"
            )
    lines += [
        "",
        f"Total de las secciones: {_duration(total)}.",
        f"Esperas del operador (PR, fusión y sync; aparte): {_duration(waits)}"
        + "".join(f"; {w['name']}: {_duration(float(w['seconds']))}" for w in manifest.data["operator_waits"])
        + ".",
        "",
        "## No ejecutado y por qué",
        "",
    ]
    reasons = reasons_not_executed(verification.rows, manifest)
    if reasons:
        lines += ["| Elemento | Motivo |", "|---|---|"]
        lines += [f"| {name} | {report._cell(reason)} |" for name, reason in reasons]  # noqa: SLF001
    else:
        lines.append("Ninguno.")
    return "\n".join(lines) + "\n"
