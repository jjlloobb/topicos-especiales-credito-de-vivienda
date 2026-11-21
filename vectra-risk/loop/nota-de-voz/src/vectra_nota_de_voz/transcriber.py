"""El transcriptor: una interfaz, y la implementacion real con `faster-whisper` (Whisper sobre CTranslate2, en CPU y con cuantizacion int8).

La transcripcion ocurre en esta maquina. Lo unico que toca la red es la descarga de los pesos del modelo la primera vez, desde huggingface.co, y se
avisa antes; con el modelo ya en la cache, o con `--model-path`, no hay ninguna conexion (`local_files_only`). El audio no viaja a ningun sitio.

`faster-whisper` es una dependencia opcional (extra `transcriptor`): se importa aqui dentro, tarde, para que el resto del paquete funcione sin ella.
El WAV lo lee la biblioteca estandar (`wave`) y se entrega al modelo como muestras: no hace falta `ffmpeg`.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import re
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, Protocol

from vectra_nota_de_voz.errors import VozError

#: Los modelos que se descargan solos: repositorio de pesos (conversion a CTranslate2 de los de OpenAI, licencia MIT) y tamano de `model.bin`.
MODELS: Final = {
    "tiny": ("Systran/faster-whisper-tiny", "76 MB"),
    "base": ("Systran/faster-whisper-base", "145 MB"),
    "small": ("Systran/faster-whisper-small", "484 MB"),
}
DEFAULT_MODEL: Final = "base"
LANGUAGE: Final = re.compile(r"[a-z]{2,3}")
INSTALL_HINT: Final = (
    "falta el transcriptor (`faster-whisper`). Es opcional y no se instala por omision; ejecute la orden asi, desde `vectra-risk/`:\n"
    "  uv run --group voz vectra-nota-de-voz <PR>"
)


class Transcriber(Protocol):
    @property
    def label(self) -> str:
        """El nombre del modelo que se escribe en la cabecera de la nota."""

    def problem(self) -> str | None:
        """Por que no se puede transcribir, o `None` si todo esta listo. No descarga ni carga nada."""

    def transcribe(self, wav: Path, language: str | None, notify: Callable[[str], None]) -> str:
        """El texto de un WAV de 16 kHz mono. `language=None` deja que el modelo detecte el idioma."""


def valid_language(language: str) -> str | None:
    if language == "auto":
        return None
    if LANGUAGE.fullmatch(language) is None:
        raise VozError(
            f"argumento rechazado: el idioma {language[:20]!r} no es un codigo como `es` o `en`, ni `auto`"
        )
    return language


class FasterWhisperTranscriber:
    def __init__(self, model: str = DEFAULT_MODEL, model_path: Path | None = None) -> None:
        if model not in MODELS:
            raise VozError(
                f"argumento rechazado: el modelo debe ser uno de {', '.join(MODELS)} (otro, con `--model-path`)"
            )
        self._model = model
        self._model_path = model_path

    @property
    def label(self) -> str:
        if self._model_path is None:
            return self._model
        return re.sub(r"[^A-Za-z0-9._-]", "-", self._model_path.name)[:40] or "modelo-local"

    def problem(self) -> str | None:
        if importlib.util.find_spec("faster_whisper") is None:
            return INSTALL_HINT
        if self._model_path is not None and not (self._model_path / "model.bin").is_file():
            return f"`--model-path {self._model_path}` no es un directorio de modelo de faster-whisper (falta `model.bin`)"
        return None

    def transcribe(self, wav: Path, language: str | None, notify: Callable[[str], None]) -> str:
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        source, offline = self._source(notify)
        try:
            samples = _samples(wav)
            whisper: Any = importlib.import_module("faster_whisper")
            model = whisper.WhisperModel(source, device="cpu", compute_type="int8", local_files_only=offline)
            segments, _info = model.transcribe(
                samples, language=language, beam_size=5, vad_filter=True, condition_on_previous_text=False
            )
            return " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as error:  # noqa: BLE001 - frontera con bibliotecas ajenas (red, pesos, audio): cualquier fallo es "no hay texto", sin traza
            raise VozError(f"la transcripcion fallo ({type(error).__name__}: {str(error)[:200]})") from None

    def _source(self, notify: Callable[[str], None]) -> tuple[str, bool]:
        """De donde sale el modelo y si se carga sin red. Avisa antes de una descarga."""
        if self._model_path is not None:
            notify(f"Modelo local: {self._model_path} (sin red).")
            return str(self._model_path), True
        repo, size = MODELS[self._model]
        hub: Any = importlib.import_module("huggingface_hub")
        if isinstance(hub.try_to_load_from_cache(repo, "model.bin"), str):
            notify(f"Modelo `{self._model}` ya descargado (cache de Hugging Face): se carga sin red.")
            return self._model, True
        notify(
            f"AVISO: el modelo `{self._model}` no esta en esta maquina. Se descarga ahora de https://huggingface.co/{repo} "
            f"(unos {size}, una sola vez, a ~/.cache/huggingface). Solo se descargan los pesos: el audio no sale de la maquina."
        )
        return self._model, False


def _samples(wav: Path) -> Any:
    """Las muestras del WAV (ya validado: 16 kHz, mono, 16 bits) como float32 entre -1 y 1, que es lo que Whisper espera."""
    numpy: Any = importlib.import_module("numpy")
    with wave.open(str(wav), "rb") as reader:
        frames = reader.readframes(reader.getnframes())
    return numpy.frombuffer(frames, dtype=numpy.int16).astype(numpy.float32) / 32768.0
