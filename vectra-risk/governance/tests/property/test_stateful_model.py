"""PBT-U4-01: la maquina de estados del modelo completa, con actores y MFA, contra la capa de servicio (Paso 8; PBT-06).

Para toda secuencia de acciones con actores arbitrarios (incluidos `bias-monitoring-job`, el Job de validacion, el sistema, `cro`
y `cumplimiento` con y sin MFA, y el registro caido o con el ack perdido) se cumplen siempre las invariantes de
business-logic-model §3, comprobadas con SQL sobre `transitions` y `model_versions`:

- a lo sumo una version `activo` o `congelado`;
- `congelado -> activo` solo ocurre con `cumplimiento` + MFA (`reactivar`);
- un `freeze` con un `mark_active` pendiente deja la version `congelado` y ninguna otra pasa a `activo` por ese `mark_active`,
  confirme o no el registro (una unidad con una mitad `descartada` no tiene ninguna `confirmada`);
- bias nunca produce un estado distinto de `congelado`;
- los estados terminales (`retirado`) no cambian;
- toda transicion confirmada esta en la tabla de BR-U4-01 con un actor que esa tabla permite.

Queda fuera la invariante de `source_candidate_for` (P-5 de `demo-recorte-funcional.md`: US-306 diferida, Q-6). Ademas de las
rechazadas por el actor, cada rechazo (`Forbidden`/`ConflictState`) deja la base sin ninguna fila nueva.

`HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_stateful_model.py`; los ejemplos son menos que los 500 del
perfil `ci` por el costo de PostgreSQL real (misma decision que U3), con las mismas invariantes.
"""

import os
from typing import Any

import pytest
from evidence_invariants import check_pbt01, check_pbt07
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
    report,
)
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule, run_state_machine_as_test
from vectra_contracts.catalog import Role
from vectra_governance.evidence import RegistryUnavailable
from vectra_governance.model_fsm import Actor, ConflictState, Forbidden

pytestmark = pytest.mark.integration

STATEFUL_EXAMPLES = int(os.environ.get("U4_STATEFUL_EXAMPLES", "25"))
STEPS = 40
MODELS = ["mv-1", "mv-2", "mv-3"]
ANALISTA = Actor("user", "ana-1", Role.ANALISTA, "mfa")
SYSTEM = Actor("system", "governance-service")
SCORING = Actor("service", "scoring-service")
NO_MFA = "pwd"
ACTORS = [
    ING,
    Actor("user", "ing-2", Role.INGENIERO_RIESGO, NO_MFA),
    CRO1,
    CRO2,
    Actor("user", "cro-3", Role.CRO, NO_MFA),
    CUM,
    Actor("user", "cum-2", Role.CUMPLIMIENTO, NO_MFA),
    ANALISTA,
    BIAS,
    Actor("service", "bias-monitoring-service"),  # el servicio HTTP no tiene `governance:freeze`
    VALIDATION_JOB,
    SYSTEM,
    SCORING,
]
any_actor = st.sampled_from(ACTORS)
pick = st.integers(0, 10_000)


def either(legit: Actor) -> st.SearchStrategy[Actor]:
    """La mitad de las veces el actor correcto (para llegar a estados profundos) y si no, uno cualquiera."""
    return st.one_of(st.just(legit), st.just(legit), any_actor)


