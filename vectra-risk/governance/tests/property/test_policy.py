"""PBT-U4-03 y PBT-U4-04, y ejemplos de BR-U4-10 y 11 (US-205, US-206, vigencia vencida). Paso 4, `policy`.

Fechas en `America/Bogota` (P-U4-05): UTC-5 fijo (sin horario de verano), asi que el oraculo usa aritmetica de enteros
y no `zoneinfo`: la fecha de Bogota de un instante es `(instante - 5 h).date()`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Final

import pytest
from hypothesis import given
from hypothesis import strategies as st
from vectra_contracts.catalog import Role
from vectra_contracts.models.governance import NormativeParams, PolicyDraft, PolicyVersion

from vectra_governance.model_fsm import Actor, ConflictState, Forbidden
from vectra_governance.policy import (
    BOGOTA,
    PolicyInvalid,
    approve_policy,
    bogota_date,
    check_four_eyes,
    normative_at,
    normative_current,
    validate_normative,
)

UTC_MINUS_5: Final = timedelta(hours=5)
EPOCH: Final = date(2026, 1, 1)


def params(start: date, end: date | None, tag: int = 0) -> NormativeParams:
    return NormativeParams(
        vis_max_property_value=150_000_000 + tag,
        usury_cap_ea="0.2500",
        effective_from=start,
        effective_to=end,
        source_ref=f"Resolucion {tag}",
    )


def draft(normative: list[NormativeParams]) -> PolicyDraft:
    return PolicyDraft(
        cutoff="0.5000", low_confidence_threshold="0.2000", channel_rules=[], normative=normative
    )


def policy(
    version: str, state: str, proposed_by: str, normative: list[NormativeParams] | None = None
) -> PolicyVersion:
    return PolicyVersion(
        policy_version_id=version,
        state=state,  # type: ignore[arg-type]
        proposed_by=proposed_by,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        cutoff="0.5000",
        low_confidence_threshold="0.2000",
        channel_rules=[],
        normative=normative or [],
    )


# --- PBT-U4-03 ------------------------------------------------------------------------------------------------------


@st.composite
def non_overlapping(draw: st.DrawFn) -> list[NormativeParams]:
    """Vigencias con huecos y bordes pegados (`effective_to == effective_from` del siguiente), en orden al azar."""
    cuts = draw(st.lists(st.integers(0, 400), min_size=0, max_size=8, unique=True).map(sorted))
    items: list[NormativeParams] = []
    i = 0
    while i + 1 < len(cuts):
        items.append(params(EPOCH + timedelta(days=cuts[i]), EPOCH + timedelta(days=cuts[i + 1]), len(items)))
        i += 2 if draw(st.booleans()) else 1  # 1 = pegadas; 2 = con hueco
    if i < len(cuts) and draw(st.booleans()):
        items.append(params(EPOCH + timedelta(days=cuts[i]), None, len(items)))  # la ultima, abierta
    return draw(st.permutations(items))


def valid_at(item: NormativeParams, day: date) -> bool:
    return item.effective_from <= day and (item.effective_to is None or day < item.effective_to)


@given(normative=non_overlapping(), offset=st.integers(-10, 420))
def test_pbt_u4_03_normative_at_returns_the_only_valid_param_or_none(
    normative: list[NormativeParams], offset: int
) -> None:
    day = EPOCH + timedelta(days=offset)
    validate_normative(normative)
    matching = [item for item in normative if valid_at(item, day)]
    assert len(matching) <= 1
    assert normative_at(draft(normative), day) == (matching[0] if matching else None)


@given(normative=non_overlapping())
def test_pbt_u4_03_the_boundaries_of_each_validity_are_exact(normative: list[NormativeParams]) -> None:
    policy_ = draft(normative)
    for item in normative:
        assert normative_at(policy_, item.effective_from) == item
        assert normative_at(policy_, item.effective_from - timedelta(days=1)) != item
        if item.effective_to is not None:
            assert normative_at(policy_, item.effective_to) != item
            assert normative_at(policy_, item.effective_to - timedelta(days=1)) == item


@st.composite
def overlapping(draw: st.DrawFn) -> list[NormativeParams]:
    """Dos vigencias que comparten al menos un dia, en orden al azar."""
    a = draw(st.integers(0, 300))
    b = a + draw(st.integers(1, 60))
    c = draw(st.integers(a, b - 1))  # el segundo comienza dentro del primero
    e: int | None = c + draw(st.integers(1, 60))
    if draw(st.booleans()):
        e = None
    first = params(EPOCH + timedelta(days=a), EPOCH + timedelta(days=b), 1)
    second = params(EPOCH + timedelta(days=c), None if e is None else EPOCH + timedelta(days=e), 2)
    return draw(st.permutations([first, second]))


@given(normative=overlapping())
def test_pbt_u4_03_validation_rejects_every_list_with_overlaps(normative: list[NormativeParams]) -> None:
    with pytest.raises(PolicyInvalid) as error:
        validate_normative(normative)
    assert error.value.reason == "normative_overlap"


@given(normative=st.one_of(non_overlapping(), overlapping()))
def test_br_u0_33_validation_is_the_one_of_u0(normative: list[NormativeParams]) -> None:
    """No se duplica la regla: la validacion de `policy` acepta y rechaza lo mismo que `PolicyDraft` de U0."""
    try:
        draft(normative)
        u0_accepts = True
    except ValueError:
        u0_accepts = False
    try:
        validate_normative(normative)
        ours_accepts = True
    except PolicyInvalid:
        ours_accepts = False
    assert ours_accepts == u0_accepts


def test_br_u0_33_a_validity_ending_before_it_starts_is_rejected() -> None:
    with pytest.raises(PolicyInvalid) as error:
        validate_normative([params(date(2026, 5, 1), date(2026, 5, 1))])
    assert error.value.reason == "effective_to_not_after_from"


# --- Medianoche de Bogota (P-U4-05) ---------------------------------------------------------------------------------


@given(day=st.dates(date(2026, 1, 2), date(2030, 12, 31)), seconds=st.integers(-3 * 3600, 3 * 3600))
def test_pbt_u4_03_bogota_date_around_05_00_utc(day: date, seconds: int) -> None:
    """Los bordes de la medianoche de Bogota: 05:00 UTC cambia la fecha; 00:00 UTC no."""
    instant = datetime(day.year, day.month, day.day, 5, tzinfo=UTC) + timedelta(seconds=seconds)
    assert bogota_date(instant) == (instant - UTC_MINUS_5).date()
    assert bogota_date(instant) == (day if seconds >= 0 else day - timedelta(days=1))


@given(instant=st.datetimes(datetime(2026, 1, 1), datetime(2032, 1, 1), timezones=st.just(UTC)))
def test_pbt_u4_03_bogota_date_is_the_utc_minus_5_date(instant: datetime) -> None:
    assert bogota_date(instant) == (instant - UTC_MINUS_5).date()
    assert bogota_date(instant.astimezone(BOGOTA)) == bogota_date(
        instant
    )  # no depende de la zona del argumento


def test_bogota_date_rejects_a_naive_instant() -> None:
    with pytest.raises(ValueError):
        bogota_date(datetime(2026, 11, 10, 5))


class FakeClock:
    """Reloj simulado: el modulo nunca lo lee, la prueba pasa `clock.now` como parametro."""

    def __init__(self, local: datetime) -> None:
        self.now = local.astimezone(UTC)

    def set_local(self, local: datetime) -> None:
        self.now = local.astimezone(UTC)


def bogota(day: int, hour: int, minute: int, second: int) -> datetime:
    return datetime(2026, 11, day, hour, minute, second, tzinfo=BOGOTA)


def test_vigencia_changes_at_midnight_of_bogota_and_not_at_19_00() -> None:
    """P-U4-05: el cambio de vigencia ocurre a las 00:00 de Bogota (05:00 UTC), no a las 19:00 (00:00 UTC)."""
    old = params(date(2026, 1, 1), date(2026, 11, 10), 1)
    new = params(date(2026, 11, 10), None, 2)
    p = draft([old, new])
    clock = FakeClock(bogota(9, 23, 59, 59))
    assert normative_current(p, clock.now) == old
    clock.set_local(bogota(10, 0, 0, 0))
    assert clock.now == datetime(2026, 11, 10, 5, tzinfo=UTC)
    assert normative_current(p, clock.now) == new  # cambia a las 00:00 de Bogota

    clock.set_local(bogota(9, 18, 59, 59))
    before = normative_current(p, clock.now)
    clock.set_local(bogota(9, 19, 0, 0))
    assert clock.now == datetime(2026, 11, 10, 0, tzinfo=UTC)  # ya es el dia 10 en UTC
    assert normative_current(p, clock.now) == before == old  # y no cambia a las 19:00 de Bogota


def test_vigencia_vencida_gives_none() -> None:
    """Vigencia normativa vencida -> `normative_current` nulo (U7 lo convierte en `revision_requerida`)."""
    p = draft([params(date(2026, 1, 1), date(2026, 11, 10), 1)])
    assert normative_current(p, bogota(9, 23, 59, 59).astimezone(UTC)) is not None
    assert normative_current(p, bogota(10, 0, 0, 0).astimezone(UTC)) is None
    assert normative_current(draft([]), datetime(2026, 11, 9, tzinfo=UTC)) is None


# --- PBT-U4-04 / BR-U4-10 -------------------------------------------------------------------------------------------

_USERS = st.sampled_from(["sub-a", "sub-b", "sub-c"])
_ACTORS = st.one_of(
    st.builds(
        Actor,
        kind=st.just("user"),
        id=_USERS,
        role=st.sampled_from(list(Role)),
        acr=st.sampled_from(["mfa", "pwd"]),
    ),
    st.builds(Actor, kind=st.just("service"), id=st.sampled_from(["bias-monitoring-job", "scoring-service"])),
    st.builds(Actor, kind=st.just("system"), id=st.just("governance-service")),
)


@given(proposed_by=_USERS, approver=_ACTORS)
def test_pbt_u4_04_four_eyes_oracle(proposed_by: str, approver: Actor) -> None:
    """Aprobar <=> `approved_by != proposed_by` y rol `cro` con MFA; si no, 403 (rol o MFA) o 409 (mismo usuario)."""
    is_cro_mfa = approver.kind == "user" and approver.role == Role.CRO and approver.acr == "mfa"
    if is_cro_mfa and approver.id != proposed_by:
        check_four_eyes(proposed_by, approver)
        return
    with pytest.raises(Forbidden if not is_cro_mfa else ConflictState):
        check_four_eyes(proposed_by, approver)


def test_br_u4_10_the_cro_who_proposed_cannot_approve() -> None:
    cro = Actor("user", "sub-a", Role.CRO, "mfa")
    with pytest.raises(ConflictState) as error:
        check_four_eyes("sub-a", cro)
    assert error.value.reason == "approver_is_proposer"
    check_four_eyes("sub-b", cro)


# --- Activacion (BR-U4-11; US-205 y US-206) -------------------------------------------------------------------------

CRO_B = Actor("user", "sub-b", Role.CRO, "mfa")


def test_us_205_p2_proposed_while_p1_stays_active() -> None:
    """P2 propuesta no toca a P1; los servicios no escriben politica (BR-U4-12: ningun rol de servicio la aprueba)."""
    p1, p2 = policy("p1", "activa", "sub-a"), policy("p2", "propuesta", "sub-a")
    assert (p1.state, p2.state) == ("activa", "propuesta")
    with pytest.raises(Forbidden):
        approve_policy(p2, Actor("service", "scoring-service"), p1)


def test_us_206_other_cro_approves_p2_active_and_p1_historica() -> None:
    p1, p2 = policy("p1", "activa", "sub-a"), policy("p2", "propuesta", "sub-a")
    result = approve_policy(p2, CRO_B, p1)
    assert (result.activated.policy_version_id, result.activated.from_state, result.activated.to_state) == (
        "p2",
        "propuesta",
        "activa",
    )
    assert result.superseded is not None
    assert (
        result.superseded.policy_version_id,
        result.superseded.from_state,
        result.superseded.to_state,
    ) == ("p1", "activa", "historica")
    assert result.changes == (result.activated, result.superseded)  # una sola unidad de evidencia (BR-U4-17)


def test_br_u4_11_first_policy_has_nothing_to_supersede() -> None:
    result = approve_policy(policy("p1", "propuesta", "sub-a"), CRO_B, None)
    assert result.superseded is None and len(result.changes) == 1


def test_br_u4_11_only_a_propuesta_is_approved_and_the_active_must_be_active() -> None:
    p1 = policy("p1", "activa", "sub-a")
    for state in ("activa", "rechazada", "historica"):
        with pytest.raises(ConflictState):
            approve_policy(policy("p2", state, "sub-a"), CRO_B, p1)
    with pytest.raises(ConflictState):
        approve_policy(policy("p2", "propuesta", "sub-a"), CRO_B, policy("p0", "historica", "sub-a"))
    with pytest.raises(ConflictState):
        approve_policy(policy("p1", "propuesta", "sub-a"), CRO_B, p1)  # la activa no es la propuesta


@given(proposed_by=_USERS, approver=_ACTORS)
def test_br_u4_11_activation_changes_only_when_four_eyes_hold(proposed_by: str, approver: Actor) -> None:
    p1, p2 = policy("p1", "activa", "sub-z"), policy("p2", "propuesta", proposed_by)
    try:
        check_four_eyes(proposed_by, approver)
    except (Forbidden, ConflictState) as expected:
        with pytest.raises(type(expected)):
            approve_policy(p2, approver, p1)
    else:
        assert len(approve_policy(p2, approver, p1).changes) == 2
