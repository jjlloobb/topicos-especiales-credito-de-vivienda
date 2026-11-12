"""PBT-U8-06 (BLM §4): idempotencia de la ingesta y del alta manual, con la limpieza de 30 dias, contra PostgreSQL real.

Stateful (PBT-06): secuencias de envios con llaves, cuerpos, alcances (cliente `azp` en la ingesta, usuario en el alta manual) y
edades repetidos. Propiedades: misma llave y mismo cuerpo -> el mismo `case_id`; misma llave y otro cuerpo -> 409; nunca dos casos con la
misma llave en el mismo alcance; la misma llave en alcances distintos no choca; tras la limpieza de 30 dias la llave queda libre (la
purga corre con el rol `case_retention`); `X-Test-Scenario` solo con `azp = channel-simulator` fuera de produccion.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from case_pg import Db, url
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule, run_state_machine_as_test
from psycopg import connect
from u8_support import application, harness
from vectra_case.intake import SIMULATOR, check_test_scenario
from vectra_case.retention import purge_intake_keys
from vectra_common.errors import ValidationFailed

pytestmark = pytest.mark.integration
CALLERS = [
    ("simulator", False),
    ("channel", False),
    ("channel2", False),
    ("analista", True),
    ("analista2", True),
]
BODIES = [
    application(),
    application(term_months=120),
    application(free_text="'; DROP TABLE cases; --"),
    application(requested_amount=2_000_000),
]


def make_machine(runner: asyncio.Runner, h: Any, db: Db) -> type[RuleBasedStateMachine]:
    class IntakeMachine(RuleBasedStateMachine):
        @initialize()
        def start(self) -> None:
            self.ns = uuid.uuid4().hex[:10]
            self.model: dict[tuple[str, str], tuple[int, str]] = {}  # (alcance, llave) -> (cuerpo, case_id)
            self.created: set[str] = set()
            self.aged: set[tuple[str, str]] = set()

        def _send(self, who: str, manual: bool, key: str, body: int) -> tuple[int, dict[str, Any]]:
            path = "/v1/cases" if manual else "/v1/intake/applications"
            r = runner.run(
                h.client.post(
                    path,
                    json=BODIES[body],
                    headers={"Authorization": f"Bearer {who}", "Idempotency-Key": f"{self.ns}-{key}"},
                )
            )
            return r.status_code, r.json()

        @rule(
            caller=st.sampled_from(CALLERS),
            key=st.sampled_from(["a", "b", "c"]),
            body=st.integers(0, len(BODIES) - 1),
        )
        def send(self, caller: tuple[str, bool], key: str, body: int) -> None:
            who, manual = caller
            scope = (who, f"{self.ns}-{key}")
            status, data = self._send(who, manual, key, body)
            known = self.model.get(scope)
            if known is None:
                assert status == 200, data
                assert data["case_id"] not in self.created
                self.model[scope] = (body, data["case_id"])
                self.created.add(data["case_id"])
            elif known[0] == body:
                assert status == 200 and data["case_id"] == known[1]
            else:
                assert status == 409 and data["code"] == "conflict_state"

        @rule(data=st.data())
        def age_and_purge(self, data: st.DataObject) -> None:
            """Envejece una llave 31 dias y corre la purga con el rol `case_retention`: la llave queda libre."""
            if not self.model:
                return
            scope = data.draw(st.sampled_from(sorted(self.model)))
            db.execute(
                "UPDATE intake_keys SET created_at = %s WHERE idempotency_key = %s AND scope LIKE %s",
                datetime.now(UTC) - timedelta(days=31),
                scope[1],
                ("user:%" if scope[0].startswith("analista") else "client:%"),
            )
            with connect(url(db.pg, db.name, "case_retention", "case_retention"), autocommit=True) as conn:
                purge_intake_keys(conn)
            # solo se borran las llaves de este escenario que se envejecieron: las demas siguen vivas
            for other in [
                s
                for s in self.model
                if s[1] == scope[1] and (s[0].startswith("analista") == scope[0].startswith("analista"))
            ]:
                self.model.pop(other)

        @invariant()
        def one_case_per_live_key_and_scope(self) -> None:
            live = db.query(
                "SELECT scope, idempotency_key, count(*) FROM intake_keys WHERE idempotency_key LIKE %s GROUP BY 1, 2",
                f"{self.ns}-%",
            )
            assert all(row[2] == 1 for row in live)
            assert len(live) == len(self.model)

    return IntakeMachine


def test_pbt_u8_06_idempotency_and_the_30_day_purge(db: Db) -> None:
    with asyncio.Runner() as runner:
        cm = harness(db)
        h = runner.run(cm.__aenter__())
        try:
            machine = make_machine(runner, h, db)
            run_state_machine_as_test(
                machine, settings=settings(stateful_step_count=15, max_examples=120, deadline=None)
            )
        finally:
            runner.run(cm.__aexit__(None, None, None))


@given(
    client=st.one_of(st.none(), st.just(SIMULATOR), st.text(min_size=1, max_size=12)),
    header=st.one_of(st.none(), st.sampled_from(["adversarial-1", "x.y:z", "bad value!", "", "a" * 101])),
    allow=st.booleans(),
)
def test_pbt_u8_06_test_scenario_only_for_the_simulator_outside_production(
    client: str | None, header: str | None, allow: bool
) -> None:
    valid = (
        header is not None
        and 1 <= len(header) <= 100
        and all(c.isalnum() or c in "_.:-" for c in header)
        and header.isascii()
    )
    try:
        result = check_test_scenario(client, header, allow)
    except ValidationFailed:
        assert header is not None and not (client == SIMULATOR and allow and valid)
    else:
        assert result == (header if header is not None else None)
        assert header is None or (client == SIMULATOR and allow)
