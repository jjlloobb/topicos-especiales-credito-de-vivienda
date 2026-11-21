"""El transcriptor real, sin el modelo: `faster_whisper` y `huggingface_hub` son modulos falsos. La prueba con el modelo de verdad es `manual`."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from voz_doubles import write_wav

from vectra_nota_de_voz.audio import wav_seconds
from vectra_nota_de_voz.errors import VozError
from vectra_nota_de_voz.transcriber import (
    DEFAULT_MODEL,
    INSTALL_HINT,
    MODELS,
    FasterWhisperTranscriber,
    valid_language,
)


class FakeWhisper:
    def __init__(self, monkeypatch, cached: bool) -> None:
        self.loaded: list[tuple] = []
        self.transcribed: list[dict] = []
        self.cache_lookups: list[tuple] = []
        self.fails: Exception | None = None
        outer = self

        class WhisperModel:
            def __init__(self, source: str, **options) -> None:
                outer.loaded.append((source, options))
                if outer.fails is not None:
                    raise outer.fails

            def transcribe(self, samples, **options):
                outer.transcribed.append({"samples": samples, **options})
                segments = [
                    SimpleNamespace(text=" Apruebo el cambio."),
                    SimpleNamespace(text=" Tiene pruebas. "),
                ]
                return iter(segments), SimpleNamespace(language="es")

        def try_to_load_from_cache(repo: str, filename: str):
            outer.cache_lookups.append((repo, filename))
            return "/home/x/.cache/huggingface/hub/model.bin" if cached else None

        monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=WhisperModel))
        monkeypatch.setitem(
            sys.modules, "huggingface_hub", SimpleNamespace(try_to_load_from_cache=try_to_load_from_cache)
        )


def test_the_default_model_is_base_and_only_three_download_by_name() -> None:
    assert DEFAULT_MODEL == "base" and list(MODELS) == ["tiny", "base", "small"]
    assert all(repo.startswith("Systran/faster-whisper-") for repo, _ in MODELS.values())


def test_a_cached_model_is_loaded_without_network_on_cpu_with_int8(monkeypatch, tmp_path: Path) -> None:
    fake = FakeWhisper(monkeypatch, cached=True)
    wav = write_wav(tmp_path / "nota.wav", seconds=1)
    notes: list[str] = []
    text = FasterWhisperTranscriber("base").transcribe(wav, "es", notes.append)
    assert text == "Apruebo el cambio. Tiene pruebas."
    assert fake.cache_lookups == [("Systran/faster-whisper-base", "model.bin")]
    assert fake.loaded == [("base", {"device": "cpu", "compute_type": "int8", "local_files_only": True})]
    assert len(notes) == 1 and "sin red" in notes[0] and "AVISO" not in notes[0]
    call = fake.transcribed[0]
    assert call["language"] == "es" and call["vad_filter"] is True
    samples = call["samples"]
    assert (
        str(samples.dtype) == "float32"
        and samples.shape == (16000,)
        and abs(float(samples[0]) - 1 / 32768) < 1e-9
    )


def test_a_download_is_announced_before_it_happens(monkeypatch, tmp_path: Path) -> None:
    fake = FakeWhisper(monkeypatch, cached=False)
    wav = write_wav(tmp_path / "nota.wav")
    events: list[str] = []
    fake_loaded = fake.loaded

    class Spy(list):
        def append(self, item) -> None:
            events.append("load")
            super().append(item)

    fake.loaded = Spy(fake_loaded)
    FasterWhisperTranscriber("small").transcribe(wav, None, lambda line: events.append(line))
    assert events[1] == "load" and events[0].startswith("AVISO: el modelo `small` no esta en esta maquina.")
    assert "https://huggingface.co/Systran/faster-whisper-small" in events[0] and "484 MB" in events[0]
    assert "el audio no sale de la maquina" in events[0]
    assert fake.loaded[0] == ("small", {"device": "cpu", "compute_type": "int8", "local_files_only": False})
    assert fake.transcribed[0]["language"] is None


def test_a_local_model_path_never_touches_the_network(monkeypatch, tmp_path: Path) -> None:
    fake = FakeWhisper(monkeypatch, cached=False)
    model_dir = tmp_path / "mi modelo;v1"
    model_dir.mkdir()
    transcriber = FasterWhisperTranscriber("base", model_dir)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    assert "falta `model.bin`" in (transcriber.problem() or "")
    (model_dir / "model.bin").write_bytes(b"x")
    assert transcriber.problem() is None
    assert transcriber.label == "mi-modelo-v1"
    notes: list[str] = []
    transcriber.transcribe(write_wav(tmp_path / "nota.wav"), "es", notes.append)
    assert fake.cache_lookups == [] and fake.loaded[0] == (
        str(model_dir),
        {"device": "cpu", "compute_type": "int8", "local_files_only": True},
    )
    assert "sin red" in notes[0]


def test_a_missing_package_is_a_clear_problem_and_nothing_is_imported(monkeypatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    transcriber = FasterWhisperTranscriber()
    assert transcriber.problem() == INSTALL_HINT and transcriber.label == "base"
    assert "uv run --group voz" in INSTALL_HINT


def test_a_failure_inside_the_library_becomes_one_line_without_a_trace(monkeypatch, tmp_path: Path) -> None:
    fake = FakeWhisper(monkeypatch, cached=True)
    fake.fails = RuntimeError("mkl_malloc: failed to allocate memory")
    with pytest.raises(VozError, match="la transcripcion fallo .RuntimeError: mkl_malloc"):
        FasterWhisperTranscriber().transcribe(write_wav(tmp_path / "nota.wav"), "es", lambda _line: None)


def test_language_codes() -> None:
    assert valid_language("es") == "es" and valid_language("auto") is None and valid_language("yue") == "yue"


@pytest.mark.manual
@pytest.mark.skipif(
    os.environ.get("VECTRA_NOTA_DE_VOZ_MANUAL") != "1",
    reason="transcripcion real: descarga y carga un modelo. Ver README, «La prueba manual con el modelo real»",
)
def test_the_real_model_transcribes_a_local_wav(capsys) -> None:  # pragma: no cover - manual
    """`VECTRA_NOTA_DE_VOZ_WAV`: un WAV de 16 kHz mono. `VECTRA_NOTA_DE_VOZ_ESPERA`: palabras, separadas por comas, que deben salir en el texto."""
    wav = Path(os.environ["VECTRA_NOTA_DE_VOZ_WAV"])
    seconds = wav_seconds(wav)
    transcriber = FasterWhisperTranscriber(os.environ.get("VECTRA_NOTA_DE_VOZ_MODEL", DEFAULT_MODEL))
    assert transcriber.problem() is None, transcriber.problem()
    notes: list[str] = []
    text = transcriber.transcribe(
        wav, valid_language(os.environ.get("VECTRA_NOTA_DE_VOZ_IDIOMA", "es")), notes.append
    )
    with capsys.disabled():
        print(f"\n[{transcriber.label}, {seconds:.0f} s] {notes}\n{text}")
    assert text.strip()
    for word in filter(None, os.environ.get("VECTRA_NOTA_DE_VOZ_ESPERA", "").lower().split(",")):
        assert word.strip() in text.lower(), word
