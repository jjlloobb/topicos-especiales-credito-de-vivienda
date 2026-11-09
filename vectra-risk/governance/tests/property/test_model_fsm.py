"""PBT-U4-02 y ejemplos de BR-U4-01, BR-U4-02, BR-U4-04 y BR-U4-10 (US-203, US-305). Paso 3, `model_fsm`.

El oraculo `ORACLE` es una tabla escrita aparte, copiada de BR-U4-01 (`business-rules.md` §1). No importa la tabla del
modulo: si la importara, la prueba compararia el modulo consigo mismo.
"""

from __future__ import annotations

import itertools
from typing import Final

import pytest
from hypothesis import given
from hypothesis import strategies as st
from vectra_contracts.catalog import Role

from vectra_governance.model_fsm import (
    ACTIONS,
    Actor,
    ConflictState,
    Forbidden,
    ModelContext,
    transition,
)

STATES: Final = (
    None,
    "registrado",
    "en_validacion",
    "validacion_fallida",
    "lista_para_aprobacion",
    "aprobado",
    "rechazado",
    "activo",
    "inactivo",
    "congelado",
    "retirado",
)

# (desde, accion, hacia, actores). Un actor de rol se escribe `<rol>+mfa` (acr = mfa) o `<rol>` (sin MFA).
ORACLE: Final = [
    (None, "register", "registrado", {"ingeniero_riesgo+mfa"}),
    ("registrado", "start_validation", "en_validacion", {"ingeniero_riesgo+mfa"}),
    ("en_validacion", "validation_passed", "lista_para_aprobacion", {"model-validation-job"}),
    ("en_validacion", "validation_failed", "validacion_fallida", {"model-validation-job", "sistema"}),
    ("validacion_fallida", "retry_validation", "en_validacion", {"ingeniero_riesgo+mfa"}),
    ("lista_para_aprobacion", "approve", "aprobado", {"cro+mfa"}),
    ("lista_para_aprobacion", "reject", "rechazado", {"cro+mfa"}),
    ("aprobado", "mark_active", "activo", {"ingeniero_riesgo+mfa"}),
    ("inactivo", "mark_active", "activo", {"ingeniero_riesgo+mfa"}),
    ("activo", "deactivate", "inactivo", {"sistema"}),
    ("activo", "freeze", "congelado", {"bias-monitoring-job"}),
    ("congelado", "reactivar", "activo", {"cumplimiento+mfa"}),
    ("congelado", "descartar", "retirado", {"cumplimiento+mfa"}),
    ("congelado", "investigar", "congelado", {"cumplimiento+mfa"}),
    ("inactivo", "retire", "retirado", {"cro+mfa"}),
    ("rechazado", "retire", "retirado", {"cro+mfa"}),
    ("validacion_fallida", "retire", "retirado", {"cro+mfa"}),
]

ACTORS: Final[dict[str, Actor]] = {
    **{
        label: Actor("user", f"sub-{role.value}", role, "mfa" if mfa else "pwd")
        for role in Role
        for mfa in (True, False)
        for label in [f"{role.value}+mfa" if mfa else role.value]
    },
    "bias-monitoring-job": Actor("service", "bias-monitoring-job"),
    "model-validation-job": Actor("service", "model-validation-job"),
    "scoring-service": Actor("service", "scoring-service"),
    "sistema": Actor("system", "governance-service"),
}
CLEAN = ModelContext(registered_by="sub-registrant")


def oracle(state: str | None, action: str, label: str) -> str | type[Forbidden] | type[ConflictState]:
    """Resultado esperado segun BR-U4-01: actor equivocado -> 403; estado equivocado -> 409 (actor primero)."""
    rows = [row for row in ORACLE if row[1] == action]
    if label not in set().union(*(row[3] for row in rows)):
        return Forbidden
    for desde, _, hacia, _actors in rows:
        if desde == state:
            return hacia
    return ConflictState


def run(state: str | None, action: str, actor: Actor, context: ModelContext = CLEAN) -> object:
    try:
        return transition(state, action, actor, context)  # type: ignore[arg-type]
    except (Forbidden, ConflictState) as error:
        return type(error)


def test_actions_are_the_oracle_actions() -> None:
    assert set(ACTIONS) == {row[1] for row in ORACLE}


