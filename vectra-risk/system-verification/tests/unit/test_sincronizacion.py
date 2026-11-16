"""CA-3 de U12-T09: los casos en `en_sincronizacion` (el worker los dejo para reintentar) se esperan, y los que siguen asi al vencer el plazo se cuentan y se nombran.

`sim_normal.read_cases` solo sondeaba `en_evaluacion` (`CANDIDATAS.md`, matiz de U12-T03): un caso en `en_sincronizacion` no se esperaba y el conductor no lo decidia. Los nombres llevan `sincronizacion` para el filtro `-k` del criterio.
"""

from __future__ import annotations

from types import SimpleNamespace

from fake_clock import FakeClock

from vectra_verification.clients._api import ApiError
from vectra_verification.scenarios import sim_normal


class StatesBff:
    """Un BFF de mentira: `script[case_id]` es la lista de estados que da cada lectura (el ultimo se repite)."""

    def __init__(self, script: dict[str, list[tuple[str, str | None]]]) -> None:
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: dict[str, int] = {k: 0 for k in script}

    def get_case(self, case_id: str) -> SimpleNamespace:
        if case_id not in self.script:
            raise ApiError(404, "not_found")
        states = self.script[case_id]
        index = min(self.calls[case_id], len(states) - 1)
        self.calls[case_id] += 1
        state, cause = states[index]
        return SimpleNamespace(state=state, last_cause=cause)


def test_sincronizacion_a_case_that_returns_to_listo_is_waited_for_and_read_as_listo() -> None:
    bff = StatesBff(
        {
            "a": [("listo", None)],
            "b": [("en_sincronizacion", "timeout"), ("en_sincronizacion", "timeout"), ("listo", None)],
        }
    )
    clock = FakeClock()
    reads = sim_normal.read_cases(bff, clock, ["a", "b"])  # type: ignore[arg-type]
    assert reads["b"].state == "listo" and bff.calls["b"] == 3
    assert bff.calls["a"] == 1  # el que ya esta en `listo` no se vuelve a leer
    assert sum(clock.sleeps) >= 2 * sim_normal.EVALUATION_POLL


def test_sincronizacion_a_case_that_stays_there_is_read_once_per_sweep_until_the_deadline() -> None:
    bff = StatesBff({"b": [("en_sincronizacion", "timeout")]})
    clock = FakeClock()
    reads = sim_normal.read_cases(bff, clock, ["b"], timeout=60.0)  # type: ignore[arg-type]
    assert reads["b"].state == "en_sincronizacion" and reads["b"].cause == "timeout"
    assert bff.calls["b"] > 1 and sum(clock.sleeps) >= 59.0


def test_sincronizacion_the_counts_after_the_wait_name_each_waiting_state() -> None:
    reads = {
        "a": sim_normal.CaseRead("listo"),
        "b": sim_normal.CaseRead("en_sincronizacion", "timeout"),
        "c": sim_normal.CaseRead("en_evaluacion"),
        "d": sim_normal.CaseRead("en_sincronizacion", "timeout"),
    }
    assert sim_normal.waiting_counts(reads) == {"en_evaluacion": 1, "en_sincronizacion": 2}
