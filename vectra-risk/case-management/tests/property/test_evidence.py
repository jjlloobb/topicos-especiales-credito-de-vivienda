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
from datetime import datetime
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
#: Cuantas veces la maquina recorrio `lose_ack` -> decision -> mas de 24 h -> decision nueva (409 `decision_already_recorded`).
STATS = {"abandon_then_new": 0}


def norm(value: Any) -> Any:
    """Compara cargas del outbox y del registro: fechas como instantes (`Z` o `+00:00`) y sin campos nulos."""
    if isinstance(value, dict):
        return {k: norm(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [norm(v) for v in value]
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    return value


def make_machine(runner: asyncio.Runner, h: Any, db: Db) -> type[RuleBasedStateMachine]:
    class EvidenceMachine(RuleBasedStateMachine):
        @initialize(forced=st.booleans())
        def start(self, forced: bool) -> None:
            h.registry.entries.clear()
            h.registry.requests.clear()
            h.registry.by_key.clear()
            h.registry.down = False
            h.registry.lose_ack_next = 0
            db.execute(
                "DELETE FROM decisions; DELETE FROM explanation_views; DELETE FROM evidence_outbox"
            )  # cada ejemplo parte limpio
            self.case_id = seed_case(db, state="listo")
            if forced:  # recorrido forzado en la mitad de los ejemplos (F-02 de la ronda 1)
                self._abandon_then_new_decision()

        def _abandon_then_new_decision(self) -> None:
            """`lose_ack` -> decision -> mas de 24 h -> decision nueva: el registro si escribio la abandonada (BR-U8-18)."""
            path = f"/v1/cases/{self.case_id}/decision"
            h.registry.lose_ack_next = 1
            assert self._post(path, "analista", BODIES[0]).status_code == 503
            h.registry.lose_ack_next = 0
            h.clock.advance(hours=25)
            runner.run(h.reconciler.run_once())  # abandona la pendiente
            second = self._post(path, "analista2", BODIES[1])
            assert second.status_code == 409 and second.json()["reason"] == "decision_already_recorded"
            assert db.query("SELECT decided_by->>'id' FROM decisions WHERE state = 'confirmada'") == [
                ("analista-1",)
            ]
            STATS["abandon_then_new"] += 1

        def _post(self, path: str, who: str, body: dict[str, Any] | None) -> Any:
            return runner.run(
                h.client.post(path, json=body, headers=auth(who))
                if body is not None
                else h.client.post(path, headers=auth(who))
            )

        @rule(mode=st.sampled_from(["ok", "down", "lose_ack"]))
        def registry(self, mode: str) -> None:
            h.registry.down = mode == "down"
            h.registry.lose_ack_next = 1 if mode == "lose_ack" else 0

        @rule(who=st.sampled_from(["analista", "analista2"]), body=st.integers(0, 1))
        def decide(self, who: str, body: int) -> None:
            assert self._post(f"/v1/cases/{self.case_id}/decision", who, BODIES[body]).status_code in (
                200,
                409,
                503,
            )

        @rule(who=st.sampled_from(["analista", "analista2"]))
        def view(self, who: str) -> None:
            assert self._post(f"/v1/cases/{self.case_id}/explanation-views", who, None).status_code in (
                204,
                409,
            )

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
            # Por evidencia (`evidence_id`), no por llave: cada envio es la carga de **una** fila del outbox con esa llave, tal como se
            # guardo (momento de negocio incluido); el reconciliador no la cambia entre intentos (`occurred_at` si). Una decision nueva con
            # la misma llave tras un abandono es otra evidencia con su propia carga.
            stored = db.query(
                "SELECT idempotency_key, payload->'payload' FROM evidence_outbox WHERE case_id = %s",
                self.case_id,
            )
            candidates: dict[str, list[Any]] = {}
            for key, payload in stored:
                candidates.setdefault(str(key), []).append(norm(payload))
            for req in h.registry.requests:
                assert norm(req["payload"]) in candidates[req["idempotency_key"]]
            rows = db.query(
                "SELECT idempotency_key, state, registry_entry_id, entry_type FROM evidence_outbox WHERE case_id = %s",
                self.case_id,
            )
            confirmed_keys = [str(r[0]) for r in rows if r[1] == "confirmada"]
            assert len(confirmed_keys) == len(set(confirmed_keys))
            for key in confirmed_keys:
                assert key in keys  # `confirmada` implica entrada en el registro
            by_id = {r["registry_entry_id"]: r["entry"] for r in h.registry.entries}
            for payload, entry_id in db.query(
                "SELECT payload->'payload', registry_entry_id FROM evidence_outbox WHERE case_id = %s AND state = 'confirmada'",
                self.case_id,
            ):
                # lo que el registro tiene bajo ese `registry_entry_id` es la carga de la fila `confirmada`, no la de otra decision
                assert norm(by_id[entry_id].payload.model_dump(mode="json")) == norm(payload)
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
    STATS["abandon_then_new"] = 0
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
    print(f"\nPBT-U8-07 recorridos abandono -> decision nueva: {STATS['abandon_then_new']}")
    assert STATS["abandon_then_new"] > 0
