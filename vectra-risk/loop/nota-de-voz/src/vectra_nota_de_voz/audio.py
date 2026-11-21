"""El audio: un directorio privado bajo `$XDG_RUNTIME_DIR` (memoria, no disco), la grabacion y la validacion del WAV.

La voz es un dato personal. El audio vive solo en ese directorio (0700, archivos 0600) y `private_dir` lo borra al salir del bloque, pase lo que pase:
exito, error o Ctrl-C. Un `kill -9` no se puede atender; lo que quede esta en `$XDG_RUNTIME_DIR`, que el sistema vacia al cerrar la sesion.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import wave
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Final, Protocol

from vectra_nota_de_voz.commands import RECORDERS, SAMPLE_RATE, Runner, recorder_command
from vectra_nota_de_voz.errors import VozError

DIR_PREFIX: Final = "vectra-nota-de-voz-"
MAX_AUDIO_SECONDS: Final = 600
_STEP: Final = 0.25


class EnterWaiter(Protocol):
    def wait_enter(self, seconds: float) -> bool: ...


@contextmanager
def private_dir(environ: Mapping[str, str]) -> Iterator[Path]:
    """Un directorio 0700 bajo `$XDG_RUNTIME_DIR`, borrado al salir (tambien con una excepcion o una interrupcion)."""
    base = environ.get("XDG_RUNTIME_DIR", "")
    if not base or not os.path.isabs(base) or not os.path.isdir(base):
        raise VozError(
            "no hay `$XDG_RUNTIME_DIR` utilizable: el audio solo se guarda en ese directorio privado (en memoria). "
            "Ejecute la orden desde una sesion de usuario normal."
        )
    info = os.stat(base)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise VozError(
            f"`$XDG_RUNTIME_DIR` ({base}) no es un directorio privado suyo (0700): no se graba ahi"
        )
    path = Path(tempfile.mkdtemp(prefix=DIR_PREFIX, dir=base))
    try:
        os.chmod(path, 0o700)
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        if path.exists():  # pragma: no cover - solo si el sistema de archivos falla al borrar
            raise VozError(f"ATENCION: no se pudo borrar {path}; borrelo a mano (contiene el audio)")


def write_private(path: Path, text: str) -> None:
    """Un archivo nuevo 0600 con el texto."""
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as handle:
        handle.write(text)


def pick_recorder(runner: Runner, wanted: str) -> str:
    """El grabador que se usara: el pedido, o el primero de la lista que este instalado."""
    if wanted != "auto" and wanted not in RECORDERS:
        raise VozError(f"argumento rechazado: el grabador debe ser auto, {' o '.join(RECORDERS)}")
    candidates = RECORDERS if wanted == "auto" else (wanted,)
    for program in candidates:
        if runner.which(program) is not None:
            return program
    raise VozError(
        f"no hay grabador: no se encontro {' ni '.join(f'`{c}`' for c in candidates)} en el PATH. "
        "Instale `alsa-utils` (arecord) o `pipewire-bin` (pw-record), o pase una grabacion con `--audio archivo.wav`."
    )


def wav_seconds(path: Path) -> float:
    """Comprueba que el archivo es un WAV PCM de 16 kHz, mono y 16 bits con algo dentro, y devuelve su duracion."""
    try:
        with wave.open(str(path), "rb") as reader:
            shape = (
                reader.getframerate(),
                reader.getnchannels(),
                reader.getsampwidth(),
                reader.getcomptype(),
            )
            frames = reader.getnframes()
    except (OSError, EOFError, wave.Error):
        raise VozError(f"{path.name} no es un archivo WAV legible") from None
    if shape != (SAMPLE_RATE, 1, 2, "NONE"):
        raise VozError(
            f"{path.name} no es WAV PCM de 16 kHz, mono y 16 bits (es {shape[0]} Hz, {shape[1]} canal(es), {shape[2] * 8} bits). "
            "Grabe con: arecord -t wav -f S16_LE -r 16000 -c 1 archivo.wav"
        )
    seconds = frames / SAMPLE_RATE
    if seconds < 0.5:
        raise VozError("la grabacion esta vacia o dura menos de medio segundo: no hay nada que transcribir")
    if seconds > MAX_AUDIO_SECONDS:
        raise VozError(f"la grabacion dura {seconds:.0f} s; el maximo es {MAX_AUDIO_SECONDS} s")
    return seconds


def record(runner: Runner, waiter: EnterWaiter, program: str, directory: Path, max_seconds: int) -> Path:
    """Graba del microfono hasta Enter o hasta `max_seconds`. Devuelve el WAV, dentro de `directory` y con modo 0600."""
    wav = directory / "nota.wav"
    log = directory / "grabador.log"
    process = runner.spawn(recorder_command(program, wav, max_seconds), log)
    try:
        elapsed = 0.0
        while process.poll() is None and elapsed < max_seconds:
            if waiter.wait_enter(_STEP):
                break
            elapsed += _STEP
    finally:
        process.stop()
    if not wav.is_file():
        detail = log.read_text(encoding="utf-8", errors="replace").strip()[-300:] if log.is_file() else ""
        raise VozError(f"`{program}` no grabo nada. ¿Hay microfono y permiso para usarlo? {detail}".strip())
    os.chmod(wav, 0o600)
    return wav
