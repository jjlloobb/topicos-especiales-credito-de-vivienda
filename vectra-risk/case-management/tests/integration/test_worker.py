"""Paso 15: `job_queue`, `evaluation` y `worker` (BR-U8-05..09, 12; P-U8-01, 08, 09; INF-U8-06; NFR-U8-02, 03, 04, 11, 24; US-109, US-112).

PostgreSQL real con los roles de U1 (el worker corre como `case_worker`), dobles HTTP de governance, scoring y registro, y el reloj
simulado. Cada prueba que cambia estado afirma sobre la **lectura de vuelta** (`SELECT ... FROM cases`, `evaluation_jobs`, `evidence_outbox`).
"""

import asyncio
import json
import time
import uuid
from random import Random
from typing import Any

import pytest
from case_pg import Db
from u8_support import auth, insert_fail_closed, scalar
from vectra_case import metrics
from vectra_case.config import LEASE, MAX_ATTEMPTS
from vectra_case.db_gauges import DbGauges
from vectra_contracts.catalog import FailClosedCause
from worker_support import (
    World,
    attempts_total,
    bulk_cases,
    case_row,
    expire_case,
    job_count,
    job_row,
    new_case,
    outbox,
    worker_world,
)

pytestmark = pytest.mark.integration


def logs(out: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def _hist_total() -> float:
    from vectra_common.metrics import REGISTRY

    return REGISTRY.get_sample_value("vectra_case_time_to_ready_seconds_count") or 0.0


async def fail_n(w: World, case_id: uuid.UUID, n: int, behavior: Any = ("status", 503)) -> None:
    """`n` intentos seguidos que fallan, con el reloj saltando mas alla del backoff de cada uno."""
    for _ in range(n):
        w.scoring.by_case[case_id].append(behavior)
        taken = await w.step()
        assert taken is not None and taken.case_id == case_id
        w.clock.advance(minutes=20)


async def test_first_attempt_success_is_listo_with_attempts_1_and_the_job_is_deleted(db: Db) -> None:
    case_id = new_case(db)
    before_ready, before_metric = _hist_total(), attempts_total("recommendation", 1)
    async with worker_world(db) as w:
        taken = await w.step()
    assert taken is not None and taken.attempt == 1
    row = case_row(db, case_id)
    assert (row["state"], row["attempts"], row["recommendation_entry_id"], row["ever_degraded"]) == (
        "listo",
        1,
        "7",
        False,
    )
    assert job_count(db, case_id) == 0
    assert (
        scalar(db, "SELECT recommendation->>'kind' FROM cases WHERE case_id = %s", case_id)
        == "recommendation"
    )
    assert attempts_total("recommendation", 1) == before_metric + 1
    assert _hist_total() == before_ready + 1  # un `listo` al primer intento


async def test_recovery_at_attempt_3_is_listo_with_the_simulated_clock(db: Db) -> None:
    case_id = new_case(db)
    async with worker_world(db) as w:
        for n in (1, 2):
            w.scoring.by_case[case_id].append(("status", 503))
            assert (await w.step()) is not None
            row = case_row(db, case_id)
            assert (row["state"], row["attempts"], row["last_cause"], row["ever_degraded"]) == (
                "en_sincronizacion",
                n,
                "scoring_unreachable",
                True,
            )
            job = job_row(db, case_id)
            assert job is not None and job["locked_until"] is None and job["attempt"] == n
            assert job["run_at"] > w.clock()  # reprogramado con backoff
            assert await w.step() is None  # todavia no toca
            w.clock.advance(minutes=3)
        before = _hist_total()
        assert (await w.step()) is not None
    row = case_row(db, case_id)
    assert (row["state"], row["attempts"], row["last_cause"]) == ("listo", 3, "scoring_unreachable")
    assert job_count(db, case_id) == 0
    assert _hist_total() == before  # solo los `listo` al primer intento entran en el histograma


async def test_six_failures_escalate_to_no_disponible_with_gauge_1_and_one_fail_closed_entry(db: Db) -> None:
    case_id = new_case(db)
    async with worker_world(db) as w:
        await fail_n(w, case_id, 6)
        row = case_row(db, case_id)
        assert (row["state"], row["attempts"], row["last_cause"], row["escalation_count"]) == (
            "no_disponible",
            6,
            "scoring_unreachable",
            1,
        )
        assert job_count(db, case_id) == 0
        entries = outbox(db, case_id)
        assert len(entries) == 1 and entries[0][0] == "fail_closed"
        payload = entries[0][2]["payload"]
        assert (
            payload["local_cause"] == "scoring_unreachable"
            and payload["retryable"] is True
            and payload["attempt"] == 6
        )
        assert "cause" not in payload and payload["escalated_at"]
        assert entries[0][1] == uuid.uuid5(case_id, "fail_closed:1")
        await DbGauges(
            w.h.database
        ).refresh()  # un ciclo de `DbGauges` de `case-service` despues del escalamiento
        assert metrics.FAILCLOSED_PERSISTENT._value.get() == 1  # type: ignore[attr-defined]
        assert w.scoring.count(case_id) == 6


async def test_version_requested_different_from_scoring_is_fail_closed_version_mismatch_and_the_case_retries(
    db: Db,
) -> None:
    case_id = new_case(db)
    before = attempts_total("failclosed", 1)
    async with worker_world(db) as w:
        w.h.governance_handler.model_version_id = (
            "mv-2"  # governance ya sirve la nueva; scoring sigue en mv-1
        )
        assert (await w.step()) is not None
        row = case_row(db, case_id)
        assert (row["state"], row["last_cause"], row["attempts"]) == (
            "en_sincronizacion",
            "version_mismatch",
            1,
        )
        assert job_count(db, case_id) == 1
        assert w.scoring.requests[0].model_version_id == "mv-2"
        w.scoring.serving_version = "mv-2"  # la version nueva ya es visible para los dos
        w.clock.advance(minutes=2)
        w.h.governance_handler.model_version_id = "mv-2"
        assert (await w.step()) is not None
    assert case_row(db, case_id)["state"] == "listo"
    assert attempts_total("failclosed", 1) == before + 1


async def test_scoring_403_is_scoring_rejected_escalates_at_once_and_the_metric_rises(db: Db) -> None:
    case_id = new_case(db)
    before = attempts_total("scoring_rejected", 1)
    async with worker_world(db) as w:
        w.scoring.default = ("status", 403)
        assert (await w.step()) is not None
    row = case_row(db, case_id)
    assert (
        row["state"],
        row["attempts"],
        row["last_cause"],
        row["escalation_count"],
        row["ever_degraded"],
    ) == (
        "no_disponible",
        1,
        "scoring_rejected",
        1,
        True,
    )
    assert job_count(db, case_id) == 0 and w.scoring.calls == 1  # sin reintento
    payload = outbox(db, case_id)[0][2]["payload"]
    assert (
        payload["local_cause"] == "scoring_rejected"
        and payload["retryable"] is False
        and payload["attempt"] == 1
    )
    assert attempts_total("scoring_rejected", 1) == before + 1


async def test_a_401_once_retries_with_a_new_token_inside_the_same_attempt(db: Db) -> None:
    case_id = new_case(db)
    async with worker_world(db) as w:
        w.scoring.reject_token = "t1"
        assert (await w.step()) is not None
        assert w.token.invalidated == 1 and w.scoring.calls == 2
    row = case_row(db, case_id)
    assert (row["state"], row["attempts"]) == ("listo", 1)  # el 401 no consume uno de los 6


async def test_a_result_that_arrives_with_the_case_vencido_changes_nothing_and_is_logged(
    db: Db, capsys: pytest.CaptureFixture[str]
) -> None:
    case_id = new_case(db)
    async with worker_world(db) as w:
        taken = await w.queue.take()
        assert taken is not None
        expire_case(
            db, case_id
        )  # P-5 (a): el vencimiento lo aplica un apoyo de la prueba con el rol `case_retention`
        capsys.readouterr()
        assert await w.evaluator.run(taken) is False
    assert (
        case_row(db, case_id)["state"] == "vencido"
        and case_row(db, case_id)["recommendation_entry_id"] is None
    )
    discarded = [e for e in logs(capsys.readouterr().out) if e.get("event") == "evaluation.result_discarded"]
    assert len(discarded) == 1 and discarded[0]["case_id"] == str(case_id)


@pytest.mark.parametrize(
    ("behavior", "before"),
    [
        ("ok", 0),
        (("fail", FailClosedCause.MODEL_FROZEN), 0),
        (("status", 503), 0),  # reintentable: la reprogramacion tampoco pasa la guarda
        (("status", 503), 5),  # el intento 6: el escalamiento tampoco
        (("status", 403), 0),  # `scoring_rejected`: escala de inmediato, pero el caso ya esta `vencido`
    ],
    ids=["recommendation", "model_frozen", "retryable", "attempt_6", "rejected"],
)
async def test_every_kind_of_late_result_is_discarded_when_the_case_is_vencido_without_an_outbox_entry(
    db: Db, behavior: Any, before: int
) -> None:
    case_id = new_case(
        db, state="en_evaluacion" if before == 0 else "en_sincronizacion", attempts=before, job_attempt=before
    )
    async with worker_world(db) as w:
        taken = await w.queue.take()
        assert taken is not None and taken.attempt == before + 1
        expire_case(db, case_id)
        w.scoring.default = behavior
        assert await w.evaluator.run(taken) is False
    row = case_row(db, case_id)
    assert (
        row["state"] == "vencido" and row["recommendation_entry_id"] is None and row["escalation_count"] == 0
    )
    assert outbox(db, case_id) == [] and job_count(db, case_id) == 0


async def test_an_idle_worker_takes_a_new_job_within_600_ms(db: Db) -> None:
    async with worker_world(db) as w:
        task = asyncio.create_task(w.worker.run_forever())
        try:
            await asyncio.sleep(0.8)  # ocioso: ya sondeo al menos una vez con la cola vacia
            case_id = new_case(db)
            started = time.monotonic()
            while case_row(db, case_id)["attempts"] == 0 and time.monotonic() - started < 3:
                await asyncio.sleep(0.02)
            taken_after = time.monotonic() - started
        finally:
            w.worker.stop()
            await task
    assert taken_after <= 0.6, taken_after  # el sondeo es de 400 ms +- 100 ms (NFR-U8-04)
    assert case_row(db, case_id)["state"] == "listo"


async def test_16_jobs_in_flight_with_a_7_s_scoring_and_a_pool_of_5_never_wait_for_a_connection_nor_hold_a_transaction(
    db: Db,
) -> None:
    """NFR-U8-11: la toma es una transaccion corta y el worker no retiene conexion ni transaccion durante la llamada a scoring."""
    ids = bulk_cases(db, 16)
    async with worker_world(db, pool=5) as w:
        w.scoring.delay = 7.0
        task = asyncio.create_task(w.worker.run_forever())
        try:
            started = time.monotonic()
            while w.scoring.in_flight < 16 and time.monotonic() - started < 6:
                await asyncio.sleep(0.05)
            assert (
                w.scoring.in_flight == 16
            )  # los 16 llegaron a scoring: ninguno espero una conexion del pool de 5
            idle_in_tx = scalar(
                db,
                "SELECT count(*) FROM pg_stat_activity WHERE usename = 'case_worker' AND datname = %s "
                "AND state IN ('idle in transaction', 'idle in transaction (aborted)', 'active')",
                db.name,
            )
            assert idle_in_tx == 0  # la conexion volvio al pool antes de la llamada
        finally:
            w.worker.stop()
            await task  # espera las 16 llamadas en vuelo
    assert {case_row(db, i)["state"] for i in ids} == {"listo"}


async def test_a_stopped_worker_is_replaced_after_30_s_and_the_late_result_of_the_first_is_discarded(
    db: Db, capsys: pytest.CaptureFixture[str]
) -> None:
    case_id = new_case(db)
    async with worker_world(db) as w:
        first = await w.queue.take()  # el worker A toma y se detiene sin resultado
        assert first is not None and first.attempt == 1
        assert await w.queue.take() is None  # arrendado: nadie mas lo toma
        w.clock.advance(seconds=LEASE + 1)
        second = await w.queue.take()  # el worker B lo retoma al vencer el arrendamiento
        assert second is not None and second.attempt == 2
        assert case_row(db, case_id)["attempts"] == 2
        w.scoring.by_case[case_id].append(("status", 503))
        await w.evaluator.run(second)  # B: falla -> `en_sincronizacion`
        capsys.readouterr()
        assert (
            await w.evaluator.run(first) is False
        )  # el resultado tardio de A (una `Recommendation`) no pasa la guarda
    row = case_row(db, case_id)
    assert (row["state"], row["attempts"], row["last_cause"]) == (
        "en_sincronizacion",
        2,
        "scoring_unreachable",
    )
    assert job_count(db, case_id) == 1
    discarded = [e for e in logs(capsys.readouterr().out) if e.get("event") == "evaluation.result_discarded"]
    assert len(discarded) == 1


async def test_worker_lost_at_attempt_6_escalates_on_the_take_without_calling_scoring_or_breaking_the_check(
    db: Db,
) -> None:
    case_id = new_case(
        db, state="en_sincronizacion", attempts=6, job_attempt=6, last_cause="scoring_unreachable"
    )
    async with worker_world(db) as w:
        assert await w.queue.take() is None  # escala en la toma
        assert w.scoring.calls == 0
    row = case_row(db, case_id)
    assert (
        row["state"],
        row["attempts"],
        row["last_cause"],
        row["escalation_count"],
        row["ever_degraded"],
    ) == (
        "no_disponible",
        6,
        "scoring_unreachable",
        1,
        True,
    )
    assert job_count(db, case_id) == 0
    entries = outbox(db, case_id)
    assert len(entries) == 1 and entries[0][2]["payload"]["local_cause"] == "scoring_unreachable"
    assert entries[0][2]["payload"]["attempt"] == 6 and entries[0][2]["payload"]["retryable"] is True


async def test_a_worker_lost_in_the_six_attempts_without_any_result_escalates_from_en_evaluacion(
    db: Db,
) -> None:
    """P-1 (a): `en_evaluacion` + `attempt_6_failed`. Seis tomas sin resultado, y la septima escala sin incrementar."""
    case_id = new_case(db)
    async with worker_world(db) as w:
        for n in range(1, MAX_ATTEMPTS + 1):
            taken = await w.queue.take()
            assert taken is not None and taken.attempt == n
            assert (
                case_row(db, case_id)["attempts"] == n and case_row(db, case_id)["state"] == "en_evaluacion"
            )
            w.clock.advance(seconds=LEASE + 1)
        assert await w.queue.take() is None
    row = case_row(db, case_id)
    assert (row["state"], row["attempts"], row["last_cause"]) == ("no_disponible", 6, "scoring_unreachable")
    assert w.scoring.calls == 0


async def test_escalation_with_the_same_fail_closed_key_already_present_leaves_no_disponible_and_commits(
    db: Db,
) -> None:
    case_id = new_case(db, state="en_sincronizacion", attempts=6, job_attempt=6)
    insert_fail_closed(
        db, case_id, 1
    )  # la llave `fail_closed:1` ya esta (commit incierto del escalamiento anterior)
    async with worker_world(db) as w:
        assert await w.queue.take() is None
    assert (
        case_row(db, case_id)["state"] == "no_disponible" and case_row(db, case_id)["escalation_count"] == 1
    )
    assert len(outbox(db, case_id)) == 1 and job_count(db, case_id) == 0


async def test_a_job_whose_case_already_left_the_loop_is_dropped_on_the_take(db: Db) -> None:
    case_id = new_case(db, state="listo", job_attempt=0)  # un trabajo huerfano de un caso `listo`
    async with worker_world(db) as w:
        assert await w.queue.take() is None
    assert job_count(db, case_id) == 0 and case_row(db, case_id)["state"] == "listo"


async def test_a_lost_attempt_6_of_a_case_that_left_the_loop_drops_the_job_without_a_fail_closed(
    db: Db,
) -> None:
    case_id = new_case(db, state="decidido", attempts=6, job_attempt=6)
    async with worker_world(db) as w:
        assert await w.queue.take() is None
    assert job_count(db, case_id) == 0 and outbox(db, case_id) == []


@pytest.mark.parametrize(
    ("behavior", "config_down", "expect"),
    [
        (("status", 403), False, {"local_cause": "scoring_rejected", "retryable": False}),
        (("status", 503), False, {"local_cause": "scoring_unreachable", "retryable": True}),
        ("drop", True, {"local_cause": "serving_config_unavailable", "retryable": True}),
        (("fail", FailClosedCause.TIMEOUT), False, {"cause": "timeout", "retryable": True}),
    ],
    ids=["rejected", "unreachable", "serving_config_unavailable", "failclosed_cause"],
)
async def test_the_fail_closed_entry_of_the_worker_is_confirmed_by_the_reconciler_against_the_registry_double(
    db: Db, behavior: Any, config_down: bool, expect: dict[str, Any]
) -> None:
    case_id = new_case(db, state="en_sincronizacion", attempts=5, job_attempt=5)
    async with worker_world(db) as w:
        w.scoring.default = behavior
        w.h.governance_handler.down = config_down
        assert (await w.step()) is not None  # el intento 6 falla (o es rechazado): escala
        assert case_row(db, case_id)["state"] == "no_disponible"
        w.h.governance_handler.down = False
        await w.h.reconciler.run_once()  # el reconciliador (`case_app`) la envia al doble del registro
    sent = w.h.registry.of_type("fail_closed")
    assert len(sent) == 1
    entry = sent[0]["entry"]
    payload = entry.payload
    assert (payload.cause is None) != (payload.local_cause is None)  # exactamente uno
    assert {
        k: (v.value if hasattr(v, "value") else v) for k, v in payload.model_dump().items() if k in expect
    } == expect
    assert payload.retryable is (expect["retryable"]) and payload.escalated_at is not None
    assert entry.actor.id == "case-worker"
    states = db.query("SELECT state, registry_entry_id FROM evidence_outbox WHERE case_id = %s", case_id)
    assert states == [("confirmada", sent[0]["registry_entry_id"])]


async def test_first_attempt_failure_ratio_of_a_scoring_double_that_fails_30_percent_is_0_3_plus_or_minus_0_05(
    db: Db,
) -> None:
    """P-U8-08 (`CaseFirstAttemptFailureHigh`, P-3 (a) de U08-T04): la razon se calcula desde los contadores del proceso, con la definicion de NFR-U8-03 (intentos 1 que no terminaron en
    `recommendation` / intentos 1), sobre 300 casos y con semilla fija. En PromQL (la regla de grabacion es del Paso 21):
    `sum(rate(vectra_case_attempts_total{attempt="1",result!="recommendation"}[5m])) / sum(rate(vectra_case_attempts_total{attempt="1"}[5m]))`.
    """
    n = 300
    ids = bulk_cases(db, n)
    rng = Random(20261112)
    results = (
        "recommendation",
        "failclosed",
        "model_frozen",
        "scoring_unreachable",
        "serving_config_unavailable",
        "scoring_rejected",
    )
    before = {r: attempts_total(r, 1) for r in results}
    async with worker_world(db) as w:
        failing = 0
        for case_id in ids:
            if rng.random() < 0.3:
                # `FailClosed` 200 y no un 503: los 5xx abririan el breaker de scoring (ratio >= 0,5 en 20 llamadas) en una racha larga
                w.scoring.by_case[case_id].append(("fail", FailClosedCause.TIMEOUT))
                failing += 1
        for _ in ids:
            assert (await w.step()) is not None
    delta = {r: attempts_total(r, 1) - before[r] for r in results}
    total = sum(delta.values())
    failed = total - delta["recommendation"]
    assert total == n and failed == failing
    ratio = failed / total
    assert abs(ratio - 0.3) <= 0.05, (ratio, delta)


async def test_first_evaluation_is_true_only_on_attempt_1_of_a_case_that_never_degraded(db: Db) -> None:
    case_id = new_case(db)
    async with worker_world(db) as w:
        w.scoring.by_case[case_id].append(("status", 503))
        await w.step()
        w.clock.advance(minutes=3)
        await w.step()
    assert [r.first_evaluation for r in w.scoring.requests] == [True, False]
    assert [r.attempt for r in w.scoring.requests] == [1, 2]
    assert case_row(db, case_id)["ever_degraded"] is True  # nunca vuelve a `false`
    created = scalar(db, "SELECT created_at FROM cases WHERE case_id = %s", case_id)
    assert {r.received_at for r in w.scoring.requests} == {
        created
    }  # `received_at` es el `created_at` del caso en todos los intentos


async def test_a_thawed_case_with_attempts_0_is_not_a_first_evaluation(db: Db) -> None:
    case_id = new_case(
        db, ever_degraded=True
    )  # descongelado: `attempts = 0`, trabajo nuevo, `ever_degraded` ya `true`
    async with worker_world(db) as w:
        await w.step()
    assert [(r.attempt, r.first_evaluation) for r in w.scoring.requests] == [(1, False)]
    assert case_row(db, case_id)["ever_degraded"] is True


async def test_a_case_retried_by_the_cro_from_no_disponible_is_not_a_first_evaluation(db: Db) -> None:
    case_id = new_case(db)
    async with worker_world(db) as w:
        w.scoring.default = ("status", 403)
        await w.step()  # `scoring_rejected`: no_disponible, ever_degraded
        assert case_row(db, case_id)["state"] == "no_disponible"
        w.scoring.default = "ok"
        retry = await w.h.client.post(
            f"/v1/cases/{case_id}/retry", headers=auth("cro")
        )  # case-service: `retry` del CRO
        assert retry.status_code == 200, retry.text
        assert case_row(db, case_id)["state"] == "en_evaluacion" and case_row(db, case_id)["attempts"] == 0
        await w.step()
    assert [(r.attempt, r.first_evaluation) for r in w.scoring.requests] == [(1, True), (1, False)]
    assert case_row(db, case_id)["state"] == "listo"


async def test_fail_closed_model_frozen_is_modelo_congelado_without_job_and_after_the_sweep_the_attempt_is_not_first(
    db: Db,
) -> None:
    case_id = new_case(db)
    before = attempts_total("model_frozen", 1)
    async with worker_world(db) as w:
        w.scoring.by_case[case_id].append(("fail", FailClosedCause.MODEL_FROZEN))
        await w.step()
        row = case_row(db, case_id)
        assert (row["state"], row["attempts"], row["ever_degraded"]) == ("modelo_congelado", 0, True)
        assert job_count(db, case_id) == 0 and outbox(db, case_id) == []  # no escala: espera al barrido
        assert attempts_total("model_frozen", 1) == before + 1
        await (
            w.h.sweeper.run_once()
        )  # U08-T03: `serving-config` activo -> `en_evaluacion`, `attempts = 0`, trabajo nuevo
        assert case_row(db, case_id)["state"] == "en_evaluacion" and job_count(db, case_id) == 1
        await w.step()
    assert [(r.attempt, r.first_evaluation) for r in w.scoring.requests] == [(1, True), (1, False)]
    assert case_row(db, case_id)["state"] == "listo"


async def test_a_job_that_is_not_due_yet_is_not_taken_and_two_workers_never_take_the_same_job(db: Db) -> None:
    ids = bulk_cases(db, 8)
    async with worker_world(db) as w1, worker_world(db) as w2:
        takes = await asyncio.gather(*[q.take() for q in (w1.queue, w2.queue) for _ in range(8)])
    taken = [t.case_id for t in takes if t is not None]
    assert sorted(taken) == sorted(ids) and len(set(taken)) == 8  # SKIP LOCKED: ninguno se toma dos veces
    future = new_case(db, job_attempt=None)
    db.execute(
        "INSERT INTO evaluation_jobs (case_id, attempt, run_at) VALUES (%s, 0, now() + interval '1 hour')",
        future,
    )
    async with worker_world(db) as w:
        assert await w.queue.take() is None


async def test_a_database_failure_while_taking_does_not_kill_the_loop(db: Db) -> None:
    new_case(db)
    async with worker_world(db) as w:
        real = w.queue.take
        calls = {"n": 0}

        async def flaky() -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("la base no responde")
            return await real()

        w.queue.take = flaky  # type: ignore[method-assign]
        task = asyncio.create_task(w.worker.run_forever())
        started = time.monotonic()
        while calls["n"] < 2 and time.monotonic() - started < 5:
            await asyncio.sleep(0.05)
        w.worker.stop()
        await task
    assert calls["n"] >= 2


async def test_an_exception_inside_an_attempt_is_logged_and_the_job_stays_leased_for_another_worker(
    db: Db,
) -> None:
    case_id = new_case(db)
    async with worker_world(db) as w:

        async def boom(*_: Any) -> Any:
            raise RuntimeError("fallo inesperado")

        w.evaluator.run = boom  # type: ignore[method-assign]
        task = asyncio.create_task(w.worker.run_forever())
        started = time.monotonic()
        while case_row(db, case_id)["attempts"] == 0 and time.monotonic() - started < 5:
            await asyncio.sleep(0.05)
        w.worker.stop()
        await task
    row, job = case_row(db, case_id), job_row(db, case_id)
    assert (row["state"], row["attempts"]) == ("en_evaluacion", 1)
    assert job is not None and job["locked_until"] is not None  # sigue arrendado: se retoma al vencer


async def test_the_drain_cancels_what_does_not_finish_within_the_grace(db: Db) -> None:
    case_id = new_case(db)
    async with worker_world(db) as w:
        w.scoring.delay = 30.0
        task = asyncio.create_task(w.worker.run_forever(grace=0.3))
        started = time.monotonic()
        while w.scoring.in_flight < 1 and time.monotonic() - started < 5:
            await asyncio.sleep(0.05)
        w.worker.stop()
        await asyncio.wait_for(task, 5)
    assert (
        case_row(db, case_id)["state"] == "en_evaluacion"
    )  # sin resultado: otro worker lo retoma (BR-U8-07)


async def test_a_new_feature_spec_version_is_read_on_every_attempt_of_the_active_version(db: Db) -> None:
    case_id = new_case(db)
    async with worker_world(db) as w:
        w.scoring.by_case[case_id].append(("status", 503))
        await w.step()
        w.clock.advance(minutes=3)
        w.h.governance_handler.model_version_id = "mv-2"
        w.scoring.serving_version = "mv-2"
        await w.step()
    assert [r.model_version_id for r in w.scoring.requests] == ["mv-1", "mv-2"]
    assert w.h.governance_handler.spec_calls == ["mv-1", "mv-2"]
