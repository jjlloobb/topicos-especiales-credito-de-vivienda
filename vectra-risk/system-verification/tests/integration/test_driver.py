"""CA-14: el conductor contra el BFF **real** (`console_bff.app.build`) con los dobles de U10 en sus destinos (U12 Paso 6; BR-U12-03; P-3 (a)); y el ritmo, la renovacion del token y el informe."""

import dataclasses
import json
from collections.abc import Iterator

import pytest
from fake_clock import FakeClock
from real_bff import RealBff, TokenSession, decision_posts

from vectra_verification import evidence, guard
from vectra_verification.clients._api import SCENARIO_PATTERN, TRACEPARENT_PATTERN, RunTag
from vectra_verification.driver import ANALYSTS, DEMO_MIX, DecisionMix, Driver, DriverError, DriverReport

TAG = RunTag("decisions", "3fa9c2d1")
ALL_SIGUE = DecisionMix(
    p_view=1.0, p_sigue=1.0, p_se_aparta=0.0, p_resuelve_revision=1.0, p_factors=1.0, seed=3
)


@pytest.fixture
def world() -> Iterator[RealBff]:
    bff = RealBff()
    yield bff
    bff.close()


def _driver(
    environment: guard.Environment,
    world: RealBff,
    clock: FakeClock,
    mix: DecisionMix = DEMO_MIX,
    sessions=None,
):  # type: ignore[no-untyped-def]
    sessions = sessions or {user: TokenSession(user) for user in ANALYSTS}
    return Driver(environment, sessions, TAG, clock, mix, transport=world.transport), sessions


def test_a_409_decision_already_recorded_counts_and_the_driver_goes_on_with_the_next_case(
    dynamic_environment: guard.Environment, world: RealBff
) -> None:
    first, second, third = world.add_cases(3)
    world.decision_conflicts.add(first)
    driver, _ = _driver(
        dynamic_environment, world, FakeClock(), ALL_SIGUE.__class__(1.0, 1.0, 0.0, 1.0, 1.0, 3)
    )
    report = driver.run()
    assert report.conflicts_409 == 1 and report.cases_seen == 3
    assert {first: 1, second: 1, third: 1} == world.decisions  # un solo POST por caso: el siguiente se decide
    assert report.decided_case_ids == (second, third) or set(report.decided_case_ids) == {second, third}


def test_a_409_from_the_bff_object_rule_counts_too(
    dynamic_environment: guard.Environment, world: RealBff
) -> None:
    (case,) = world.add_cases(1)
    original = world.doubles.case.responders[("GET", "/v1/cases/{id}")]

    def decided_after_reading(call):  # type: ignore[no-untyped-def]
        reply = original(call)
        world.doubles.case.details[case]["state"] = (
            "decidido"  # el caso deja de estar `listo` entre la lectura y la decision
        )
        return reply

    world.doubles.case.responders[("GET", "/v1/cases/{id}")] = decided_after_reading
    report = _driver(dynamic_environment, world, FakeClock(), DecisionMix(0.0, 1.0, 0.0, 1.0, 0.0, 1))[
        0
    ].run()
    assert report.conflicts_409 == 1 and report.invalid_422 == 0 and not report.decided_case_ids


def test_a_422_is_counted_with_one_post_and_no_second_attempt_with_other_content(
    dynamic_environment: guard.Environment, world: RealBff
) -> None:
    bad, good = world.add_cases(2)
    world.decision_invalid.add(bad)
    report = _driver(dynamic_environment, world, FakeClock(), ALL_SIGUE)[0].run()
    assert report.invalid_422 == 1 and world.decisions[bad] == 1 and world.decisions[good] == 1
    assert [
        c.json()["used_factors"] for c in decision_posts(world) if c.params["id"] == bad
    ] != []  # un solo cuerpo enviado


def test_both_analysts_are_used_and_the_split_is_deterministic(
    dynamic_environment: guard.Environment, world: RealBff
) -> None:
    world.add_cases(6)
    first = _driver(dynamic_environment, world, FakeClock(), ALL_SIGUE)[0].run()
    assert world.users_seen() == {"analista-1", "analista-2"} and first.cases_seen == 6
    by_user: dict[str, list[str]] = {}
    import jwt

    for call in decision_posts(world):
        sub = jwt.decode(
            call.headers["authorization"].removeprefix("Bearer "), options={"verify_signature": False}
        )["sub"]
        by_user.setdefault(sub, []).append(call.params["id"])
    assert by_user["analista-1"] == world.case_ids[0::2] and by_user["analista-2"] == world.case_ids[1::2]


@pytest.mark.parametrize(("p_view", "views"), [(1.0, 4), (0.0, 0)])
def test_per_case_get_view_by_p_view_and_decision_and_the_report_counts_the_views(
    dynamic_environment: guard.Environment, world: RealBff, p_view: float, views: int
) -> None:
    world.add_cases(4)
    report = _driver(dynamic_environment, world, FakeClock(), DecisionMix(p_view, 1.0, 0.0, 1.0, 0.0, 5))[
        0
    ].run()
    assert (
        report.views == views
        and world.doubles.case.count("POST", "/v1/cases/{id}/explanation-views") == views
    )
    assert (
        world.doubles.case.count("GET", "/v1/cases/{id}") >= 4
        and sum(report.decisions_by_kind.values()) == 4
        and report.not_decided == 0
    )


