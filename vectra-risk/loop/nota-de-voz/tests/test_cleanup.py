"""El audio y los temporales se borran siempre: en exito, en error y en interrupcion, sea cual sea el paso en que ocurra."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from voz_doubles import FakeConsole

from vectra_nota_de_voz.audio import private_dir, write_private
from vectra_nota_de_voz.errors import VozError


def assert_everything_is_gone(runner, leftovers) -> None:
    assert runner.seen_files, "la prueba no llego a crear ningun temporal"
    for path in runner.seen_files:
        assert not path.exists(), path
        assert not path.parent.exists(), path.parent
    assert leftovers() == []


def test_success_deletes_the_audio_the_draft_and_the_body(launch, runner, leftovers) -> None:
    assert launch(FakeConsole("s"), "12", env={"EDITOR": "nano"}) == 0
    assert {p.name for p in runner.seen_files} == {"nota.wav", "nota.md", "cuerpo.md"}
    assert_everything_is_gone(runner, leftovers)


def test_the_audio_is_deleted_right_after_transcribing_before_any_question(
    launch, runner, transcriber
) -> None:
    console = FakeConsole("s")
    wav_at_question: list[bool] = []
    original = console.ask
    console.ask = lambda prompt: (wav_at_question.append(runner.seen_files[0].exists()), original(prompt))[1]  # type: ignore[method-assign]
    assert launch(console, "12") == 0
    assert transcriber.heard[0][2] is True and wav_at_question == [False]


def test_the_private_files_are_0700_and_0600_while_they_exist(launch, runner, transcriber) -> None:
    modes: dict[str, str] = {}

    def spy(text: str) -> str:
        for path in [*runner.seen_files, runner.seen_files[0].parent]:
            if path.exists():
                modes[path.name[:19]] = oct(stat.S_IMODE(path.stat().st_mode))
        return text

    runner.edit = spy
    transcriber_transcribe = transcriber.transcribe
    transcriber.transcribe = lambda wav, language, notify: (
        spy(""),
        transcriber_transcribe(wav, language, notify),
    )[1]  # type: ignore[method-assign]
    assert launch(FakeConsole("s"), "12", env={"EDITOR": "nano"}) == 0
    assert modes == {"nota.wav": "0o600", "nota.md": "0o600", "vectra-nota-de-voz-": "0o700"}
    assert runner.reviews[0]["mode"] == "0o600"


def test_a_transcription_error_deletes_the_audio(launch, runner, transcriber, leftovers) -> None:
    transcriber.raises = VozError("la transcripcion fallo (RuntimeError: sin memoria)")
    console = FakeConsole("s")
    assert launch(console, "12") == 2
    assert "la transcripcion fallo" in console.output and runner.gh_writes() == []
    assert transcriber.heard[0][2] is True
    assert_everything_is_gone(runner, leftovers)


def test_an_unexpected_exception_still_deletes_the_audio(launch, runner, transcriber, leftovers) -> None:
    transcriber.raises = MemoryError()
    with pytest.raises(MemoryError):
        launch(FakeConsole("s"), "12")
    assert_everything_is_gone(runner, leftovers)


def test_an_empty_transcription_is_an_error_and_deletes_the_audio(
    launch, runner, transcriber, leftovers
) -> None:
    transcriber.text = " \n\x00 "
    console = FakeConsole("s")
    assert launch(console, "12") == 2
    assert "salio vacia" in console.output and console.prompts == []
    assert_everything_is_gone(runner, leftovers)


def test_a_recorder_that_records_nothing_is_an_error_with_its_message(
    launch, runner, transcriber, leftovers
) -> None:
    runner.records_audio = False
    runner.recorder_exit = 1
    console = FakeConsole("s")
    assert launch(console, "12") == 2
    assert "`arecord` no grabo nada" in console.output and "audio open error" in console.output
    assert transcriber.heard == [] and runner.gh_writes() == [] and leftovers() == []


@pytest.mark.parametrize("stage", ["recording", "transcribing", "question", "publishing"])
def test_ctrl_c_at_any_stage_deletes_everything_and_exits_130(
    stage, launch, runner, transcriber, leftovers
) -> None:
    console = FakeConsole("s")
    if stage == "recording":
        console.wait_raises = KeyboardInterrupt()
    elif stage == "transcribing":
        transcriber.raises = KeyboardInterrupt()
    elif stage == "question":
        console.ask_raises = KeyboardInterrupt()
    else:
        runner.review_raises = KeyboardInterrupt()
    assert launch(console, "12") == 130
    assert "Interrumpido" in console.output
    assert_everything_is_gone(runner, leftovers)
    assert runner.processes[0].stopped == 1, "el grabador se para siempre"
    if stage != "publishing":
        assert runner.gh_writes() == []


def test_private_dir_removes_the_directory_on_any_exit(runtime: Path) -> None:
    env = {"XDG_RUNTIME_DIR": str(runtime)}
    for error in (None, VozError("x"), KeyboardInterrupt(), SystemExit(3)):
        try:
            with private_dir(env) as directory:
                write_private(directory / "nota.wav", "audio")
                (directory / "sub").mkdir()
                assert stat.S_IMODE(directory.stat().st_mode) == 0o700
                assert stat.S_IMODE((directory / "nota.wav").stat().st_mode) == 0o600
                if error is not None:
                    raise error
        except BaseException as raised:
            assert raised is error
        assert list(runtime.iterdir()) == []
