"""PBT-U4-07: evidencia en dos fases con el registro fallando al azar (Paso 8; NFR-U4-40; PBT-06).

Maquina de estados sobre la capa de servicio (`Evidence`), 2 replicas contra la misma base de PostgreSQL de Testcontainers y el
doble del registro (U3) que cae o pierde el ack. Para toda secuencia: ninguna transicion distinta de `freeze` cambia el estado
sin un `registry_entry_id`; los reintentos no crean dos eventos; nunca hay dos eventos para la misma `n` de una entidad
(tambien con un abandono seguido de una transicion nueva); los eventos de una entidad van en orden de `n`; nunca una
`frozen_resolution` sin su `freeze` antes; una sola pendiente por entidad (salvo `freeze`); una `descartada` nunca aplica; las
mitades de una unidad van juntas; una compensacion nunca se abandona; lo mismo para politicas. La parte de fuentes de datos
(US-306) queda diferida con Q-6.

`HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_stateful_evidence.py`. El perfil `ci` fija 500 ejemplos para las
propiedades puras; cada ejemplo de esta maquina crea una base y corre hasta 40 pasos con PostgreSQL real, asi que usa menos ejemplos
(`STATEFUL_EXAMPLES`) con las mismas invariantes (misma decision que U3, `test_append_stateful.py`).
"""

import os
from collections import Counter
from typing import Any

import pytest
from evidence_invariants import check_pbt07
from evidence_support import (
    BIAS,
    CRO1,
    CRO2,
    CUM,
    ING,
    VALIDATION_JOB,
    Harness,
    freeze_context,
    new_model,
    policy_draft,
    report,
)
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule, run_state_machine_as_test
from vectra_governance.evidence import RegistryUnavailable
from vectra_governance.model_fsm import ConflictState, Forbidden

pytestmark = pytest.mark.integration

COVERAGE: Counter[tuple[object, ...]] = Counter()
STATEFUL_EXAMPLES = int(os.environ.get("U4_STATEFUL_EXAMPLES", "25"))
STEPS = 40
MODELS = ["mv-1", "mv-2", "mv-3"]
POLICIES = ["p-1", "p-2", "p-3"]
replica = st.sampled_from(["a", "b"])
pick = st.integers(0, 10_000)


