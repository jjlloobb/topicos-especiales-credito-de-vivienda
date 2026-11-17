"""Guarda de R-01 para `tests/unit`: ninguna prueba unitaria llega al cluster, a Docker ni a Argo CD por la puerta de atras.

Cada prueba corre con `KUBECONFIG=/nonexistent` y con centinelas de `kubectl`, `docker`, `argocd` y `gh` **delante** del `PATH` real. Los dobles que una prueba pone delante (`PATH=<doble>:<PATH>`) siguen ganando; si un doble
falta y el binario real habria respondido, el centinela lo atrapa y la prueba falla en su cierre con el nombre de la herramienta.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

TOOLS = ("kubectl", "docker", "argocd", "gh")


@pytest.fixture(autouse=True)
def no_real_cluster_tools(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    directory = tmp_path_factory.mktemp("sentinels")
    log = directory / "calls.log"
    log.write_text("", encoding="utf-8")
    for name in TOOLS:
        script = directory / name
        script.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\nexit 99\n', encoding="utf-8")
        script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("KUBECONFIG", "/nonexistent")
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("ARGOCD_OPTS", raising=False)
    yield
    called = Path(log).read_text(encoding="utf-8").strip()
    assert called == "", f"una prueba llamó a una herramienta real del cluster (falta su doble): {called}"
