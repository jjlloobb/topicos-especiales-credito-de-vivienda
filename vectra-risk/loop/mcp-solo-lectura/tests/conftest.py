"""Las fixtures comunes: el `kubectl` falso (`tests/doubles/mcp_doubles.py`) y un `Kubectl` atado a el."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp_doubles import FakeRunner

from vectra_mcp_readonly.kubectl import Kubectl


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def kubectl(runner: FakeRunner) -> Kubectl:
    return Kubectl(runner, Path("/run/user/1000/kind-vectra-readonly"), "kind-vectra")
