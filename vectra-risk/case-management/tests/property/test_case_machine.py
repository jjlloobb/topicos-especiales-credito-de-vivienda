"""PBT-U8-01 (BLM §4, stateful PBT-06): `case_fsm` + `evaluation` contra un modelo de referencia, con PostgreSQL real.

Para toda secuencia de 1 a 50 comandos: resultado de scoring de cada tipo (`Recommendation`, `FailClosed` con las 10 causas, fallo de
transporte, 5xx, 401 y otros 4xx, y `serving-config` caido), congelar y descongelar (barrido), `retry` del CRO, decision con y sin ack del
registro, ciclo del reconciliador, abandono a las 24 h, vencimiento de la retencion, `worker_lost` (vence el arrendamiento sin resultado) y
`late_result` (llega el resultado de una toma anterior).

El modelo de referencia es un dato de la prueba (la tabla de BR-U8-12 y contadores de BR-U8-07..09), no una llamada a `evaluation`:
`expected()` dice, para cada tipo de resultado, el estado, los intentos, la causa y el trabajo que dejan las reglas. Los invariantes se leen
de la base con el superusuario despues de cada comando. El vencimiento de la retencion lo aplica un apoyo de la prueba con el rol
`case_retention` real (P-5 (a) de U08-T04): `retention.py` no tiene todavia ese codigo (Paso 16 diferido).

Los recorridos raros se fuerzan en la mitad de los ejemplos y se cuentan en `STATS` (F-02 de la ronda 1 de U08-T03): seis `worker_lost`
seguidos, `late_result` tras un vencimiento, `late_result` tras una retoma, `late_result` tras reiniciarse `attempts` (congelar y descongelar, o
`retry`) y decision tras un abandono.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
from case_pg import Db
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)
from u8_support import auth, decision_body
from vectra_case.config import MAX_ATTEMPTS
from vectra_case.evaluation import Taken
from vectra_common import deps
from vectra_contracts.catalog import FailClosedCause, Outcome
from worker_support import World, expire_case, new_case, worker_world

pytestmark = pytest.mark.integration
S = {
    n: n
    for n in (
        "en_evaluacion",
        "en_sincronizacion",
        "no_disponible",
        "modelo_congelado",
        "listo",
        "decidido",
        "vencido",
    )
}
IN_FLIGHT = ("en_evaluacion", "en_sincronizacion")
TERMINAL = ("decidido", "vencido")
# Pares de estado permitidos por comando (BR-U8-12): una tabla escrita aparte de `case_fsm`; incluye P-1 (a).
ALLOWED = {
    ("en_evaluacion", "listo"),
    ("en_sincronizacion", "listo"),
    ("en_evaluacion", "en_sincronizacion"),
    ("en_sincronizacion", "en_sincronizacion"),
    ("en_sincronizacion", "no_disponible"),
    ("en_evaluacion", "no_disponible"),
    ("en_evaluacion", "modelo_congelado"),
    ("en_sincronizacion", "modelo_congelado"),
    ("modelo_congelado", "en_evaluacion"),
    ("no_disponible", "en_evaluacion"),
    ("listo", "decidido"),
    *{
        (s, "vencido")
        for s in ("en_evaluacion", "listo", "en_sincronizacion", "no_disponible", "modelo_congelado")
    },
}
REJECTED_STATUS = (400, 403, 404, 409, 415, 422)
KINDS: list[tuple[Any, ...]] = [
    *[("rec", o) for o in Outcome],
    *[("fc", c) for c in FailClosedCause],
    ("drop",),
    *[("http", n) for n in (500, 502, 503)],
    ("401_once",),
    ("401_always",),
    *[("http", n) for n in REJECTED_STATUS],
    ("cfg_down",),
]
#: Recorridos forzados/alcanzados por la maquina.
STATS = {
    "six_lost": 0,
    "late_after_expire": 0,
    "late_after_retake": 0,
    "abandon_decide": 0,
    "escalations": 0,
    "frozen_then_thawed": 0,
    "late_after_reset": 0,  # el resultado tardio de una toma anterior llega con `attempts` de nuevo igual a su numero (F-01, ronda 2)
}


@dataclass
class Model:
    state: str = "en_evaluacion"
    attempts: int = 0
    job: int | None = 0  # `attempt` del trabajo vivo, o `None`
    ever_degraded: bool = False
    escalations: int = 0
    last_cause: str | None = None
    mark: bool = False
    has_rec: bool = (
        False  # la recomendacion se guarda al pasar a `listo` y no se borra (tampoco al vencer el caso)
    )
    pending_decision: bool = False
    lost: int = 0  # `worker_lost` seguidos sobre este caso
    stale: list[Taken] = field(default_factory=list)
    # La unica toma cuyo resultado puede aplicarse: la ultima que entrego un intento, mientras ni su resultado, ni un barrido que descongela, ni
    # el `retry`, ni un escalamiento en la toma, ni un vencimiento, ni una decision hayan reemplazado o consumido su trabajo. No mira `attempts`.
    live: Taken | None = None


@dataclass(frozen=True)
class Expect:
    """Lo que dejan BR-U8-08 y BR-U8-09 para un resultado del intento `attempt`."""

    state: str
    attempts: int
    last_cause: str | None
    job: str  # "none" | "rescheduled"
    escalated: bool
    calls: int


def expected(kind: tuple[Any, ...], attempt: int, prev_last: str | None) -> Expect:
    name = kind[0]
    if name in ("rec", "401_once"):
        return Expect("listo", attempt, prev_last, "none", False, 2 if name == "401_once" else 1)
    if name == "fc" and kind[1] is FailClosedCause.MODEL_FROZEN:
        return Expect("modelo_congelado", 0, "model_frozen", "none", False, 1)
    if name == "401_always" or (
        name == "http" and kind[1] in REJECTED_STATUS
    ):  # un 4xx distinto de 401 escala de inmediato
        return Expect(
            "no_disponible", attempt, "scoring_rejected", "none", True, 2 if name == "401_always" else 1
        )
    cause, calls = {
        "fc": (kind[1].value if name == "fc" else None, 1),
        "drop": ("scoring_unreachable", 1),
        "http": ("scoring_unreachable", 1),  # 5xx
        "cfg_down": ("serving_config_unavailable", 0),
    }[name]
    if attempt >= MAX_ATTEMPTS:
        return Expect("no_disponible", attempt, cause, "none", True, calls)
    return Expect("en_sincronizacion", attempt, cause, "rescheduled", False, calls)


def reset_breakers(w: World) -> None:
    """El breaker no es lo que prueba esta maquina (lo prueban las lineas del Paso 14): cada comando parte con los circuitos cerrados."""
    for client in (w.scoring_client._client, w.governance._client):
        assert client.breaker is not None
        client.breaker = deps.CircuitBreaker("x", client.breaker._config)


def make_machine(runner: asyncio.Runner, w: World, db: Db) -> type[RuleBasedStateMachine]:
    conn = db.admin()
    h = w.h
    h.sweeper.governance._clock = lambda: h.clock().timestamp()  # type: ignore[attr-defined]  # sin la cache de 5 s del barrido

    def snapshot(case_id: uuid.UUID) -> dict[str, Any]:
        row = conn.execute(
            "SELECT c.state, c.attempts, c.last_cause, c.ever_degraded, c.escalation_count, c.model_frozen_after_recommendation, "
            "c.recommendation IS NOT NULL, (SELECT count(*) FROM evaluation_jobs j WHERE j.case_id = c.case_id), "
            "(SELECT max(attempt) FROM evaluation_jobs j WHERE j.case_id = c.case_id), "
            "(SELECT count(*) FROM evidence_outbox o WHERE o.case_id = c.case_id AND o.entry_type = 'fail_closed'), "
            "(SELECT count(*) FROM decisions d WHERE d.case_id = c.case_id AND d.state = 'confirmada') "
            "FROM cases c WHERE c.case_id = %s",
            (case_id,),
        ).fetchone()
        assert row is not None
        keys = (
            "state",
            "attempts",
            "last_cause",
            "ever",
            "esc",
            "mark",
            "has_rec",
            "jobs",
            "job_attempt",
            "outbox",
            "confirmed",
        )
        return dict(zip(keys, row, strict=True))

    class CaseMachine(RuleBasedStateMachine):
        @initialize(
            script=st.sampled_from(
                [
                    None,
                    None,
                    "six_lost",
                    "late_after_expire",
                    "late_after_retake",
                    "abandon_decide",
                    "freeze_thaw",
                    "late_after_thaw",
                    "late_after_retry",
                ]
            )
        )
        def start(self, script: str | None) -> None:
            conn.execute("SET session_replication_role = replica")
            conn.execute(
                "DELETE FROM evidence_outbox; DELETE FROM decisions; DELETE FROM explanation_views; DELETE FROM evaluation_jobs; "
                "DELETE FROM intake_keys; DELETE FROM case_identifiers; DELETE FROM cases"
            )
            conn.execute("SET session_replication_role = origin")
            h.registry.entries.clear()
            h.registry.requests.clear()
            h.registry.by_key.clear()
            h.registry.down = False
            h.registry.lose_ack_next = 0
            h.governance_handler.state = "activo"
            h.governance_handler.down = False
            w.scoring.queue.clear()
            w.scoring.by_case.clear()
            w.scoring.default = "ok"
            w.scoring.reject_token = None
            self.case_id = new_case(db)
            self.m = Model()
            self.prev_state = "en_evaluacion"
            self.seen_terminal: str | None = None
            self.takes = 0  # tomas que entregaron un intento
            self.takes_when_listo: int | None = None
            if script is not None:
                getattr(self, f"_script_{script}")()

        # --- scripts forzados (recorridos raros) ---
        def _script_six_lost(self) -> None:
            for _ in range(MAX_ATTEMPTS):
                self._lost()
            assert self._take() is None  # la septima toma escala sin incrementar
            assert self.m.state == "no_disponible" and self.m.attempts == MAX_ATTEMPTS
            STATS["six_lost"] += 1

        def _script_late_after_expire(self) -> None:
            self._lost()
            old = self.m.stale[-1]
            self._expire()
            self._late(old, ("rec", Outcome.FAVORABLE))
            STATS["late_after_expire"] += 1

        def _script_late_after_retake(self) -> None:
            self._lost()
            old = self.m.stale[-1]
            self._evaluate(("http", 503))  # la retoma (intento 2) falla: `en_sincronizacion`
            self._late(
                old, ("rec", Outcome.FAVORABLE)
            )  # el resultado tardio de la primera toma no pasa la guarda
            STATS["late_after_retake"] += 1

        def _script_freeze_thaw(self) -> None:
            self._evaluate(("fc", FailClosedCause.MODEL_FROZEN))  # `modelo_congelado`, sin trabajo
            assert self.m.state == "modelo_congelado" and self.m.job is None
            self.sweep("congelado")  # sigue congelado: no se mueve
            assert self.m.state == "modelo_congelado"
            self.sweep(
                "activo"
            )  # el barrido lo devuelve a `en_evaluacion` con `attempts = 0` y un trabajo nuevo
            self.matches_the_reference_model()

        def _script_late_after_thaw(self) -> None:
            self._lost()  # A: intento 1, sin resultado
            old = self.m.stale[-1]
            self._evaluate(
                ("fc", FailClosedCause.MODEL_FROZEN)
            )  # B retoma (intento 2): `modelo_congelado`, `attempts = 0`
            self.sweep("activo")  # descongela: `en_evaluacion`, `attempts = 0`, trabajo nuevo
            self._lost()  # C: otra vez el intento 1
            self._late(
                old, ("rec", Outcome.FAVORABLE)
            )  # el de A no es el de C aunque los dos sean el intento 1
            assert self.m.state == "en_evaluacion" and self.m.live is not old

        def _script_late_after_retry(self) -> None:
            self._lost()
            old = self.m.stale[-1]
            self._evaluate(("http", 403))  # B: `scoring_rejected`, `no_disponible`
            self.retry()  # `en_evaluacion`, `attempts = 0`, trabajo nuevo
            self._lost()  # C: otra vez el intento 1
            self._late(old, ("rec", Outcome.FAVORABLE))
            assert self.m.state == "en_evaluacion" and self.m.live is not old

        def _script_abandon_decide(self) -> None:
            self._evaluate(("rec", Outcome.FAVORABLE))
            h.registry.lose_ack_next = 1  # el registro escribe la decision y se pierde el ack
            first = self._decide("analista", ack=True, expect_status=503)
            assert first == 503
            self.matches_the_reference_model()
            h.registry.lose_ack_next = 0
            h.clock.advance(hours=25)
            runner.run(h.reconciler.run_once())  # abandona la pendiente (el registro si la habia escrito)
            self.matches_the_reference_model()
            second = self._decide("analista2", ack=True)
            assert second == 409  # `decision_already_recorded`
            self.m.state = "decidido"
            self.m.job = self.m.live = None
            self.matches_the_reference_model()
            STATS["abandon_decide"] += 1

        # --- comandos del worker ---
        def _take(self) -> Taken | None:
            """Una toma con el reloj pasado el backoff y el arrendamiento; verifica `toda toma incrementa` y `attempt = 6 escala`."""
            h.clock.advance(minutes=20)
            reset_breakers(w)
            calls = w.scoring.calls
            taken = runner.run(w.queue.take())
            m = self.m
            if m.job is None:
                assert taken is None and w.scoring.calls == calls
                return None
            if (
                m.job >= MAX_ATTEMPTS
            ):  # la retoma con attempt = 6 escala sin incrementar y sin llamar a scoring
                assert taken is None and w.scoring.calls == calls
                m.live = None
                m.state, m.job, m.last_cause, m.ever_degraded = (
                    "no_disponible",
                    None,
                    "scoring_unreachable",
                    True,
                )
                m.escalations += 1
                STATS["escalations"] += 1
                return None
            assert taken is not None and taken.attempt == m.job + 1  # toda toma incrementa
            self.takes += 1
            m.attempts = m.job = taken.attempt
            m.live = taken
            return taken

        def _lost(self) -> None:
            taken = self._take()
            if taken is not None:
                self.m.stale.append(taken)
                self.m.lost += 1
            self.matches_the_reference_model()

        def _arm(self, kind: tuple[Any, ...]) -> None:
            w.scoring.default = "ok"
            h.governance_handler.down = False
            name = kind[0]
            if name == "rec":
                w.scoring.default = ("ok", kind[1])
            elif name == "fc":
                w.scoring.default = ("fail", kind[1])
            elif name == "drop":
                w.scoring.default = "drop"
            elif name == "http":
                w.scoring.default = ("status", kind[1])
            elif name == "401_once":
                w.scoring.reject_token = f"t{w.token.n}"
            elif name == "401_always":
                w.scoring.default = ("status", 401)
            else:
                h.governance_handler.down = True

        def _disarm(self) -> None:
            w.scoring.reject_token = None
            w.scoring.default = "ok"
            h.governance_handler.down = False

        def _apply_expect(self, e: Expect, attempt: int) -> None:
            m = self.m
            m.live = (
                None  # el resultado aplicado consume el trabajo (se borra o se reprograma sin arrendamiento)
            )
            m.state, m.attempts, m.last_cause = e.state, e.attempts, e.last_cause
            if e.state != "listo":
                m.ever_degraded = True
            m.job = attempt if e.job == "rescheduled" else None
            if e.escalated:
                m.escalations += 1
                STATS["escalations"] += 1
            self.takes_when_listo = self.takes if e.state == "listo" else None
            m.has_rec = m.has_rec or e.state == "listo"

        def _evaluate(self, kind: tuple[Any, ...]) -> None:
            taken = self._take()
            if taken is None:
                self.matches_the_reference_model()
                return
            prev_ever, prev_last = self.m.ever_degraded, self.m.last_cause
            self._arm(kind)
            calls = w.scoring.calls
            reset_breakers(w)
            applied = runner.run(w.evaluator.run(taken))
            self._disarm()
            e = expected(kind, taken.attempt, prev_last)
            assert applied is True
            assert (
                w.scoring.calls - calls == e.calls
            )  # un 4xx no se reintenta; el 401 no cuenta como intento (pero si son dos llamadas)
            if e.calls:
                sent = w.scoring.requests[-1]
                assert sent.attempt == taken.attempt  # el 401 no cambia el numero de intento
                assert sent.first_evaluation is (not prev_ever and taken.attempt == 1)
            self._apply_expect(e, taken.attempt)
            self.matches_the_reference_model()

        def _late(self, old: Taken, kind: tuple[Any, ...]) -> None:
            """Llega el resultado de una toma anterior: solo cuenta si es la toma vigente (`m.live`), que el modelo sigue por su cuenta."""
            m = self.m
            before = snapshot(self.case_id)
            current = m.state in IN_FLIGHT and m.live is old
            if not current and m.state in IN_FLIGHT and m.job is not None and m.attempts == old.attempt:
                STATS["late_after_reset"] += 1  # el numero de intento coincide, la toma no
            prev_last = m.last_cause
            self._arm(kind)
            reset_breakers(w)
            applied = runner.run(w.evaluator.run(old))
            self._disarm()
            assert applied is current
            if not current:
                assert snapshot(self.case_id) == before  # un resultado tardio nunca modifica el caso
                return
            self._apply_expect(expected(kind, old.attempt, prev_last), old.attempt)
            self.matches_the_reference_model()

        @rule(kind=st.sampled_from(KINDS))
        def result(self, kind: tuple[Any, ...]) -> None:
            self._evaluate(kind)

        @rule()
        def worker_lost(self) -> None:
            self._lost()

        @precondition(lambda self: bool(self.m.stale))
        @rule(data=st.data(), kind=st.sampled_from(KINDS))
        def late_result(self, data: st.DataObject, kind: tuple[Any, ...]) -> None:
            old = data.draw(st.sampled_from(self.m.stale))
            if self.m.state == "vencido":
                STATS["late_after_expire"] += 1
            self._late(old, kind)

        @rule(state=st.sampled_from(["activo", "congelado"]))
        def sweep(self, state: str) -> None:
            """Congelar y descongelar: el barrido de `case-service` (U08-T03) mueve `modelo_congelado` y la marca de congelamiento."""
            h.governance_handler.state = state
            h.clock.advance(seconds=10)
            m = self.m
            runner.run(h.sweeper.run_once())
            if state == "activo":
                if m.state == "modelo_congelado":
                    m.state, m.attempts, m.job, m.live = "en_evaluacion", 0, 0, None
                    STATS["frozen_then_thawed"] += 1
                m.mark = False
            elif m.state == "listo":
                m.mark = True

        @rule()
        def retry(self) -> None:
            r = runner.run(h.client.post(f"/v1/cases/{self.case_id}/retry", headers=auth("cro")))
            m = self.m
            if m.state == "no_disponible":
                assert r.status_code == 200
                m.state, m.attempts, m.job, m.live = "en_evaluacion", 0, 0, None
            else:
                assert r.status_code == 409

        def _decide(self, who: str, *, ack: bool, expect_status: int | None = None) -> int:
            h.registry.down = not ack
            outcome = snapshot_outcome()
            body = (
                decision_body(final_outcome=outcome)
                if outcome != "revision_requerida"
                else decision_body(
                    decision="resuelve_revision", final_outcome="favorable", justification="se revisa el caso"
                )
            )
            r = runner.run(h.client.post(f"/v1/cases/{self.case_id}/decision", json=body, headers=auth(who)))
            h.registry.down = False
            if expect_status is not None:
                assert r.status_code == expect_status
            return int(r.status_code)

        @rule(ack=st.booleans(), who=st.sampled_from(["analista", "analista2"]))
        def decide(self, ack: bool, who: str) -> None:
            m = self.m
            was = m.state
            status = self._decide(who, ack=ack)
            if was != "listo":
                assert (
                    status in (409, 422)
                )  # decision sobre un caso que no esta `listo` (la validacion del cuerpo va antes que el estado)
            elif status == 200:
                m.state, m.job, m.live = "decidido", None, None
            else:
                assert status in (409, 422, 503)
                m.pending_decision = m.pending_decision or status == 503

        @rule()
        def reconcile(self) -> None:
            h.clock.advance(minutes=6)
            runner.run(h.reconciler.run_once())
            snap = snapshot(self.case_id)
            if (
                snap["state"] == "decidido" and self.m.state == "listo"
            ):  # el ciclo confirmo una decision pendiente
                self.m.state, self.m.job, self.m.live = "decidido", None, None

        @rule()
        def abandon(self) -> None:
            h.registry.down = True
            h.clock.advance(hours=25)
            runner.run(h.reconciler.run_once())  # a las 24 h la evidencia pendiente pasa a `abandonada`
            h.registry.down = False

        def _expire(self) -> None:
            if self.m.state in TERMINAL:
                return
            expire_case(db, self.case_id)
            self.m.state, self.m.job, self.m.live = "vencido", None, None
            self.matches_the_reference_model()

        @rule()
        def expire(self) -> None:
            self._expire()

        @rule(seconds=st.sampled_from([1, 45, 700, 7200]))
        def tick(self, seconds: int) -> None:
            h.clock.advance(seconds=seconds)

        @invariant()
        def matches_the_reference_model(self) -> None:
            snap, m = snapshot(self.case_id), self.m
            # estado alcanzable por BR-U8-12 desde el anterior; `decidido` y `vencido` terminales
            assert snap["state"] == self.prev_state or (self.prev_state, snap["state"]) in ALLOWED, (
                self.prev_state,
                snap["state"],
            )
            if self.seen_terminal is not None:
                assert snap["state"] == self.seen_terminal
            if snap["state"] in TERMINAL:
                self.seen_terminal = snap["state"]
            self.prev_state = snap["state"]
            assert snap["state"] == m.state, (snap, m)
            # attempts <= 6 y el modelo de contadores de BR-U8-07
            assert 0 <= snap["attempts"] <= MAX_ATTEMPTS and snap["attempts"] == m.attempts
            assert snap["ever"] == m.ever_degraded and snap["esc"] == m.escalations
            assert snap["last_cause"] == m.last_cause
            assert snap["mark"] == m.mark
            # exactamente un trabajo vivo en `en_evaluacion` y `en_sincronizacion`; ninguno fuera de ellos
            assert snap["jobs"] == (1 if m.state in IN_FLIGHT else 0)
            assert snap["job_attempt"] == (m.job if m.state in IN_FLIGHT else None)
            # una entrada `fail_closed` por escalamiento, una sola decision confirmada
            assert snap["outbox"] == m.escalations and snap["confirmed"] <= 1
            # una decision `confirmada` sin caso `decidido` solo ocurre si el caso vencio con la decision pendiente y el registro confirmo despues
            assert (m.state == "decidido") <= (snap["confirmed"] == 1)
            assert snap["confirmed"] == 0 or m.state in ("decidido", "vencido")
            # `listo` nunca recibe otro intento
            # (un worker lento puede seguir llamando a scoring con su toma vieja: lo que no ocurre es una toma nueva)
            if m.state in ("listo", "decidido") and self.takes_when_listo is not None:
                assert self.takes == self.takes_when_listo
            assert snap["has_rec"] == m.has_rec

    def snapshot_outcome() -> str:
        row = conn.execute(
            "SELECT recommendation->>'outcome' FROM cases WHERE recommendation IS NOT NULL LIMIT 1"
        ).fetchone()
        return str(row[0]) if row else "favorable"

    return CaseMachine


def test_pbt_u8_01_case_fsm_and_evaluation_against_the_reference_model(db: Db) -> None:
    for name in STATS:
        STATS[name] = 0
    with asyncio.Runner() as runner:
        cm = worker_world(db)
        w = runner.run(cm.__aenter__())
        try:
            run_state_machine_as_test(
                make_machine(runner, w, db), settings=settings(stateful_step_count=50, deadline=None)
            )
        finally:
            runner.run(cm.__aexit__(None, None, None))
    print(f"\nPBT-U8-01 recorridos: {STATS}")
    if (
        settings().max_examples >= 100
    ):  # perfiles `ci` y `nightly`: cada recorrido raro ocurrio (un comando que nunca corre no prueba nada)
        assert STATS["six_lost"] > 0 and STATS["late_after_expire"] > 0 and STATS["late_after_retake"] > 0
        assert STATS["abandon_decide"] > 0 and STATS["escalations"] > 0 and STATS["frozen_then_thawed"] > 0
        assert STATS["late_after_reset"] > 0