def test_the_decision_body_passes_the_real_bff_validation_zero_unexpected_422s_in_the_base_run(
    dynamic_environment: guard.Environment, world: RealBff
) -> None:
    world.add_cases(30)
    report = _driver(dynamic_environment, world, FakeClock(), DEMO_MIX)[0].run()
    assert report.invalid_422 == 0 and report.conflicts_409 == 0 and report.errors_by_status == {}
    assert sum(report.decisions_by_kind.values()) + report.not_decided == 30


def test_a_role_that_is_not_analista_gets_403_counted_as_an_error_not_as_a_decision(
    dynamic_environment: guard.Environment, world: RealBff
) -> None:
    world.add_cases(3)
    sessions = {
        "analista-1": TokenSession("analista-1", roles=("cro",)),
        "analista-2": TokenSession("analista-2", roles=("cro",)),
    }
    report = _driver(dynamic_environment, world, FakeClock(), ALL_SIGUE, sessions)[0].run()
    assert (
        report.decisions_by_kind == {}
        and report.errors_by_status.get("403", 0) >= 1
        and not report.decided_case_ids
    )


def test_a_401_refreshes_once_and_repeats_the_same_request_and_a_second_401_is_an_error(
    dynamic_environment: guard.Environment, world: RealBff
) -> None:
    world.add_cases(2)
    sessions = {user: TokenSession(user) for user in ANALYSTS}
    sessions["analista-2"].unauthorized_next = 1
    driver, _ = _driver(dynamic_environment, world, FakeClock(), ALL_SIGUE, sessions)
    assert sum(driver.run().decisions_by_kind.values()) == 2 and sessions["analista-2"].refreshed == 1
    world2 = RealBff()
    try:
        world2.add_cases(1)
        stuck = {user: TokenSession(user) for user in ANALYSTS}
        stuck["analista-1"].unauthorized_next = 99  # el refresco no arregla el token
        driver2 = Driver(dynamic_environment, stuck, TAG, FakeClock(), ALL_SIGUE, transport=world2.transport)
        with pytest.raises(DriverError, match="unauthorized_after_refresh"):
            driver2.run()
        assert stuck["analista-1"].refreshed == 1
    finally:
        world2.close()


def test_the_rate_per_user_never_exceeds_20_per_second_on_the_fake_clock(
    dynamic_environment: guard.Environment, world: RealBff
) -> None:
    world.add_cases(40)
    clock = FakeClock()
    times: dict[str, list[float]] = {}
    sessions = {user: TokenSession(user) for user in ANALYSTS}
    real_bearer = {u: s.bearer for u, s in sessions.items()}
    for user, session in sessions.items():
        session.bearer = lambda u=user: (times.setdefault(u, []).append(clock.monotonic()), real_bearer[u]())[
            1
        ]  # type: ignore[method-assign]
    _driver(dynamic_environment, world, clock, ALL_SIGUE, sessions)[0].run()
    for stamps in times.values():
        assert max(sum(1 for u in stamps if t <= u < t + 1.0 - 1e-6) for t in stamps) <= 20


def test_the_report_has_the_domain_fields_without_applicant_data_and_passes_the_filter(
    dynamic_environment: guard.Environment, world: RealBff
) -> None:
    (case,) = world.add_cases(1)
    report = _driver(dynamic_environment, world, FakeClock(), ALL_SIGUE)[0].run()
    assert {
        "cases_seen",
        "decisions_by_kind",
        "views",
        "conflicts_409",
        "invalid_422",
        "started_at",
        "finished_at",
    } <= {f.name for f in dataclasses.fields(DriverReport)}
    text = json.dumps(dataclasses.asdict(report), default=str, sort_keys=True)
    assert evidence.prepare(text, ["x" * 12]) == text
    for field in ("full_name", "document_number", "phone", "email", "address", "Ana"):
        assert field not in text
    assert case in text


def test_every_request_to_the_bff_carries_the_header_and_the_prefix(
    dynamic_environment: guard.Environment, world: RealBff
) -> None:
    world.add_cases(2)
    seen: list[dict[str, str]] = []
    inner = world.transport.handle_request

    def spy(request):  # type: ignore[no-untyped-def]
        seen.append(dict(request.headers))
        return inner(request)

    world.transport.handle_request = spy  # type: ignore[method-assign]
    _driver(dynamic_environment, world, FakeClock(), ALL_SIGUE)[0].run()
    assert seen and all(
        SCENARIO_PATTERN.fullmatch(h["x-test-scenario"])
        and TRACEPARENT_PATTERN.fullmatch(h["traceparent"])
        and h["traceparent"].split("-")[1].startswith("3fa9c2d1")
        for h in seen
    )
