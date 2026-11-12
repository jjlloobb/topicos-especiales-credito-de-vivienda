"""PBT-U8-07 (BLM §4, stateful PBT-06): evidencia en dos fases contra el doble del registro (BR-U3-05/06, BR-U0-37) y PostgreSQL real.

Para toda secuencia de decisiones, consultas, fallos del registro (503, ack perdido tras el commit), saltos de reloj (mas de 5 min,
mas de 24 h, mas de 7 dias) y ciclos del reconciliador: cada evidencia termina `confirmada` exactamente una vez, `abandonada` a las
24 h o, solo `explanation_view` rechazada por BR-U0-37, `descartada`; siempre con la misma `idempotency_key`; el momento de negocio no cambia
entre intentos (`occurred_at` si); el registro tiene una sola entrada por evidencia y nunca mas de una `human_decision` por caso, incluso
con un abandono seguido de una decision nueva cuando la abandonada si se habia escrito; `explanation_viewed_before` solo es `true`
con la consulta confirmada.
"""

import asyncio
import uuid
from typing import Any

import pytest
from case_pg import Db
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule, run_state_machine_as_test
from u8_support import auth, decision_body, harness, seed_case

pytestmark = pytest.mark.integration
BODIES = [decision_body(), decision_body(justification="una justificacion distinta")]
TERMINAL = {"confirmada", "abandonada", "descartada"}


def make_machine(runner: asyncio.Runner, h: Any, db: Db) -> type[RuleBasedStateMachine]:
    class EvidenceMachine(RuleBasedStateMachine):
        @initialize()
        def start(self) -> None:
            h.registry.entries.clear()
            h.registry.requests.clear()
            h.registry.by_key.clear()
            h.registry.down = False
            h.registry.lose_ack_next = 0
            db.execute(
                "DELETE FROM decisions; DELETE FROM explanation_views; DELETE FROM evidence_outbox"
            )  # cada ejemplo parte limpio
            self.case_id = seed_case(db, state="listo")
            self.moments: dict[str, set[str]] = {}

        def _post(self, path: str, who: str, body: dict[str, Any] | None) -> int:
            r = runner.run(
                h.client.post(path, json=body, headers=auth(who))
                if body is not None
                else h.client.post(path, headers=auth(who))
            )
            return r.status_code

        @rule(mode=st.sampled_from(["ok", "down", "lose_ack"]))
        def registry(self, mode: str) -> None:
            h.registry.down = mode == "down"
            h.registry.lose_ack_next = 1 if mode == "lose_ack" else 0

        @rule(who=st.sampled_from(["analista", "analista2"]), body=st.integers(0, 1))
        def decide(self, who: str, body: int) -> None:
            assert self._post(f"/v1/cases/{self.case_id}/decision", who, BODIES[body]) in (200, 409, 503)

        @rule(who=st.sampled_from(["analista", "analista2"]))
        def view(self, who: str) -> None:
            assert self._post(f"/v1/cases/{self.case_id}/explanation-views", who, None) in (204, 409)

        @rule(seconds=st.sampled_from([1, 400, 7200, 30 * 3600, 8 * 86400]))
        def tick(self, seconds: int) -> None:
            h.clock.advance(seconds=seconds)
            runner.run(h.reconciler.run_once())

        @rule()
        def reconcile(self) -> None:
            h.clock.advance(minutes=6)
            runner.run(h.reconciler.run_once())

        @invariant()
        def registry_and_outbox_agree(self) -> None:
            decisions = h.registry.of_type("human_decision")
            assert len(decisions) <= 1  # nunca mas de una `human_decision` por caso
            keys = [str(r["entry"].idempotency_key) for r in h.registry.entries]
            assert len(keys) == len(set(keys))  # una sola entrada por evidencia
            # El momento de negocio (`decided_at`, `viewed_at`) de cada envio es el que se guardo en el outbox al crear la evidencia: el
            # reconciliador nunca lo cambia entre intentos (`occurred_at` si). Una decision nueva con la misma llave tras un abandono
            # es otra evidencia y trae su propio momento.
            stored: dict[str, set[object]] = {}
            for key, payload in db.query(
                "SELECT idempotency_key, payload->'payload' FROM evidence_outbox WHERE case_id = %s",
                self.case_id,
            ):
                moment = payload.get("decided_at") or payload.get("viewed_at")  # type: ignore[union-attr]
                stored.setdefault(str(key), set()).add(moment)
            for req in h.registry.requests:
                sent = req["payload"].get("decided_at") or req["payload"].get("viewed_at")
                assert sent in stored[req["idempotency_key"]]
            rows = db.query(
                "SELECT idempotency_key, state, registry_entry_id, entry_type FROM evidence_outbox WHERE case_id = %s",
                self.case_id,
            )
            confirmed_keys = [str(r[0]) for r in rows if r[1] == "confirmada"]
            assert len(confirmed_keys) == len(set(confirmed_keys))
            for key in confirmed_keys:
                assert key in keys  # `confirmada` implica entrada en el registro
            for r in rows:
                assert r[1] in TERMINAL | {"pendiente_registro"}
                if r[1] == "descartada":
                    assert r[3] == "explanation_view"
            state = db.query("SELECT state FROM cases WHERE case_id = %s", self.case_id)[0][0]
            live = db.query(
                "SELECT count(*) FROM decisions WHERE case_id = %s AND state = 'confirmada'", self.case_id
            )[0][0]
            assert (state == "decidido") == (live == 1)
            for entry in decisions:
                if entry[
                    "entry"
                ].payload.explanation_viewed_before:  # solo con la consulta confirmada del mismo usuario
                    view_key = str(uuid.uuid5(self.case_id, entry["entry"].actor.id))
                    assert view_key in keys

        def teardown(self) -> None:
            h.registry.down = False
            h.registry.lose_ack_next = 0
            for _ in range(8):  # con el registro de vuelta toda evidencia viva termina
                h.clock.advance(minutes=6)
                runner.run(h.reconciler.run_once())
            rows = db.query("SELECT state FROM evidence_outbox WHERE case_id = %s", self.case_id)
            assert all(r[0] in TERMINAL for r in rows), rows
            self.registry_and_outbox_agree()

    return EvidenceMachine


def test_pbt_u8_07_evidence_converges_exactly_once(db: Db) -> None:
    with asyncio.Runner() as runner:
        cm = harness(db)
        h = runner.run(cm.__aenter__())
        try:
            run_state_machine_as_test(
                make_machine(runner, h, db),
                settings=settings(stateful_step_count=14, max_examples=80, deadline=None),
            )
        finally:
            runner.run(cm.__aexit__(None, None, None))
