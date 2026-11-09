"""PBT-U3-07 y PBT-U3-08 sobre `append` (Paso 7 del plan de U3; BR-U3-05, 06).

- PBT-U3-07: `recorded_at` es no decreciente en `seq` para todo reloj generado, incluso si retrocede.
- PBT-U3-08: para una llave nueva, `occurred_at` se acepta <=> `|occurred_at - now| <= 300 s`; para una llave existente con el
  mismo contenido, la ventana no aplica (ack original).

`HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_append_time.py` (500 ejemplos, semilla impresa). Cada
ejemplo escribe en PostgreSQL real con standby sincrono.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from entries import entry_dict, iso
from hypothesis import given, settings
from hypothesis import strategies as st
from registry_cluster import ClusterDb
from vectra_common.errors import ValidationFailed
from vectra_contracts.models.registry import RegistryEntryIn
from vectra_registry import append
from vectra_registry.pools import Pools

pytestmark = pytest.mark.integration


def entry(now: datetime, occurred_at: datetime, key: uuid.UUID | None = None, **over: Any) -> RegistryEntryIn:
    """Una `explanation_view` cuyo momento de negocio (`viewed_at`) es `occurred_at - 1 s`: no interviene en lo que se prueba."""
    data = entry_dict(
        "explanation_view",
        key=key,
        now=now,
        occurred_at=occurred_at,
        payload={"viewed_at": iso(occurred_at - timedelta(seconds=1)), "recommendation_entry_id": "1"},
        **over,
    )
    return RegistryEntryIn.model_validate_json(json.dumps(data))


def run(cdb: ClusterDb, scenario: Any) -> Any:
    async def main() -> Any:
        pools = Pools.build(cdb.dsns())
        try:
            return await scenario(pools)
        finally:
            await pools.close()

    return asyncio.run(main())


# --- PBT-U3-07 -------------------------------------------------------------------------------------------------------------


clocks = st.lists(st.integers(-7200, 7200), min_size=1, max_size=6)  # saltos del reloj de la base, hacia atras y adelante


@settings(deadline=None)
@given(clocks)
def test_pbt_u3_07_recorded_at_es_no_decreciente_aunque_el_reloj_retroceda(shared_db: ClusterDb, jumps: list[int]) -> None:
    base = datetime.now(UTC)
    readings = [base + timedelta(seconds=jump) for jump in jumps]

    async def scenario(pools: Pools) -> list[datetime]:
        stamps = []
        for reading in readings:
            outcome = await append.append_entry(
                pools, entry(base, base), clock=lambda: base, db_clock=lambda reading=reading: reading
            )
            stamps.append(outcome.ack.recorded_at)
        return stamps

    stamps = run(shared_db, scenario)
    previous = shared_db.db.query("SELECT recorded_at FROM registry_entries ORDER BY seq DESC OFFSET %s LIMIT 1", len(stamps))
    floor = previous[0][0] if previous else datetime.min.replace(tzinfo=UTC)
    assert all(a <= b for a, b in zip(stamps, stamps[1:], strict=False))
    # Oraculo: max(reloj, recorded_at de la fila anterior).
    expected, running = [], floor
    for reading in readings:
        running = max(reading.astimezone(UTC).replace(microsecond=reading.microsecond), running)  # type: ignore[type-var]
        expected.append(running)
    assert stamps == expected


def test_pbt_u3_07_en_toda_la_base_recorded_at_no_decrece_en_seq(shared_db: ClusterDb) -> None:
    rows = shared_db.db.query("SELECT seq, recorded_at FROM registry_entries ORDER BY seq")
    assert len(rows) > 1
    assert all(a[1] <= b[1] for a, b in zip(rows, rows[1:], strict=False))  # type: ignore[operator]
    assert [r[0] for r in rows] == list(range(len(rows)))


@given(st.integers(-10**6, 10**6), st.integers(-10**6, 10**6))
def test_pbt_u3_07_next_recorded_at_es_el_maximo(clock_us: int, head_us: int) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    clock, head = base + timedelta(microseconds=clock_us), base + timedelta(microseconds=head_us)
    result = append.next_recorded_at(clock, head)
    assert result >= head and result >= clock and result in (clock, head)


# --- PBT-U3-08 -------------------------------------------------------------------------------------------------------------


WINDOW_US = 300_000_000
offsets = st.one_of(
    st.integers(-WINDOW_US - 5_000_000, WINDOW_US + 5_000_000),
    st.sampled_from([-WINDOW_US, WINDOW_US, -WINDOW_US - 1, WINDOW_US + 1, 0]),
)


@given(offsets)
def test_pbt_u3_08_el_oraculo_de_la_ventana(offset_us: int) -> None:
    now = datetime(2026, 11, 8, 12, tzinfo=UTC)
    occurred = now + timedelta(microseconds=offset_us)
    if abs(offset_us) <= WINDOW_US:
        append.check_window(occurred, now)
    else:
        with pytest.raises(ValidationFailed):
            append.check_window(occurred, now)


@settings(deadline=None)
@given(offsets, st.integers(-30 * 86400 * 10**6, 30 * 86400 * 10**6))
def test_pbt_u3_08_una_llave_nueva_se_acepta_si_y_solo_si_esta_en_la_ventana_y_una_existente_no_la_mira(
    shared_db: ClusterDb, offset_us: int, later_us: int
) -> None:
    now = datetime.now(UTC)
    key = uuid.uuid4()
    occurred = now + timedelta(microseconds=offset_us)

    async def scenario(pools: Pools) -> tuple[Any, Any]:
        first: Any
        try:
            first = await append.append_entry(pools, entry(now, occurred, key), clock=lambda: now)
        except ValidationFailed as error:
            return error, None  # sin fila, no hay reintento que probar: la llave sigue siendo nueva
        # Mas tarde, con otro occurred_at cualquiera (incluso fuera de la ventana) y la misma llave y contenido.
        again_at = now + timedelta(microseconds=later_us)
        retry_entry = entry(now, occurred, key, correlation_id=uuid.uuid4().hex)
        retry_entry = retry_entry.model_copy(update={"occurred_at": again_at})
        retry: Any
        try:
            retry = await append.append_entry(pools, retry_entry, clock=lambda: now)
        except ValidationFailed as error:
            retry = error
        return first, retry

    first, retry = run(shared_db, scenario)
    in_window = abs(offset_us) <= WINDOW_US
    assert isinstance(first, append.AppendOutcome) == in_window
    rows = shared_db.db.query("SELECT count(*) FROM registry_entries WHERE idempotency_key = %s", key)[0][0]
    if in_window:
        assert first.created and rows == 1
        assert isinstance(retry, append.AppendOutcome) and not retry.created  # la ventana no aplica a una llave existente
        assert retry.ack == first.ack
    else:
        assert isinstance(first, ValidationFailed) and rows == 0  # una llave nueva fuera de la ventana no escribe
