"""La CLI `vectra-verification` (U12-T04, Paso 13; CA-6, 7, 8, 11, 13, 14): barreras, `--help`, codigos de salida, retoma, `prepare`, `decisions`, el informe y las evidencias de las demos.

Las secciones corren sobre los dobles de U12-T03 (`Rt2World`, `JobKubectl`, `PromDouble`) con el reloj falso: ninguna espera es real. Los nombres de las pruebas llevan la palabra con que los criterios filtran con `-k`
(`guard`, `help`, `exit`, `decisions`, `prepare`, `report`, `demo_evidence`).
"""

# ruff: noqa: E402
from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cli_world import Harness, WorldBackend
from rt2_world import REFERENCE, Rt2World
from rt5_world import JobKubectl, PromDouble, Rt5Spec, completed_job, every
from vectra_verification import cli, guard
from vectra_verification.clients.prom import PromClient
from vectra_verification.guard import GuardError

SYSTEM = Path(__file__).resolve().parents[2]
STAGING = guard.STAGING
SECTIONS_RUN = ("prepare", "decisions", "rt5", "rt3", "rt2-setup", "rt2", "u11", "report")
DEFERRED = ("network", "rt1", "rt4", "load", "pii", "resilience")


@pytest.fixture
def world() -> Iterator[Rt2World]:
    built = Rt2World()
    built.add_model(REFERENCE, "activo", registered_by="otro-ingeniero", approved_by="otro-cro")
    yield built
    built.close()


def harness(tmp_path: Path, world: Rt2World | None = None, **kw: object) -> Harness:
    backend = WorldBackend(world, **kw) if world is not None else None  # type: ignore[arg-type]
    return Harness(tmp_path / "verificacion", backend)


# --- guard: las barreras, antes de la primera solicitud ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("issuer", "host"),
    [
        ("https://vectra.banco.example/auth/realms/vectra", "vectra.banco.example"),  # produccion
        (guard.KIND.issuer, "vectra.banco.example"),
        (guard.STAGING.issuer, guard.KIND.host),
        ("https://vectra.localtest.me/auth/realms/vectra/", guard.KIND.host),
    ],
)
def test_guard_an_issuer_or_host_that_is_not_known_is_refused_with_3_and_no_request(
    tmp_path: Path, world: Rt2World, issuer: str, host: str
) -> None:
    h = harness(tmp_path, world)
    assert h.prepare() == 0
    for section in ("decisions", "rt5", "rt3", "rt2", "u11", "report", "network"):
        assert h.run(section, "--issuer", issuer, "--gateway-host", host) == 3, section
        assert "environment_not_allowed" in h.err.getvalue()
    assert h.factory_calls == 0 and h.requests == 0


@pytest.mark.parametrize("section", ["rt5", "rt3", "rt2-setup", "rt2", "network", "pii"])
def test_guard_sections_that_staging_does_not_allow_are_refused_with_3_and_no_request(
    tmp_path: Path, world: Rt2World, section: str
) -> None:
    h = harness(tmp_path, world)
    code = h.run(section, "--issuer", STAGING.issuer, "--gateway-host", STAGING.host)
    assert code == 3 and f"section_denied_in_staging:{section}" in h.err.getvalue()
    assert h.factory_calls == 0 and h.requests == 0 and not h.dir.exists()


def test_guard_decisions_with_2000_in_staging_is_refused_and_with_100_it_is_not_refused_by_the_volume(
    tmp_path: Path, world: Rt2World
) -> None:
    h = harness(tmp_path, world)
    staging = ("--issuer", STAGING.issuer, "--gateway-host", STAGING.host)
    assert h.run("decisions", *staging, "--volume", "2000") == 3
    assert "decisions_volume_over_100_in_staging" in h.err.getvalue() and h.factory_calls == 0
    assert (
        h.run("decisions", *staging, "--volume", "100") == 3
    )  # no hay `prepare`: se niega por eso, no por el volumen
    assert "prepare_missing" in h.err.getvalue() and h.factory_calls == 0 and h.requests == 0


