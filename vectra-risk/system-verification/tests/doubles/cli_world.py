"""El mundo de las pruebas de la CLI (U12-T04): un `cli.Backend` sobre los dobles de U12-T03 (`Rt2World`, `JobKubectl`, `PromDouble`) y un arnes que corre `cli.main` con reloj falso, dos `StringIO` y la cuenta de solicitudes.

`Harness.requests` suma todo lo que un doble pudo recibir (`kubectl`, la boveda, el BFF, el simulador, el registro, Prometheus, el conductor): un `0` es «cero solicitudes». La fabrica del `Backend` cuenta cuantas veces se
pidio: una barrera que se niega **antes** de la primera solicitud no la llama nunca.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fake_clock import FakeClock
from rt2_world import Rt2World
from vectra_verification import cli, guard
from vectra_verification.clients.k8s_read import Completed, K8sRead, Runner
from vectra_verification.clients.prom import PromClient
from vectra_verification.clients.registry import RegistryClient
from vectra_verification.driver import DriverReport

VALUES = (
    Path(__file__).resolve().parents[3] / "vectra-risk-gitops" / "values" / "kind" / "case-management.yaml"
)
SECRETS = frozenset({"semilla-Zq81xkLm-de-prueba", "contrasena-de-prueba-77"})
DIGEST = "docker.io/library/app@sha256:" + "ab" * 32


class PodsRunner:
    """El `Runner` de la CLI: `get pods` responde los pods con su `imageID` (los digests del manifiesto); lo demas lo atiende `inner` (el doble de la seccion)."""

    def __init__(self, inner: Runner | None = None) -> None:
        self.inner = inner
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: Sequence[str]) -> Completed:
        self.calls.append(tuple(args))
        if args[1] == "get" and args[2] == "pods":
            pod = {
                "metadata": {"name": "p-0"},
                "status": {"containerStatuses": [{"name": "app", "imageID": DIGEST}]},
            }
            return Completed(0, json.dumps({"items": [pod]}), "")
        if self.inner is None:
            return Completed(1, "", "sin doble")
        return self.inner.run(args)

    def start(self, args: Sequence[str]) -> Any:
        raise AssertionError("la CLI de prueba no abre port-forward")


class FakeDriver:
    """El conductor de mentira: decide los casos que **en ese momento** estan en `listo` (como el real, que solo mira la bandeja `listo`)."""

    def __init__(self, world: Rt2World) -> None:
        self.world = world
        self.started_at: datetime | None = None
        self.ready_at_start = 0

    def run(self, case_ids: Sequence[str] | None = None) -> DriverReport:
        self.started_at = self.world.clock.now()
        ids = list(case_ids or [])
        ready = [i for i in ids if self.world.case_state(i)[0] == "listo"]
        self.ready_at_start = len(ready)
        now = self.world.clock.now()
        return DriverReport(
            cases_seen=len(ready),
            decisions_by_kind={"sigue": len(ready)},
            views=0,
            conflicts_409=0,
            invalid_422=0,
            started_at=now,
            finished_at=now,
            errors_by_status={},
            not_decided=0,
            not_ready=len(ids) - len(ready),
            decided_case_ids=tuple(ready),
        )


class WorldBackend:
    def __init__(
        self,
        world: Rt2World,
        *,
        inner: Runner | None = None,
        prom: PromClient | None = None,
        runners: dict[str, Runner] | None = None,
        proms: dict[str, PromClient] | None = None,
    ) -> None:
        self.world = world
        self.runner = PodsRunner(inner)
        self.runners = runners or {}
        self.proms = proms or {}
        self.section = ""
        self.prom_client = prom if prom is not None else world.prom
        self.driver_double = FakeDriver(world)
        self.closed = False
        self.events: list[str] = []

    def secret_values(self) -> frozenset[str]:
        return SECRETS

    def k8s(self) -> K8sRead:
        self.runner.inner = self.runners.get(self.section, self.runner.inner)
        return K8sRead(self.runner)

    @contextmanager
    def prom(self) -> Iterator[PromClient]:
        yield self.proms.get(self.section, self.prom_client)

    @contextmanager
    def registry(self) -> Iterator[RegistryClient]:
        yield self.world.registry

    def sessions(self) -> Any:
        return self.world.sessions

    def bff(self) -> Any:
        return self.world.sessions.reader("analista-1")

    def simulator(self, run_prefix: str) -> Any:
        self.events.append(f"simulator:{run_prefix}")
        return self.world.simulator

    def driver(self, seed: int) -> Any:
        return self.driver_double

    def close(self) -> None:
        self.closed = True


class Harness:
    def __init__(
        self, directory: Path, backend: WorldBackend | None = None, clock: FakeClock | None = None
    ) -> None:
        self.dir = directory
        self.backend = backend
        self.clock = clock or (backend.world.clock if backend is not None else FakeClock())
        self.out, self.err = io.StringIO(), io.StringIO()
        self.factory_calls = 0
        self.args_seen: list[Any] = []
        self.before: dict[
            str, Any
        ] = {}  # un gancho por seccion, antes de crear el `Backend` (el operador que hace algo entre secciones)

    def factory(self, environment: guard.Environment, args: Any, clock: Any, prefix: str) -> WorldBackend:
        self.factory_calls += 1
        self.args_seen.append(args)
        assert self.backend is not None, "la prueba no esperaba un Backend"
        self.backend.section = str(args.section)
        if args.section in self.before:
            self.before[args.section](self.backend.world)
        return self.backend

    @property
    def requests(self) -> int:
        if self.backend is None:
            return 0
        world = self.backend.world
        return (
            len(self.backend.runner.calls)
            + len(world.simulator.runs)
            + len(world.registrations)
            + len(world.registry_transport.__dict__.get("requests", []))
        )

    def run(self, *argv: str, directory: bool = True, environ: dict[str, str] | None = None) -> int:
        full = [argv[0], *(["--dir", str(self.dir)] if directory else []), *argv[1:]]
        self.out.seek(0)
        self.out.truncate()
        self.err.seek(0)
        self.err.truncate()
        return cli.main(
            full,
            environ=environ if environ is not None else {},
            clock=self.clock,
            backend_factory=self.factory,
            stdout=self.out,
            stderr=self.err,
        )

    def prepare(self, **over: str) -> int:
        values = {"commit": "c0ffee1", "operator": "operadora", "values-file": str(VALUES), **over}
        argv = ["prepare"]
        for key, value in values.items():
            argv += [f"--{key}", value]
        return self.run(*argv)

    def manifest(self) -> dict[str, Any]:
        return json.loads((self.dir / "manifest.json").read_text(encoding="utf-8"))

    def evidence(self, name: str) -> dict[str, Any]:
        return json.loads((self.dir / name).read_text(encoding="utf-8"))
