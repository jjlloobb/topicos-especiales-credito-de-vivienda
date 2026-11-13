"""`guard` (U12 Paso 2; NFR-U12-03, NFR-U12-32; INF-U12-01; BR-U12-10): barrera de entorno, de secciones, de reactivacion y horaria."""

import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import yaml
from vault_double import CountingTransport

from vectra_verification import guard
from vectra_verification.guard import KIND, STAGING, GuardError

REPO = Path(__file__).resolve().parents[3]
PROD_ISSUER = "https://vectra.banco.internal/auth/realms/vectra"
PROD_HOST = "vectra.banco.internal"


def _client(issuer: str, host: str) -> tuple[httpx.Client | None, CountingTransport]:
    transport = CountingTransport()
    try:
        return guard.gateway_client(issuer, host, transport), transport
    except GuardError:
        return None, transport


def test_production_issuer_is_refused_with_zero_requests() -> None:
    client, transport = _client(PROD_ISSUER, KIND.host)
    assert client is None and transport.count == 0


def test_production_host_is_refused_with_zero_requests() -> None:
    client, transport = _client(KIND.issuer, PROD_HOST)
    assert client is None and transport.count == 0
    client, transport = _client(PROD_ISSUER, PROD_HOST)
    assert client is None and transport.count == 0


def test_production_is_not_a_known_environment() -> None:
    assert all(PROD_HOST != e.host for e in guard.ENVIRONMENTS)


def test_lookalike_issuer_and_unknown_host_are_refused() -> None:
    with pytest.raises(GuardError):
        guard.check_environment("https://vectra.localtest.me.ejemplo.test/auth/realms/vectra", KIND.host)
    with pytest.raises(GuardError):
        guard.check_environment(
            "https://vectra.localtest.me.ejemplo.test/auth/realms/vectra", "vectra.localtest.me.ejemplo.test"
        )
    with pytest.raises(GuardError):
        guard.check_environment(KIND.issuer, "otro.host.test")
    with pytest.raises(GuardError):
        guard.check_environment(KIND.issuer, "x" + KIND.host)
    # el host de produccion no pasa por parecerse al de staging (comparacion exacta, sin sufijos)
    with pytest.raises(GuardError):
        guard.check_environment(PROD_ISSUER, "vectra.banco.internal")
    with pytest.raises(GuardError):
        guard.check_environment(STAGING.issuer, "prefijo." + STAGING.host)


def test_kind_and_staging_pass_and_a_request_goes_through() -> None:
    for environment in (KIND, STAGING):
        client, transport = _client(environment.issuer, environment.host)
        assert client is not None
        assert guard.check_environment(environment.issuer, environment.host) == environment
        assert client.get("/ping").status_code == 200
        assert transport.count == 1


@pytest.mark.parametrize(("environment", "name"), [(KIND, "kind"), (STAGING, "staging"), (None, "prod")])
def test_constants_match_the_gateway_values_and_policies(
    environment: guard.Environment | None, name: str
) -> None:
    values = yaml.safe_load((REPO / "identity-edge" / "gateway" / "values" / f"{name}.yaml").read_text())
    policies = (REPO / "identity-edge" / "gateway" / "generated" / name / "securitypolicies.yaml").read_text()
    issuers = set(re.findall(r"issuer: (\S+)", policies))
    assert issuers == {f"https://{values['hostname']}/auth/realms/vectra"}
    if environment is None:  # produccion: existe en el repo y NO esta en la lista
        assert values["hostname"] == PROD_HOST
    else:
        assert environment.host == values["hostname"]
        assert environment.issuer in issuers


def test_token_issuer_must_be_the_realm_of_the_environment() -> None:
    guard.check_token_issuer(KIND, KIND.issuer)
    with pytest.raises(GuardError):
        guard.check_token_issuer(KIND, PROD_ISSUER)
    with pytest.raises(GuardError):
        guard.check_token_issuer(KIND, STAGING.issuer)
    with pytest.raises(GuardError):
        guard.check_token_issuer(STAGING, KIND.issuer + "/")


def test_there_are_fourteen_sections() -> None:
    assert len(guard.SECTIONS) == 14 and len(set(guard.SECTIONS)) == 14


@pytest.mark.parametrize("section", guard.SECTIONS)
def test_every_section_passes_in_kind(section: str) -> None:
    guard.check_section(KIND, section)


@pytest.mark.parametrize(
    "section", ["rt2", "rt2-setup", "rt3", "rt5", "rt1", "rt4", "network", "load", "pii", "resilience"]
)
def test_denied_sections_in_staging(section: str) -> None:
    with pytest.raises(GuardError, match="section_denied_in_staging"):
        guard.check_section(STAGING, section)


@pytest.mark.parametrize("section", ["prepare", "u11", "report"])
def test_allowed_sections_in_staging(section: str) -> None:
    guard.check_section(STAGING, section)