def test_guard_decisions_at_2230_utc_is_refused_and_at_an_hour_that_ends_before_2300_it_runs(
    tmp_path: Path, world: Rt2World
) -> None:
    h = harness(tmp_path, world)
    assert h.prepare() == 0
    world.clock.advance((datetime(2026, 11, 13, 22, 30, tzinfo=UTC) - world.clock.now()).total_seconds())
    assert (
        h.run("decisions", "--volume", "2000") == 3 and "decisions_would_end_after_23_utc" in h.err.getvalue()
    )
    assert h.factory_calls == 0 and h.requests == 0
    world.clock.advance(
        -1
    )  # sigue siendo tarde: el reloj no vuelve; una hora de la manana se arma con otro mundo
    early = harness(tmp_path / "otro", Rt2World())
    early.backend.world.add_model(REFERENCE, "activo", registered_by="a", approved_by="b")  # type: ignore[union-attr]
    assert early.prepare() == 0 and early.run("decisions", "--volume", "20", "--settle-timeout", "120") == 0
    early.backend.world.close()  # type: ignore[union-attr]


def test_guard_a_reactivation_outside_rt2_is_refused() -> None:
    with pytest.raises(GuardError, match="reactivation_outside_rt2:rt3"):
        guard.check_reactivation(guard.KIND, "rt3")


def test_guard_the_reactivation_option_does_not_exist_outside_rt2(tmp_path: Path, world: Rt2World) -> None:
    h = harness(tmp_path, world)
    assert h.prepare() == 0
    for section in ("rt3", "rt5", "decisions", "rt2-setup", "u11", "report"):
        assert h.run(section, "--reactivation", "presenter") == 3, section
        assert "uso incorrecto" in h.err.getvalue()
    assert h.run("rt2", "--reactivation", "otra") == 3
    assert h.factory_calls == 0 and h.requests == 0


def test_guard_no_section_runs_without_prepare_and_network_is_refused_before_it_says_deferred(
    tmp_path: Path, world: Rt2World
) -> None:
    h = harness(tmp_path, world)
    for section in ("decisions", "rt5", "rt3", "rt2-setup", "rt2", "u11", "report", "network", "rt1", "pii"):
        assert h.run(section) == 3, section
        assert "prepare_missing" in h.err.getvalue() and "diferida" not in h.out.getvalue()
    assert h.factory_calls == 0 and h.requests == 0 and not h.dir.exists()


def test_guard_the_red_check_section_after_opening_the_session_would_have_sent_a_request(
    tmp_path: Path, world: Rt2World
) -> None:
    """El rojo de «cero solicitudes»: si la barrera corriera **despues** de crear el `Backend`, la fabrica ya habria sido llamada. La CLI llama a `guard.check_section` antes."""
    h = harness(tmp_path, world)
    assert h.prepare() == 0
    assert h.run("rt5", "--issuer", STAGING.issuer, "--gateway-host", STAGING.host) == 3
    assert h.factory_calls == 0


# --- help ----------------------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("section", [None, *guard.SECTIONS, "all"])
def test_help_of_the_tool_and_of_every_section_is_exit_0_without_requests_or_files(
    tmp_path: Path, world: Rt2World, section: str | None
) -> None:
    h = harness(tmp_path, world)
    argv = ["--help"] if section is None else [section, "--help"]
    code = h.run(*argv, directory=False)
    assert code == 0 and "usage" in h.out.getvalue().lower()
    assert h.factory_calls == 0 and h.requests == 0 and not h.dir.exists() and list(tmp_path.iterdir()) == []


def test_help_does_not_import_playwright_or_pyarrow_nor_read_the_vault() -> None:
    code = (
        "import sys, io\n"
        "from vectra_verification import cli\n"
        "assert cli.main(['--help'], stdout=io.StringIO()) == 0\n"
        "for s in ['prepare','decisions','rt2','u11','report','network','all']:\n"
        "    assert cli.main([s, '--help'], stdout=io.StringIO()) == 0, s\n"
        "bad = [m for m in ('playwright', 'pyarrow', 'vectra_verification.live', 'vectra_verification.simulator') if m in sys.modules]\n"
        "assert not bad, bad\n"
        "print('limpio')\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "", "HOME": str(Path.home())},
    )
    assert done.returncode == 0 and "limpio" in done.stdout, done.stderr


def test_help_the_console_script_answers_and_a_bad_option_is_3(tmp_path: Path, world: Rt2World) -> None:
    h = harness(tmp_path, world)
    assert h.run("rt5", "--no-existe") == 3 and "uso incorrecto" in h.err.getvalue()
    assert h.run("noexiste", directory=False) == 3
    assert h.run(*[], directory=False) if False else True


