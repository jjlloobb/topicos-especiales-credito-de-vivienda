"""Las fixtures comunes: los dobles (`tests/doubles/voz_doubles.py`), un `$XDG_RUNTIME_DIR` falso y `launch`, que corre el flujo entero."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from voz_doubles import FakeConsole, FakeRunner, FakeTranscriber

from vectra_nota_de_voz.cli import Deps, run


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def transcriber() -> FakeTranscriber:
    return FakeTranscriber()


@pytest.fixture
def runtime(tmp_path: Path) -> Path:
    path = tmp_path / "run"
    path.mkdir(mode=0o700)
    return path


@pytest.fixture
def leftovers(runtime: Path) -> Callable[[], list[Path]]:
    """Lo que queda en el directorio privado tras la orden. Debe ser siempre nada."""
    return lambda: sorted(runtime.rglob("*"))


@pytest.fixture
def launch(runner: FakeRunner, transcriber: FakeTranscriber, runtime: Path) -> Callable[..., int]:
    def _launch(console: FakeConsole, *argv: str, env: dict[str, str] | None = None) -> int:
        environ = {"XDG_RUNTIME_DIR": str(runtime), "PATH": "/usr/bin", "HOME": "/home/x", **(env or {})}
        return run(list(argv), Deps(runner, console, environ, transcriber.make))

    return _launch