class EvidenceMachine(RuleBasedStateMachine):
    pg: Any
    template: str

    def __init__(self) -> None:
        super().__init__()
        self.h = Harness(self.pg, self.template)

    def teardown(self) -> None:
        snap = self.h.snapshot()
        for r in snap["transitions"]:
            COVERAGE[(r["kind"], r["status"], bool(r["unit_id"]), r["entity_type"], r["to_state"] == "congelado")] += 1
        
        self.h.close()

    # --- lectura -----------------------------------------------------------------------------------------------------------

    def model_states(self) -> dict[str, str]:
        return {r["model_version_id"]: r["state"] for r in self.h.admin.execute("SELECT * FROM model_versions").fetchall()}

    def policy_states(self) -> dict[str, str]:
        return {r["policy_version_id"]: r["state"] for r in self.h.admin.execute("SELECT * FROM policies").fetchall()}

    def models_in(self, *states: str) -> list[str]:
        return sorted(m for m, s in self.model_states().items() if s in states)

    def policies_in(self, *states: str) -> list[str]:
        return sorted(p for p, s in self.policy_states().items() if s in states)

    def attempt(self, who: str, op: Any) -> Any:
        """Una operacion que puede ser rechazada (403/409) o quedar pendiente (503); cualquier otro error es un defecto."""
        try:
            result = op(self.h.services[who])
        except (ConflictState, Forbidden, RegistryUnavailable):
            return None
        for transition_id in result.transition_ids:  # lo que devuelve con exito esta confirmado y con ack
            row = self.h.admin.execute("SELECT status, registry_entry_id FROM transitions WHERE transition_id = %s", (transition_id,)).fetchone()
            assert row is not None
            if result.status == "confirmada":
                assert row["status"] == "confirmada" and row["registry_entry_id"] is not None
        return result

    # --- el registro y el tiempo -------------------------------------------------------------------------------------------

    @rule(mode=st.sampled_from(["up", "up", "up", "down", "lost_ack"]))
    def registry_mode(self, mode: str) -> None:
        self.h.registry.mode = mode

    @rule(who=replica)
    def reconcile(self, who: str) -> None:
        self.h.background[who].reconcile_once()

    @rule(who=replica, hours=st.sampled_from([1, 13, 25, 30]))
    def tick_and_reconcile(self, who: str, hours: int) -> None:
        self.h.clock.advance(hours=hours)
        self.h.background[who].reconcile_once()

    @rule(who=replica)
    def sweep_validations(self, who: str) -> None:
        self.h.clock.advance(hours=3)
        self.h.background[who].sweep_validations_once()

    @rule(who=replica, i=pick)
    def fast_forward(self, who: str, i: int) -> None:
        """Lleva una version hacia `activo` con el modo del registro vigente (para llegar a estados profundos)."""
        self.walk(who, MODELS[i % len(MODELS)])

    def walk(self, who: str, model_id: str, stop: str | None = None) -> None:
        for _ in range(5):
            state = self.model_states().get(model_id)
            if state is not None and state == stop:
                return
            run = self.h.admin.execute(
                "SELECT run_id FROM validation_runs WHERE model_version_id = %s AND state = 'lanzado'", (model_id,)
            ).fetchall()
            job = f"job-{model_id}-{self.h.clock().timestamp():.0f}"
            ops: dict[str | None, Any] = {
                None: lambda svc: svc.register(ING, new_model(model_id)),
                "registrado": lambda svc: svc.start_validation(ING, model_id, job_name=job),
                "validacion_fallida": lambda svc: svc.retry_validation(ING, model_id, job_name=job),
                "en_validacion": lambda svc: svc.receive_report(
                    VALIDATION_JOB, model_id, str(run[-1]["run_id"]), report(True)
                ),
                "lista_para_aprobacion": lambda svc: svc.approve(CRO1, model_id),
                "aprobado": lambda svc: svc.mark_active(ING, model_id),
                "inactivo": lambda svc: svc.mark_active(ING, model_id),
            }
            if state == "en_validacion" and not run:
                return
            op = ops.get(state)
            if op is None or self.attempt(who, op) is None:
                return

    @rule(
        who=replica,
        i=pick,
        mode=st.sampled_from(["down", "lost_ack", "up"]),
        freeze_first=st.booleans(),
        settle=st.booleans(),
        ack_only=st.booleans(),
    )
    def freeze_during_a_promotion(
        self, who: str, i: int, mode: str, freeze_first: bool, settle: bool, ack_only: bool
    ) -> None:
        """Un `mark_active` en vuelo (sin ack o con el ack perdido) y un `freeze` de la version activa (BR-U4-17)."""
        if not (self.models_in("activo") and self.models_in("aprobado", "inactivo")):
            self.h.registry.mode = "up"  # arma el escenario: una version activa y otra aprobada
            if not self.models_in("activo"):
                self.walk(who, "mv-1")
            if not self.models_in("aprobado", "inactivo"):
                self.walk(who, "mv-2", stop="aprobado")
            if not (self.models_in("activo") and self.models_in("aprobado", "inactivo")):
                return
        live = self.models_in("activo")[0]
        target = self.models_in("aprobado", "inactivo")[i % len(self.models_in("aprobado", "inactivo"))]
        self.h.registry.mode = mode
        self.attempt(who, lambda svc: svc.mark_active(ING, target))
        acked: list[Any] = []
        if ack_only:  # el ack queda guardado pero la TX2 no corre: la revalidacion de la TX2 es lo unico que protege
            self.h.registry.mode = "up"
            svc = self.h.services[who]
            acked = [
                r["transition_id"]
                for r in self.h.admin.execute(
                    "SELECT transition_id FROM transitions WHERE status = 'pendiente_registro' AND kind = 'cambio_estado' "
                    "ORDER BY created_at, transition_number"
                ).fetchall()
            ]
            for transition_id in acked:
                svc.send(transition_id, svc.pools.tx)
            self.h.registry.mode = mode
        if freeze_first or mode != "up":
            self.attempt(who, lambda svc: svc.freeze(BIAS, live, freeze_context(live, self.h.clock())))
        if ack_only:  # la TX2 del llamador original llega tarde, despues del freeze
            for transition_id in acked:
                self.h.services[who].finish(transition_id, self.h.services[who].pools.tx)
        if settle:  # el registro vuelve y llegan los acks (o se reenvian) despues del freeze
            self.h.registry.mode = "up"
            for _ in range(3):
                self.h.background["a"].reconcile_once()
                self.h.background["b"].reconcile_once()

    @precondition(lambda self: self.models_in("registrado", "validacion_fallida", "aprobado", "inactivo"))
    @rule(who=replica, other=replica, i=pick)
    def abandon_then_retry_when_the_abandoned_was_written(self, who: str, other: str, i: int) -> None:
        """BR-U4-17: el ack se pierde, la pendiente se abandona a las 24 h y una transicion nueva repite su llave."""
        ids = self.models_in("registrado", "validacion_fallida", "aprobado", "inactivo")
        model_id = ids[i % len(ids)]
        state = self.model_states()[model_id]
        n = int(self.h.clock().timestamp())

        def op(svc: Any) -> Any:
            if state == "registrado":
                return svc.start_validation(ING, model_id, job_name=f"job-{model_id}-{n}")
            if state == "validacion_fallida":
                return svc.retry_validation(ING, model_id, job_name=f"job-{model_id}-{n}")
            return svc.mark_active(ING, model_id)

        self.h.registry.mode = "lost_ack"
        self.attempt(who, op)
        self.h.registry.mode = "up"
        self.h.clock.advance(hours=25)
        self.h.background[who].reconcile_once()
        n += 1
        self.attempt(other, op)

    # --- modelos -----------------------------------------------------------------------------------------------------------

    @rule(who=replica, i=pick)
    def register(self, who: str, i: int) -> None:
        model_id = MODELS[i % len(MODELS)]
        self.attempt(who, lambda svc: svc.register(ING, new_model(model_id)))

    @precondition(lambda self: self.models_in("registrado", "validacion_fallida"))
    @rule(who=replica, i=pick)
    def start_validation(self, who: str, i: int) -> None:
        ids = self.models_in("registrado", "validacion_fallida")
        model_id = ids[i % len(ids)]
        retry = self.model_states()[model_id] == "validacion_fallida"
        job = f"job-{model_id}-{self.h.clock().timestamp():.0f}"
        self.attempt(
            who,
            lambda svc: svc.retry_validation(ING, model_id, job_name=job)
            if retry
            else svc.start_validation(ING, model_id, job_name=job),
        )

    @precondition(lambda self: self.models_in("en_validacion"))
    @rule(who=replica, i=pick, passed=st.booleans())
    def report_received(self, who: str, i: int, passed: bool) -> None:
        ids = self.models_in("en_validacion")
        model_id = ids[i % len(ids)]
        runs = self.h.admin.execute(
            "SELECT run_id FROM validation_runs WHERE model_version_id = %s AND state = 'lanzado'", (model_id,)
        ).fetchall()
        if runs:
            self.attempt(who, lambda svc: svc.receive_report(VALIDATION_JOB, model_id, str(runs[-1]["run_id"]), report(passed)))

    @precondition(lambda self: self.models_in("lista_para_aprobacion"))
    @rule(who=replica, i=pick, approve=st.booleans())
    def decide(self, who: str, i: int, approve: bool) -> None:
        ids = self.models_in("lista_para_aprobacion")
        model_id = ids[i % len(ids)]
        if approve:
            self.attempt(who, lambda svc: svc.approve(CRO1, model_id))
        else:
            self.attempt(who, lambda svc: svc.reject(CRO1, model_id, "no cumple"))

    @precondition(lambda self: self.models_in("aprobado", "inactivo"))
    @rule(who=replica, i=pick)
    def mark_active(self, who: str, i: int) -> None:
        ids = self.models_in("aprobado", "inactivo")
        model_id = ids[i % len(ids)]
        self.attempt(who, lambda svc: svc.mark_active(ING, model_id))

    @precondition(lambda self: self.models_in("activo"))
    @rule(who=replica, i=pick)
    def freeze(self, who: str, i: int) -> None:
        ids = self.models_in("activo")
        model_id = ids[i % len(ids)]
        result = self.attempt(who, lambda svc: svc.freeze(BIAS, model_id, freeze_context(model_id, self.h.clock())))
        if result is not None:  # BR-U4-15: el estado cambia aunque el registro este caido
            assert self.model_states()[model_id] == "congelado"

    @precondition(lambda self: self.models_in("congelado"))
    @rule(who=replica, i=pick, action=st.sampled_from(["reactivar", "descartar", "investigar"]))
    def resolve(self, who: str, i: int, action: str) -> None:
        ids = self.models_in("congelado")
        model_id = ids[i % len(ids)]
        self.attempt(who, lambda svc: svc.frozen_resolution(CUM, model_id, action, "revisado"))  # type: ignore[arg-type]

    @precondition(lambda self: self.models_in("inactivo", "rechazado", "validacion_fallida"))
    @rule(who=replica, i=pick)
    def retire(self, who: str, i: int) -> None:
        ids = self.models_in("inactivo", "rechazado", "validacion_fallida")
        model_id = ids[i % len(ids)]
        self.attempt(who, lambda svc: svc.retire(CRO1, model_id))

    # --- politicas ---------------------------------------------------------------------------------------------------------

    @rule(who=replica, i=pick)
    def propose_policy(self, who: str, i: int) -> None:
        policy_id = POLICIES[i % len(POLICIES)]
        self.attempt(who, lambda svc: svc.propose_policy(CRO1, policy_id, policy_draft()))

    @precondition(lambda self: self.policies_in("propuesta"))
    @rule(who=replica, i=pick, approve=st.booleans())
    def decide_policy(self, who: str, i: int, approve: bool) -> None:
        ids = self.policies_in("propuesta")
        policy_id = ids[i % len(ids)]
        if approve:
            self.attempt(who, lambda svc: svc.approve_policy(CRO2, policy_id))
        else:
            self.attempt(who, lambda svc: svc.reject_policy(CRO2, policy_id, "no"))

    # --- invariantes -------------------------------------------------------------------------------------------------------

    @invariant()
    def pbt_u4_07(self) -> None:
        check_pbt07(self.h.snapshot())


def test_pbt_u4_07_evidencia_con_el_registro_fallando_al_azar(pg: Any, template_db: str) -> None:
    EvidenceMachine.pg = pg
    EvidenceMachine.template = template_db
    run_state_machine_as_test(
        EvidenceMachine,
        settings=settings(max_examples=STATEFUL_EXAMPLES, stateful_step_count=STEPS, deadline=None, print_blob=True),
    )

    print("\nCOVERAGE", sorted(COVERAGE.items(), key=str))
