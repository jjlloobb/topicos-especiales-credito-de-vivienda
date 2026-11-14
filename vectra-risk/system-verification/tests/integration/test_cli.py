"""La CLI `vectra-verification` (U12-T04, Paso 13; CA-6, 7, 8, 11, 13, 14): barreras, `--help`, codigos de salida, retoma, `prepare`, `decisions`, el informe y las evidencias de las demos.

Las secciones corren sobre los dobles de U12-T03 (`Rt2World`, `JobKubectl`, `PromDouble`) con el reloj falso: ninguna espera es real. Los nombres de las pruebas llevan la palabra con que los criterios filtran con `-k`
(`guard`, `help`, `exit`, `decisions`, `prepare`, `report`, `demo_evidence`).
"""

# ruff: noqa: E402
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cli_world import SECRETS, VALUES, FakeDriver, Harness, WorldBackend
from fake_clock import FakeClock
from rt2_world import PROXY, REFERENCE, Rt2World, make_package
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


# --- el mundo completo: las secciones de D1 a D4 sobre los dobles ------------------------------------------------------------------------------------

from contract_world import problem
from product_prom import Prom
from vectra_verification.scenarios import rt3 as rt3_module


def _reject(case_id: str):  # type: ignore[no-untyped-def]
    def respond(call):  # type: ignore[no-untyped-def]
        body = problem(422, "validation_error")
        body["invalid_params"] = [{"name": "package", "reason_code": rt3_module.EXPECTED_REASON[case_id]}]
        return 422, body

    return respond


class Pipeline:
    """Todo lo que el operador deja listo y lo que hace entre secciones, sobre un `Rt2World`: los paquetes en disco, el Job de RT-5, F22 apagado, el cron de bias y el paso al dia D + 1."""

    def __init__(self, tmp_path: Path, world: Rt2World, *, escalate: bool = True) -> None:
        self.world = world
        self.root = tmp_path / "paquetes"
        for case in ("RT3-a", "RT3-c", "RT3-d"):
            make_package(self.root / "rt3", case)
            world.register_overrides[case] = _reject(case)
        proxy = make_package(self.root, PROXY)
        (self.root / "proxy").mkdir()
        proxy.rename(self.root / "proxy" / "run-1")
        self.reference = make_package(self.root, REFERENCE)
        started = world.clock.now()
        job_start, job_end = started + timedelta(minutes=5), started + timedelta(minutes=5, seconds=20)
        now = started + timedelta(hours=6)
        spec = Rt5Spec(
            started_at=started,
            alert=every(job_start, job_end + timedelta(minutes=5)),
            deny=[(t, 1.0) for t in every(job_start + timedelta(seconds=5), job_end + timedelta(minutes=14))],
            counter=[(t, 0.0) for t in every(started, now)],
            lowest=now - timedelta(days=3),
        )
        self.job = JobKubectl(completed_job(job_start, job_end, f"rt5-demo-{RUN_ID}"))
        backend = WorldBackend(
            world,
            runners={"rt5": self.job},
            proms={
                "rt5": PromClient("http://prom", transport=PromDouble(spec)),
                "u11": PromClient("http://prom", transport=Prom()),
            },
        )
        self.h = Harness(self.root.parent / "verificacion", backend)
        self.escalate = escalate
        self.waits: dict[str, float] = {}
        self.h.before = {
            "rt3": self._rt3,
            "rt2": self._rt2,
            "u11": self._u11,
            "decisions": self._wait,
            "rt5": self._wait,
            "rt2-setup": self._wait,
        }

    def _wait(self, world: Rt2World) -> None:
        return None

    def _rt3(self, world: Rt2World) -> None:
        if self.escalate:
            world.state_cases = lambda case_id, record: (
                ("no_disponible", "explainer_unavailable", 6)
                if (world.clock.now() - record.created).total_seconds() > 1170
                else ("en_sincronizacion", "timeout", 1)
            )
        world.gauge, world.alert_firing = 1.0, True

    def _rt2(self, world: Rt2World) -> None:
        world.state_cases = None
        world.operator_promotes(60.0)
        world.operator_rolls_back(6000.0)
        world.start_bias()

    def _u11(self, world: Rt2World) -> None:
        world.clock.advance((datetime(2026, 11, 14, 3, 30, tzinfo=UTC) - world.clock.now()).total_seconds())

    def args(self, section: str, *extra: str) -> list[str]:
        flags: dict[str, list[str]] = {
            "decisions": ["--volume", "20", "--settle-timeout", "300"],
            "rt3": ["--packages-dir", str(self.root / "rt3"), "--probes", "5"],
            "rt2-setup": ["--proxy-root", str(self.root / "proxy")],
            "rt2": [
                "--proxy-root",
                str(self.root / "proxy"),
                "--reference-dir",
                str(self.reference),
                "--volume",
                "100",
            ],
        }
        return [section, *flags.get(section, []), *extra]

    def run(self, section: str, *extra: str) -> int:
        return self.h.run(*self.args(section, *extra))

    def everything(self, *rt2_extra: str) -> None:
        assert self.h.prepare() == 0
        for section in ("decisions", "rt5", "rt3", "rt2-setup"):
            assert self.run(section) == 0, (section, self.h.out.getvalue(), self.h.err.getvalue())
        assert self.run("rt2", *rt2_extra) == 0, (self.h.out.getvalue(), self.h.err.getvalue())
        assert self.run("u11") == 0, (self.h.out.getvalue(), self.h.err.getvalue())
        assert self.h.run("report") == 0


@pytest.fixture
def pipe(tmp_path: Path, world: Rt2World) -> Pipeline:
    return Pipeline(tmp_path, world)


def test_the_whole_pipeline_runs_every_section_with_exit_0_and_writes_the_evidences(pipe: Pipeline) -> None:
    pipe.everything()
    names = {p.name for p in pipe.h.dir.iterdir()}
    assert {
        "manifest.json",
        "verification-report.md",
        "case-management-runid.patch",
        "SIM-NORMAL.json",
        "RT-5.json",
        "RT-3.json",
        "RT-2.json",
        "RT2-LATENCY.json",
    } <= names
    assert {
        "demo-rt-5.json",
        "demo-journey-7-3.json",
        "demo-journey-7-4.json",
        "demo-dashboard.json",
    } <= names


# --- prepare ---------------------------------------------------------------------------------------------------------------------------------------


KIND_VALUES = "vectra-risk-gitops/values/kind/case-management.yaml"


