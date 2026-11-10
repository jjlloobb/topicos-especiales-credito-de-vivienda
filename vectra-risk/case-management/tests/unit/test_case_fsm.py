"""Paso 4: BR-U8-12 (US-107, US-112). Una prueba por fila, rechazo exhaustivo y comparacion con `case_transitions` de la migracion."""

import importlib.util
import itertools
from pathlib import Path

import pytest

from vectra_case.case_fsm import TERMINAL, TRANSITIONS, CaseEvent, Rechazo, transition
from vectra_contracts.catalog import CaseState

S = CaseState
E = CaseEvent
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0003_guards.py"

# Las 10 filas de BR-U8-12, escritas aparte de la implementacion: (estados de partida, evento, llegada).
ROWS = [
    ([None], E.ALTA, S.EN_EVALUACION),
    ([S.EN_EVALUACION, S.EN_SINCRONIZACION], E.RECOMMENDATION, S.LISTO),
    ([S.EN_EVALUACION, S.EN_SINCRONIZACION], E.RETRYABLE_FAILURE, S.EN_SINCRONIZACION),
    ([S.EN_SINCRONIZACION], E.ATTEMPT_6_FAILED, S.NO_DISPONIBLE),
    ([S.EN_EVALUACION, S.EN_SINCRONIZACION], E.SCORING_REJECTED, S.NO_DISPONIBLE),
    ([S.EN_EVALUACION, S.EN_SINCRONIZACION], E.MODEL_FROZEN, S.MODELO_CONGELADO),
    ([S.MODELO_CONGELADO], E.SWEEP_ACTIVE, S.EN_EVALUACION),
    ([S.NO_DISPONIBLE], E.RETRY, S.EN_EVALUACION),
    ([S.LISTO], E.DECISION_CONFIRMED, S.DECIDIDO),
    (
        [S.EN_EVALUACION, S.LISTO, S.EN_SINCRONIZACION, S.NO_DISPONIBLE, S.MODELO_CONGELADO],
        E.RETENTION_EXPIRED,
        S.VENCIDO,
    ),
]
ACCEPTED = {(src, ev): dst for sources, ev, dst in ROWS for src in sources}


@pytest.mark.parametrize(("sources", "event", "target"), ROWS, ids=[r[1].value for r in ROWS])
def test_each_row_of_br_u8_12_is_accepted(sources, event, target):
    for source in sources:
        assert transition(source, event) is target


def test_there_are_ten_event_rows():
    assert len(ROWS) == 10
    assert {r[1] for r in ROWS} == set(CaseEvent)


def test_fsm_table_is_exactly_the_rows():
    assert TRANSITIONS == ACCEPTED


def test_every_pair_outside_the_table_is_rejected():
    """El universo: (7 estados + el alta) x 10 eventos; lo que no esta en las filas es `Rechazo`, sin muestreo."""
    universe = list(itertools.product([None, *CaseState], CaseEvent))
    assert len(universe) == 80
    rejected = 0
    for state, event in universe:
        result = transition(state, event)
        if (state, event) in ACCEPTED:
            assert result is ACCEPTED[(state, event)]
        else:
            assert result == Rechazo(state, event)
            rejected += 1
    assert rejected == 80 - len(ACCEPTED) == 80 - 18


def test_rechazo_is_a_value_not_an_exception():
    result = transition(S.DECIDIDO, E.RECOMMENDATION)
    assert isinstance(result, Rechazo)
    assert result.state is S.DECIDIDO
    assert result.event is E.RECOMMENDATION


@pytest.mark.parametrize("terminal", [S.DECIDIDO, S.VENCIDO])
def test_terminal_states_have_no_exit(terminal):
    assert terminal in TERMINAL
    assert all(isinstance(transition(terminal, e), Rechazo) for e in CaseEvent)
    assert not any(src is terminal for src, _ in TRANSITIONS)


def test_listo_is_never_evaluated_again():
    """Un caso `listo` solo sale por la decision o por la retencion (BR-U8-12)."""
    exits = {e: transition(S.LISTO, e) for e in CaseEvent if not isinstance(transition(S.LISTO, e), Rechazo)}
    assert exits == {E.DECISION_CONFIRMED: S.DECIDIDO, E.RETENTION_EXPIRED: S.VENCIDO}
    assert S.EN_EVALUACION not in exits.values()


def test_same_state_transition_is_a_valid_row():
    assert transition(S.EN_SINCRONIZACION, E.RETRYABLE_FAILURE) is S.EN_SINCRONIZACION


def _migration_pairs() -> set[tuple[str, str]]:
    spec = importlib.util.spec_from_file_location("case_migration_0003", MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {(a, b) for a, b, _role in module.CASE_TRANSITIONS}


def test_fsm_table_equals_case_transitions_of_the_migration():
    """Sin el rol y sin la fila de creacion (la cubre la rama INSERT del trigger). Igualdad de conjuntos, no inclusion."""
    fsm_pairs = {(src.value, dst.value) for (src, _ev), dst in TRANSITIONS.items() if src is not None}
    migration_pairs = _migration_pairs()
    assert len(migration_pairs) == 16
    assert fsm_pairs == migration_pairs
