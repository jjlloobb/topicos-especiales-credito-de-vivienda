"""El flujo completo: publica exactamente una vez y con el cuerpo esperado, y solo con un «s» explicito."""

from __future__ import annotations

from pathlib import Path

import pytest
from voz_doubles import FakeConsole, write_wav

from vectra_nota_de_voz import note

HEADER = (
    "**Nota de voz del revisor humano**, transcrita en local con Whisper (`base`) y revisada y confirmada por la persona "
    "antes de publicarla. El audio no se conserva."
)
TEXT = "Apruebo porque las pruebas cubren el caso de borde."


def test_the_full_flow_publishes_exactly_once_with_the_expected_body(
    launch, runner, transcriber, leftovers, runtime
) -> None:
    console = FakeConsole("s")
    assert launch(console, "12") == 0
    assert len(runner.reviews) == 1
    review = runner.reviews[0]
    assert review["body"] == f"{HEADER}\n\n{TEXT}\n"
    assert review["as"] == "jjlloobb" and review["mode"] == "0o600"
    command = review["command"]
    assert (
        command[:5] == ("gh", "pr", "review", "12", "--comment")
        and command[5] == "--body-file"
        and len(command) == 7
    )
    assert Path(command[6]).parent.parent == runtime
    assert "--approve" not in command
    # El orden: lecturas, grabacion, y la escritura al final.
    assert [c[:3] for c in runner.calls] == [
        ("gh", "auth", "status"),
        ("gh", "pr", "view"),
        ("arecord", "-q", "-t"),
        ("gh", "pr", "review"),
    ]
    assert console.prompts == [
        "¿Publicar esta nota en el PR #12 como jjlloobb? (como comentario, sin aprobar) [s/N] "
    ]
    assert "Se publicaria como: jjlloobb" in console.output and "Audio borrado." in console.output
    assert transcriber.heard[0][1:] == ("es", True)
    assert leftovers() == []


