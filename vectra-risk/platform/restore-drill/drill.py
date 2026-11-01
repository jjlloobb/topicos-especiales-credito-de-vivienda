#!/usr/bin/env python3
"""Simulacro de restore (P-U1-05, NFR-U1-07). Sale con error salvo cadena integra y 0 identificadores vencidos.

Cada paso es un comando de `DrillCommands`; se inyecta para probar sin cluster. `verify_chain` llega con U3 y
`case-retention` con U8. Cualquier excepcion es un simulacro fallido: se destruye lo creado, se empuja
`success 0` y se sale con 1, para que la alerta dispare por el motivo correcto y no por falta de metrica.
"""

import logging
import os
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

TIMEOUT = 5
REGISTRY = ("restore-registry", "registry-db")
CASE = ("restore-case", "case-db")
LOG = logging.getLogger("restore-drill")


class DrillCommands(Protocol):
    def create_cluster(self, name: str, source: str) -> None: ...
    def destroy_cluster(self, name: str) -> None: ...
    def verify_chain(self, cluster: str) -> str: ...
    def run_case_retention(self, cluster: str) -> int: ...
    def reached_lsn(self, cluster: str) -> int: ...


@dataclass
class DrillResult:
    success: bool
    duration_seconds: float
    retention_violations: int
    lsn: int


def _destroy_all(commands: DrillCommands, names: list[str]) -> bool:
    """Intenta destruir todos aunque alguno falle. Falso si quedo algo sin destruir."""
    clean = True
    for name in names:
        try:
            commands.destroy_cluster(name)
        except Exception:
            LOG.exception("No se pudo destruir %s", name)
            clean = False
    return clean


def run_drill(commands: DrillCommands, clock: Callable[[], float] = time.monotonic) -> DrillResult:
    started = clock()
    created: list[str] = []
    success = False
    violations = 0
    lsn = 0
    try:
        # Un simulacro anterior pudo morir por activeDeadlineSeconds sin limpiar.
        if not _destroy_all(commands, [CASE[0], REGISTRY[0]]):
            raise RuntimeError("Quedan clusters de un simulacro anterior")
        # Se anota antes de crear: un `kubectl wait` vencido deja el Cluster creado.
        created.append(REGISTRY[0])
        commands.create_cluster(*REGISTRY)
        verdict = commands.verify_chain(REGISTRY[0])
        lsn = commands.reached_lsn(REGISTRY[0])
        created.append(CASE[0])
        commands.create_cluster(*CASE)
        violations = commands.run_case_retention(CASE[0])
        success = verdict == "integra" and violations == 0
    except Exception:
        LOG.exception("El simulacro fallo")
        success = False
    if not _destroy_all(commands, list(reversed(created))):
        success = False
    return DrillResult(success, clock() - started, violations, lsn)


def metrics_body(result: DrillResult) -> bytes:
    lines = [
        f"vectra_restore_drill_success {int(result.success)}",
        f"vectra_restore_drill_duration_seconds {result.duration_seconds:.3f}",
        f"vectra_restore_drill_lsn {result.lsn}",
        f"vectra_restore_drill_retention_violations {result.retention_violations}",
    ]
    return ("\n".join(lines) + "\n").encode()


def push(pushgateway: str, result: DrillResult) -> None:
    url = f"{pushgateway.rstrip('/')}/metrics/job/restore-drill"
    request = urllib.request.Request(url, data=metrics_body(result), method="PUT")  # noqa: S310
    with urllib.request.urlopen(request, timeout=TIMEOUT):  # noqa: S310
        pass


class KubectlCommands:
    """Implementacion real; corre dentro del CronJob con el RBAC K12."""

    def _run(self, *args: str) -> str:
        try:
            return subprocess.run(args, check=True, capture_output=True, text=True, timeout=7200).stdout  # noqa: S603
        except subprocess.CalledProcessError as exc:
            LOG.error("%s salio con %s: %s", args[0], exc.returncode, exc.stderr)  # noqa: TRY400
            raise

    def create_cluster(self, name: str, source: str) -> None:
        self._run("restore-cluster.sh", "create", name, source)

    def destroy_cluster(self, name: str) -> None:
        self._run("restore-cluster.sh", "destroy", name)

    def verify_chain(self, cluster: str) -> str:
        return self._run("vectra-registry", "verify", "--mode", "full", "--cluster", cluster).strip()

    def run_case_retention(self, cluster: str) -> int:
        return int(self._run("case-retention", "--cluster", cluster, "--count-expired").strip())

    def reached_lsn(self, cluster: str) -> int:
        return int(self._run("restore-cluster.sh", "lsn", cluster).strip())


def main(commands: DrillCommands | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    result = run_drill(commands if commands is not None else KubectlCommands())
    try:
        push(os.environ["PUSHGATEWAY_URL"], result)
    except Exception:
        LOG.exception("No se pudieron empujar las metricas")
        return 1
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