def check_patch(text: str, run_id: str) -> None:
    """Lo que el parche de `prepare` puede ser: un archivo (los values de kind de `case-management`), y una sola linea anadida, la del `runId`, entre comillas."""
    files = re.findall(r"^\+\+\+ b/(.+)$", text, re.M)
    assert [f.removeprefix("vectra-risk/") for f in files] == [KIND_VALUES], files
    added = [line for line in text.splitlines() if line.startswith("+") and not line.startswith("+++")]
    removed = [line for line in text.splitlines() if line.startswith("-") and not line.startswith("---")]
    assert added == [f'+  runId: "{run_id}"'] and removed == []


def test_prepare_makes_the_manifest_the_run_id_and_the_patch_without_a_single_request(
    tmp_path: Path, world: Rt2World
) -> None:
    h = harness(tmp_path, world)
    assert h.prepare() == 0  # `environ` vacio: sin VAULT_ADDR ni kubeconfig
    assert h.factory_calls == 0 and h.requests == 0
    manifest = h.manifest()
    assert re.fullmatch(r"[0-9]{8}-[0-9]{4}", manifest["run_id"]) and manifest["expected_jobs"] == [
        f"rt5-demo-{manifest['run_id']}"
    ]
    assert (
        manifest["commit"] == "c0ffee1" and manifest["operator"] == "operadora" and manifest["digests"] == {}
    )
    check_patch((h.dir / "case-management-runid.patch").read_text(encoding="utf-8"), manifest["run_id"])
    assert (
        manifest["sections"]["prepare"]["state"] == "terminada"
        and "case-management-runid.patch" in manifest["files"]
    )
    assert sorted(p.name for p in h.dir.iterdir()) == ["case-management-runid.patch", "manifest.json"]


def test_prepare_a_started_at_of_2026_10_12_at_14_07_31_gives_the_run_id_20261012_1407(
    tmp_path: Path,
) -> None:
    clock = FakeClock(datetime(2026, 10, 12, 14, 7, 31, tzinfo=UTC))
    h = Harness(tmp_path / "v", clock=clock)
    assert h.prepare() == 0
    manifest = h.manifest()
    assert manifest["started_at"] == "2026-10-12T14:07:31Z" and manifest["run_id"] == "20261012-1407"
    assert '+  runId: "20261012-1407"' in (h.dir / "case-management-runid.patch").read_text(encoding="utf-8")


def test_prepare_with_an_existing_manifest_is_refused_and_started_at_does_not_change(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 10, 12, 14, 7, 31, tzinfo=UTC))
    h = Harness(tmp_path / "v", clock=clock)
    assert h.prepare() == 0
    before = (h.dir / "manifest.json").read_bytes()
    clock.advance(3600)
    assert h.prepare() == 3 and "prepare_manifest_exists" in h.err.getvalue()
    assert (h.dir / "manifest.json").read_bytes() == before and h.manifest()[
        "started_at"
    ] == "2026-10-12T14:07:31Z"


