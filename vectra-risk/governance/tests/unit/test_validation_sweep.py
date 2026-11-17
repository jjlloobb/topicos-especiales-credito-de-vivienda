"""U04-T12: la decision del barrido de validaciones (`sweep_verdict`) sin base de datos: que hace con cada estado del Job."""

from datetime import timedelta

import pytest
from vectra_governance.background import MISSING_JOB_GRACE, sweep_verdict
from vectra_governance.k8s_jobs import JobInfo

JUST_LAUNCHED = timedelta(seconds=10)
LONG_AGO = timedelta(hours=1)


@pytest.mark.parametrize(
    ("info", "expired", "age", "verdict"),
    [
        # plazo vigente: solo un Job `Failed` (o ausente pasado el margen) cierra la corrida
        (JobInfo(failed=True), False, JUST_LAUNCHED, "failed"),
        (JobInfo(failed=True, deadline_exceeded=True), False, LONG_AGO, "deadline"),
        (JobInfo(), False, JUST_LAUNCHED, None),  # corriendo
        (JobInfo(), False, LONG_AGO, None),  # corriendo, o `Complete` esperando su informe
        (None, False, JUST_LAUNCHED, None),  # recien creado: el API aun no lo devuelve
        (None, False, MISSING_JOB_GRACE - timedelta(seconds=1), None),
        (None, False, MISSING_JOB_GRACE, "sin informe"),
        # plazo vencido: como antes de U04-T12
        (JobInfo(failed=True), True, LONG_AGO, "failed"),
        (JobInfo(failed=True, deadline_exceeded=True), True, LONG_AGO, "deadline"),
        (JobInfo(), True, LONG_AGO, "sin informe"),
        (None, True, JUST_LAUNCHED, "sin informe"),
    ],
)
def test_sweep_verdict_for_each_job_state(info: JobInfo | None, expired: bool, age: timedelta, verdict: str | None) -> None:
    assert sweep_verdict(info, expired, age) == verdict


def test_sweep_missing_job_grace_covers_the_create_timeout_and_stays_far_below_the_deadline() -> None:
    from vectra_governance.k8s_jobs import ACTIVE_DEADLINE_SECONDS, K8S_TIMEOUT

    assert MISSING_JOB_GRACE.total_seconds() >= 10 * K8S_TIMEOUT
    assert MISSING_JOB_GRACE.total_seconds() < ACTIVE_DEADLINE_SECONDS / 10
