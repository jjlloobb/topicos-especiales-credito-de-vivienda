"""Paso 11: gauges de la base (P-U8-04, 08; NFR-U8-13). Las metricas de retencion se difieren por la demo."""

from datetime import timedelta

import pytest
from case_pg import Db
from u8_support import harness, insert_fail_closed, seed_case
from vectra_case.db_gauges import DbGauges
from vectra_common.metrics import REGISTRY

pytestmark = pytest.mark.integration


def gauge(name: str, **labels: str) -> float:
    value = REGISTRY.get_sample_value(name, labels)
    assert value is not None, name
    return value


async def test_failclosed_persistent_counts_the_no_disponible_cases(db: Db) -> None:
    for _ in range(3):
        seed_case(db, state="no_disponible")
    seed_case(db, state="listo")
    async with harness(db) as h:
        await DbGauges(h.database, h.clock).refresh()
    assert gauge("vectra_cases_failclosed_persistent") == 3


async def test_jobs_overdue_counts_untaken_jobs_older_than_30_seconds(db: Db) -> None:
    old, fresh, taken = (seed_case(db) for _ in range(3))
    db.execute(
        "INSERT INTO evaluation_jobs (case_id, attempt, run_at) VALUES (%s, 0, now() - interval '5 minutes')",
        old,
    )
    db.execute("INSERT INTO evaluation_jobs (case_id, attempt, run_at) VALUES (%s, 0, now())", fresh)
    db.execute(
        "INSERT INTO evaluation_jobs (case_id, attempt, run_at, locked_until) VALUES (%s, 0, now() - interval '5 minutes', now() + interval '20 seconds')",
        taken,
    )
    async with harness(db) as h:
        await DbGauges(h.database, h.clock).refresh()
    assert gauge("vectra_case_jobs_overdue") == 1


async def test_evidence_pending_oldest_seconds_by_entry_type(db: Db) -> None:
    case_id = seed_case(db, state="no_disponible")
    insert_fail_closed(db, case_id, 2)
    db.execute("UPDATE evidence_outbox SET created_at = now() - interval '2 hours'")
    async with harness(db) as h:
        await DbGauges(h.database, h.clock).refresh()
        assert gauge("vectra_case_evidence_pending_oldest_seconds", entry_type="fail_closed") >= 7200
        assert gauge("vectra_case_evidence_pending_oldest_seconds", entry_type="human_decision") == 0
        h.clock.advance(seconds=60)
        await DbGauges(h.database, h.clock).refresh()
        assert gauge("vectra_case_evidence_pending_oldest_seconds", entry_type="fail_closed") >= 7260
        assert timedelta(0) == timedelta(0)