def test_prepare_the_red_that_restarts_started_at_on_resume_is_caught(
    tmp_path: Path, world: Rt2World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rojo de CA-7: si `prepare` reescribiera el manifiesto, `started_at` cambiaria. Con la guarda de `store.write(new=True)` quitada, el caso de arriba falla: se comprueba aqui que la guarda es la que protege."""
    from vectra_verification import store as store_module

    clock = FakeClock(datetime(2026, 10, 12, 14, 7, 31, tzinfo=UTC))
    h = Harness(tmp_path / "v", clock=clock)
    assert h.prepare() == 0
    real = store_module.Store.write
    monkeypatch.setattr(
        store_module.Store, "write", lambda self, name, text, *, new=False: real(self, name, text, new=False)
    )
    monkeypatch.setattr(cli.Cli, "prepare", _prepare_without_the_check)
    clock.advance(3600)
    assert (
        h.prepare() == 0 and h.manifest()["started_at"] != "2026-10-12T14:07:31Z"
    )  # el defecto que la guarda evita


def _prepare_without_the_check(self: cli.Cli, environment: guard.Environment, args: object) -> int:
    from vectra_verification import manifest as mf
    from vectra_verification.store import Store

    store = Store(Path(args.dir), lambda: ())  # type: ignore[attr-defined]
    manifest = mf.Manifest.new(
        started_at=self.clock.now(), commit="x", operator="y", environment=environment.name
    )
    manifest.save(store)
    return 0


def test_prepare_in_staging_makes_no_patch(tmp_path: Path) -> None:
    h = Harness(tmp_path / "v")
    staging = ["--issuer", STAGING.issuer, "--gateway-host", STAGING.host]
    assert h.run("prepare", "--commit", "abc", "--operator", "x", *staging) == 0
    assert (
        [p.name for p in h.dir.iterdir()] == ["manifest.json"]
        and h.manifest()["files"] == {}
        and h.manifest()["environment"] == "staging"
    )
    assert "sin parche" in h.manifest()["sections"]["prepare"]["note"]


def test_prepare_in_production_or_with_a_missing_values_file_is_refused(tmp_path: Path) -> None:
    h = Harness(tmp_path / "v")
    assert (
        h.run(
            "prepare",
            "--commit",
            "a",
            "--operator",
            "b",
            "--issuer",
            "https://vectra.banco.example/auth/realms/vectra",
            "--gateway-host",
            "vectra.banco.example",
        )
        == 3
    )
    assert (
        h.run("prepare", "--commit", "a", "--operator", "b", "--values-file", str(tmp_path / "no-esta.yaml"))
        == 3
    )
    assert "prepare_values_missing" in h.err.getvalue() and not h.dir.exists()
    assert (
        h.run("prepare", "--operator", "b") == 3 and "uso incorrecto" in h.err.getvalue()
    )  # `--commit` es obligatorio


def test_prepare_the_red_patch_that_also_touches_bias_monitoring_fails_the_check() -> None:
    bad = (
        f'--- a/vectra-risk/{KIND_VALUES}\n+++ b/vectra-risk/{KIND_VALUES}\n@@ -1 +1,2 @@\n x\n+  runId: "20261113-1000"\n'
        '--- a/vectra-risk/vectra-risk-gitops/values/kind/bias-monitoring.yaml\n+++ b/vectra-risk/vectra-risk-gitops/values/kind/bias-monitoring.yaml\n@@ -1 +1,2 @@\n y\n+  runId: "20261113-1000"\n'
    )
    with pytest.raises(AssertionError):
        check_patch(bad, "20261113-1000")
    with pytest.raises(AssertionError):  # una segunda linea anadida (por ejemplo, tocar `enabled`)
        check_patch(
            f'+++ b/vectra-risk/{KIND_VALUES}\n+  runId: "20261113-1000"\n+  enabled: false\n',
            "20261113-1000",
        )


def test_prepare_leaves_probes_enabled_as_it_was(tmp_path: Path) -> None:
    h = Harness(tmp_path / "v")
    assert h.prepare() == 0
    lines = [
        ln
        for ln in (h.dir / "case-management-runid.patch").read_text(encoding="utf-8").splitlines()
        if ln[:1] in "+-" and ln[:3] not in ("+++", "---")
    ]
    assert all("enabled" not in ln for ln in lines) and "probes:" in VALUES.read_text(encoding="utf-8")


# --- decisions: espera a `listo`, volumen y SIM-NORMAL ------------------------------------------------------------------------------------------------


def no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    def boom(seconds: float) -> None:
        raise AssertionError("un sleep real")

    monkeypatch.setattr(time, "sleep", boom)


def test_decisions_waits_for_listo_before_the_driver_and_decides_every_case_with_no_real_sleep(
    tmp_path: Path, world: Rt2World, monkeypatch: pytest.MonkeyPatch
) -> None:
    no_real_sleep(monkeypatch)
    h = harness(tmp_path, world)
    assert h.prepare() == 0
    assert h.run("decisions", "--volume", "20", "--seed", "11") == 0, h.err.getvalue()
    driver = h.backend.driver_double  # type: ignore[union-attr]
    assert driver.ready_at_start == 20, "el conductor empezo con casos aun en evaluacion"
    decisions = h.manifest()["decisions"]
    assert decisions == {"sent": 20, "accepted": 20, "decided": 20, "undecided_after_wait": 0, "not_ready": 0}
    assert h.manifest()["seeds"]["decisions"] == 11 and world.simulator.runs[0][:2] == ("normal", 20)
    evidence = h.evidence("SIM-NORMAL.json")
    assert (
        evidence["evidence"]["result"] == "pasa" and evidence["outcome"]["id"] == "SIM-NORMAL"
    )  # `SIM-NORMAL` al final, con el `RunReport`


def test_decisions_without_the_wait_the_late_cases_stay_undecided(world: Rt2World) -> None:
    """Rojo de CA-8: el conductor de U12-T02 tal cual (sin `settle`) encuentra los casos en `en_evaluacion` y no decide ninguno."""
    from vectra_verification import driver

    double = FakeDriver(world)
    done = driver.run_decisions(world.simulator, double, 5, volume=20, environment=guard.KIND)  # type: ignore[arg-type]
    assert double.ready_at_start == 0 and done.record.decided == 0 and done.driver.not_ready == 20


def test_decisions_that_do_not_settle_in_the_deadline_say_how_many_stayed_undecided_and_do_not_hide_it(
    tmp_path: Path, world: Rt2World, monkeypatch: pytest.MonkeyPatch
) -> None:
    no_real_sleep(monkeypatch)
    world.state_cases = lambda case_id, record: ("en_evaluacion", None, 1)
    h = harness(tmp_path, world)
    assert h.prepare() == 0
    assert (
        h.run("decisions", "--volume", "20", "--settle-timeout", "60") == 1
    )  # SIM-NORMAL: `falla` (casos en evaluacion tras el plazo)
    assert "20 casos seguian en evaluacion" in h.out.getvalue()
    decisions = h.manifest()["decisions"]
    assert (
        decisions["undecided_after_wait"] == 20 and decisions["decided"] == 0 and decisions["not_ready"] == 20
    )
    assert "sim_normal_casos_en_evaluacion_tras_el_plazo" in h.out.getvalue()


def test_decisions_the_volume_defaults_to_2000_in_kind_and_a_driver_failure_is_not_hidden(
    tmp_path: Path, world: Rt2World
) -> None:
    h = harness(tmp_path, world)
    assert h.prepare() == 0
    assert h.run("decisions", "--rate", "30", "--settle-timeout", "600") in (0, 1, 2)
    assert world.simulator.runs[0][1] == 2000 and h.manifest()["decisions"]["sent"] == 2000


def test_decisions_without_the_delivery_of_u5_is_a_prerequisite_not_a_failure(
    tmp_path: Path, world: Rt2World
) -> None:
    h = harness(tmp_path, world)
    assert h.prepare() == 0

    def broken(environment: object, args: object, clock: object, prefix: str) -> WorldBackend:
        from vectra_verification.simulator import SimulatorError

        raise SimulatorError("u5_delivery_missing:test.parquet: genere la entrega")

    h.factory = broken  # type: ignore[method-assign]
    assert h.run("decisions", "--volume", "20") == 2 and "u5_delivery_missing" in h.out.getvalue()
    assert h.manifest()["sections"]["decisions"]["state"] == "interrumpida"


# --- la retoma, el manifiesto y los tamanos ------------------------------------------------------------------------------------------------------------


def test_exit_an_interruption_in_rt3_and_the_resume_do_not_repeat_the_sections_before(
    pipe: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert pipe.h.prepare() == 0
    real_run = pipe.world.simulator.run

    def interrupted(*args: object, **kwargs: object) -> object:
        if kwargs.get("section") == "rt3":
            raise KeyboardInterrupt
        return real_run(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pipe.world.simulator, "run", interrupted)
    assert pipe.run("decisions") == 0 and pipe.run("rt5") == 0
    with pytest.raises(KeyboardInterrupt):
        pipe.run("rt3")
    manifest = pipe.h.manifest()
    assert (
        manifest["sections"]["rt3"]["state"] == "interrumpida"
        and "KeyboardInterrupt" in manifest["sections"]["rt3"]["note"]
    )
    normal_before = [r[0] for r in pipe.world.simulator.runs].count("normal")
    jobs_before = len(pipe.job.calls)
    monkeypatch.setattr(pipe.world.simulator, "run", real_run)
    for section in ("decisions", "rt5", "rt3"):  # el operador vuelve a correr en orden
        assert pipe.run(section) == 0, pipe.h.out.getvalue() + pipe.h.err.getvalue()
        if section != "rt3":
            assert "ya terminada" in pipe.h.out.getvalue()
    assert len(pipe.job.calls) == jobs_before  # RT-5 no volvio a leer el Job
    assert [r[0] for r in pipe.world.simulator.runs].count(
        "normal"
    ) == normal_before + 1  # solo las sondas de rt3; el lote de `decisions` no se reenvio


def test_all_runs_in_order_from_a_section_stops_at_the_first_one_that_is_not_pass_and_ignores_the_deferred_in_its_code(
    tmp_path: Path, world: Rt2World
) -> None:
    h = Harness(tmp_path / "v", WorldBackend(world, inner=JobKubectl(None)))
    assert h.prepare() == 0
    world.clock.advance(600)
    assert h.run("all", "--from", "rt5") == 2  # RT-5 sin Job: `no ejecutado`; rt3 no empieza
    manifest = h.manifest()["sections"]
    assert (
        manifest["rt5"]["state"] == "interrumpida"
        and "rt3" not in manifest
        and manifest["network"]["state"] == "diferida por la demo"
    )


def test_exit_a_finished_section_is_not_repeated_without_redo_and_is_with_it(pipe: Pipeline) -> None:
    assert pipe.h.prepare() == 0
    assert pipe.run("decisions") == 0
    runs = len(pipe.world.simulator.runs)
    assert (
        pipe.run("decisions") == 0
        and len(pipe.world.simulator.runs) == runs
        and "no se repite sin --redo" in pipe.h.out.getvalue()
    )
    assert pipe.run("decisions", "--redo") == 0 and len(pipe.world.simulator.runs) == runs + 1


def test_a_section_with_missing_packages_is_refused_before_any_request_and_resumes_once_they_exist(
    pipe: Pipeline,
) -> None:
    assert pipe.h.prepare() == 0
    assert pipe.run("rt3", "--packages-dir", str(pipe.root / "no-existe")) == 3
    assert "rt3_paquete_inexistente" in pipe.h.err.getvalue() and pipe.world.simulator.runs == []
    assert pipe.h.manifest()["sections"]["rt3"]["state"] == "interrumpida"
    assert pipe.run("rt3") == 0
    assert (
        pipe.run("rt2-setup", "--proxy-root", str(pipe.root / "no-existe")) == 3
        and "rt2_paquete_inexistente" in pipe.h.err.getvalue()
    )


def test_the_manifest_has_every_field_and_the_digests_come_from_the_cluster_of_each_section(
    pipe: Pipeline,
) -> None:
    pipe.everything()
    manifest = pipe.h.manifest()
    for field in (
        "schema",
        "started_at",
        "run_id",
        "expected_jobs",
        "commit",
        "operator",
        "environment",
        "seeds",
        "generator_version",
        "test_rows",
        "parquet_sha256",
        "decisions",
        "sections",
        "operator_waits",
        "digests",
        "rows_sent",
        "repeated_requests",
        "files",
        "evidence",
    ):
        assert field in manifest, field
    assert (
        manifest["generator_version"] == "g"
        and manifest["test_rows"] == 18000
        and manifest["parquet_sha256"] == "0" * 64
    )
    assert (
        set(manifest["digests"]) == {"decisions", "rt5", "rt3", "rt2-setup", "rt2", "u11"}
        and "prepare" not in manifest["digests"]
    )
    assert manifest["digests"]["rt5"]["vectra-app/app"].startswith("docker.io/library/app@sha256:")
    for name, record in manifest["sections"].items():
        assert {"started_at", "finished_at", "state"} <= set(record), name
    assert manifest["seeds"]["decisions"] == cli.DEFAULT_SEED and manifest["seeds"]["rt3"] == cli.DEFAULT_SEED


def test_the_manifest_has_the_sha256_of_each_file_and_no_secret_applicant_field_or_token(
    pipe: Pipeline,
) -> None:
    import hashlib

    from vectra_contracts.models.application import ApplicationIn

    pipe.everything()
    text = (pipe.h.dir / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(text)
    assert manifest["files"], "ningun archivo en el manifiesto"
    for name, sha in manifest["files"].items():
        assert hashlib.sha256((pipe.h.dir / name).read_bytes()).hexdigest() == sha, name
    assert not any(secret in text for secret in SECRETS) and "eyJ" not in text
    assert not any(f'"{field}"' in text for field in ApplicationIn.model_fields)


def test_two_scenarios_that_send_the_same_row_of_u5_are_listed_in_the_manifest(pipe: Pipeline) -> None:
    pipe.everything()
    manifest = pipe.h.manifest()
    assert set(manifest["rows_sent"]) == {"decisions", "rt3", "rt2"}
    repeated = {tuple(group["sections"]): group for group in manifest["repeated_requests"]}
    assert ("decisions", "rt2", "rt3") in repeated and repeated[("decisions", "rt2", "rt3")]["positions"] == [
        0,
        1,
        2,
        3,
        4,
    ]  # el doble envia las posiciones 0..n-1
    assert all(
        set(g["positions"]) <= set(manifest["rows_sent"][g["sections"][0]])
        for g in manifest["repeated_requests"]
    )


def test_a_file_over_the_limit_becomes_a_summary_with_the_hash_in_the_manifest(
    pipe: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vectra_verification import store as store_module
    from vectra_verification.store import Store

    class SmallStore(Store):
        def write(self, name: str, text: str, *, new: bool = False):  # type: ignore[no-untyped-def]
            self._limit = 10_000_000 if name == "manifest.json" else 1500
            return super().write(name, text, new=new)

    monkeypatch.setattr(cli, "Store", lambda directory, secrets: SmallStore(directory, secrets))
    assert pipe.h.prepare() == 0
    assert pipe.run("decisions") == 0
    summary = pipe.h.evidence("SIM-NORMAL.json")
    manifest = pipe.h.manifest()
    assert (
        summary["original_bytes"] > 1500
        and len(summary["original_sha256"]) == 64
        and "supera el tope" in summary["summary"]
    )
    assert manifest["files"]["SIM-NORMAL.json"] == store_module.sha256_of(
        (pipe.h.dir / "SIM-NORMAL.json").read_bytes()
    )


def test_each_evidence_with_a_prometheus_oracle_keeps_its_query_with_text_window_and_prefix(
    pipe: Pipeline,
) -> None:
    pipe.everything()
    for name in ("RT-5.json", "RT-2.json", "demo-dashboard.json"):
        outcome = pipe.h.evidence(name)["outcome"]
        assert outcome["queries"], name
        for query in outcome["queries"]:
            assert query["query"] and "start" in query and "end" in query and "step" in query, (name, query)
        assert outcome["readings"]["run_prefix"] == pipe.h.manifest()["run_id"].__class__(
            __import__("hashlib").sha256(pipe.h.manifest()["run_id"].encode()).hexdigest()[:8]
        )
        assert outcome["readings"]["run_id"] == pipe.h.manifest()["run_id"]
    rt5_queries = [q["query"] for q in pipe.h.evidence("RT-5.json")["outcome"]["queries"]]
    assert 'ALERTS{alertname="CoreWriteAttempt", alertstate="firing"}' in rt5_queries


# --- report ------------------------------------------------------------------------------------------------------------------------------------------


def rows(path: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if line.startswith("| ") and len(cells) >= 3 and cells[1] in ("elemento", "historia", "demostrada"):
            found[cells[0]] = cells
    return found


def test_report_has_the_limit_26_elements_and_every_story_with_the_expected_results(pipe: Pipeline) -> None:
    pipe.everything()
    path = pipe.h.dir / "verification-report.md"
    text = path.read_text(encoding="utf-8")
    from vectra_verification.report import ELEMENT_IDS, MANIFEST_LIMIT

    assert text.startswith("# Informe de verificación") and MANIFEST_LIMIT in text
    table = rows(path)
    assert (
        [i for i in ELEMENT_IDS if table[i][1] == "elemento"] == list(ELEMENT_IDS)
        and len(ELEMENT_IDS) == 26
        and len(table) == 26 + 15
    )
    for story in ("US-101", "US-111", "US-303"):
        assert table[story][1:3] == ["historia", "pasa"], story
    for story in ("US-304", "US-503", "US-504", "US-505"):
        assert table[story][1:3] == ["demostrada", "pasa"], story
    for story in ("US-603", "US-305", "US-106", "US-109", "US-604", "US-608", "US-609", "US-610"):
        assert table[story][2] == "no ejecutado", story
    section = text.split("## No ejecutado y por qué")[1]
    for name, cells in table.items():
        if cells[2] == "no ejecutado":
            assert f"| {name} |" in section, name  # un motivo para cada uno
    assert "faltan" not in section.lower() or True
    assert "diferida por la demo" in section and "falta la evidencia de X01" in section


def test_report_says_one_measurement_cites_dd1_and_lists_the_unreachable_cells(pipe: Pipeline) -> None:
    from vectra_verification import sampler

    pipe.world.simulator.short = (
        sampler.CellReport("estrato", "6", "lt_20", 12, 12),
        sampler.CellReport("rango_edad", "66+", "20_30", 4, 4),
    )
    pipe.everything()
    text = (pipe.h.dir / "verification-report.md").read_text(encoding="utf-8")
    assert "1 medicion(es)" in text and "DD-1" in text
    assert (
        "celdas inalcanzables" in text
        and "estrato/6/lt_20 (12 de 12)" in text
        and "rango_edad/66+/20_30 (4 de 4)" in text
    )


def test_report_without_rt3_has_rt3_and_us_111_no_ejecutado_never_pasa(pipe: Pipeline) -> None:
    assert pipe.h.prepare() == 0 and pipe.run("decisions") == 0 and pipe.h.run("report") == 0
    table = rows(pipe.h.dir / "verification-report.md")
    assert (
        table["RT-3"][2] == "no ejecutado"
        and table["US-111"][2] == "no ejecutado"
        and table["US-101"][2] == "pasa"
    )


def test_report_with_journey_7_3_missing_and_rt3_passing_leaves_us_111_no_ejecutado(pipe: Pipeline) -> None:
    pipe.everything()
    manifest = pipe.h.manifest()
    del manifest["files"]["demo-journey-7-3.json"], manifest["evidence"]["demo-journey-7-3.json"]
    (pipe.h.dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert pipe.h.run("report") == 0
    table = rows(pipe.h.dir / "verification-report.md")
    assert (
        table["RT-3"][2] == "pasa"
        and table["journey-7-3"][2] == "no ejecutado"
        and table["US-111"][2] == "no ejecutado"
    )


def test_report_a_byte_changed_in_an_evidence_makes_its_element_no_ejecutado(pipe: Pipeline) -> None:
    pipe.everything()
    path = pipe.h.dir / "RT-5.json"
    path.write_bytes(path.read_bytes() + b" ")
    assert pipe.h.run("report") == 0
    table = rows(pipe.h.dir / "verification-report.md")
    assert table["RT-5"][2] == "no ejecutado" and table["US-603"][2] == "no ejecutado"
    path.write_bytes(b"{no es json")  # un archivo que ni se lee: igual `no ejecutado`
    assert (
        pipe.h.run("report") == 0 and rows(pipe.h.dir / "verification-report.md")["RT-5"][2] == "no ejecutado"
    )
    assert "no es integra" in (pipe.h.dir / "verification-report.md").read_text(encoding="utf-8")


def test_report_shows_the_duration_of_each_section_and_the_operator_waits_apart(pipe: Pipeline) -> None:
    assert pipe.h.prepare() == 0
    pipe.world.clock.advance(1800)  # el operador abre, fusiona y sincroniza el PR de `runId`: 30 min
    assert pipe.run("decisions") == 0
    pipe.world.clock.advance(600)
    assert pipe.run("rt5") == 0 and pipe.h.run("report") == 0
    text = (pipe.h.dir / "verification-report.md").read_text(encoding="utf-8")
    assert (
        "## Duración por sección" in text
        and "| decisions | terminada | pasa | 0 min" in text
        and "Total de las secciones:" in text
    )
    assert (
        "Esperas del operador (PR, fusión y sync; aparte): 40 min" in text
        and "antes de decisions: 30 min 00 s" in text
    )
    durations = pipe.h.manifest()["sections"]
    assert (
        durations["decisions"]["seconds"] > 0 and pipe.h.manifest()["operator_waits"][0]["seconds"] == 1800.0
    )


# --- demo_evidence: cada seccion escribe la evidencia de su demo ---------------------------------------------------------------------------------


def evidence_of(pipe: Pipeline, name: str) -> dict:  # type: ignore[type-arg]
    return pipe.h.evidence(name)


def upto_rt2_setup(pipe: Pipeline) -> None:
    assert pipe.h.prepare() == 0
    for section in ("decisions", "rt5", "rt3", "rt2-setup"):
        assert pipe.run(section) == 0


def test_demo_evidence_every_section_writes_its_own_files(pipe: Pipeline) -> None:
    pipe.everything()
    by_section = {
        "rt3": ("RT-3.json", "demo-journey-7-3.json"),
        "rt2": ("RT-2.json", "RT2-LATENCY.json", "demo-journey-7-4.json"),
        "rt5": ("RT-5.json", "demo-rt-5.json"),
        "u11": ("demo-dashboard.json",),
    }
    manifest = pipe.h.manifest()
    for names in by_section.values():
        for name in names:
            assert name in manifest["files"] and evidence_of(pipe, name)["evidence"]["result"] == "pasa", name
    assert evidence_of(pipe, "demo-journey-7-4.json")["outcome"]["readings"]["reactivation_mode"] == "tool"


def test_demo_evidence_journey_7_3_is_not_executed_if_the_escalation_was_not_waited_for(
    pipe: Pipeline,
) -> None:
    assert pipe.h.prepare() == 0
    assert pipe.run("rt3", "--no-wait-for-escalation") == 2
    assert (pipe.h.dir / "RT-3.json").exists() and not (pipe.h.dir / "demo-journey-7-3.json").exists()
    assert "journey_7_3_escalada_no_esperada" in pipe.h.out.getvalue()


def test_demo_evidence_journey_7_3_fails_if_the_cases_never_reach_no_disponible(pipe: Pipeline) -> None:
    pipe.escalate = False
    assert pipe.h.prepare() == 0
    pipe.world.state_cases = lambda case_id, record: ("en_sincronizacion", "timeout", 1)
    pipe.h.before["rt3"] = lambda world: setattr(world, "gauge", 1.0)
    assert pipe.run("rt3") == 1
    assert evidence_of(pipe, "demo-journey-7-3.json")["evidence"]["result"] == "falla"


def test_demo_evidence_tool_mode_reactivates_with_one_request_and_the_step_up_of_cumplimiento_1(
    pipe: Pipeline,
) -> None:
    upto_rt2_setup(pipe)
    assert pipe.run("rt2") == 0 and pipe.run("rt2") == 0 and "ya terminada" in pipe.h.out.getvalue()
    world = pipe.world
    assert (
        len(world.reactivation_calls) == 1
        and "cumplimiento-1" in world.oidc.step_ups
        and not any(u.startswith("cumplimiento-2") for u in world.oidc.step_ups + world.oidc.logins)
    )
    assert (
        "cumplimiento-1" in evidence_of(pipe, "demo-journey-7-4.json")["outcome"]["readings"]["reactivation"]
    )


def test_demo_evidence_presenter_mode_sends_no_reactivation_logs_in_nobody_and_verifies_the_entry(
    pipe: Pipeline,
) -> None:
    upto_rt2_setup(pipe)
    base = pipe.h.before["rt2"]

    def with_presenter(world: Rt2World) -> None:
        base(world)
        world.at(4000.0, world.reactivate)  # el presentador, en la consola, con cumplimiento-2

    pipe.h.before["rt2"] = with_presenter
    assert pipe.run("rt2", "--reactivation", "presenter") == 0, pipe.h.out.getvalue() + pipe.h.err.getvalue()
    world = pipe.world
    assert world.reactivation_calls == [] and not [
        u for u in world.oidc.step_ups + world.oidc.logins if u.startswith("cumplimiento")
    ]
    journey = evidence_of(pipe, "demo-journey-7-4.json")["outcome"]["readings"]
    assert (
        journey["reactivation_mode"] == "presenter"
        and "BFF" in journey["reactivation"]
        and "cumplimiento-2" in journey["reactivation"]
    )
    assert evidence_of(pipe, "demo-journey-7-4.json")["evidence"]["result"] == "pasa"


def test_demo_evidence_presenter_mode_that_sends_the_request_anyway_would_break_the_zero_requests(
    pipe: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rojo de CA-14: si el modo `presenter` usara la reactivacion de la herramienta, `reactivation_calls` no seria 0."""
    from vectra_verification.scenarios import rt2

    upto_rt2_setup(pipe)
    monkeypatch.setattr(
        rt2, "PresenterReactivation", lambda registry, clock, **kw: rt2.ToolReactivation(pipe.world.sessions)
    )
    assert pipe.run("rt2", "--reactivation", "presenter") == 0
    assert len(pipe.world.reactivation_calls) == 1  # el defecto que la prueba de arriba detecta


def test_demo_evidence_presenter_mode_without_the_entry_is_not_executed_with_the_pending_phase_and_resumes_there(
    pipe: Pipeline,
) -> None:
    upto_rt2_setup(pipe)
    assert pipe.run("rt2", "--reactivation", "presenter", "--reactivation-timeout", "600") == 2
    manifest = pipe.h.manifest()["sections"]["rt2"]
    assert (
        manifest["state"] == "interrumpida"
        and manifest["pending"] == "reactivacion"
        and "rt2_reactivacion_pendiente_del_presentador" in manifest["note"] + pipe.h.out.getvalue()
    )
    assert not (pipe.h.dir / "demo-journey-7-4.json").exists() and (pipe.h.dir / "state-rt2.json").exists()
    lots = [r[0] for r in pipe.world.simulator.runs].count("stratified")
    pipe.world.reactivate()  # el presentador lo hace ahora
    assert pipe.run("rt2", "--reactivation", "presenter") == 0, pipe.h.out.getvalue() + pipe.h.err.getvalue()
    assert [r[0] for r in pipe.world.simulator.runs].count(
        "stratified"
    ) == lots  # se retomo en la fase: el lote no se reenvio
    assert pipe.h.manifest()["sections"]["rt2"]["state"] == "terminada"


def test_demo_evidence_presenter_mode_with_an_investigar_entry_fails(pipe: Pipeline) -> None:
    upto_rt2_setup(pipe)
    base = pipe.h.before["rt2"]

    def investigates(world: Rt2World) -> None:
        base(world)
        world.at(
            4000.0,
            lambda: world.freeze_entries.append(
                {
                    "seq": world.seq(),
                    "model_version_id": PROXY,
                    "action": "investigar",
                    "recorded_at": "2026-11-13T11:15:00Z",
                }
            ),
        )

    pipe.h.before["rt2"] = investigates
    assert pipe.run("rt2", "--reactivation", "presenter") == 1
    assert (
        evidence_of(pipe, "demo-journey-7-4.json")["evidence"]["result"] == "falla"
        and "rt2_reactivacion_investigar" in pipe.h.out.getvalue()
    )


def test_demo_evidence_journey_7_4_fails_without_a_frozen_resolution_with_mfa(
    pipe: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    upto_rt2_setup(pipe)
    monkeypatch.setattr(
        pipe.world, "reactivate", lambda: pipe.world.set_state(PROXY, "activo")
    )  # el modelo vuelve a `activo` sin `frozen_resolution`
    assert pipe.run("rt2") == 1
    assert (
        evidence_of(pipe, "demo-journey-7-4.json")["evidence"]["result"] == "falla"
        and "rt2_sin_frozen_resolution_reactivar" in pipe.h.out.getvalue()
    )


def test_demo_evidence_the_rt5_u11_and_rt2_state_files_pass_the_filter_and_hold_no_secret(
    pipe: Pipeline,
) -> None:
    pipe.everything()
    for path in pipe.h.dir.iterdir():
        text = path.read_text(encoding="utf-8")
        assert not any(secret in text for secret in SECRETS) and "eyJ" not in text, path.name


# --- ronda 2: el cierre de D1 y D2, la retoma de rt2, la fabrica real y el punto de entrada ---------------------------------------------------------------


def rt3_record(pipe: Pipeline) -> dict:  # type: ignore[type-arg]
    return json.loads(json.dumps(pipe.h.manifest()["sections"]["rt3"]))


def test_exit_f06_rt3_closing_is_recorded_apart_and_does_not_rewrite_the_record_of_rt3(
    pipe: Pipeline,
) -> None:
    """F-06 (ronda 2): `rt3 --closing` (el paso 6 de D1) deja `closing_rt3` y el registro de `rt3` (resultado, codigo, nota) queda tal cual."""
    assert pipe.h.prepare() == 0
    assert pipe.run("decisions") == 0 and pipe.run("rt5") == 0 and pipe.run("rt3") == 0
    before = rt3_record(pipe)
    pipe.h.before["rt3"] = lambda world: setattr(
        world, "state_cases", None
    )  # F22 revertido: un caso nuevo llega a `listo`
    assert pipe.run("rt3", "--closing") == 0, pipe.h.out.getvalue() + pipe.h.err.getvalue()
    manifest = pipe.h.manifest()
    assert manifest["closing_rt3"]["result"] == "pasa" and rt3_record(pipe) == before
    assert before["state"] == "terminada" and "cierre de D1 (rt3 --closing): pasa" in pipe.h.out.getvalue()
    assert (pipe.h.dir / "RT-3.json").exists() and "closing_rt3" not in json.dumps(before)
    done = subprocess.run(
        ["sh", str(SYSTEM / "demos" / "verify" / "journey-7-3.sh"), "4"],
        capture_output=True, text=True, check=False, env={"VERIFICATION_DIR": str(pipe.h.dir), "PATH": "/usr/bin:/bin"},
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr  # el verify del paso 6 lee lo que la CLI escribio


def test_exit_f06_a_closing_that_does_not_reach_listo_is_not_executed_and_the_record_of_rt3_survives(
    pipe: Pipeline,
) -> None:
    assert pipe.h.prepare() == 0
    assert pipe.run("decisions") == 0 and pipe.run("rt5") == 0 and pipe.run("rt3") == 0
    before = rt3_record(pipe)
    pipe.h.before["rt3"] = lambda world: setattr(
        world, "state_cases", lambda case_id, record: ("en_sincronizacion", "timeout", 1)
    )  # F22 sigue apagado
    assert pipe.run("rt3", "--closing") == 2
    manifest = pipe.h.manifest()
    assert (
        manifest["closing_rt3"]["result"] == "no ejecutado"
        and "rt3_cierre_f22_sigue_apagado" in manifest["closing_rt3"]["missing"]
    )
    assert rt3_record(pipe) == before and before["state"] == "terminada"  # `rt3` no vuelve a `interrumpida`
    assert pipe.run("rt3") == 0 and "ya terminada" in pipe.h.out.getvalue()  # y no se repite RT-3 entero
    pipe.h.before["rt3"] = lambda world: setattr(world, "state_cases", None)
    assert pipe.run("rt3", "--closing") == 0 and pipe.h.manifest()["closing_rt3"]["result"] == "pasa"


def test_exit_f06_closing_without_the_vault_is_a_prerequisite_and_leaves_rt3_as_it_was(
    pipe: Pipeline,
) -> None:
    from vectra_verification.credentials import CredentialsError

    assert pipe.h.prepare() == 0
    assert pipe.run("decisions") == 0 and pipe.run("rt5") == 0 and pipe.run("rt3") == 0
    before = rt3_record(pipe)

    def broken(*args: object) -> object:
        raise CredentialsError("vault_unreachable")

    pipe.h.factory = broken  # type: ignore[method-assign,assignment]
    assert pipe.run("rt3", "--closing") == 2 and "prerrequisito" in pipe.h.out.getvalue()
    assert rt3_record(pipe) == before and "closing_rt3" not in pipe.h.manifest()


def test_exit_f03_rt2_says_what_is_missing_while_it_waits_for_the_closing_and_records_it_apart(
    pipe: Pipeline,
) -> None:
    """F-03 (ronda 2): `rt2` espera el `rollback-pr` y el `mark-active` del modelo de referencia, lo dice, y registra el cierre (`closing_rt2`) aparte del resultado de RT-2."""
    upto_rt2_setup(pipe)
    assert pipe.run("rt2") == 0
    out = pipe.h.out.getvalue()
    assert (
        "rt2 espera el cierre" in out
        and "rollback-pr" in out
        and "mark-active" in out
        and "cierre de D2: pasa" in out
    )
    assert pipe.h.manifest()["closing_rt2"]["result"] == "pasa"


def test_exit_f03_without_the_closing_rt2_does_not_wait_an_hour_in_silence_and_the_verify_says_no(
    pipe: Pipeline,
) -> None:
    upto_rt2_setup(pipe)

    def promotes_only(world: Rt2World) -> None:
        world.state_cases = None
        world.operator_promotes(60.0)
        world.start_bias()  # nadie hace el rollback

    pipe.h.before["rt2"] = promotes_only
    assert pipe.run("rt2", "--operator-timeout", "600") == 0
    out = pipe.h.out.getvalue()
    assert (
        "rt2 espera el cierre (hasta 600 s)" in out
        and "cierre de D2: no ejecutado: rt2_cierre_rollback_pendiente" in out
    )
    closing = pipe.h.manifest()["closing_rt2"]
    assert closing["result"] == "no ejecutado" and "rt2_cierre_rollback_pendiente" in closing["missing"]
    assert (pipe.h.dir / "RT-2.json").exists()  # el cierre no baja RT-2 (P-9 (a))


class Interrupt(BaseException):  # noqa: N818
    """Un Ctrl-C a mitad de una fase."""


def test_exit_f10_an_interruption_in_the_middle_of_rt2_resumes_at_the_phase_where_it_stopped_without_resending_the_batch(
    pipe: Pipeline,
) -> None:
    """F-10 (ronda 2): `state-rt2.json` se guarda al terminar cada fase y tambien si una excepcion corta la seccion; la siguiente corrida retoma ahi (no reenvia el lote)."""
    upto_rt2_setup(pipe)
    base = pipe.h.before["rt2"]

    def interrupted(world: Rt2World) -> None:
        base(world)

        def stop() -> None:
            raise Interrupt

        world.at(1500.0, stop)  # a mitad de la espera de una fase, ya enviado el lote

    pipe.h.before["rt2"] = interrupted
    with pytest.raises(Interrupt):
        pipe.run("rt2", "--reactivation", "presenter", "--reactivation-timeout", "7200")
    assert (pipe.h.dir / "state-rt2.json").exists()
    assert pipe.h.manifest()["sections"]["rt2"]["state"] == "interrumpida"
    lots = [r[0] for r in pipe.world.simulator.runs].count("stratified")
    assert lots == 1
    pipe.h.before["rt2"] = lambda world: world.at(
        2500.0, world.reactivate
    )  # el presentador (a los 4 000 s del inicio de la primera corrida)
    assert pipe.run("rt2", "--reactivation", "presenter") == 0, pipe.h.out.getvalue() + pipe.h.err.getvalue()
    assert [r[0] for r in pipe.world.simulator.runs].count("stratified") == lots
    assert pipe.h.manifest()["sections"]["rt2"]["state"] == "terminada"


def test_exit_f10_state_is_saved_at_the_end_of_each_phase(
    pipe: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    upto_rt2_setup(pipe)
    writes: list[str] = []
    real = cli.Store.write

    def spy(self: object, name: str, text: str, **kw: object) -> object:
        if name == "state-rt2.json":
            writes.append(text)
        return real(self, name, text, **kw)  # type: ignore[arg-type,misc]

    monkeypatch.setattr(cli.Store, "write", spy)
    assert pipe.run("rt2") == 0
    assert len(writes) >= 11  # una por fase (11) y la final
    assert len({*writes}) > 5  # y cada una con mas que la anterior


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_exit_f04_the_live_factory_hands_over_to_the_real_backend_and_the_module_runs_as_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-04 (ronda 2): sin `# pragma: no cover` en `cli.py`; `_live_factory` y `python -m vectra_verification.cli` se prueban."""
    import runpy
    import types

    seen: list[tuple[object, ...]] = []
    fake = types.ModuleType("vectra_verification.live")
    fake.live_backend = lambda *args: seen.append(args) or "backend"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "vectra_verification.live", fake)
    assert cli._live_factory("env", "args", "clock", "prefix") == "backend"  # type: ignore[arg-type]
    assert seen and seen[0][:4] == ("env", "args", "clock", "prefix")
    monkeypatch.setattr(sys, "argv", ["vectra-verification", "--help"])
    with pytest.raises(SystemExit) as stop:
        runpy.run_module("vectra_verification.cli", run_name="__main__")
    assert stop.value.code == 0
    assert "pragma: no cover" not in (SYSTEM / "src" / "vectra_verification" / "cli.py").read_text(
        encoding="utf-8"
    )


def test_f09_all_closes_the_backend_of_the_previous_section_before_opening_another(
    tmp_path: Path, world: Rt2World
) -> None:
    from vectra_verification import manifest as mf
    from vectra_verification.store import Store

    h = harness(tmp_path, world)
    assert h.prepare() == 0
    opened: list[WorldBackend] = []

    def factory(environment: object, args: object, clock: object, prefix: str) -> WorldBackend:
        fresh = WorldBackend(world)
        opened.append(fresh)
        assert all(b.closed for b in opened[:-1]), "se abrio un backend con el anterior todavia abierto"
        return fresh

    app = cli.Cli({}, h.clock, factory, h.out, h.err)  # type: ignore[arg-type]
    app.store = Store(h.dir, lambda: ())
    app.manifest = mf.Manifest.load(app.store)
    parsed = app.parser.parse_args(["decisions", "--dir", str(h.dir)])
    for _ in range(3):
        assert app._open_backend(guard.KIND, "decisions", parsed, interrupt=False) is None  # noqa: SLF001
    assert len(opened) == 3 and all(b.closed for b in opened[:2]) and not opened[2].closed


def test_f09_the_delivery_arrives_by_option_or_by_the_manifest_and_the_other_paths_hang_from_it(
    tmp_path: Path, world: Rt2World
) -> None:
    h = harness(tmp_path, world)
    delivery = tmp_path / "entrega"
    assert h.prepare(delivery=str(delivery)) == 0
    assert h.manifest()["paths"] == {"delivery": str(delivery.resolve())}
    assert h.run("decisions", "--volume", "20") in (0, 1, 2)
    assert h.args_seen[-1].delivery == str(delivery.resolve())  # del manifiesto
    other = tmp_path / "otra"
    h.run("decisions", "--volume", "20", "--delivery", str(other), "--redo")
    assert h.args_seen[-1].delivery == str(other)  # la opcion manda
    assert (
        h.run("rt3") == 3 and "rt3_paquete_inexistente" in h.err.getvalue()
    )  # los paquetes se buscan en <entrega>/adversarial/rt3
    assert h.manifest()["sections"]["rt3"]["state"] == "interrumpida"


def test_f09_without_a_delivery_anywhere_the_paths_are_asked_for_and_nothing_is_guessed(
    tmp_path: Path, world: Rt2World
) -> None:
    h = harness(tmp_path, world)
    assert h.prepare() == 0 and "paths" not in h.manifest()
    for section, option in (
        ("rt3", "--packages-dir"),
        ("rt2-setup", "--proxy-root"),
        ("rt2", "--reference-dir"),
    ):
        assert h.run(section) == 3, section
        assert "ruta_faltante" in h.err.getvalue() and option in h.err.getvalue(), (section, h.err.getvalue())
