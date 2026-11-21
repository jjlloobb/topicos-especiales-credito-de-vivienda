"""Dobles de las pruebas: un `gh`, un grabador y un editor falsos (un solo ejecutor que guarda cada orden), una terminal falsa y un transcriptor falso.

Ninguno toca el microfono, la red ni GitHub. El ejecutor falso rechaza cualquier orden que no conozca: una orden nueva hace fallar la prueba.
"""

from __future__ import annotations

import json
import wave
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from vectra_nota_de_voz.commands import Completed


def write_wav(path: Path, seconds: float = 1.0, rate: int = 16000, channels: int = 1, width: int = 2) -> Path:
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(width)
        writer.setframerate(rate)
        writer.writeframes(b"\x01\x00"[:width] * int(rate * seconds) * channels)
    return path


class FakeProcess:
    def __init__(self, exit_code: int | None = None) -> None:
        self.exit_code = exit_code
        self.stopped = 0

    def poll(self) -> int | None:
        return self.exit_code

    def stop(self) -> None:
        self.stopped += 1
        self.exit_code = 0 if self.exit_code is None else self.exit_code


class FakeRunner:
    def __init__(self) -> None:
        self.programs = {"gh", "arecord", "pw-record", "nano"}
        self.accounts: list[dict] = [
            {"login": "jjlloobb", "active": True, "state": "success"},
            {"login": "joseluisjedi", "active": False, "state": "success"},
        ]
        self.pr: dict | None = {
            "number": 12,
            "state": "OPEN",
            "title": "feat: algo",
            "url": "https://github.com/jjlloobb/repo/pull/12",
            "author": {"login": "jjlloobb"},
        }
        self.calls: list[tuple[str, ...]] = []
        self.envs: list[dict[str, str]] = []
        self.reviews: list[
            dict
        ] = []  # cada `gh pr review`: orden, cuerpo leido del archivo y cuenta activa en ese momento
        self.review_returncode = 0
        self.review_raises: BaseException | None = None
        self.switch_works = True
        self.restore_works = True
        self.switches = 0
        self.records_audio = True
        self.recorder_exit: int | None = None
        self.processes: list[FakeProcess] = []
        self.edit: Callable[[str], str] = lambda text: text
        self.editor_returncode = 0
        self.seen_files: list[Path] = []

    def active(self) -> str | None:
        return next((a["login"] for a in self.accounts if a["active"]), None)

    def which(self, program: str) -> str | None:
        return f"/usr/bin/{program}" if program in self.programs else None

    def run(self, args: Sequence[str], env: Mapping[str, str]) -> Completed:
        command = tuple(args)
        self.calls.append(command)
        self.envs.append(dict(env))
        if command[:3] == ("gh", "auth", "status"):
            return Completed(0, json.dumps(self.accounts), "")
        if command[:3] == ("gh", "auth", "switch"):
            self.switches += 1
            works = self.switch_works if self.switches == 1 else self.restore_works
            user = command[command.index("--user") + 1]
            if not works or user not in [a["login"] for a in self.accounts]:
                return Completed(1, "", "not logged in")
            for account in self.accounts:
                account["active"] = account["login"] == user
            return Completed(0, "", "")
        if command[:3] == ("gh", "pr", "view"):
            if self.pr is None or str(self.pr["number"]) != command[3]:
                return Completed(1, "", "GraphQL: Could not resolve to a PullRequest with the number of 999.")
            return Completed(0, json.dumps(self.pr), "")
        if command[:3] == ("gh", "pr", "review"):
            body_file = Path(command[command.index("--body-file") + 1])
            self.seen_files.append(body_file)
            self.reviews.append(
                {
                    "command": command,
                    "body": body_file.read_text(encoding="utf-8"),
                    "as": self.active(),
                    "mode": oct(body_file.stat().st_mode & 0o777),
                }
            )
            if self.review_raises is not None:
                raise self.review_raises
            return Completed(
                self.review_returncode, "", "" if self.review_returncode == 0 else "HTTP 422: nope"
            )
        raise AssertionError(f"orden fuera de la lista cerrada: {command}")

    def spawn(self, args: Sequence[str], stderr_path: Path) -> FakeProcess:
        command = tuple(args)
        self.calls.append(command)
        wav = Path(command[-1])
        self.seen_files.append(wav)
        if self.records_audio:
            write_wav(wav)
        else:
            stderr_path.write_text("arecord: main:831: audio open error: No such file or directory\n")
        process = FakeProcess(self.recorder_exit)
        self.processes.append(process)
        return process

    def interactive(self, args: Sequence[str]) -> int:
        command = tuple(args)
        self.calls.append(command)
        draft = Path(command[-1])
        self.seen_files.append(draft)
        draft.write_text(self.edit(draft.read_text(encoding="utf-8")), encoding="utf-8")
        return self.editor_returncode

    def gh_writes(self) -> list[tuple[str, ...]]:
        return [c for c in self.calls if c[:3] in (("gh", "pr", "review"), ("gh", "auth", "switch"))]


class FakeConsole:
    def __init__(self, *answers: str, tty: bool = True) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.lines: list[str] = []
        self.tty = tty
        self.enter_after = 2
        self.waits = 0
        self.ask_raises: BaseException | None = None
        self.wait_raises: BaseException | None = None

    @property
    def output(self) -> str:
        return "\n".join(self.lines)

    def say(self, text: str) -> None:
        self.lines.append(text)

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.ask_raises is not None:
            raise self.ask_raises
        return self.answers.pop(0) if self.answers else ""

    def wait_enter(self, seconds: float) -> bool:
        self.waits += 1
        if self.wait_raises is not None:
            raise self.wait_raises
        return self.waits >= self.enter_after

    def interactive(self) -> bool:
        return self.tty


class FakeTranscriber:
    def __init__(self, text: str = "Apruebo porque las pruebas cubren el caso de borde.") -> None:
        self.text = text
        self.label = "base"
        self.problem_message: str | None = None
        self.raises: BaseException | None = None
        self.heard: list[tuple[Path, str | None, bool]] = []
        self.made_with: tuple[str, Path | None] | None = None

    def make(self, model: str, model_path: Path | None) -> FakeTranscriber:
        self.made_with = (model, model_path)
        self.label = model
        return self

    def problem(self) -> str | None:
        return self.problem_message

    def transcribe(self, wav: Path, language: str | None, notify: Callable[[str], None]) -> str:
        self.heard.append((wav, language, wav.is_file()))
        if self.raises is not None:
            raise self.raises
        return self.text
