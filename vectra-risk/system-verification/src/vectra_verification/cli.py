"""`vectra-verification <seccion> [opciones]` (U12-T04, Paso 13; NFR-U12-03, 10, 20, 30, 31, 32, 50; BR-U12-11, 13; INF-U12-04).

Una subcomando por cada una de las 14 secciones de `guard.SECTIONS`, en el orden de business-logic-model §2.1. Corren `prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11` y `report`; las seis diferidas por la demo
(`network`, `rt1`, `rt4`, `load`, `pii`, `resilience`) existen y responden `no ejecutado` sin hacer ninguna solicitud, con su linea en el manifiesto y la cita de la enmienda. `all --from <seccion>` corre desde ahi en orden.

Barreras, en este orden y **antes de la primera solicitud**: `guard.check_environment` (emisor y host), `guard.check_section`, y las propias de la seccion (`decisions`: `guard.check_decisions`). Sin `prepare` (sin
`manifest.json`) ninguna otra seccion corre. Codigos de salida: `0` la seccion termino y todo lo suyo es `pasa`; `1` algun `falla`; `2` `no ejecutado` (falto un prerrequisito, o es una seccion diferida); `3` la herramienta se nego
(barrera, uso, `prepare` ausente o repetido). `falla` y `no ejecutado` nunca comparten codigo ni texto. Todo lo que se escribe pasa por `store.Store` (el filtro de evidencias).

`--help` no tiene efectos: no lee la boveda, no hace solicitudes, no escribe archivos y no importa `playwright` ni `pyarrow` (los modulos de escenarios se importan al ejecutar una seccion, no al cargar este).
El mundo exterior entra por un `Backend` (`live.LiveBackend` en la herramienta; dobles en las pruebas): este modulo no abre sockets ni procesos.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager, ExitStack
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol, TextIO, cast

from vectra_verification import evidence as evidence_filter
from vectra_verification import guard, report, story_map
from vectra_verification import manifest as mf
from vectra_verification.clock import Clock
from vectra_verification.guard import Environment, GuardError
from vectra_verification.store import Store, StoreError

if TYPE_CHECKING:
    from vectra_verification.clients.bff import BffClient
    from vectra_verification.clients.k8s_read import K8sRead
    from vectra_verification.clients.prom import PromClient
    from vectra_verification.clients.registry import RegistryClient
    from vectra_verification.scenarios.common import Sessions
    from vectra_verification.scenarios.outcome import Outcome

EXIT_PASS: Final = 0
EXIT_FAIL: Final = 1
EXIT_NOT_RUN: Final = 2
EXIT_REFUSED: Final = 3
RESULT_TEXT: Final = {
    EXIT_PASS: "pasa",
    EXIT_FAIL: "falla",
    EXIT_NOT_RUN: "no ejecutado",
    EXIT_REFUSED: "la herramienta se nego",
}

DEFAULT_SEED: Final = 2026111301
DEFAULT_DIR: Final = "evidence"
DEFAULT_VALUES: Final = "vectra-risk-gitops/values/kind/case-management.yaml"
DEFAULT_PATCH_ROOT: Final = "vectra-risk"
PATCH_NAME: Final = "case-management-runid.patch"
REPORT_NAME: Final = "verification-report.md"
RT2_STATE: Final = "state-rt2.json"
STORY_MAP: Final = Path(__file__).resolve().parents[2] / "report" / "story-map.yaml"
SECTIONS_RUN: Final = ("prepare", "decisions", "rt5", "rt3", "rt2-setup", "rt2", "u11", "report")
CLUSTER_SECTIONS: Final = ("decisions", "rt5", "rt3", "rt2-setup", "rt2", "u11")
K16_NAMESPACES: Final = (
    "vectra-app",
    "vectra-serving",
    "vectra-observability",
    "vectra-edge",
    "vectra-identity",
    "vectra-data",
)
HELP: Final = {
    "prepare": "genera el runId y el manifiesto inicial y el parche de values de kind (sin ninguna solicitud)",
    "network": "(diferida por la demo) responde no ejecutado",
    "decisions": "envia las solicitudes (normal), espera a `listo`, decide como los analistas y evalua SIM-NORMAL",
    "rt1": "(diferida por la demo) responde no ejecutado",
    "rt4": "(diferida por la demo) responde no ejecutado",
    "rt5": "RT-5 (D3): el Job rt5-demo-<runId> y la alerta CoreWriteAttempt",
    "rt3": "RT-3 y D1: paquetes alterados rechazados por U4, F22 apagado y la escalada a no_disponible",
    "rt2-setup": "registra, valida y aprueba la version del proxy (D2)",
    "rt2": "RT-2 y D2: congelamiento, paquete, reactivacion (herramienta o presentador) y latencia",
    "load": "(diferida por la demo) responde no ejecutado",
    "pii": "(diferida por la demo) responde no ejecutado",
    "u11": "dashboard Producto (D4): las cuatro series y ProductMetricsStale, el dia D + 1",
    "resilience": "(diferida por la demo) responde no ejecutado",
    "report": "genera verification-report.md (en cualquier momento)",
}


class UsageError(Exception):
    """Un uso incorrecto (opcion desconocida, opcion de otra seccion): codigo 3."""


class Refused(Exception):
    """La herramienta se niega por una razon propia (no de `guard`); el mensaje empieza por un codigo estable."""


class _Parser(argparse.ArgumentParser):
    def __init__(self, *args: Any, out: TextIO | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._out = out

    def print_help(self, file: Any = None) -> None:
        super().print_help(file or self._out)

    def print_usage(self, file: Any = None) -> None:
        super().print_usage(file or self._out)

    def error(self, message: str) -> Any:
        raise UsageError(message)


class Backend(Protocol):
    """Todo lo que toca el mundo (credenciales, `kubectl`, Prometheus, el registro, el BFF, el simulador): `live.LiveBackend` o los dobles de las pruebas. Se crea **despues** de las barreras."""

    def secret_values(self) -> frozenset[str]: ...

    def k8s(self) -> K8sRead: ...

    def prom(self) -> AbstractContextManager[PromClient]: ...

    def registry(self) -> AbstractContextManager[RegistryClient]: ...

    def sessions(self) -> Sessions: ...

    def bff(self) -> BffClient: ...

    def simulator(self, run_prefix: str) -> Any: ...

    def driver(self, seed: int) -> Any: ...

    def close(self) -> None: ...


BackendFactory = Callable[[Environment, argparse.Namespace, Clock, str], Backend]


def build_parser(
    environ: dict[str, str] | os._Environ[str], out: TextIO | None = None
) -> argparse.ArgumentParser:
    parser = _Parser(
        prog="vectra-verification",
        description="Verificacion del sistema de Vectra Risk (U12), por secciones.",
        out=out,
    )
    common = _Parser(add_help=False)
    common.add_argument(
        "--dir",
        default=DEFAULT_DIR,
        help="directorio de la verificacion (manifest.json, evidencias, informe)",
    )
    common.add_argument("--issuer", default=environ.get("VERIFICATION_ISSUER", guard.KIND.issuer))
    common.add_argument("--gateway-host", default=environ.get("VERIFICATION_GATEWAY_HOST", guard.KIND.host))
    common.add_argument(
        "--ca-file",
        default=environ.get("VERIFICATION_CA_FILE"),
        help="la CA del entorno (para el login y el gateway)",
    )
    common.add_argument("--redo", action="store_true", help="repite una seccion terminada")
    sub = parser.add_subparsers(dest="section", metavar="seccion", parser_class=_Parser)
    sections: dict[str, _Parser] = {}
    for name in guard.SECTIONS:
        sections[name] = sub.add_parser(name, parents=[common], help=HELP[name], description=HELP[name])
    every: _Parser = sub.add_parser(
        "all",
        parents=[common],
        help="corre las secciones en orden desde `--from`",
        description="corre las secciones en orden desde `--from`",
    )
    every.add_argument("--from", dest="start", default="decisions", choices=SECTIONS_RUN[1:])
    for each in (*sections.values(), every):
        each._out = out
    p = sections["prepare"]
    p.add_argument("--commit", required=True)
    p.add_argument("--operator", required=True)
    p.add_argument("--values-file", default=DEFAULT_VALUES)
    p.add_argument(
        "--patch-root",
        default=DEFAULT_PATCH_ROOT,
        help="la carpeta de los values dentro del repositorio, para las rutas del parche",
    )
    d = sections["decisions"]
    d.add_argument("--volume", type=int, default=None)
    d.add_argument("--rate", type=float, default=10.0)
    d.add_argument("--seed", type=int, default=DEFAULT_SEED)
    d.add_argument(
        "--settle-timeout",
        type=float,
        default=1800.0,
        help="segundos que se espera a que ningun caso siga en evaluacion",
    )
    d.add_argument("--delivery", default="reference-model/.out", help="la entrega de U5")
    sections["rt5"].add_argument("--after-job-minutes", type=float, default=15.0)
    t = sections["rt3"]
    t.add_argument("--packages-dir", default="reference-model/.out/adversarial/rt3")
    t.add_argument(
        "--rt3b-dir",
        default=None,
        help="el paquete RT3-b generado desde uno no registrado (por omision, RT3-b no se ejecuta)",
    )
    t.add_argument("--seed", type=int, default=DEFAULT_SEED)
    t.add_argument("--probes", type=int, default=5)
    t.add_argument("--no-wait-for-escalation", dest="wait_for_escalation", action="store_false")
    t.add_argument("--deployed-a", default=None, help="InferenceService de RT3-a en vectra-staging")
    t.add_argument("--deployed-d", default=None, help="InferenceService de RT3-d en vectra-staging")
    t.add_argument("--operator-timeout", type=float, default=3600.0)
    t.add_argument("--closing", action="store_true", help="solo el cierre de D1 (tras revertir el PR de F22)")
    for name in ("rt2-setup", "rt2"):
        s = sections[name]
        s.add_argument("--proxy-root", default="reference-model/.out/proxy")
        s.add_argument("--versions", type=int, default=1, help="versiones del proxy (1 en la demo: DD-1)")
        s.add_argument("--seed", type=int, default=DEFAULT_SEED)
    sections["rt2-setup"].add_argument("--validation-timeout", type=float, default=1800.0)
    r = sections["rt2"]
    r.add_argument("--reference-dir", default="reference-model/.out/package")
    r.add_argument(
        "--reactivation",
        choices=("tool", "presenter"),
        default="tool",
        help="quien reactiva: la herramienta (cumplimiento-1) o el presentador en la consola (cumplimiento-2)",
    )
    r.add_argument("--operator-timeout", type=float, default=3600.0)
    r.add_argument("--reactivation-timeout", type=float, default=3600.0)
    r.add_argument("--bias-timeout", type=float, default=3600.0)
    r.add_argument("--volume", type=int, default=1500)
    sections["report"].add_argument("--story-map", default=str(STORY_MAP))
    return parser


def _prerequisite_errors() -> tuple[type[Exception], ...]:
    from vectra_verification.clients.k8s_read import K8sError
    from vectra_verification.credentials import CredentialsError
    from vectra_verification.simulator import SimulatorError

    return (CredentialsError, K8sError, SimulatorError, OSError, ValueError)


def code_of(results: Sequence[str]) -> int:
    if report.FALLA in results:
        return EXIT_FAIL
    if report.NO_EJECUTADO in results:
        return EXIT_NOT_RUN
    return EXIT_PASS


class RecordingSimulator:
    """Pasa todo al simulador y anota las posiciones de fila que cada seccion envio: con ellas el manifiesto detecta las solicitudes repetidas entre escenarios (NFR-U12-11)."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.runs: list[tuple[str, tuple[int, ...]]] = []
        self.reports: list[Any] = []

    def select(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.select(*args, **kwargs)

    def run(self, scenario: str, volume: int, seed: int, **kwargs: Any) -> Any:
        result = self._inner.run(scenario, volume, seed, **kwargs)
        self.runs.append((str(kwargs.get("section", "decisions")), tuple(result.sent_positions)))
        self.reports.append(result.report)
        return result


@dataclass
class SectionResult:
    outcomes: list[Outcome] = field(default_factory=list)
    extra_results: list[str] = field(
        default_factory=list
    )  # lo que no es una evidencia (rt2-setup, el cierre)
    pending: str | None = None
    note: str = ""


class Cli:
    def __init__(
        self,
        environ: dict[str, str] | os._Environ[str],
        clock: Clock,
        factory: BackendFactory | None,
        out: TextIO,
        err: TextIO,
    ) -> None:
        self.environ, self.clock, self.factory, self.out, self.err = environ, clock, factory, out, err
        self.parser = build_parser(environ, out)
        self.backend: Backend | None = None
        self.store: Store | None = None
        self.manifest: mf.Manifest | None = None

    def say(self, text: str, stream: TextIO | None = None) -> None:
        print(text, file=stream or self.out)

    # --- entrada ------------------------------------------------------------------------------------------------------------------------
    def main(self, argv: Sequence[str]) -> int:
        try:
            args = self.parser.parse_args(list(argv))
        except SystemExit as stop:  # `--help`
            return int(stop.code or 0)
        except UsageError as error:
            self.say(f"uso incorrecto: {error}", self.err)
            return EXIT_REFUSED
        if args.section is None:
            self.parser.print_usage(self.err)
            return EXIT_REFUSED
        try:
            if args.section == "all":
                return self.run_all(args)
            return self.run_section(args.section, args)
        finally:
            if self.backend is not None:
                self.backend.close()
                self.backend = None

    def run_all(self, args: argparse.Namespace) -> int:
        start = SECTIONS_RUN.index(args.start)
        codes: list[int] = []
        common = ["--dir", args.dir, "--issuer", args.issuer, "--gateway-host", args.gateway_host]
        common += ["--ca-file", args.ca_file] if args.ca_file else []
        for name in guard.SECTIONS:
            if name != "report" and name in SECTIONS_RUN and SECTIONS_RUN.index(name) < start:
                continue
            if name in ("prepare",):
                continue
            section_args = self.parser.parse_args([name, *common, *(["--redo"] if args.redo else [])])
            code = self.run_section(name, section_args)
            if name in SECTIONS_RUN:  # las diferidas responden 2 siempre: no cuentan en el codigo de `all`
                codes.append(code)
            if code in (EXIT_FAIL, EXIT_REFUSED) or (code == EXIT_NOT_RUN and name in SECTIONS_RUN):
                break
        return max(codes) if codes else EXIT_PASS

    # --- una seccion ------------------------------------------------------------------------------------------------------------------
    def run_section(self, section: str, args: argparse.Namespace) -> int:
        try:
            environment = guard.check_environment(args.issuer, args.gateway_host)
            guard.check_section(environment, section)
            if section == "prepare":
                return self.prepare(environment, args)
            if section == "decisions":
                guard.check_decisions(
                    environment, self.clock.now(), self._volume(environment, args), args.rate
                )
            self.store = Store(Path(args.dir), self._secrets)
            self.manifest = mf.Manifest.load(self.store)
            if self.manifest is None:
                raise Refused(
                    "prepare_missing: corra `prepare` primero (sin el manifiesto ninguna otra seccion corre)"
                )
            return self._execute(environment, section, args)
        except (GuardError, Refused, StoreError, mf.ManifestError) as error:
            return self._refused(section, str(error))
        except evidence_filter.EvidenceError as error:
            return self._blocked(section, str(error))

    def _secrets(self) -> frozenset[str]:
        return self.backend.secret_values() if self.backend is not None else frozenset()

    def _refused(self, section: str, message: str) -> int:
        self.say(f"seccion {section}: {RESULT_TEXT[EXIT_REFUSED]} ({EXIT_REFUSED}): {message}", self.err)
        return EXIT_REFUSED

    def _blocked(self, section: str, message: str) -> int:
        """El filtro de evidencias se nego a escribir: no quedo el archivo; la seccion queda interrumpida."""
        self._interrupt(section, f"filtro de evidencias: {message}")
        return self._refused(section, f"evidence_blocked: {message}")

    def _interrupt(self, section: str, note: str) -> None:
        if self.manifest is not None and self.store is not None and section in self.manifest.sections:
            self.manifest.interrupt_section(section, self.clock.now(), note)
            try:
                self.manifest.save(self.store)
            except (evidence_filter.EvidenceError, StoreError):
                pass  # el manifiesto no lleva secretos; si aun asi falla, queda el estado anterior

    def _volume(self, environment: Environment, args: argparse.Namespace) -> int:
        from vectra_verification import driver

        return int(args.volume) if args.volume is not None else driver.default_volume(environment)

    # --- prepare ------------------------------------------------------------------------------------------------------------------------
    def prepare(self, environment: Environment, args: argparse.Namespace) -> int:
        """Sin ninguna solicitud: ni cluster, ni boveda, ni gateway. Se niega si ya hay `manifest.json` (`started_at` no cambia)."""
        store = Store(Path(args.dir), lambda: ())
        if store.exists(mf.NAME):
            raise Refused(
                "prepare_manifest_exists: ya hay un manifest.json; para otra verificacion usa un directorio nuevo"
            )
        started = self.clock.now()
        manifest = mf.Manifest.new(
            started_at=started, commit=args.commit, operator=args.operator, environment=environment.name
        )
        manifest.start_section("prepare", started)
        patched = False
        try:
            guard.check_job_patch(environment)
            patched = True
        except GuardError:
            pass  # en staging no hay parche de los Jobs de prueba
        if patched:
            values = Path(args.values_file)
            if not values.is_file():
                raise Refused(
                    f"prepare_values_missing:{values.name}: el archivo de values de kind no esta; pasa --values-file"
                )
            path = f"{args.patch_root.strip('/')}/{DEFAULT_VALUES}" if args.patch_root else DEFAULT_VALUES
            stored = store.write(
                PATCH_NAME, mf.runid_patch(values.read_text(encoding="utf-8"), manifest.run_id, path=path)
            )
            manifest.set_file(PATCH_NAME, stored.sha256)
        manifest.finish_section(
            "prepare",
            self.clock.now(),
            result=report.PASA,
            exit_code=EXIT_PASS,
            note="con parche" if patched else "sin parche (staging)",
        )
        manifest.save(store, new=True)
        self.say(f"runId: {manifest.run_id}")
        self.say(f"started_at: {mf.iso(started)}")
        if patched:
            self.say(
                f"parche: {Path(args.dir) / PATCH_NAME} (git apply desde la raiz del repositorio; el operador abre el PR)"
            )
        self.say(f"seccion prepare: {RESULT_TEXT[EXIT_PASS]} ({EXIT_PASS})")
        return EXIT_PASS

    # --- el resto ---------------------------------------------------------------------------------------------------------------------
    def _execute(self, environment: Environment, section: str, args: argparse.Namespace) -> int:
        assert self.manifest is not None and self.store is not None
        manifest, store = self.manifest, self.store
        if section in guard.SECTIONS and section not in SECTIONS_RUN:
            manifest.defer_section(section, self.clock.now())
            manifest.save(store)
            self.say(f"{section}: diferida por la demo ({mf.DEFERRED_CITATION})")
            self.say(f"seccion {section}: {RESULT_TEXT[EXIT_NOT_RUN]} ({EXIT_NOT_RUN})")
            return EXIT_NOT_RUN
        closing = bool(getattr(args, "closing", False))
        if section != "report" and manifest.is_done(section) and not args.redo and not closing:
            record = manifest.sections[section]
            self.say(f"seccion {section}: ya terminada ({record.get('result')}); no se repite sin --redo")
            return int(record.get("exit_code") or EXIT_PASS)
        now = self.clock.now()
        last = manifest.last_finished()
        if section != "report" and last is not None and now > last:
            manifest.add_wait(
                f"antes de {section}", last, now
            )  # lo que tardo el operador entre secciones: aparte del tiempo de las secciones
        manifest.start_section(section, now)
        if section == "report":
            return self._finish(section, SectionResult(), self._report(args))
        if self.factory is None:
            raise Refused("backend_missing: no hay forma de llegar al sistema")
        try:
            self.backend = self.factory(environment, args, self.clock, mf.prefix_of(manifest.run_id))
        except _prerequisite_errors() as error:  # la boveda, la CA, el kubeconfig o la entrega de U5 que faltan: un prerrequisito, no un fallo
            text = evidence_filter.scrub(f"{type(error).__name__}: {error}")[:200]
            manifest.interrupt_section(section, self.clock.now(), f"prerrequisito: {text}")
            manifest.save(store)
            self.say(
                f"seccion {section}: {RESULT_TEXT[EXIT_NOT_RUN]} ({EXIT_NOT_RUN}): prerrequisito: {text}"
            )
            return EXIT_NOT_RUN
        digests = self._read_digests()
        manifest.set_digests(section, digests)
        from vectra_verification.scenarios.common import ScenarioError
        from vectra_verification.simulator import SimulatorError

        try:
            result = self._run(environment, section, args, digests)
        except (
            ScenarioError,
            SimulatorError,
        ) as error:  # la herramienta se nego antes de enviar (por ejemplo, una celda alcanzable corta)
            text = evidence_filter.scrub(f"{type(error).__name__}: {error}")[:300]
            self._interrupt(section, text)
            return self._refused(section, text)
        except BaseException as error:
            self._interrupt(section, f"interrumpida: {type(error).__name__}")
            raise
        return self._finish(section, result, None)

    def _read_digests(self) -> dict[str, str]:
        """Los digests `imageID` de los pods de los namespaces de K16, leidos del cluster al empezar la seccion (nunca en `prepare`)."""
        from vectra_verification.clients.k8s_read import K8sError

        assert self.backend is not None
        digests: dict[str, str] = {}
        k8s = self.backend.k8s()
        for namespace in K16_NAMESPACES:
            try:
                items = json.loads(k8s.get("pods", namespace))["items"]
            except (K8sError, ValueError, KeyError, TypeError):
                digests[f"{namespace}/sin-lectura"] = "no se pudo leer"
                continue
            for item in items:
                for status in (item.get("status") or {}).get("containerStatuses") or []:
                    if status.get("imageID"):
                        digests[f"{namespace}/{status.get('name')}"] = str(status["imageID"])
        return digests

    def _run(
        self, environment: Environment, section: str, args: argparse.Namespace, digests: dict[str, str]
    ) -> SectionResult:
        from vectra_verification.scenarios import demos

        assert self.backend is not None and self.manifest is not None
        manifest, backend, clock = self.manifest, self.backend, self.clock
        prefix = mf.prefix_of(manifest.run_id)
        sim = RecordingSimulator(backend.simulator(prefix))
        outcomes: list[Outcome] = []
        result = SectionResult()
        with ExitStack() as stack:
            if section == "decisions":
                outcomes, result.note = self._decisions(environment, args, sim)
            elif section == "rt5":
                from datetime import timedelta as td

                from vectra_verification.scenarios import rt5

                prom = stack.enter_context(backend.prom())
                rt5_outcome = rt5.run(
                    backend.k8s(),
                    prom,
                    clock,
                    manifest.run_id,
                    manifest.started_at,
                    environment=environment,
                    after_job=td(minutes=args.after_job_minutes),
                )
                outcomes = [rt5_outcome, demos.rt_5_demo(rt5_outcome)]
            elif section == "rt3":
                outcomes, result = self._rt3(environment, args, sim, stack)
            elif section == "rt2-setup":
                result.extra_results.append(self._rt2_setup(environment, args))
            elif section == "rt2":
                outcomes, result = self._rt2(environment, args, sim, stack)
            elif section == "u11":
                from vectra_verification.scenarios import u11

                prom = stack.enter_context(backend.prom())
                decisions = manifest.sections.get("decisions", {})
                finished = (
                    mf.parse_iso(decisions["finished_at"])
                    if decisions.get("state") == mf.STATE_DONE
                    else None
                )
                outcomes = [u11.u11(environment, prom, clock.now(), finished)]
        for name, positions in sim.runs:
            manifest.record_rows(name, positions)
        for simulated in sim.reports[:1]:
            manifest.set_population(
                simulated.generator_version, simulated.test_rows, simulated.parquet_sha256
            )
        manifest.set_seed(section, int(getattr(args, "seed", 0) or 0)) if hasattr(args, "seed") else None
        result.outcomes = outcomes
        return result

    # --- decisions ------------------------------------------------------------------------------------------------------------------
    def _decisions(
        self, environment: Environment, args: argparse.Namespace, sim: RecordingSimulator
    ) -> tuple[list[Outcome], str]:
        from vectra_verification import driver
        from vectra_verification.scenarios import sim_normal

        assert self.backend is not None and self.manifest is not None
        backend, clock = self.backend, self.clock
        bff = backend.bff()
        left: dict[str, int] = {}

        def settle(sent: Any) -> None:
            reads = sim_normal.read_cases(bff, clock, sent.case_ids, args.settle_timeout)
            left["undecided"] = sum(1 for read in reads.values() if read.state == "en_evaluacion")

        done = driver.run_decisions(
            cast(Any, sim),
            backend.driver(args.seed),
            args.seed,
            volume=self._volume(environment, args),
            rate=args.rate,
            environment=environment,
            settle=settle,
        )
        record = done.record
        undecided = left.get("undecided", 0)
        self.manifest.set_decisions(
            sent=record.sent,
            accepted=record.accepted,
            decided=record.decided,
            undecided_after_wait=undecided,
            not_ready=done.driver.not_ready,
        )
        note = f"enviadas {record.sent}, aceptadas {record.accepted}, decididas {record.decided}"
        if undecided:
            note += f"; {undecided} casos seguian en evaluacion al vencer el plazo y no se decidieron"
            self.say(
                f"decisions: {undecided} casos seguian en evaluacion al vencer el plazo y no se decidieron"
            )
        outcome = sim_normal.sim_normal(environment, bff, clock, done.simulation.report, timeout=60.0)
        return [outcome], note

    # --- rt3 -----------------------------------------------------------------------------------------------------------------------
    def _rt3(
        self, environment: Environment, args: argparse.Namespace, sim: RecordingSimulator, stack: ExitStack
    ) -> tuple[list[Outcome], SectionResult]:
        from vectra_verification.scenarios import demos, rt3
        from vectra_verification.scenarios.common import ScenarioError
        from vectra_verification.scenarios.outcome import SubOutcome

        assert self.backend is not None
        backend = self.backend
        root = Path(args.packages_dir)
        absent = [case for case in rt3.REGISTRY_CASES if not (root / case / "manifest.json").is_file()]
        if args.rt3b_dir and not (Path(args.rt3b_dir) / "manifest.json").is_file():
            absent.append("RT3-b")
        if absent:
            raise ScenarioError("rt3_paquete_inexistente", ",".join(absent))
        packages = {
            case: rt3.Rt3Package(case, root / case, f"adversarial/rt3/{case}") for case in rt3.REGISTRY_CASES
        }
        if args.rt3b_dir:
            packages["RT3-b"] = rt3.Rt3Package("RT3-b", Path(args.rt3b_dir), "adversarial/rt3/RT3-b")
        deployed = {
            case: name for case, name in (("RT3-a", args.deployed_a), ("RT3-d", args.deployed_d)) if name
        }
        params = rt3.Rt3Params(
            packages,
            args.seed,
            deployed=deployed,
            probes=args.probes,
            wait_for_escalation=args.wait_for_escalation,
            operator_timeout=args.operator_timeout,
        )
        deps = rt3.Rt3Deps(
            environment,
            self.clock,
            backend.sessions(),
            sim,
            stack.enter_context(backend.registry()),
            backend.k8s(),
            stack.enter_context(backend.prom()),
        )
        result = SectionResult()
        if args.closing:
            closing: SubOutcome = rt3.rt3_closing(deps, params)
            assert self.manifest is not None
            self.manifest.data["closing_rt3"] = {
                "result": closing.result,
                "missing": list(closing.missing),
                "detail": closing.detail,
            }
            result.extra_results.append(closing.result)
            result.note = f"cierre de D1: {closing.result}"
            return [], result
        rt3_outcome = rt3.rt3(deps, params)
        return [rt3_outcome, demos.journey_7_3(rt3_outcome)], result

    # --- rt2-setup y rt2 -----------------------------------------------------------------------------------------------------
    def _versions(self, args: argparse.Namespace) -> list[Any]:
        from vectra_verification.scenarios import rt2
        from vectra_verification.scenarios.common import ScenarioError, package_version

        versions = []
        for run in range(1, int(args.versions) + 1):
            directory = Path(args.proxy_root) / f"run-{run}"
            if not (directory / "manifest.json").is_file():
                raise ScenarioError("rt2_paquete_inexistente", directory.name)
            identifier = package_version(directory)
            versions.append(rt2.ProxyVersion(run, identifier, directory, identifier))
        return versions

    def _rt2_setup(self, environment: Environment, args: argparse.Namespace) -> str:
        from vectra_verification.scenarios import rt2

        assert self.backend is not None
        outcome = rt2.rt2_setup(
            environment,
            self.backend.sessions(),
            self.clock,
            self._versions(args),
            validation_timeout=args.validation_timeout,
        )
        self.say(
            f"rt2-setup: {outcome.result}" + (f": {', '.join(outcome.missing)}" if outcome.missing else "")
        )
        return outcome.result

    def _rt2(
        self, environment: Environment, args: argparse.Namespace, sim: RecordingSimulator, stack: ExitStack
    ) -> tuple[list[Outcome], SectionResult]:
        from vectra_verification.scenarios import demos, resume, rt2
        from vectra_verification.scenarios.common import package_version

        assert self.backend is not None and self.manifest is not None and self.store is not None
        backend, manifest, store = self.backend, self.manifest, self.store
        registry = stack.enter_context(backend.registry())
        prom = stack.enter_context(backend.prom())
        reactivator: Any = (
            rt2.PresenterReactivation(
                registry, self.clock, since=manifest.started_at, timeout=args.reactivation_timeout
            )
            if args.reactivation == "presenter"
            else None
        )
        deps = rt2.Rt2Deps(environment, self.clock, backend.sessions(), sim, registry, prom, reactivator)
        params = rt2.Rt2Params(
            package_version(Path(args.reference_dir)), self._versions(args), args.seed, volume=args.volume,
            operator_timeout=args.operator_timeout, bias_timeout=args.bias_timeout,
        )  # fmt: skip
        state = None
        if not args.redo and store.exists(RT2_STATE) and manifest.pending_of("rt2"):
            state = resume.decode(json.loads(store.read_text(RT2_STATE)))
        done = rt2.run_rt2(deps, params, state)
        store.write(RT2_STATE, json.dumps(resume.encode(done.state)))
        result = SectionResult(pending=done.pending, note=f"reactivacion: {args.reactivation}")
        if done.pending:
            result.note += f"; se paro en la fase `{done.pending}`: vuelve a correr `rt2` para retomar"
        journey = demos.journey_7_4(done.rt2.subresults, args.reactivation)
        return [done.rt2, done.latency, journey], result

    # --- report ---------------------------------------------------------------------------------------------------------------------
    def _report(self, args: argparse.Namespace) -> str:
        assert self.manifest is not None and self.store is not None
        manifest, store = self.manifest, self.store
        evidences: list[report.Evidence] = []
        notes: dict[str, str] = {}
        for name, element in sorted(manifest.data["evidence"].items()):
            loaded = self._load_evidence(name, element)
            evidences.append(loaded[0])
            notes.update({k: v for k, v in loaded[1].items()})
        declared = dict(manifest.files)
        observed = {name: sha for name in declared if (sha := store.sha256(name)) is not None}
        built = report.build(evidences, declared, observed, story_map.load(Path(args.story_map)))
        store.write(REPORT_NAME, mf.render_full(built, manifest, notes))
        counts = {
            result: sum(1 for row in built.rows if row.result == result)
            for result in (report.PASA, report.FALLA, report.NO_EJECUTADO)
        }
        self.say(
            f"informe: {Path(self.store.directory) / REPORT_NAME}: "
            + ", ".join(f"{n} {r}" for r, n in counts.items())
        )
        return REPORT_NAME

    def _load_evidence(self, name: str, element: str) -> tuple[report.Evidence, dict[str, str]]:
        assert self.store is not None and self.manifest is not None
        notes: dict[str, str] = {}
        try:
            document = json.loads(self.store.read_text(name))
            raw = document["evidence"]
            loaded = report.Evidence(
                id=raw["id"], command=raw["command"], output=raw["output"], expected=raw["expected"], obtained=raw["obtained"],
                result=raw["result"], commit=raw["commit"], images=raw["images"], executed_at=mf.parse_iso(raw["executed_at"]), operator=raw["operator"],
            )  # fmt: skip
            outcome = document.get("outcome", {})
            if element == "RT2-LATENCY":
                notes[element] = str(loaded.expected)
            cells = (outcome.get("readings") or {}).get("unreachable_cells")
            if element == "RT-2" and cells:
                notes[element] = "celdas inalcanzables (menos de 30 filas en test): " + "; ".join(
                    f"{c['attribute']}/{c['group']}/{c['band']} ({c['taken']} de {c['available']})"
                    for c in cells
                )
        except (OSError, ValueError, KeyError, TypeError):
            # un archivo que ya no se lee: la evidencia no es integra (su hash no coincide) y el elemento sale `no ejecutado`
            loaded = report.Evidence(
                id=element, command="", output=name, expected="x", obtained="x", result=report.PASA, commit="", images={}, executed_at=self.manifest.started_at, operator="",
            )  # fmt: skip
        return loaded, notes

    # --- cerrar la seccion ---------------------------------------------------------------------------------------------------
    def _write_evidence(self, outcome: Outcome, section: str) -> None:
        from vectra_verification.scenarios.outcome import to_evidence, to_text

        assert self.manifest is not None and self.store is not None
        manifest, store = self.manifest, self.store
        file = mf.evidence_file(outcome.id)
        item = to_evidence(
            outcome, command=f"vectra-verification {section}", output=file, commit=manifest.commit, images=manifest.digests_of(section),
            executed_at=self.clock.now(), operator=manifest.operator,
        )  # fmt: skip
        if item is None:
            return  # `no ejecutado` no da evidencia (BR-U12-11)
        enriched = type(outcome)(
            **{
                **{f: getattr(outcome, f) for f in outcome.__dataclass_fields__},
                "readings": {
                    **outcome.readings,
                    "run_id": manifest.run_id,
                    "run_prefix": mf.prefix_of(manifest.run_id),
                },
            }
        )
        plain = asdict(item)
        plain["executed_at"] = mf.iso(item.executed_at)
        text = json.dumps(
            {"evidence": plain, "outcome": json.loads(to_text(enriched))},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        stored = store.write(file, text)
        manifest.set_file(file, stored.sha256)
        manifest.data["evidence"][file] = outcome.id

    def _finish(self, section: str, result: SectionResult, report_file: str | None) -> int:
        assert self.manifest is not None and self.store is not None
        manifest, store = self.manifest, self.store
        for outcome in result.outcomes:
            self._write_evidence(outcome, section)
            codes = (", ".join(outcome.missing)) if outcome.missing else ""
            self.say(f"{outcome.id}: {outcome.result}" + (f": {codes}" if codes else ""))
        results = [o.result for o in result.outcomes] + result.extra_results
        code = EXIT_PASS if section == "report" else code_of(results)
        pending = result.pending if code != EXIT_PASS else None
        note = result.note or ("; ".join(c for o in result.outcomes for c in o.missing))
        manifest.finish_section(
            section,
            self.clock.now(),
            result=RESULT_TEXT[code] if code != EXIT_REFUSED else report.NO_EJECUTADO,
            exit_code=code,
            note=note,
            pending=pending,
        )
        manifest.save(store)
        self.say(
            f"seccion {section}: {RESULT_TEXT[code]} ({code})" + (f": {result.note}" if result.note else "")
        )
        return code


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: dict[str, str] | os._Environ[str] | None = None,
    clock: Clock | None = None,
    backend_factory: BackendFactory | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """El punto de entrada. Sin `backend_factory`, usa el real (`live.live_backend`), que se importa solo al ejecutar una seccion."""
    cli = Cli(
        environ if environ is not None else os.environ,
        clock or Clock(),
        backend_factory or _live_factory,
        stdout or sys.stdout,
        stderr or sys.stderr,
    )
    return cli.main(list(sys.argv[1:] if argv is None else argv))


def _live_factory(
    environment: Environment, args: argparse.Namespace, clock: Clock, prefix: str
) -> Backend:  # pragma: no cover - el mundo real: lo cubre U12-T06
    from vectra_verification.live import live_backend

    return live_backend(environment, args, clock, prefix, os.environ)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
