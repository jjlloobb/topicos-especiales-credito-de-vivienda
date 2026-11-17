"""Reconciliador y barridos sin lider (P-U4-02; Paso 8). Corren en cada replica; `SKIP LOCKED` evita el trabajo doble.

Cada 10 s (`reconcile_once`):
1. las pendientes de mas de 24 h pasan a `abandonada` y se alerta (`abandon`); nunca un `freeze` ni una compensacion;
2. toma hasta 20 transiciones `pendiente_registro`, **solo la de menor `n` de cada entidad**, y reintenta el append con su
   llave (nunca duplica, BR-U3-06); con el ack confirma y aplica (BR-U4-17). Las `descartada` no se escriben (el orden las
   salta); sus compensaciones `transicion_descartada` si, sin limite de tiempo;
3. los gauges de las alertas: eventos `freeze` pendientes (`FreezeEventPending`), compensaciones pendientes
   (`CompensationEventPending`) y transiciones abandonadas (`GovernanceTransitionAbandoned`).

Cada 60 s (`sweep_validations_once`): las `ValidationRun` `lanzado` en modo `validacion` se leen (hasta
`BATCH`, las de plazo vencido primero: son a lo mas `BATCH` lecturas del API de Kubernetes por barrido y replica); se consulta el Job
(`sweep_verdict`) y la version pasa a `validacion_fallida` por una transicion del sistema (con evidencia, como cualquier otra):
- plazo vencido: con el motivo del Job (`failed`, `deadline`, `sin informe`);
- plazo vigente (U04-T12): solo si el Job ya termino `Failed` (no esperar dos horas a un pod que murio en un minuto) o si el Job no
  existe pasado `MISSING_JOB_GRACE`. Un Job que corre, o `Complete` cuyo informe aun no llego, no se toca: el informe lo envia el propio
  Job por `PUT`; si no llega, la corrida se cierra al vencer el plazo con `sin informe`.
La carrera con el informe (y entre replicas) la resuelve el candado global de la evidencia: `receive_report` y `begin_fail_validation`
exigen la corrida `lanzado` (`_require_run`) ya con el candado; el que llega segundo recibe `ConflictState` y el estado final es el del
primero. El barrido ya no retiene filas con `FOR UPDATE SKIP LOCKED` mientras lee el Job (se cruzaba con el `PUT`: deadlock); a cambio dos
replicas pueden leer el mismo Job (a lo mas `BATCH` lecturas cada una) y solo una cierra la corrida.

**Diferido** (enmienda de recorte, US-306 / Q-6): la rama `source_comparison` del barrido. Esas corridas se ignoran.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from prometheus_client import Gauge
from vectra_common.errors import DependencyUnavailable
from vectra_common.metrics import REGISTRY

from vectra_governance.evidence import ABANDON_AFTER, Evidence, is_freeze
from vectra_governance.k8s_jobs import JobInfo, JobReader, JobReason, reason_of
from vectra_governance.model_fsm import ConflictState

log = logging.getLogger(__name__)

RECONCILE_EVERY: Final = 10.0
SWEEP_EVERY: Final = 60.0
BATCH: Final = 20
# U04-T12: `POST /validations` confirma la corrida (`started_at`) y SOLO DESPUES crea el Job (`api.py`, `begin` y luego `launch`, con un
# timeout de 5 s por llamada a K01, NFR-U4-25): un Job ausente poco despues de `started_at` es lo normal. Cinco minutos = cinco barridos
# de margen sobre esos 5 s; un Job ausente pasado el margen (y antes del plazo de 2 h; el TTL es de 24 h) lo borro alguien.
MISSING_JOB_GRACE: Final = timedelta(minutes=5)

FREEZE_PENDING: Final = Gauge(
    "vectra_governance_freeze_events_pending",
    "Eventos freeze sin escribir en el registro (FreezeEventPending)",
    registry=REGISTRY,
)
COMPENSATION_PENDING: Final = Gauge(
    "vectra_governance_compensation_events_pending",
    "Compensaciones transicion_descartada sin escribir (CompensationEventPending)",
    registry=REGISTRY,
)
ABANDONED: Final = Gauge(
    "vectra_governance_transitions_abandoned",
    "Transiciones en estado abandonada (GovernanceTransitionAbandoned)",
    registry=REGISTRY,
)


def sweep_verdict(info: JobInfo | None, expired: bool, age: timedelta) -> JobReason | None:
    """El motivo con que el barrido cierra la corrida, o `None` si no se toca (U04-T12). `age` es el tiempo desde `started_at`."""
    if expired:
        return reason_of(info)
    if info is None:
        return "sin informe" if age >= MISSING_JOB_GRACE else None
    return reason_of(info) if info.failed else None


@dataclass
class ReconcileReport:
    abandoned: int = 0
    written: int = 0
    unavailable: int = 0
    skipped: int = 0


class Background:
    def __init__(self, evidence: Evidence, jobs: JobReader | None = None) -> None:
        self.evidence = evidence
        self.jobs = jobs
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    @property
    def clock(self) -> Callable[[], datetime]:
        return self.evidence.clock

    # --- reconciliador -----------------------------------------------------------------------------------------------------

    def reconcile_once(self) -> ReconcileReport:
        report = ReconcileReport()
        pool = self.evidence.pools.background
        cutoff = self.clock() - ABANDON_AFTER
        with pool() as conn:
            stale = conn.execute(
                "SELECT * FROM transitions WHERE status = 'pendiente_registro' AND kind = 'cambio_estado' AND created_at < %s",
                (cutoff,),
            ).fetchall()
            conn.rollback()
        for row in stale:
            if is_freeze(row):
                continue
            if self.evidence.abandon(row["transition_id"], pool) in ("abandonada", "descartada"):
                report.abandoned += 1
        with pool() as conn:
            candidates = conn.execute(
                "SELECT transition_id FROM (SELECT DISTINCT ON (entity_type, entity_id) transition_id, created_at "
                "FROM transitions WHERE status = 'pendiente_registro' ORDER BY entity_type, entity_id, transition_number) s "
                "ORDER BY created_at LIMIT %s",
                (BATCH,),
            ).fetchall()
            conn.rollback()
        for candidate in candidates:
            transition_id = candidate["transition_id"]
            try:
                outcome = self.evidence.send(transition_id, pool)
                if outcome == "acked":
                    self.evidence.finish(transition_id, pool)
                    report.written += 1
                elif outcome == "unavailable":
                    report.unavailable += 1
                else:
                    report.skipped += 1
            except ConflictState:
                report.written += 1  # recupero la abandonada (BR-U4-17); la nueva ya quedo rechazada
            except DependencyUnavailable:
                report.unavailable += 1
        self.update_gauges()
        return report

    def update_gauges(self) -> None:
        with self.evidence.pools.background() as conn:
            row = conn.execute(
                "SELECT count(*) FILTER (WHERE status = 'pendiente_registro' AND kind = 'cambio_estado' "
                "AND entity_type = 'model_version' AND from_state = 'activo' AND to_state = 'congelado') AS freeze, "
                "count(*) FILTER (WHERE status = 'pendiente_registro' AND kind = 'compensacion') AS compensation, "
                "count(*) FILTER (WHERE status = 'abandonada') AS abandoned FROM transitions"
            ).fetchone()
            conn.rollback()
        assert row is not None
        FREEZE_PENDING.set(row["freeze"])
        COMPENSATION_PENDING.set(row["compensation"])
        ABANDONED.set(row["abandoned"])

    # --- barrido de validaciones ----------------------------------------------------------------------------------

    def sweep_validations_once(self) -> int:
        """Pasa a `validacion_fallida` las versiones de las `ValidationRun` `validacion` vencidas o cuyo Job fallo. Devuelve cuantas."""
        assert self.jobs is not None, "el barrido necesita la lectura del Job"
        pool = self.evidence.pools.background
        now = self.clock()
        # Sin candados mientras se lee el Job (hasta 5 s por lectura): un `FOR UPDATE` aqui retendria la fila de la corrida y se cruzaria
        # con el `PUT` del informe, que toma el candado global y despues actualiza la corrida (deadlock). Quien decide es `begin_fail_validation`,
        # que toma el candado global y comprueba que la corrida siga `lanzado`: el informe que llega primero gana y este ConflictState se omite.
        with pool() as conn:
            runs = conn.execute(
                "SELECT run_id, model_version_id, job_name, started_at, deadline_at FROM validation_runs "
                "WHERE state = 'lanzado' AND mode = 'validacion' ORDER BY (deadline_at < %s) DESC, started_at LIMIT %s",
                (now, BATCH),
            ).fetchall()
            conn.rollback()
        created = []
        for run in runs:
            expired = run["deadline_at"] < now
            reason = sweep_verdict(self.jobs.get(run["job_name"]), expired, now - run["started_at"])
            if reason is None:
                continue  # sigue corriendo, o `Complete` esperando su informe, o el API aun no devuelve el Job
            try:
                rows = self.evidence.begin_fail_validation(
                    run["model_version_id"],
                    str(run["run_id"]),
                    reason,
                    run_state="fallido" if reason == "failed" or (not expired and reason == "sin informe") else "timeout",
                )
            except ConflictState:
                continue  # el informe llego primero, otra replica la cerro, o la version tiene otra transicion pendiente
            created.append(rows)
        done = 0
        for rows in created:
            try:
                self.evidence.publish(rows, pool)
            except DependencyUnavailable:
                log.warning("el evento de validacion_fallida queda pendiente para el reconciliador")
            except ConflictState:
                continue
            done += 1
        return done

    # --- hilos -------------------------------------------------------------------------------------------------------------

    def start(self, reconcile_every: float = RECONCILE_EVERY, sweep_every: float = SWEEP_EVERY) -> None:
        self._stop.clear()
        for name, action, every in (
            ("reconcile", self.reconcile_once, reconcile_every),
            ("sweep", self.sweep_validations_once if self.jobs is not None else None, sweep_every),
        ):
            if action is None:
                continue
            thread = threading.Thread(target=self._loop, args=(action, every), name=f"governance-{name}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def _loop(self, action: Callable[[], object], every: float) -> None:
        while not self._stop.wait(every):
            try:
                action()
            except Exception:
                log.exception("fallo la tarea de fondo; se reintenta en el siguiente ciclo")

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=5)
        self._threads.clear()
