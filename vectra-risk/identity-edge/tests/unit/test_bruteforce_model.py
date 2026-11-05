"""Modelo puro de la fuerza bruta de BR-U2-05 con la enmienda H10 (U02-T14, PBT-U2-08), sin clúster.

Los parámetros salen del realm de Git, no de literales. La semántica se fijó contra Keycloak 26.8.1:
- `DefaultBruteForceProtector.java`, líneas 109-116 (espera por fallo), 129-143 (bloqueo temporal, contador de bloqueos),
  161-164 (permanente con `numTemporaryLockouts > maxTemporaryLockouts`);
- `AbstractUsernameFormAuthenticator.java`, líneas 225-231: con el usuario bloqueado, `isDisabledByBruteForce` devuelve antes de
  `badPasswordHandler`, así que un intento durante el bloqueo NO cuenta como fallo;
- `LoginFailureEntity.java`, líneas 126-132: un acierto pone a cero fallos y bloqueos.
"""

import pytest
from bruteforce_model import BruteForceModel, Params, lockout_seconds
from realm_exports import ENVS, load_git


@pytest.fixture(params=ENVS)
def params(request: pytest.FixtureRequest) -> Params:
    return Params.from_realm(load_git(str(request.param)))


def test_the_parameters_come_from_the_realm(params: Params) -> None:
    realm = load_git("kind")
    assert params == Params(
        failure_factor=realm["failureFactor"],
        wait_increment_seconds=realm["waitIncrementSeconds"],
        max_failure_wait_seconds=realm["maxFailureWaitSeconds"],
        max_temporary_lockouts=realm["maxTemporaryLockouts"],
        strategy=realm["bruteForceStrategy"],
    )
    assert params.strategy == "LINEAR"


def test_failures_5_6_and_7_lock_for_60_120_and_180_seconds(params: Params) -> None:
    assert [lockout_seconds(params, n) for n in (5, 6, 7)] == [60, 120, 180]


def test_below_the_failure_factor_there_is_no_lockout(params: Params) -> None:
    assert [lockout_seconds(params, n) for n in range(0, params.failure_factor)] == [0] * params.failure_factor


def test_failure_19_locks_for_900_seconds_and_20_is_permanent(params: Params) -> None:
    model = BruteForceModel(params)
    for _ in range(18):
        model.wrong(at=model.next_free_time())
    assert model.failures == 18 and not model.permanent
    model.wrong(at=model.next_free_time())
    assert model.failures == 19 and not model.permanent
    assert lockout_seconds(params, 19) == 900 == params.max_failure_wait_seconds
    assert model.remaining(at=model.last_failure_at) == 900
    model.wrong(at=model.next_free_time())
    assert model.failures == 20 and model.permanent
    assert model.locked(at=10**9)


def test_the_series_never_exceeds_the_maximum_wait(params: Params) -> None:
    assert all(lockout_seconds(params, n) <= params.max_failure_wait_seconds for n in range(0, 40))


def test_attempts_during_a_lockout_do_not_count(params: Params) -> None:
    model = BruteForceModel(params)
    for _ in range(params.failure_factor):
        model.wrong(at=model.next_free_time())
    assert model.failures == params.failure_factor
    assert model.wrong(at=model.last_failure_at + 1) is False
    assert model.right(at=model.last_failure_at + 1) is False
    assert model.failures == params.failure_factor


def test_the_lockout_ends_after_its_seconds(params: Params) -> None:
    model = BruteForceModel(params)
    for _ in range(params.failure_factor):
        model.wrong(at=model.next_free_time())
    start = model.last_failure_at
    assert model.locked(at=start + 59) and not model.locked(at=start + 61)
    assert model.wrong(at=start + 61) is True and model.failures == params.failure_factor + 1
    assert lockout_seconds(params, params.failure_factor + 1) == 120


def test_a_success_clears_failures_and_lockouts(params: Params) -> None:
    model = BruteForceModel(params)
    for _ in range(params.failure_factor + 2):
        model.wrong(at=model.next_free_time())
    assert model.right(at=model.next_free_time()) is True
    assert model.failures == 0
    for _ in range(params.failure_factor):
        model.wrong(at=model.next_free_time())
    assert lockout_seconds(params, model.failures) == 60


def test_a_success_before_the_failure_factor_resets_the_count(params: Params) -> None:
    model = BruteForceModel(params)
    for _ in range(params.failure_factor - 1):
        model.wrong(at=model.next_free_time())
    assert model.right(at=model.next_free_time()) is True
    assert model.failures == 0 and not model.locked(at=model.last_failure_at)


def test_with_the_multiple_strategy_and_3_lockouts_the_permanent_one_arrives_at_failure_8() -> None:
    """Lo que llevó a H10 (parada B-1): la estrategia por defecto y `maxTemporaryLockouts: 3`."""
    multiple = Params(failure_factor=5, wait_increment_seconds=60, max_failure_wait_seconds=900, max_temporary_lockouts=3, strategy="MULTIPLE")
    model = BruteForceModel(multiple)
    for _ in range(7):
        model.wrong(at=model.next_free_time())
    assert not model.permanent
    model.wrong(at=model.next_free_time())
    assert model.failures == 8 and model.permanent


def test_the_model_honours_other_values_of_the_realm() -> None:
    other = Params(failure_factor=3, wait_increment_seconds=10, max_failure_wait_seconds=25, max_temporary_lockouts=4, strategy="LINEAR")
    assert [lockout_seconds(other, n) for n in range(1, 8)] == [0, 0, 10, 20, 25, 25, 25]
    model = BruteForceModel(other)
    for _ in range(6):
        model.wrong(at=model.next_free_time())
    assert not model.permanent
    model.wrong(at=model.next_free_time())
    assert model.permanent  # el 5.o bloqueo (fallo 7) supera a 4
