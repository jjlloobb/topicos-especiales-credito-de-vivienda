"""Ninguna prueba de `platform/kind` puede ejecutar `kubectl` de verdad (U01-T16, CI-01).

Dos pruebas de `main()` llegaron a leer los `ExternalSecret` y los `Secret` del cluster real de la maquina (y fallaban en la CI, sin cluster). Esta
salvaguarda sustituye el ejecutor por omision de `vault_paths` por uno que falla con un mensaje claro: una prueba que necesite un cluster inyecta su ejecutor falso.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vault_paths as vp  # noqa: E402

REAL_KUBECTL_RUNNER = vp.kubectl_runner
MESSAGE = "una prueba intento ejecutar kubectl real ({command}): inyecta un ejecutor falso (ClusterSecrets/Vault/ca_from_cluster con `run`, o sustituye la clase en vp)"


def refuse_real_kubectl(command: list[str], stdin: str | None) -> None:
    raise RuntimeError(MESSAGE.format(command=" ".join(command[:5])))


@pytest.fixture(autouse=True)
def no_real_kubectl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vp, "kubectl_runner", refuse_real_kubectl)
