"""Los dos unicos verbos de `kubectl` del servidor: `get` y `auth can-i`. Nada mas.

Mismo enfoque que `system-verification/src/vectra_verification/clients/k8s_read.py` (U12), sin `logs` ni `port-forward`: este es el **unico** archivo del
paquete que importa `subprocess` y el unico que nombra `kubectl`. Cada orden se arma como lista de argumentos, con el verbo literal justo despues de
`kubectl` y sin `shell=True`; no hay una funcion que reciba el verbo de `kubectl` ni una que reciba una orden. El recurso de `get` sale de una lista cerrada
(`READ_RESOURCES`); el namespace se valida contra el patron de etiqueta DNS. El ejecutor se inyecta (`Runner`): las pruebas nunca llaman al `kubectl` real.

El proceso hijo no hereda el entorno: recibe solo `PATH`, `HOME` y `KUBECONFIG` (el de solo lectura), y cada orden lleva `--kubeconfig` y `--context`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol

#: Lo unico que `get` puede pedir. Cada nombre esta en el ClusterRole `vectra-readonly-agent`; `secrets` no esta ni aqui ni alli.
READ_RESOURCES: Final = frozenset(
    {
        "applications.argoproj.io",
        "pods",
        "events",
        "inferenceservices.serving.kserve.io",
        "deployments.apps",
        "statefulsets.apps",
        "daemonsets.apps",
        "jobs.batch",
    }
)
NAMESPACE: Final = re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?")
_WORD: Final = re.compile(r"[a-z*]{1,20}")
_RESOURCE: Final = re.compile(r"[a-z0-9.*]{1,80}")
_SECRET_LIKE: Final = re.compile(
    r"(?i)(eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_.-]+|((?:password|passwd|token|secret|authorization|bearer)\S*\s*[=:]\s*)\S+)"
)
REQUEST_TIMEOUT: Final = "10s"
PROCESS_TIMEOUT: Final = 30


class K8sError(Exception):
    """Un fallo de `kubectl` o un argumento rechazado. El mensaje es corto y sin secretos."""


class Rejected(K8sError):
    """Un argumento que no pasa la validacion: no se ejecuto nada."""


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    def run(self, args: Sequence[str], env: Mapping[str, str]) -> Completed: ...


class SubprocessRunner:  # pragma: no cover - lanza el kubectl real; las pruebas inyectan un doble
    def run(self, args: Sequence[str], env: Mapping[str, str]) -> Completed:
        try:
            done = subprocess.run(  # noqa: S603
                list(args),
                capture_output=True,
                text=True,
                check=False,
                timeout=PROCESS_TIMEOUT,
                env=dict(env),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return Completed(127, "", type(error).__name__)
        return Completed(done.returncode, done.stdout, done.stderr)


def redact(text: str) -> str:
    """Quita lo que parece un JWT o un `clave=valor` de credencial."""
    return _SECRET_LIKE.sub(lambda m: f"{m.group(2) or ''}<oculto>", text)


def shown(value: object) -> str:
    """Un argumento rechazado, recortado, para el mensaje de error."""
    return repr(str(value)[:40])


def valid_namespace(namespace: object) -> str:
    if not isinstance(namespace, str) or NAMESPACE.fullmatch(namespace) is None:
        raise Rejected(
            f"argumento rechazado: namespace {shown(namespace)} no es una etiqueta DNS (a-z, 0-9 y guion; 63 como maximo)"
        )
    return namespace


class Kubectl:
    """`kubectl get` y `kubectl auth can-i` con el kubeconfig de solo lectura. `commands` guarda cada orden lanzada (las pruebas la leen)."""

    def __init__(self, runner: Runner, kubeconfig: Path, context: str) -> None:
        self._runner = runner
        self._kubeconfig = kubeconfig
        self._context = context
        self.commands: list[tuple[str, ...]] = []

    def _tail(self) -> list[str]:
        return [
            f"--kubeconfig={self._kubeconfig}",
            f"--context={self._context}",
            f"--request-timeout={REQUEST_TIMEOUT}",
        ]

    def _env(self) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/nonexistent"),
            "KUBECONFIG": str(self._kubeconfig),
        }

    def _run(self, args: list[str]) -> Completed:
        self.commands.append(tuple(args))
        return self._runner.run(args, self._env())

    def get(self, resource: str, namespace: str) -> list[dict[str, Any]]:
        """Los `items` de `kubectl get <recurso> -n <namespace> -o json`. `resource` solo puede ser uno de `READ_RESOURCES`."""
        if resource not in READ_RESOURCES:
            raise Rejected(
                f"argumento rechazado: el recurso {shown(resource)} no esta en la lista cerrada de lectura"
            )
        namespace = valid_namespace(namespace)
        done = self._run(["kubectl", "get", resource, "-n", namespace, "-o", "json"] + self._tail())
        if done.returncode != 0:
            raise K8sError(f"get_failed:{namespace}/{resource}:{redact(done.stderr.strip())[:200]}")
        try:
            items = json.loads(done.stdout)["items"]
        except (ValueError, KeyError, TypeError):
            raise K8sError(f"get_response_shape:{namespace}/{resource}") from None
        if not isinstance(items, list):
            raise K8sError(f"get_response_shape:{namespace}/{resource}")
        return [item for item in items if isinstance(item, dict)]

    def can_i(self, verb: str, resource: str, namespace: str | None, subresource: str | None = None) -> bool:
        """`kubectl auth can-i <verbo> <recurso>`: pregunta, no hace. `namespace=None` pregunta en todos (`-A`)."""
        if _WORD.fullmatch(verb) is None or _RESOURCE.fullmatch(resource) is None:
            raise Rejected(f"argumento rechazado: pregunta can-i {shown(verb)} {shown(resource)}")
        args = ["kubectl", "auth", "can-i", verb, resource]
        if subresource is not None:
            if _WORD.fullmatch(subresource) is None:
                raise Rejected(f"argumento rechazado: subrecurso {shown(subresource)}")
            args.append(f"--subresource={subresource}")
        args += ["-A"] if namespace is None else ["-n", valid_namespace(namespace)]
        done = self._run(args + self._tail())
        answer = (done.stdout.strip().lower().split() or [""])[0]  # `no - <motivo>` sigue siendo un no
        if answer in ("yes", "no"):
            return answer == "yes"
        raise K8sError(f"auth_can_i_no_answer:{verb} {resource}:{redact(done.stderr.strip())[:200]}")

    def can_i_list(self, namespace: str) -> str:
        """La tabla de `kubectl auth can-i --list -n <namespace>`: lo que la propia identidad puede hacer."""
        namespace = valid_namespace(namespace)
        done = self._run(["kubectl", "auth", "can-i", "--list", "-n", namespace] + self._tail())
        if done.returncode != 0:
            raise K8sError(f"auth_can_i_list_failed:{namespace}:{redact(done.stderr.strip())[:200]}")
        return done.stdout