def test_unknown_section_is_refused() -> None:
    with pytest.raises(GuardError, match="section_unknown"):
        guard.check_section(KIND, "rt9")


def test_test_job_patch_is_denied_in_staging_and_allowed_in_kind() -> None:
    guard.check_job_patch(KIND)
    with pytest.raises(GuardError, match="job_patch_denied_in_staging"):
        guard.check_job_patch(STAGING)


def test_reactivation_only_inside_rt2() -> None:
    guard.check_reactivation(KIND, "rt2")
    for section in ("decisions", "rt2-setup", "report", "prepare"):
        with pytest.raises(GuardError, match="reactivation_outside_rt2"):
            guard.check_reactivation(KIND, section)
    with pytest.raises(GuardError, match="section_denied_in_staging"):
        guard.check_reactivation(STAGING, "rt2")


def _at(hour: int, minute: int = 0, day: int = 12) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def test_decisions_estimate_for_2000_cases_at_10_per_second_is_about_42_minutes() -> None:
    assert guard.estimated_duration(2000, 10) == timedelta(seconds=200 + 2000 + 300)


def test_decisions_at_22_30_utc_is_refused_and_at_22_00_starts() -> None:
    with pytest.raises(GuardError, match="decisions_would_end_after_23_utc"):
        guard.check_decisions(KIND, _at(22, 30), 2000, 10)
    guard.check_decisions(KIND, _at(22, 0), 2000, 10)


def test_decisions_at_23_30_is_refused_and_at_10_00_starts() -> None:
    with pytest.raises(GuardError, match="decisions_would_end_after_23_utc"):
        guard.check_decisions(KIND, _at(23, 30), 2000, 10)
    guard.check_decisions(KIND, _at(10, 0), 2000, 10)


def test_decisions_that_end_exactly_at_23_00_start() -> None:
    start = datetime(2026, 11, 12, 23, 0, tzinfo=UTC) - guard.estimated_duration(2000, 10)
    guard.check_decisions(KIND, start, 2000, 10)
    with pytest.raises(GuardError):
        guard.check_decisions(KIND, start + timedelta(seconds=1), 2000, 10)


def test_decisions_at_00_10_of_the_next_day_starts() -> None:
    guard.check_decisions(KIND, _at(0, 10, day=13), 2000, 10)


def test_decisions_use_the_utc_instant_not_the_local_clock() -> None:
    bogota = timezone(timedelta(hours=-5))
    with pytest.raises(GuardError):
        guard.check_decisions(KIND, datetime(2026, 11, 12, 17, 30, tzinfo=bogota), 2000, 10)  # 22:30 UTC
    guard.check_decisions(KIND, datetime(2026, 11, 12, 5, 0, tzinfo=bogota), 2000, 10)  # 10:00 UTC


def test_decisions_clock_must_carry_a_timezone() -> None:
    with pytest.raises(GuardError, match="clock_without_timezone"):
        guard.check_decisions(KIND, datetime(2026, 11, 12, 10, 0), 100, 10)


def test_decisions_in_staging_are_capped_at_100_cases() -> None:
    guard.check_decisions(STAGING, _at(10), 100, 10)
    with pytest.raises(GuardError, match="decisions_volume_over_100_in_staging"):
        guard.check_decisions(STAGING, _at(10), 101, 10)


@pytest.mark.parametrize(("volume", "rate"), [(-1, 10), (10, 0), (10, -1)])
def test_decisions_volume_and_rate_are_validated(volume: int, rate: float) -> None:
    with pytest.raises(GuardError, match="decisions_volume_or_rate_invalid"):
        guard.check_decisions(KIND, _at(10), volume, rate)


def test_guard_never_reads_the_system_clock() -> None:
    assert (
        "datetime.now" not in Path(guard.__file__).read_text()
        and ".now(" not in Path(guard.__file__).read_text()
    )


# --- U12-T02, F-04 de la revision de U12-T01: la barrera compara la identidad del entorno, no su nombre ------------------------------------------------


def test_f04_a_hand_built_environment_is_refused_everywhere() -> None:
    forged = guard.Environment(
        "kind", "vectra.banco.internal", "https://vectra.banco.internal/auth/realms/vectra"
    )
    for call in (
        lambda: guard.check_section(forged, "rt2"),
        lambda: guard.check_reactivation(forged, "rt2"),
        lambda: guard.check_job_patch(forged),
        lambda: guard.check_decisions(forged, datetime(2026, 11, 13, 10, tzinfo=UTC), 10, 10),
        lambda: guard.check_token_issuer(forged, forged.issuer),
    ):
        with pytest.raises(GuardError, match="environment_not_allowed"):
            call()
    equal_copy = guard.Environment(
        KIND.name, KIND.host, KIND.issuer
    )  # igual por valor, no es el entorno de la lista
    with pytest.raises(GuardError, match="environment_not_allowed"):
        guard.check_section(equal_copy, "prepare")
    guard.check_section(KIND, "rt2")