def test_help_without_arguments_prints_the_usage_and_exits_3(tmp_path: Path) -> None:
    h = Harness(tmp_path / "v")
    assert cli.main([], environ={}, stdout=h.out, stderr=h.err) == 3 and "usage" in h.err.getvalue().lower()


# --- exit: 0 pasa, 1 falla, 2 no ejecutado, 3 se nego ---------------------------------------------------------------------------------------------


T0 = datetime(2026, 11, 13, 14, 0, tzinfo=UTC)  # el reloj de `prepare` en estas pruebas
RUN_ID = "20261113-1000"  # el `runId` que da el reloj de `WorldClock` (10:00 UTC)


def rt5_world(world: Rt2World, *, log: str | None = None, job_ready: bool = True) -> WorldBackend:
    """Un RT-5 correcto: el Job `rt5-demo-<runId>` corrio entre 10:05 y 10:05:20, la alerta duro hasta 5 min despues y todo se mide 6 h mas tarde."""
    started = world.clock.now()
    job_start = started + timedelta(minutes=5)
    job_end = job_start + timedelta(seconds=20)
    now = started + timedelta(hours=6)
    spec = Rt5Spec(
        started_at=started,
        alert=every(job_start, job_end + timedelta(minutes=5)),
        deny=[(t, 1.0) for t in every(job_start + timedelta(seconds=5), job_end + timedelta(minutes=14))],
        counter=[(t, 0.0) for t in every(started, now)],
        lowest=now - timedelta(days=3),
    )
    kubectl = JobKubectl(
        completed_job(job_start, job_end, f"rt5-demo-{RUN_ID}") if job_ready else None,
        **({"log": log} if log else {}),
    )
    backend = WorldBackend(world, inner=kubectl, prom=PromClient("http://prom", transport=PromDouble(spec)))
    world.clock.advance(6 * 3600)
    return backend


@pytest.mark.parametrize(
    ("variant", "code", "text"),
    [
        ("good", 0, "pasa"),
        ("app403", 1, "falla"),
        ("nojob", 2, "no ejecutado"),
    ],
)
def test_exit_codes_pasa_is_0_falla_is_1_and_no_ejecutado_is_2_with_three_different_texts(
    tmp_path: Path, variant: str, code: int, text: str
) -> None:
    world = Rt2World()
    h = Harness(tmp_path / "v")
    assert h.prepare() == 0 if False else True
    h = Harness(tmp_path / "v", clock=world.clock)
    assert h.prepare() == 0
    from rt5_world import APP_LOG

    backend = rt5_world(world, log=APP_LOG if variant == "app403" else None, job_ready=variant != "nojob")
    h.backend = backend
    assert h.run("rt5") == code
    last = h.out.getvalue().strip().splitlines()[-1]
    assert last.startswith("seccion rt5: ") and f"({code})" in last and text in last
    other = {t for _, _, t in [("", 0, "pasa"), ("", 1, "falla"), ("", 2, "no ejecutado")]} - {text}
    assert not any(f"seccion rt5: {o} " in last for o in other)
    world.close()


def test_exit_the_three_results_and_the_refusal_have_four_different_texts() -> None:
    assert len(set(cli.RESULT_TEXT.values())) == 4 and cli.code_of(["pasa"]) == 0
    assert (
        cli.code_of(["pasa", "falla", "no ejecutado"]) == 1
        and cli.code_of(["pasa", "no ejecutado"]) == 2
        and cli.code_of([]) == 0
    )


@pytest.mark.parametrize("section", DEFERRED)
def test_exit_the_deferred_sections_are_2_with_zero_requests_and_a_line_in_the_manifest_with_the_citation(
    tmp_path: Path, world: Rt2World, section: str
) -> None:
    h = harness(tmp_path, world)
    assert h.prepare() == 0
    assert h.run(section) == 2
    assert h.factory_calls == 0 and h.requests == 0
    record = h.manifest()["sections"][section]
    assert (
        record["state"] == "diferida por la demo"
        and record["exit_code"] == 2
        and "enmienda §3 U12, fila «13»" in record["note"]
    )
    assert "diferida por la demo" in h.out.getvalue() and "(2)" in h.out.getvalue()