def test_the_recorder_writes_a_16khz_mono_wav_in_the_private_directory_and_is_stopped(
    launch, runner, runtime
) -> None:
    assert launch(FakeConsole("s"), "12", "--max-seconds", "30") == 0
    command = next(c for c in runner.calls if c[0] == "arecord")
    assert command[1:-1] == ("-q", "-t", "wav", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", "30")
    wav = Path(command[-1])
    assert (
        wav.name == "nota.wav"
        and wav.parent.name.startswith("vectra-nota-de-voz-")
        and wav.parent.parent == runtime
    )
    assert runner.processes[0].stopped == 1


def test_recording_stops_at_the_maximum_without_enter(launch, runner) -> None:
    console = FakeConsole("s")
    console.enter_after = 10**9
    assert launch(console, "12", "--max-seconds", "5") == 0
    assert console.waits == 20 and runner.processes[0].stopped == 1  # 5 s en pasos de 0,25 s


def test_pw_record_is_used_when_asked_or_when_arecord_is_missing(launch, runner) -> None:
    runner.programs.discard("arecord")
    assert launch(FakeConsole("s"), "12") == 0
    command = next(c for c in runner.calls if c[0] == "pw-record")
    assert command[1:-1] == ("--rate", "16000", "--channels", "1", "--format", "s16")


@pytest.mark.parametrize("answer", ["", "n", "N", "no", "y", "yes", "ss", "s!", "aprobar", "claro", "S i"])
def test_without_an_explicit_yes_nothing_is_written_to_github(answer, launch, runner, leftovers) -> None:
    console = FakeConsole(answer)
    assert launch(console, "12") == 1
    assert runner.gh_writes() == [] and runner.reviews == []
    assert "No se publico nada." in console.output
    assert leftovers() == []


@pytest.mark.parametrize("answer", ["s", "S", " si ", "sí", "SÍ"])
def test_the_explicit_yes_is_s_or_si(answer, launch, runner) -> None:
    assert launch(FakeConsole(answer), "12") == 0
    assert len(runner.reviews) == 1


def test_no_input_at_all_does_not_publish(launch, runner, tmp_path) -> None:
    """Sin terminal (`ask` devuelve vacio, como con fin de archivo) la respuesta por omision es no."""
    wav = write_wav(tmp_path / "mia.wav")
    assert launch(FakeConsole(tty=False), "12", "--audio", str(wav)) == 1
    assert runner.gh_writes() == []


def test_dry_run_never_publishes_and_never_asks(launch, runner, leftovers) -> None:
    console = FakeConsole("s", "s", "aprobar")
    assert launch(console, "12", "--dry-run", "--approve", "--as", "joseluisjedi") == 0
    assert runner.gh_writes() == [] and console.prompts == []
    assert HEADER in console.output and TEXT in console.output and "--dry-run" in console.output
    assert leftovers() == []


def test_approve_is_never_the_default(launch, runner) -> None:
    assert launch(FakeConsole("s", "aprobar"), "12", "--as", "joseluisjedi") == 0
    assert "--approve" not in runner.reviews[0]["command"] and "--comment" in runner.reviews[0]["command"]


def test_approve_needs_its_own_confirmation_and_then_the_final_one(launch, runner) -> None:
    console = FakeConsole("aprobar", "s")
    assert launch(console, "12", "--approve", "--as", "joseluisjedi") == 0
    assert len(console.prompts) == 2 and "APROBAR el PR #12 como joseluisjedi" in console.prompts[0]
    assert (
        console.prompts[1] == "¿Publicar esta nota en el PR #12 como joseluisjedi? (APROBANDO el PR) [s/N] "
    )
    command = runner.reviews[0]["command"]
    assert command[:5] == ("gh", "pr", "review", "12", "--approve") and "--comment" not in command
    assert len(runner.reviews) == 1 and runner.reviews[0]["as"] == "joseluisjedi"


@pytest.mark.parametrize("word", ["s", "si", "", "approve", "aprobar no"])
def test_approve_declined_publishes_only_a_comment(word, launch, runner) -> None:
    """Un «s» no aprueba: hace falta la palabra. Sin ella, la pregunta final dice que es solo un comentario."""
    console = FakeConsole(word, "s")
    assert launch(console, "12", "--approve", "--as", "joseluisjedi") == 0
    assert "(como comentario, sin aprobar)" in console.prompts[1]
    assert "--approve" not in runner.reviews[0]["command"]


def test_approve_confirmed_but_final_question_declined_writes_nothing(launch, runner) -> None:
    assert launch(FakeConsole("aprobar", "n"), "12", "--approve", "--as", "joseluisjedi") == 1
    assert runner.gh_writes() == []


def test_only_comment_or_approve_ever_reach_gh_pr_review(launch, runner) -> None:
    launch(FakeConsole("aprobar", "s"), "12", "--approve", "--as", "joseluisjedi")
    launch(FakeConsole("s"), "12")
    for review in runner.reviews:
        flags = {arg for arg in review["command"] if arg.startswith("-")}
        assert flags in ({"--comment", "--body-file"}, {"--approve", "--body-file"})


def test_the_editor_lets_the_person_correct_the_text(launch, runner, runtime) -> None:
    runner.edit = lambda text: text.replace("borde", "borde y el rollback esta documentado") + "\n\n"
    console = FakeConsole("s")
    assert launch(console, "12", env={"EDITOR": "nano -w"}) == 0
    editor = next(c for c in runner.calls if c[0] == "nano")
    assert editor[:2] == ("nano", "-w") and Path(editor[2]).parent.parent == runtime
    assert (
        runner.reviews[0]["body"]
        == f"{HEADER}\n\nApruebo porque las pruebas cubren el caso de borde y el rollback esta documentado.\n"
    )


def test_visual_wins_over_editor_and_a_missing_editor_falls_back_to_inline(launch, runner) -> None:
    console = FakeConsole("s")
    assert launch(console, "12", env={"VISUAL": "noexiste", "EDITOR": "nano"}) == 0
    assert not [c for c in runner.calls if c[0] in ("nano", "noexiste")]
    assert "No hay `$EDITOR` utilizable" in console.output


@pytest.mark.parametrize("editor", ["nano 'sin cerrar", ""])
def test_an_unusable_editor_value_falls_back_to_inline(editor, launch, runner) -> None:
    assert launch(FakeConsole("s"), "12", env={"EDITOR": editor}) == 0
    assert len(runner.reviews) == 1


def test_an_editor_that_fails_or_leaves_the_note_empty_cancels(launch, runner, leftovers) -> None:
    runner.editor_returncode = 1
    assert launch(FakeConsole("s"), "12", env={"EDITOR": "nano"}) == 1
    runner.editor_returncode = 0
    runner.edit = lambda text: "  \n"
    console = FakeConsole("s")
    assert launch(console, "12", env={"EDITOR": "nano"}) == 1
    assert "La nota quedo vacia." in console.output
    assert runner.gh_writes() == [] and leftovers() == []


def test_the_transcription_is_truncated_to_the_limit_with_a_warning(launch, runner, transcriber) -> None:
    transcriber.text = "a" * (note.MAX_CHARS + 500)
    console = FakeConsole("s")
    assert launch(console, "12") == 0
    assert "se recorto a ese limite" in console.output and str(note.MAX_CHARS) in console.output
    assert runner.reviews[0]["body"] == f"{HEADER}\n\n{'a' * note.MAX_CHARS}\n"


def test_text_pasted_in_the_editor_is_truncated_too(launch, runner) -> None:
    runner.edit = lambda text: "b" * (note.MAX_CHARS * 3)
    console = FakeConsole("s")
    assert launch(console, "12", env={"EDITOR": "nano"}) == 0
    assert "se recorto" in console.output
    assert runner.reviews[0]["body"] == f"{HEADER}\n\n{'b' * note.MAX_CHARS}\n"


def test_a_short_text_is_not_reported_as_truncated(launch) -> None:
    console = FakeConsole("s")
    assert launch(console, "12") == 0
    assert "recorto" not in console.output


def test_an_existing_recording_is_used_and_not_deleted_and_the_header_does_not_claim_otherwise(
    launch, runner, transcriber, tmp_path
) -> None:
    wav = write_wav(tmp_path / "mia.wav", seconds=2)
    console = FakeConsole("s")
    assert launch(console, "12", "--audio", str(wav), "--model", "small", "--language", "auto") == 0
    assert not [c for c in runner.calls if c[0] in ("arecord", "pw-record")]
    assert transcriber.heard == [(wav, None, True)] and transcriber.made_with == ("small", None)
    assert wav.is_file(), "la grabacion de la persona no se borra"
    body = runner.reviews[0]["body"]
    assert "Whisper (`small`)" in body and "El audio no se conserva" not in body
    assert "no se borra" in console.output


def test_the_body_is_header_text_and_nothing_else() -> None:
    body = note.body("hola", "base", audio_kept_by_user=False)
    assert body == f"{HEADER}\n\nhola\n"
    assert "Claude" not in body and "Co-Authored" not in body and "Generated" not in body


def test_repo_is_passed_to_the_read_and_to_the_write(launch, runner) -> None:
    assert launch(FakeConsole("s"), "12", "--repo", "jjlloobb/topicos.especiales") == 0
    for command in runner.calls:
        if command[:2] == ("gh", "pr"):
            assert command[-2:] == ("--repo", "jjlloobb/topicos.especiales")


def test_a_failed_review_reports_it_and_cleans_up(launch, runner, leftovers) -> None:
    runner.review_returncode = 1
    console = FakeConsole("s")
    assert launch(console, "12") == 2
    assert "NO se publico" in console.output and len(runner.reviews) == 1
    assert leftovers() == []


def test_gh_runs_without_token_overrides_and_without_prompts(launch, runner) -> None:
    env = {
        "GH_TOKEN": "ghp_x",
        "GITHUB_TOKEN": "ghp_y",
        "GH_HOST": "evil.example",
        "GH_REPO": "a/b",
        "DBUS_SESSION_BUS_ADDRESS": "unix:x",
    }
    console = FakeConsole("s")
    assert launch(console, "12", env=env) == 0
    for child in runner.envs:
        assert not {"GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_REPO"} & set(child)
        assert child["GH_PROMPT_DISABLED"] == "1" and child["DBUS_SESSION_BUS_ADDRESS"] == "unix:x"
    assert "ghp_" not in console.output
    assert not any(
        arg in ("token", "--show-token", "-t")
        for command in runner.calls
        if command[0] == "gh"
        for arg in command
    )