def test_pbt_u4_02_full_product_matches_the_oracle() -> None:
    """PBT-U4-02: estados x acciones x actores (con y sin MFA); 11 x 14 x 12 = 1 848 combinaciones."""
    combos = list(itertools.product(STATES, ACTIONS, ACTORS))
    assert len(combos) == 11 * 14 * 12
    for state, action, label in combos:
        assert run(state, action, ACTORS[label]) == oracle(state, action, label), (state, action, label)


def test_every_oracle_row_is_reachable_by_its_actors_only() -> None:
    """Cada fila del oraculo pasa con sus actores, y con ningun otro actor."""
    for desde, action, hacia, allowed in ORACLE:
        for label in ACTORS:
            got = run(desde, action, ACTORS[label])
            assert (got == hacia) == (label in allowed), (desde, action, label)


_context = st.builds(
    ModelContext,
    registered_by=st.sampled_from(["sub-registrant", "sub-cro", "sub-ingeniero_riesgo"]),
    source_candidate_for=st.sampled_from([None, "ds-1"]),
    source_state=st.sampled_from([None, "propuesta", "en_evaluacion", "aprobada", "rechazada"]),
    other_servable=st.sampled_from([None, "activo", "congelado"]),
)


def oracle_with_context(state: str | None, action: str, label: str, context: ModelContext) -> object:
    """Las condiciones de BR-U4-01 (fuente), BR-U4-02 y BR-U4-10; despues de actor y estado, en este orden."""
    base = oracle(state, action, label)
    if base in (Forbidden, ConflictState):
        return base
    if action == "approve":
        if context.registered_by is None or ACTORS[label].id == context.registered_by:
            return ConflictState
        if context.source_candidate_for is not None and context.source_state != "aprobada":
            return ConflictState
    if action == "mark_active":
        if (
            state == "aprobado"
            and context.source_candidate_for is not None
            and context.source_state != "aprobada"
        ):
            return ConflictState
        if context.other_servable == "congelado":
            return ConflictState
    return base


@given(
    state=st.sampled_from(STATES),
    action=st.sampled_from(ACTIONS),
    label=st.sampled_from(sorted(ACTORS)),
    context=_context,
)
def test_pbt_u4_02_with_context_matches_the_oracle(
    state: str | None, action: str, label: str, context: ModelContext
) -> None:
    assert run(state, action, ACTORS[label], context) == oracle_with_context(state, action, label, context)


# --- Ejemplos -------------------------------------------------------------------------------------------------------


def test_us_203_cro_approves_and_ingeniero_does_not() -> None:
    cro, ing = ACTORS["cro+mfa"], ACTORS["ingeniero_riesgo+mfa"]
    assert transition("lista_para_aprobacion", "approve", cro, CLEAN) == "aprobado"
    with pytest.raises(Forbidden):
        transition("lista_para_aprobacion", "approve", ing, CLEAN)


def test_us_203_cro_without_mfa_is_forbidden() -> None:
    with pytest.raises(Forbidden):
        transition("lista_para_aprobacion", "approve", ACTORS["cro"], CLEAN)


@pytest.mark.parametrize("action", ["reactivar", "descartar", "investigar"])
def test_us_305_only_cumplimiento_with_mfa_resolves_a_freeze(action: str) -> None:
    expected = {"reactivar": "activo", "descartar": "retirado", "investigar": "congelado"}[action]
    assert transition("congelado", action, ACTORS["cumplimiento+mfa"], CLEAN) == expected  # type: ignore[arg-type]
    for label in ("cumplimiento", "cro+mfa", "cro", "bias-monitoring-job", "model-validation-job", "sistema"):
        with pytest.raises(Forbidden):
            transition("congelado", action, ACTORS[label], CLEAN)  # type: ignore[arg-type]


def test_br_u4_01_wrong_actor_is_403_and_wrong_state_is_409() -> None:
    with pytest.raises(Forbidden):
        transition("aprobado", "mark_active", ACTORS["cro+mfa"], CLEAN)
    with pytest.raises(ConflictState):
        transition("registrado", "mark_active", ACTORS["ingeniero_riesgo+mfa"], CLEAN)


def test_br_u4_01_when_actor_and_state_both_fail_the_actor_wins() -> None:
    """Orden fijado (docstring de `transition`): actor equivocado -> Forbidden aunque el estado tambien lo este."""
    with pytest.raises(Forbidden):
        transition("registrado", "approve", ACTORS["ingeniero_riesgo+mfa"], CLEAN)
    with pytest.raises(Forbidden):
        transition("retirado", "freeze", ACTORS["cro+mfa"], CLEAN)


