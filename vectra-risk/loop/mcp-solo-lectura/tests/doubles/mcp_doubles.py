"""Dobles de las pruebas: un `kubectl` falso que responde por recurso y guarda cada orden, y un kubeconfig de solo lectura falso (token sin firma real)."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from vectra_mcp_readonly.guard import EXPECTED_SUBJECT
from vectra_mcp_readonly.kubectl import Completed

CAN_I_LIST = """Resources                                       Non-Resource URLs   Resource Names   Verbs
selfsubjectaccessreviews.authorization.k8s.io   []                  []               [create]
selfsubjectrulesreviews.authorization.k8s.io    []                  []               [create]
pods                                            []                  []               [get list watch]
pods/log                                        []                  []               [get list watch]
applications.argoproj.io                        []                  []               [get list watch]
                                                [/healthz]          []               [get]
"""
#: La identidad de solo lectura: lo que el API responde a `auth can-i <verbo> <recurso>`.
READ_ONLY_ANSWERS = {
    "get pods": "yes",
    "list applications.argoproj.io": "yes",
    "list inferenceservices.serving.kserve.io": "yes",
}


def fake_token(subject: str) -> str:
    def part(data: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'none'})}.{part({'iss': 'kubernetes/serviceaccount', 'sub': subject})}.firma"


def kubeconfig_document(subject: str = EXPECTED_SUBJECT, context: str = "kind-vectra") -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{"name": context, "cluster": {"server": "https://127.0.0.1:1"}}],
        "users": [{"name": "vectra-readonly-agent", "user": {"token": fake_token(subject)}}],
        "contexts": [{"name": context, "context": {"cluster": context, "user": "vectra-readonly-agent"}}],
        "current-context": context,
    }


def write_kubeconfig(path: Path, document: dict[str, Any], mode: int = 0o600) -> Path:
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    path.chmod(mode)
    return path


class FakeRunner:
    """Responde `get <recurso>` con `items[recurso]` y `auth can-i` con `answers` («no» por omision). Guarda cada orden y su entorno."""

    def __init__(
        self, items: dict[str, list[dict[str, Any]]] | None = None, answers: dict[str, str] | None = None
    ) -> None:
        self.items = items or {}
        self.answers = dict(READ_ONLY_ANSWERS if answers is None else answers)
        self.calls: list[tuple[str, ...]] = []
        self.envs: list[dict[str, str]] = []

    def run(self, args: Sequence[str], env: Mapping[str, str]) -> Completed:
        self.calls.append(tuple(args))
        self.envs.append(dict(env))
        if args[1] == "get":
            return Completed(0, json.dumps({"items": self.items.get(args[2], [])}), "")
        if tuple(args[1:4]) == ("auth", "can-i", "--list"):
            return Completed(0, CAN_I_LIST, "")
        if tuple(args[1:3]) == ("auth", "can-i"):
            question = f"{args[3]} {args[4]}"
            sub = next((a.split("=", 1)[1] for a in args if a.startswith("--subresource=")), None)
            answer = self.answers.get(f"{question}/{sub}" if sub else question, "no")
            return Completed(0 if answer == "yes" else 1, answer + "\n", "")
        return Completed(1, "", "orden inesperada")
