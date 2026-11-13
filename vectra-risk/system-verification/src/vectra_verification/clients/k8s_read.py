"""Los cuatro verbos de solo lectura de `kubectl` (U12 Paso 5; INF-U12-02, INF-U12-03; NFR-U12-43): `get`, `logs`, `auth can-i` y `port-forward`. Nada mas.

Este es el **unico** archivo de la herramienta que invoca `kubectl` y el unico que importa `subprocess` (contrato de import-linter): la prueba de verbos
(`test_kubectl_verbs.py`) lo recorre. Cada orden se arma como lista de argumentos con el verbo literal justo despues de `kubectl` y sin `shell=True`; no hay una
funcion generica que reciba el verbo. El ejecutor se inyecta (`Runner`): las pruebas nunca llaman al `kubectl` real.

`port_forward` (INF-U12-03; K16 no da `get` sobre `services`): elige **un pod** con `get pods -l <selector> -o json` (listo y sin `deletionTimestamp`) y reenvia a `pod/<nombre>`,
nunca a `svc/...`. Pide un puerto local libre (`:<puerto remoto>`) y lee de la salida el que `kubectl` asigno. Es un gestor de contexto: el proceso muere al salir, tambien con
una excepcion. P-8 (a): si el reenvio cae al arrancar, **una** nueva eleccion de pod, registrada en el resultado (pods usados e intentos); si vuelve a caer, error claro con el pod, el
namespace y la causa. Nunca un reintento silencioso.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final, Protocol

FORWARDING: Final = re.compile(r"Forwarding from (?:127\.0\.0\.1|\[::1\]|localhost):(\d+) ->")
READY_TIMEOUT: Final = 15.0
MAX_ATTEMPTS: Final = 2  # la primera eleccion y la unica nueva (P-8 (a))


class K8sError(Exception):
    """Un fallo claro de `kubectl`: nombra el namespace, el pod y la causa, nunca un secreto."""


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str
    stderr: str


class Process(Protocol):
    def read_line(self, timeout: float) -> str | None:
        """La siguiente linea de la salida, o `None` si el proceso termino (o no hubo salida a tiempo)."""

    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...


class Runner(Protocol):
    def run(self, args: Sequence[str]) -> Completed: ...

    def start(self, args: Sequence[str]) -> Process: ...


class _SubprocessProcess:  # pragma: no cover - lanza el kubectl real; las pruebas inyectan un doble
    def __init__(self, args: Sequence[str]) -> None:
        self._process = subprocess.Popen(  # noqa: S603
            list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

    def read_line(self, timeout: float) -> str | None:
        import select

        assert self._process.stdout is not None
        ready, _, _ = select.select([self._process.stdout], [], [], timeout)
        if not ready:
            return None
        line = self._process.stdout.readline()
        return line or None

    def poll(self) -> int | None:
        return self._process.poll()

    def terminate(self) -> None:
        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()


class SubprocessRunner:  # pragma: no cover - lanza el kubectl real; las pruebas inyectan un doble
    def run(self, args: Sequence[str]) -> Completed:
        done = subprocess.run(list(args), capture_output=True, text=True, check=False, timeout=60)  # noqa: S603
        return Completed(done.returncode, done.stdout, done.stderr)

    def start(self, args: Sequence[str]) -> Process:
        return _SubprocessProcess(args)


@dataclass(frozen=True)
class Forward:
    """Un reenvio vivo: el puerto local que asigno `kubectl`, el pod al que llego y los que se probaron (P-8 (a))."""

    local_port: int
    namespace: str
    pod: str
    pods_used: tuple[str, ...]
    attempts: int
    _process: Process

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.local_port}"

    def check(self) -> None:
        """Error claro si el proceso del reenvio ya no esta; sin reintentarlo."""
        if self._process.poll() is not None:
            raise K8sError(f"port_forward_lost:{self.namespace}/pod/{self.pod}")


def _ready_pods(document: str, namespace: str) -> list[str]:
    try:
        items = json.loads(document)["items"]
    except (ValueError, KeyError, TypeError):
        raise K8sError(f"pods_response_shape:{namespace}") from None
    ready: list[str] = []
    for item in items:
        meta, status = item.get("metadata", {}), item.get("status", {})
        conditions = {c.get("type"): c.get("status") for c in status.get("conditions", [])}
        if (
            meta.get("deletionTimestamp") is None
            and status.get("phase") == "Running"
            and conditions.get("Ready") == "True"
        ):
            ready.append(str(meta["name"]))
    return sorted(ready)


class K8sRead:
    def __init__(self, runner: Runner, context: str | None = None) -> None:
        self._runner = runner
        self._context = context
        self.commands: list[tuple[str, ...]] = []

    def _context_args(self) -> list[str]:
        return [f"--context={self._context}"] if self._context else []

    def _run(self, args: list[str]) -> Completed:
        self.commands.append(tuple(args))
        return self._runner.run(args)

    def get(self, resource: str, namespace: str, selector: str | None = None, output: str = "json") -> str:
        args = ["kubectl", "get", resource, "-n", namespace, "-o", output]
        if selector:
            args += ["-l", selector]
        done = self._run(args + self._context_args())
        if done.returncode != 0:
            raise K8sError(f"get_failed:{namespace}/{resource}:{done.stderr.strip()[:200]}")
        return done.stdout

    def logs(self, pod: str, namespace: str, tail: int | None = None, since: str | None = None) -> str:
        args = ["kubectl", "logs", pod, "-n", namespace]
        if tail is not None:
            args += [f"--tail={tail}"]
        if since:
            args += [f"--since={since}"]
        done = self._run(args + self._context_args())
        if done.returncode != 0:
            raise K8sError(f"logs_failed:{namespace}/{pod}:{done.stderr.strip()[:200]}")
        return done.stdout

    def auth_can_i(self, verb: str, resource: str, namespace: str) -> bool:
        done = self._run(["kubectl", "auth", "can-i", verb, resource, "-n", namespace] + self._context_args())
        answer = done.stdout.strip().lower()
        if answer in ("yes", "no"):
            return answer == "yes"
        raise K8sError(f"auth_can_i_failed:{namespace}/{resource}:{done.stderr.strip()[:200]}")

    def _choose_pod(self, namespace: str, selector: str, avoid: Sequence[str]) -> str:
        pods = _ready_pods(self.get("pods", namespace, selector), namespace)
        if not pods:
            raise K8sError(f"no_ready_pod:{namespace}:{selector}")
        fresh = [pod for pod in pods if pod not in avoid]
        return (fresh or pods)[0]

    def _start_forward(
        self, namespace: str, pod: str, remote_port: int
    ) -> tuple[Process | None, int | None, str]:
        args = [
            "kubectl",
            "port-forward",
            f"pod/{pod}",
            f":{remote_port}",
            "--address=127.0.0.1",
            "-n",
            namespace,
        ] + self._context_args()
        self.commands.append(tuple(args))
        process = self._runner.start(args)
        deadline = time.monotonic() + READY_TIMEOUT
        last = ""
        while time.monotonic() < deadline:
            line = process.read_line(0.5)
            if line is not None:
                last = line.strip() or last
                found = FORWARDING.search(line)
                if found:
                    return process, int(found.group(1)), last
            if process.poll() is not None:
                break
        process.terminate()
        return None, None, last[:200]

    @contextmanager
    def port_forward(self, namespace: str, selector: str, remote_port: int) -> Iterator[Forward]:
        """Reenvia un puerto local libre (el que asigne `kubectl`) a `remote_port` de **un pod** listo; el proceso muere al salir."""
        used: list[str] = []
        cause = ""
        process: Process | None = None
        for _ in range(MAX_ATTEMPTS):
            pod = self._choose_pod(namespace, selector, used)
            used.append(pod)
            process, port, cause = self._start_forward(namespace, pod, remote_port)
            if process is not None and port is not None:
                break
            process = None
        else:
            raise K8sError(f"port_forward_failed:{namespace}/pod/{used[-1]}:attempts={len(used)}:{cause}")
        assert process is not None
        try:
            yield Forward(port, namespace, used[-1], tuple(used), len(used), process)
        finally:
            process.terminate()
