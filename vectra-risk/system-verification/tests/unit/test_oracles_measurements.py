"""`SIM-NORMAL` (U12-T03, Paso 10; BR-U12-02, 06; domain-entities §4.1): el oraculo de la medicion con el BFF **real** en proceso y el reloj falso.

`LOGS-NO-PII` y `CASE-SIZE` estan diferidos por la demo (enmienda §3 U12, fila «10»): no hay pruebas de ellos.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from rt2_world import PROXY, REFERENCE, Rt2World
from vectra_verification import evidence, guard
from vectra_verification.guard import KIND
from vectra_verification.scenarios import outcome as outcome_module
from vectra_verification.scenarios import sim_normal
from vectra_verification.simulator import RunReport


@pytest.fixture
def world() -> Iterator[Rt2World]:
    built = Rt2World()
    built.add_model(REFERENCE, "activo")
    yield built
    built.close()


def report_of(
    case_ids: list[str],
    *,
    sent: int | None = None,
    accepted: int | None = None,
    rejected: dict[str, int] | None = None,
) -> RunReport:
    now = datetime(2026, 11, 13, 10, 0, tzinfo=UTC)
    count = len(case_ids)
    return RunReport(
        scenario="normal", sent=count if sent is None else sent, accepted=count if accepted is None else accepted, rejected_by_code=rejected or {},
        case_ids=tuple(case_ids), started_at=now, finished_at=now, generator_version="g", seed=1, sampling_seed=2, rate=10.0, run_prefix="3fa9c2d1",
        test_rows=18000, parquet_sha256="0" * 64, resends=0,
    )  # fmt: skip


def cases(world: Rt2World, count: int) -> list[str]:
    return [world.new_case("normal") for _ in range(count)]


def measure(world: Rt2World, report: RunReport, **kw: Any) -> outcome_module.Outcome:
    bff = world.sessions.reader("analista-1")
    return sim_normal.sim_normal(KIND, bff, world.clock, report, **kw)


def settle(world: Rt2World) -> None:
    world.clock.advance(60.0)  # los casos dejan `en_evaluacion` a los 10 s


def test_sim_normal_20_accepted_of_20_sent_with_20_distinct_cases_all_listo_passes(world: Rt2World) -> None:
    ids = cases(world, 20)
    settle(world)
    result = measure(world, report_of(ids))
    assert (
        result.result == "pasa"
        and result.missing == ()
        and result.readings["states"] == {"listo": 20}
        and result.readings["sent"] == result.readings["accepted"] == 20
    )


def test_sim_normal_accepted_below_sent_fails_with_the_rejected_by_code(world: Rt2World) -> None:
    ids = cases(world, 19)
    settle(world)
    result = measure(world, report_of(ids, sent=20, accepted=19, rejected={"validation_error": 1}))
    assert result.result == "falla" and result.missing == ("sim_normal_aceptadas_menor_que_enviadas",)
    assert "validation_error" in result.obtained and "19 de 20" in result.obtained


def test_sim_normal_a_repeated_case_id_or_fewer_ids_than_accepted_fails(world: Rt2World) -> None:
    ids = cases(world, 4)
    settle(world)
    assert (
        "sim_normal_case_id_repetido" in measure(world, report_of(ids + [ids[0]], sent=5, accepted=5)).missing
    )
    assert (
        "sim_normal_casos_distintos_de_aceptadas"
        in measure(world, report_of(ids, sent=5, accepted=5)).missing
    )


def test_sim_normal_decidido_fail_closed_and_modelo_congelado_cases_pass(world: Rt2World) -> None:
    ids = cases(world, 4)
    table = {
        ids[0]: ("decidido", None, 1),
        ids[1]: ("en_sincronizacion", "timeout", 1),
        ids[2]: ("modelo_congelado", None, 0),
        ids[3]: ("no_disponible", "scoring_unreachable", 6),
    }
    world.state_cases = lambda case_id, record: table[case_id]
    result = measure(world, report_of(ids))
    assert result.result == "pasa" and result.readings["states"] == {
        "decidido": 1,
        "en_sincronizacion": 1,
        "modelo_congelado": 1,
        "no_disponible": 1,
    }
    assert result.readings["causes"] == {"timeout": 1, "scoring_unreachable": 1}


def test_sim_normal_a_vencido_case_fails(world: Rt2World) -> None:
    ids = cases(world, 2)
    world.state_cases = lambda case_id, record: (
        ("vencido", None, 0) if case_id == ids[0] else ("listo", None, 1)
    )
    result = measure(world, report_of(ids))
    assert result.result == "falla" and result.missing == ("sim_normal_estado_vencido",)


def test_sim_normal_a_cause_outside_the_catalog_fails_and_a_fail_closed_without_cause_too(
    world: Rt2World,
) -> None:
    ids = cases(world, 1)
    world.state_cases = lambda case_id, record: ("en_sincronizacion", "sincronizando", 1)
    assert measure(world, report_of(ids)).missing == ("sim_normal_causa_fuera_del_catalogo",)
    world.state_cases = lambda case_id, record: ("no_disponible", None, 6)
    assert measure(world, report_of(ids)).missing == ("sim_normal_fail_closed_sin_causa",)


def test_sim_normal_a_case_still_en_evaluacion_after_the_deadline_fails_with_the_count_and_waits_with_the_fake_clock(
    world: Rt2World,
) -> None:
    ids = cases(world, 3)
    world.state_cases = lambda case_id, record: (
        ("en_evaluacion", None, 0) if case_id == ids[0] else ("listo", None, 1)
    )
    result = measure(world, report_of(ids), timeout=300.0)
    assert result.result == "falla" and result.missing == ("sim_normal_casos_en_evaluacion_tras_el_plazo",)
    assert "1 caso(s)" in result.obtained and sum(world.clock.sleeps) >= 299.0


def test_sim_normal_a_case_en_evaluacion_that_reaches_listo_within_the_deadline_passes(
    world: Rt2World,
) -> None:
    ids = cases(world, 3)  # `Rt2World.case_state`: `en_evaluacion` los primeros 10 s
    assert measure(world, report_of(ids)).result == "pasa"


def test_sim_normal_a_case_id_the_bff_does_not_know_fails(world: Rt2World) -> None:
    ids = cases(world, 2) + ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]
    settle(world)
    assert measure(world, report_of(ids)).missing == ("sim_normal_caso_desconocido",)


def test_sim_normal_the_bff_not_responding_is_no_ejecutado(world: Rt2World) -> None:
    ids = cases(world, 2)
    world.bff.doubles.case.fail(503)
    result = measure(world, report_of(ids))
    assert result.result == "no ejecutado" and result.missing == ("sim_normal_bff_no_responde",)


def test_sim_normal_the_result_has_counts_by_state_and_cause_and_no_applicant_data(world: Rt2World) -> None:
    ids = cases(world, 3)
    settle(world)
    text = outcome_module.to_text(measure(world, report_of(ids)))
    for forbidden in (
        "full_name",
        "document_number",
        "birth_date",
        "applicant_display",
        "monthly_income",
        "email",
    ):
        assert forbidden not in text
    assert '"states"' in text and '"causes"' in text


def test_sim_normal_2000_cases_are_read_at_most_20_per_second_in_seconds_of_real_time(
    dynamic_environment: guard.Environment,
) -> None:
    """Con el doble ligero del gateway (validado contra el contrato): 2 000 lecturas, el ritmo por usuario con el reloj falso y segundos de tiempo real."""
    import time

    from contract_world import LightGateway, case_detail_json
    from fake_clock import FakeClock
    from rt2_world import TAG
    from vectra_verification.clients.bff import BffClient

    class Analyst:
        user, step_up = "analista-1", False

        def bearer(self) -> str:
            return "tok-analista-1"

        def refresh(self) -> None:
            return None

    clock = FakeClock()
    light = LightGateway(clock)
    ids = [f"00000000-0000-4000-8000-{n:012d}" for n in range(2000)]
    for case_id in ids:
        light.cases[case_id] = case_detail_json(case_id, "listo", "favorable")
    bff = BffClient(dynamic_environment, Analyst(), TAG, transport=light)
    started = time.monotonic()
    result = sim_normal.sim_normal(dynamic_environment, bff, clock, report_of(ids))
    assert result.result == "pasa" and len(light.sent_at) == 2000
    window = max(sum(1 for s in light.sent_at if t <= s < t + 1.0) for t in light.sent_at[::20])
    assert window <= 20, f"{window} lecturas en un segundo"
    assert time.monotonic() - started < 30.0


def test_sim_normal_comparing_accepted_less_or_equal_to_sent_would_let_the_second_case_pass() -> None:
    """`accepted <= sent` seria un oraculo mas laxo: el caso `accepted < sent` ya esta cubierto arriba; aqui el juicio puro."""
    ids = [f"c{n}" for n in range(3)]
    reads = {i: sim_normal.CaseRead("listo") for i in ids}
    assert sim_normal.judge(4, 3, {"x": 1}, ids, reads).result == "falla"
    assert sim_normal.judge(3, 3, {}, ids, reads).result == "pasa"


# --- CA-13: el filtro de evidencias sobre lo que devuelven los escenarios ------------------------------------------------------------


def test_evidence_the_simulation_result_passes_the_filter_unchanged(world: Rt2World) -> None:
    ids = cases(world, 3)
    settle(world)
    text = outcome_module.to_text(measure(world, report_of(ids)))
    assert evidence.prepare(text, ["secreto-de-prueba-0123456789"]) == text


def test_leak_a_jwt_injected_into_a_result_is_caught_by_the_filter(world: Rt2World) -> None:
    from vectra_verification.report import PASA

    leaked = outcome_module.Outcome(
        "SIM-NORMAL", PASA, "e", "e", readings={"nota": "eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJ4In0.c2ln"}
    )
    with pytest.raises(evidence.EvidenceError, match="jwt"):
        evidence.prepare(outcome_module.to_text(leaked), [])


def test_the_sim_normal_in_staging_is_refused_without_reading_a_case(world: Rt2World) -> None:
    ids = cases(world, 1)
    bff = world.sessions.reader("analista-1")
    with pytest.raises(guard.GuardError):
        sim_normal.sim_normal(
            guard.Environment("prod", "x", "https://x/auth/realms/vectra"), bff, world.clock, report_of(ids)
        )
    assert PROXY not in world.models