class ModelMachine(RuleBasedStateMachine):
    pg: Any
    template: str

    def __init__(self) -> None:
        super().__init__()
        self.h = Harness(self.pg, self.template)
        self.retired: set[str] = set()

    def teardown(self) -> None:
        self.h.close()

    def states(self) -> dict[str, str]:
        return {r["model_version_id"]: r["state"] for r in self.h.admin.execute("SELECT * FROM model_versions").fetchall()}

    def models_in(self, *states: str) -> list[str]:
        return sorted(m for m, s in self.states().items() if s in states)

    def count_rows(self) -> int:
        row = self.h.admin.execute("SELECT count(*) AS n FROM transitions").fetchone()
        assert row is not None
        return int(row["n"])

    def attempt(self, op: Any) -> bool:
        """Cada rechazo (403/409) deja la base sin ninguna fila nueva; un 503 deja la transicion pendiente."""
        before = self.count_rows()
        try:
            op(self.h.services["a"])
        except (Forbidden, ConflictState):
            assert self.count_rows() == before, "un rechazo dejo filas"
            return False
        except RegistryUnavailable:
            return False
        return True

    # --- el registro -------------------------------------------------------------------------------------------------------

    @rule(mode=st.sampled_from(["up", "up", "up", "down", "lost_ack"]))
    def registry_mode(self, mode: str) -> None:
        self.h.registry.mode = mode

    @rule()
    def reconcile(self) -> None:
        self.h.background["b"].reconcile_once()

    # --- acciones con actores arbitrarios ------------------------------------------------------------------------------------

    @rule(i=pick, actor=either(ING))
    def register(self, i: int, actor: Actor) -> None:
        model_id = MODELS[i % len(MODELS)]
        self.attempt(lambda svc: svc.register(actor, new_model(model_id)))

    @precondition(lambda self: self.models_in("registrado", "validacion_fallida"))
    @rule(i=pick, actor=either(ING))
    def validate(self, i: int, actor: Actor) -> None:
        ids = self.models_in("registrado", "validacion_fallida")
        model_id = ids[i % len(ids)]
        retry = self.states()[model_id] == "validacion_fallida"
        job = f"job-{model_id}-{self.count_rows()}"
        self.attempt(
            lambda svc: svc.retry_validation(actor, model_id, job_name=job)
            if retry
            else svc.start_validation(actor, model_id, job_name=job)
        )

    @precondition(lambda self: self.models_in("en_validacion"))
    @rule(i=pick, actor=either(VALIDATION_JOB), passed=st.booleans())
    def validation_report(self, i: int, actor: Actor, passed: bool) -> None:
        ids = self.models_in("en_validacion")
        model_id = ids[i % len(ids)]
        runs = self.h.admin.execute(
            "SELECT run_id FROM validation_runs WHERE model_version_id = %s AND state = 'lanzado'", (model_id,)
        ).fetchall()
        if runs:
            self.attempt(lambda svc: svc.receive_report(actor, model_id, str(runs[-1]["run_id"]), report(passed)))

    @precondition(lambda self: self.models_in("lista_para_aprobacion"))
    @rule(i=pick, actor=either(CRO1), approve=st.booleans())
    def decide(self, i: int, actor: Actor, approve: bool) -> None:
        ids = self.models_in("lista_para_aprobacion")
        model_id = ids[i % len(ids)]
        self.attempt(
            (lambda svc: svc.approve(actor, model_id)) if approve else (lambda svc: svc.reject(actor, model_id, "no cumple"))
        )

    @precondition(lambda self: self.models_in("aprobado", "inactivo", "registrado", "congelado"))
    @rule(i=pick, actor=either(ING))
    def mark_active(self, i: int, actor: Actor) -> None:
        ids = self.models_in("aprobado", "inactivo", "registrado", "congelado")
        model_id = ids[i % len(ids)]
        self.attempt(lambda svc: svc.mark_active(actor, model_id))

    @precondition(lambda self: self.models_in("activo", "aprobado", "congelado"))
    @rule(i=pick, actor=either(BIAS))
    def freeze(self, i: int, actor: Actor) -> None:
        ids = self.models_in("activo", "aprobado", "congelado")
        model_id = ids[i % len(ids)]
        self.attempt(lambda svc: svc.freeze(actor, model_id, freeze_context(model_id, self.h.clock())))

    @precondition(lambda self: self.models_in("congelado", "activo"))
    @rule(i=pick, actor=either(CUM), action=st.sampled_from(["reactivar", "descartar", "investigar"]))
    def frozen_resolution(self, i: int, actor: Actor, action: str) -> None:
        ids = self.models_in("congelado", "activo")
        model_id = ids[i % len(ids)]
        self.attempt(lambda svc: svc.frozen_resolution(actor, model_id, action, "revisado"))  # type: ignore[arg-type]

    @precondition(lambda self: self.models_in("inactivo", "rechazado", "validacion_fallida", "registrado", "retirado"))
    @rule(i=pick, actor=either(CRO1))
    def retire(self, i: int, actor: Actor) -> None:
        ids = self.models_in("inactivo", "rechazado", "validacion_fallida", "registrado", "retirado")
        model_id = ids[i % len(ids)]
        self.attempt(lambda svc: svc.retire(actor, model_id))

    @precondition(lambda self: self.models_in("aprobado", "inactivo") and self.models_in("activo"))
    @rule(i=pick, mode=st.sampled_from(["down", "lost_ack", "up"]), bias=either(BIAS))
    def freeze_with_a_mark_active_in_flight(self, i: int, mode: str, bias: Actor) -> None:
        """El caso del diseno: un `mark_active` pendiente (sin ack o con el ack perdido) y un `freeze` de la activa."""
        live = self.models_in("activo")[0]
        candidates = self.models_in("aprobado", "inactivo")
        target = candidates[i % len(candidates)]
        self.h.registry.mode = mode
        self.attempt(lambda svc: svc.mark_active(ING, target))
        self.attempt(lambda svc: svc.freeze(bias, live, freeze_context(live, self.h.clock())))

    @rule(i=pick, actor=either(ING))
    def fast_forward(self, i: int, actor: Actor) -> None:
        """Lleva una version hacia `activo` con el actor correcto de cada paso (estados profundos)."""
        model_id = MODELS[i % len(MODELS)]
        for _ in range(5):
            state = self.states().get(model_id)
            run = self.h.admin.execute(
                "SELECT run_id FROM validation_runs WHERE model_version_id = %s AND state = 'lanzado'", (model_id,)
            ).fetchall()
            job = f"job-{model_id}-{self.count_rows()}"
            ops: dict[str | None, Any] = {
                None: lambda svc: svc.register(ING, new_model(model_id)),
                "registrado": lambda svc: svc.start_validation(ING, model_id, job_name=job),
                "validacion_fallida": lambda svc: svc.retry_validation(ING, model_id, job_name=job),
                "en_validacion": lambda svc: svc.receive_report(VALIDATION_JOB, model_id, str(run[-1]["run_id"]), report(True)),
                "lista_para_aprobacion": lambda svc: svc.approve(CRO1, model_id),
                "aprobado": lambda svc: svc.mark_active(ING, model_id),
                "inactivo": lambda svc: svc.mark_active(ING, model_id),
            }
            if (state == "en_validacion" and not run) or ops.get(state) is None or not self.attempt(ops[state]):
                return

    # --- invariantes -------------------------------------------------------------------------------------------------------

    @invariant()
    def pbt_u4_01(self) -> None:
        snap = self.h.snapshot()
        check_pbt01(snap, self.retired)
        check_pbt07(snap)  # la maquina tambien respeta la evidencia


def test_pbt_u4_01_maquina_completa_con_actores_y_mfa(pg: Any, template_db: str) -> None:
    ModelMachine.pg = pg
    ModelMachine.template = template_db
    run_state_machine_as_test(
        ModelMachine,
        settings=settings(max_examples=STATEFUL_EXAMPLES, stateful_step_count=STEPS, deadline=None, print_blob=True),
    )
