"""Si falta algo, la orden lo dice, sale con codigo 2 y no escribe nada: ni en GitHub ni en el directorio privado."""

from __future__ import annotations

import os

import pytest
from voz_doubles import FakeConsole, write_wav

from vectra_nota_de_voz.transcriber import INSTALL_HINT


def refused(launch, runner, leftovers, console, *argv, env=None) -> str:
    assert launch(console, *argv, env=env) == 2
    assert runner.gh_writes() == [] and runner.reviews == []
    assert not [c for c in runner.calls if c[0] in ("arecord", "pw-record", "nano")]
    assert leftovers() == []
    assert console.prompts == []
    assert console.output.startswith("error: ") and "Traceback" not in console.output
    return console.output


def test_a_pr_that_does_not_exist(launch, runner, leftovers) -> None:
    out = refused(launch, runner, leftovers, FakeConsole("s"), "999")
    assert "no se pudo leer el PR #999" in out and "Could not resolve" in out


@pytest.mark.parametrize("state", ["CLOSED", "MERGED"])
def test_a_pr_that_is_not_open(state, launch, runner, leftovers) -> None:
    runner.pr["state"] = state
    assert f"el PR #12 no esta abierto (estado: {state})" in refused(
        launch, runner, leftovers, FakeConsole("s"), "12"
    )


def test_no_recorder(launch, runner, leftovers) -> None:
    runner.programs -= {"arecord", "pw-record"}
    out = refused(launch, runner, leftovers, FakeConsole("s"), "12")
    assert "no hay grabador" in out and "`arecord`" in out and "`pw-record`" in out and "--audio" in out


def test_the_requested_recorder_is_missing(launch, runner, leftovers) -> None:
    runner.programs.discard("pw-record")
    assert "no hay grabador" in refused(
        launch, runner, leftovers, FakeConsole("s"), "12", "--recorder", "pw-record"
    )


def test_no_transcriber(launch, runner, transcriber, leftovers) -> None:
    transcriber.problem_message = INSTALL_HINT
    out = refused(launch, runner, leftovers, FakeConsole("s"), "12")
    assert "falta el transcriptor" in out and "uv run --group voz vectra-nota-de-voz" in out


def test_as_a_user_without_a_gh_session_explains_how_to_log_in_and_does_nothing(
    launch, runner, leftovers
) -> None:
    runner.accounts = runner.accounts[:1]
    out = refused(launch, runner, leftovers, FakeConsole("s"), "12", "--as", "joseluisjedi")
    assert (
        "la cuenta joseluisjedi no tiene sesion en `gh`" in out
        and "gh auth login --hostname github.com" in out
    )
    assert "No se hizo nada." in out
    assert [c[:3] for c in runner.calls] == [("gh", "auth", "status")]


def test_as_a_user_whose_session_is_broken_counts_as_no_session(launch, runner, leftovers) -> None:
    runner.accounts[1]["state"] = "error"
    assert "no tiene sesion" in refused(
        launch, runner, leftovers, FakeConsole("s"), "12", "--as", "joseluisjedi"
    )


def test_no_gh_session_at_all(launch, runner, leftovers) -> None:
    runner.accounts = []
    assert "gh auth login" in refused(launch, runner, leftovers, FakeConsole("s"), "12")


def test_no_gh_binary(launch, runner, leftovers) -> None:
    runner.programs.discard("gh")
    assert "no se encontro `gh`" in refused(launch, runner, leftovers, FakeConsole("s"), "12")
    assert runner.calls == []


def test_approving_your_own_pr_is_refused_before_recording(launch, runner, leftovers) -> None:
    out = refused(launch, runner, leftovers, FakeConsole("aprobar", "s"), "12", "--approve")
    assert "GitHub no deja aprobar un PR propio" in out and "--as" in out


def test_recording_needs_a_terminal(launch, runner, leftovers) -> None:
    assert "terminal interactiva" in refused(launch, runner, leftovers, FakeConsole("s", tty=False), "12")


def test_an_audio_file_that_is_missing_or_not_the_expected_wav(launch, runner, leftovers, tmp_path) -> None:
    assert "no existe el archivo" in refused(
        launch, runner, leftovers, FakeConsole("s"), "12", "--audio", str(tmp_path / "no.wav")
    )
    stereo = write_wav(tmp_path / "estereo.wav", rate=44100, channels=2)
    out = refused(launch, runner, leftovers, FakeConsole("s"), "12", "--audio", str(stereo))
    assert (
        "no es WAV PCM de 16 kHz, mono y 16 bits (es 44100 Hz, 2 canal(es), 16 bits)" in out
        and "arecord" in out
    )
    junk = tmp_path / "basura.wav"
    junk.write_bytes(b"ID3\x00no soy un wav")
    assert "no es un archivo WAV legible" in refused(
        launch, runner, leftovers, FakeConsole("s"), "12", "--audio", str(junk)
    )
    empty = write_wav(tmp_path / "vacio.wav", seconds=0.1)
    assert "menos de medio segundo" in refused(
        launch, runner, leftovers, FakeConsole("s"), "12", "--audio", str(empty)
    )
    long = write_wav(tmp_path / "largo.wav", seconds=601)
    assert "el maximo es 600 s" in refused(
        launch, runner, leftovers, FakeConsole("s"), "12", "--audio", str(long)
    )


def test_no_private_runtime_directory(launch, runner, transcriber, tmp_path, runtime) -> None:
    wav = write_wav(tmp_path / "mia.wav")
    for env in (
        {"XDG_RUNTIME_DIR": ""},
        {"XDG_RUNTIME_DIR": "relativo"},
        {"XDG_RUNTIME_DIR": str(tmp_path / "noexiste")},
    ):
        console = FakeConsole("s")
        assert launch(console, "12", "--audio", str(wav), env=env) == 2
        assert "XDG_RUNTIME_DIR" in console.output
    os.chmod(runtime, 0o755)
    console = FakeConsole("s")
    assert launch(console, "12", "--audio", str(wav)) == 2
    assert "no es un directorio privado suyo" in console.output
    assert transcriber.heard == [] and runner.gh_writes() == []


def test_gh_answers_that_cannot_be_understood(launch, runner, leftovers) -> None:
    runner.accounts = [{"login": "no valido!", "active": True, "state": "success"}]
    assert "no se entiende" in refused(launch, runner, leftovers, FakeConsole("s"), "12")
    runner.accounts = [{"login": "jjlloobb", "active": True, "state": "success"}]
    runner.pr = {"number": 12, "state": "OPEN"}
    assert "no se entiende" in refused(launch, runner, leftovers, FakeConsole("s"), "12")


def test_the_pr_title_cannot_inject_terminal_escapes(launch, runner) -> None:
    runner.pr["title"] = "feat\x1b[2J\x1b]0;pwn\x07\nsegunda linea ‮gnp"
    console = FakeConsole("n")
    launch(console, "12")
    assert "\x1b" not in console.output and "\x07" not in console.output and "‮" not in console.output
    assert "feat[2J]0;pwn segunda linea gnp" in console.output
