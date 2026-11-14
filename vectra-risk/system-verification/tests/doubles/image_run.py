"""La orden `docker run` de la imagen de U12 (Paso 15, INF-U12-01), en un solo sitio: la usan `tests/image/test_image.py` (la corre de verdad) y `tests/unit/test_demos_closed_world.py` (comprueba que el README
la trae igual). Cambiar una opcion aqui sin cambiar el README rompe la prueba del README, y al reves."""

from __future__ import annotations

import os
import subprocess
import uuid
from collections.abc import Sequence
from pathlib import Path

IMAGE = "localhost:5001/vectra/system-verification:dev"
UNIT = Path(__file__).resolve().parents[2]  # system-verification/
SECCOMP = UNIT / "seccomp" / "chrome.json"
DOUBLES = Path(__file__).resolve().parent
CONTAINER_PREFIX = "u12t05-"

# Opciones que **todo** `docker run` de la herramienta lleva (texto literal, como en el README). `--user`, `--network host` y los montajes dependen de cada corrida.
READ_ONLY = "--read-only"
TMPFS = "--tmpfs /tmp"
MEMORY = "--memory 1g"
SECCOMP_OPTION = "--security-opt seccomp=chrome.json"
NETWORK = "--network host"
README_FLAGS = (
    "--rm",
    READ_ONLY,
    TMPFS,
    NETWORK,
    '--user "$(id -u):$(id -g)"',
    MEMORY,
    SECCOMP_OPTION,
    "-v",
    "-e",
)


def base_options(
    *, user: str | None = None, seccomp: Path | None = SECCOMP, network_host: bool = False
) -> list[str]:
    """Las opciones comunes con el valor de la prueba: `--user` y la ruta del perfil cambian; el resto es literal."""
    options = [
        "--rm",
        *READ_ONLY.split(),
        *TMPFS.split(),
        *MEMORY.split(),
        "--user",
        user or f"{os.getuid()}:{os.getgid()}",
    ]
    if seccomp is not None:
        options += ["--security-opt", f"seccomp={seccomp}"]
    if network_host:
        options += NETWORK.split()
    return options


def mount(source: Path, target: str, *, read_only: bool = True) -> list[str]:
    return ["-v", f"{source}:{target}{':ro' if read_only else ''}"]


def unique_name(label: str) -> str:
    return f"{CONTAINER_PREFIX}{label}-{uuid.uuid4().hex[:8]}"


def run(
    arguments: Sequence[str], *, timeout: float = 180, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    """`docker <arguments>`; un `docker run` queda impreso (con `pytest -s`) como la bitacora lo pide."""
    return subprocess.run(  # noqa: S603 - docker local
        ["docker", *arguments],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        input=input_text,  # noqa: S607
    )