def test_br_u4_01_congelado_to_inactivo_is_rejected() -> None:
    """Candidata F-03 de U04-T01: `congelado -> inactivo` no esta en BR-U4-01, ningun actor ni accion la produce."""
    for action in ACTIONS:
        for label, actor in ACTORS.items():
            try:
                result = transition("congelado", action, actor, CLEAN)
            except (Forbidden, ConflictState):
                continue
            assert result != "inactivo", (action, label)
    with pytest.raises(ConflictState):
        transition("congelado", "deactivate", ACTORS["sistema"], CLEAN)


def test_br_u4_01_terminal_states_do_not_change() -> None:
    for action in ACTIONS:
        for label, actor in ACTORS.items():
            assert run("retirado", action, actor) in (Forbidden, ConflictState), (action, label)


def test_br_u4_01_us_306_candidate_needs_an_approved_source() -> None:
    cro, ing = ACTORS["cro+mfa"], ACTORS["ingeniero_riesgo+mfa"]
    for source_state in ("en_evaluacion", "propuesta", "rechazada", None):
        context = ModelContext(
            registered_by="sub-registrant", source_candidate_for="ds-1", source_state=source_state
        )
        with pytest.raises(ConflictState):
            transition("lista_para_aprobacion", "approve", cro, context)
        with pytest.raises(ConflictState):
            transition("aprobado", "mark_active", ing, context)
    approved = ModelContext(
        registered_by="sub-registrant", source_candidate_for="ds-1", source_state="aprobada"
    )
    assert transition("lista_para_aprobacion", "approve", cro, approved) == "aprobado"
    assert transition("aprobado", "mark_active", ing, approved) == "activo"


def test_br_u4_02_mark_active_with_another_frozen_version_is_409() -> None:
    ing = ACTORS["ingeniero_riesgo+mfa"]
    frozen = ModelContext(registered_by="sub-registrant", other_servable="congelado")
    with pytest.raises(ConflictState) as error:
        transition("aprobado", "mark_active", ing, frozen)
    assert error.value.reason == "active_version_frozen"
    with pytest.raises(ConflictState):
        transition("inactivo", "mark_active", ing, frozen)  # el rollback tampoco reemplaza un congelado
    other_active = ModelContext(registered_by="sub-registrant", other_servable="activo")
    assert (
        transition("aprobado", "mark_active", ing, other_active) == "activo"
    )  # el activo pasa a inactivo (BR-U4-08)


def test_br_u4_04_bias_only_freezes_an_active_version() -> None:
    """BR-U4-04 (X04): `bias-monitoring-job` solo produce `freeze` y solo sobre `activo`."""
    bias = ACTORS["bias-monitoring-job"]
    assert transition("activo", "freeze", bias, CLEAN) == "congelado"
    for action in ACTIONS:
        if action == "freeze":
            continue
        for state in STATES:
            with pytest.raises(Forbidden):
                transition(state, action, bias, CLEAN)
    for state in STATES:
        if state != "activo":
            with pytest.raises(ConflictState):
                transition(state, "freeze", bias, CLEAN)


def test_br_u4_04_bias_never_produces_a_state_other_than_congelado() -> None:
    bias = ACTORS["bias-monitoring-job"]
    results = {run(state, action, bias) for state in STATES for action in ACTIONS}
    assert results - {Forbidden, ConflictState} == {"congelado"}


def test_br_u4_10_cro_approving_what_he_registered_is_409() -> None:
    cro = ACTORS["cro+mfa"]
    with pytest.raises(ConflictState) as error:
        transition("lista_para_aprobacion", "approve", cro, ModelContext(registered_by=cro.id))
    assert error.value.reason == "approver_is_registrant"
    assert (
        transition("lista_para_aprobacion", "approve", cro, ModelContext(registered_by="otro")) == "aprobado"
    )


def test_br_u4_10_without_registered_by_the_check_cannot_pass_silently() -> None:
    """`approve` sin `registered_by` en el contexto no puede comparar: falla cerrado."""
    with pytest.raises(ConflictState):
        transition("lista_para_aprobacion", "approve", ACTORS["cro+mfa"], ModelContext())
