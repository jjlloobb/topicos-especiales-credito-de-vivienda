"""Doble del ejecutor de `kubectl` (U12-T02): cuenta y guarda las ordenes y responde con JSON de pods. Las pruebas nunca llaman al `kubectl` real."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from vectra_verification.clients.k8s_read import Completed


def pod(name: str, *, ready: bool = True, deleting: bool = False, phase: str = "Running") -> dict[str, Any]:
    metadata: dict[str, Any] = {"name": name}
    if deleting:
        metadata["deletionTimestamp"] = "2026-11-13T10:00:00Z"
    return {
        "metadata": metadata,
        "status": {"phase": phase, "conditions": [{"type": "Ready", "status": "True" if ready else "False"}]},
    }


class FakeProcess:
    def __init__(self, lines: list[str], exit_code: int | None = None) -> None:
        self.lines = list(lines)
        self.exit_code = exit_code
        self.terminated = False

    def read_line(self, timeout: float) -> str | None:
        return self.lines.pop(0) if self.lines else None

    def poll(self) -> int | None:
        if self.terminated:
            return -15
        return self.exit_code if not self.lines else None

    def terminate(self) -> None:
        self.terminated = True


class KubectlDouble:
    """`pods`: lo que `get pods` devuelve; `forwards`: la salida de cada `port-forward` que se pida, en orden (`None` = cae sin decir nada)."""

    def __init__(
        self, pods: list[dict[str, Any]] | None = None, forwards: list[list[str] | None] | None = None
    ) -> None:
        self.pods = pods if pods is not None else [pod("registry-0")]
        self.forwards = forwards if forwards is not None else [["Forwarding from 127.0.0.1:41234 -> 8080\n"]]
        self.calls: list[tuple[str, ...]] = []
        self.processes: list[FakeProcess] = []
        self.answers: dict[str, Completed] = {}

    def run(self, args: Sequence[str]) -> Completed:
        self.calls.append(tuple(args))
        assert args[0] == "kubectl"
        verb = args[1]
        if verb == "get" and args[2] == "pods":
            return Completed(0, json.dumps({"items": self.pods}), "")
        return self.answers.get(verb, Completed(0, "yes\n" if verb == "auth" else "salida\n", ""))

    def start(self, args: Sequence[str]) -> FakeProcess:
        self.calls.append(tuple(args))
        assert args[0] == "kubectl" and args[1] == "port-forward"
        script = self.forwards.pop(0) if self.forwards else None
        process = FakeProcess(script or [], None if script else 1)
        self.processes.append(process)
        return process

    @property
    def forward_calls(self) -> list[tuple[str, ...]]:
        return [c for c in self.calls if c[1] == "port-forward"]
