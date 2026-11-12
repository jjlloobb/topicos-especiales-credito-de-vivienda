"""Paso 11: barrido de `modelo_congelado` y de la marca de congelamiento (BR-U8-10, 14; P-U8-04, 07; US-112)."""

import asyncio
import json

import pytest
from case_pg import Db
from u8_support import GovernanceDouble, harness, scalar, seed_case

pytestmark = pytest.mark.integration


async def test_active_serving_config_moves_frozen_cases_to_en_evaluacion_with_a_new_job(db: Db) -> None:
    a = seed_case(db, state="modelo_congelado", attempts=6)
    b = seed_case(db, state="modelo_congelado", attempts=3)
    other = seed_case(db, state="no_disponible")
    async with harness(db) as h:
        assert await h.sweeper.run_once() == "done"
    assert (
        db.query("SELECT state, attempts FROM cases WHERE case_id = ANY(%s) ORDER BY case_id", [a, b])
        == [("en_evaluacion", 0)] * 2
    )
    assert db.query("SELECT attempt FROM evaluation_jobs ORDER BY case_id") == [(0,), (0,)]
    assert scalar(db, "SELECT state FROM cases WHERE case_id = %s", other) == "no_disponible"
    assert scalar(db, "SELECT updated_at > created_at FROM cases WHERE case_id = %s", a) is True


async def test_frozen_serving_config_marks_listo_cases_of_that_version_and_reactivation_clears_the_mark(
    db: Db,
) -> None:
    mv1 = seed_case(db, state="listo", model_version="mv-1")
    mv2 = seed_case(db, state="listo", model_version="mv-2")
    frozen_case = seed_case(db, state="modelo_congelado")
    async with harness(db) as h:
        h.governance_handler.state = "congelado"
        await h.sweeper.run_once()
        assert (
            scalar(db, "SELECT model_frozen_after_recommendation FROM cases WHERE case_id = %s", mv1) is True
        )
        assert (
            scalar(db, "SELECT model_frozen_after_recommendation FROM cases WHERE case_id = %s", mv2) is False
        )
        assert scalar(db, "SELECT state FROM cases WHERE case_id = %s", mv1) == "listo"  # sigue `listo`
        assert (
            scalar(db, "SELECT state FROM cases WHERE case_id = %s", frozen_case) == "modelo_congelado"
        )  # no se mueve congelado
        h.clock.advance(seconds=10)  # la cache de serving-config (<= 5 s) vence
        h.sweeper.governance._fetched_at = -1e9  # noqa: SLF001
        h.governance_handler.state = "activo"
        await h.sweeper.run_once()
    assert scalar(db, "SELECT model_frozen_after_recommendation FROM cases WHERE case_id = %s", mv1) is False
    assert scalar(db, "SELECT state FROM cases WHERE case_id = %s", frozen_case) == "en_evaluacion"


async def test_governance_down_skips_the_cycle(db: Db) -> None:
    frozen = seed_case(db, state="modelo_congelado")
    async with harness(db) as h:
        h.governance_handler.down = True
        assert await h.sweeper.run_once() == "skipped"
    assert scalar(db, "SELECT state FROM cases WHERE case_id = %s", frozen) == "modelo_congelado"
    assert scalar(db, "SELECT count(*) FROM evaluation_jobs") == 0


async def test_old_shape_serving_config_skips_the_cycle_and_moves_nothing(db: Db) -> None:
    """Sin `cutoff`, `low_confidence_threshold` ni `channel_rules`: falla la validacion estricta; el barrido falla cerrado."""
    frozen = seed_case(db, state="modelo_congelado")
    marked = seed_case(db, state="listo", frozen_mark=True)
    async with harness(db) as h:
        h.governance_handler.old_shape = True
        assert await h.sweeper.run_once() == "skipped"
    assert scalar(db, "SELECT state FROM cases WHERE case_id = %s", frozen) == "modelo_congelado"
    assert (
        scalar(db, "SELECT model_frozen_after_recommendation FROM cases WHERE case_id = %s", marked) is True
    )
    assert scalar(db, "SELECT count(*) FROM evaluation_jobs") == 0


async def test_two_replicas_do_not_process_the_same_case_twice(db: Db) -> None:
    ids = [seed_case(db, state="modelo_congelado") for _ in range(25)]
    async with harness(db) as h, harness(db, registry=h.registry, clock=h.clock) as other:
        await asyncio.gather(h.sweeper.run_once(), other.sweeper.run_once())
    assert scalar(db, "SELECT count(*) FROM evaluation_jobs") == 25
    assert scalar(db, "SELECT count(DISTINCT case_id) FROM evaluation_jobs") == 25
    assert (
        scalar(db, "SELECT count(*) FROM cases WHERE state = 'en_evaluacion' AND case_id = ANY(%s)", ids)
        == 25
    )


async def test_a_live_job_for_the_case_makes_that_case_stay_frozen_and_does_not_break_the_batch(
    db: Db,
) -> None:
    """P-2 (a): `INSERT` simple; si choca con una fila viva se revierte ese caso."""
    clash = seed_case(db, state="modelo_congelado")
    fine = seed_case(db, state="modelo_congelado")
    db.execute("INSERT INTO evaluation_jobs (case_id, attempt) VALUES (%s, 2)", clash)
    async with harness(db) as h:
        await h.sweeper.run_once()
    assert scalar(db, "SELECT state FROM cases WHERE case_id = %s", clash) == "modelo_congelado"
    assert scalar(db, "SELECT state FROM cases WHERE case_id = %s", fine) == "en_evaluacion"
    assert json.dumps(scalar(db, "SELECT attempt FROM evaluation_jobs WHERE case_id = %s", clash)) == "2"


def test_governance_double_old_shape_lacks_the_new_fields() -> None:
    g = GovernanceDouble()
    g.old_shape = True
    assert "cutoff" not in g.config()
