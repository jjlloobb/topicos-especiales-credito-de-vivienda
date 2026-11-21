"""La lista cerrada de ordenes externas. Este es el **unico** archivo del paquete que importa `subprocess`.

Ordenes que la herramienta lanza, y ninguna mas:

- `arecord` o `pw-record` (el grabador), a un archivo del directorio privado;
- `gh auth status` (lectura), `gh pr view` (lectura), `gh auth switch` y `gh pr review` (la unica escritura en GitHub);
- el editor que la persona tiene en `$VISUAL` o `$EDITOR`, sobre el archivo del texto.

Cada orden se arma como lista de argumentos que empieza por literales; no hay `shell=True` ni una funcion que reciba una orden libre. El numero de PR,
el usuario y el repositorio se validan contra un patron antes de llegar aqui y otra vez aqui. El texto de la nota nunca es un argumento: viaja en un
archivo (`--body-file`). `gh pr review` solo se lanza con `--comment` o `--approve`; `--request-changes`, `gh pr merge` y `gh api` no existen en el codigo.

El ejecutor se inyecta (`Runner`): las pruebas nunca lanzan `gh` ni un grabador.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from vectra_nota_de_voz.errors import VozError

HOST: Final = "github.com"
#: Nombre de usuario de GitHub: letras, cifras y guiones sueltos, sin guion al principio ni al final, 39 como maximo.
GH_USER: Final = re.compile(r"[A-Za-z0-9](?:-?[A-Za-z0-9]){0,38}")
GH_REPO: Final = re.compile(r"[A-Za-z0-9](?:-?[A-Za-z0-9]){0,38}/[A-Za-z0-9_.-]{1,100}")
PR_NUMBER: Final = re.compile(r"[1-9][0-9]{0,6}")
RECORDERS: Final = ("arecord", "pw-record")
SAMPLE_RATE: Final = 16000
GH_TIMEOUT: Final = 60.0
#: Variables que harian que `gh` use otra identidad u otro servidor que la sesion guardada. Se quitan del entorno del hijo; su valor no se lee.
_GH_OVERRIDES: Final = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
    "GH_HOST",
    "GH_REPO",
)
#: Solo cuenta, si esta activa y si la sesion es valida. El token no sale de `gh` (no se pide `--show-token`).
_ACCOUNTS_JQ: Final = '[.hosts["github.com"][]? | {login, active, state}]'


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str
    stderr: str


class Process(Protocol):
    def poll(self) -> int | None: ...

    def stop(self) -> None: ...


class Runner(Protocol):
    def which(self, program: str) -> str | None: ...

    def run(self, args: Sequence[str], env: Mapping[str, str]) -> Completed: ...

    def spawn(self, args: Sequence[str], stderr_path: Path) -> Process: ...

    def interactive(self, args: Sequence[str]) -> int: ...


class _Child:
    def __init__(self, popen: subprocess.Popen[bytes]) -> None:
        self._popen = popen

    def poll(self) -> int | None:
        return self._popen.poll()

    def stop(self) -> None:
        """SIGINT (el grabador cierra bien el WAV), y si no termina, SIGKILL."""
        if self._popen.poll() is None:
            self._popen.send_signal(signal.SIGINT)
            try:
                self._popen.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._popen.kill()
                self._popen.wait()


class SubprocessRunner:
    """El ejecutor real. Sin interprete de ordenes en ningun caso."""

    def which(self, program: str) -> str | None:
        return shutil.which(program)

    def run(self, args: Sequence[str], env: Mapping[str, str]) -> Completed:
        try:
            done = subprocess.run(  # noqa: S603
                list(args),
                capture_output=True,
                text=True,
                check=False,
                timeout=GH_TIMEOUT,
                env=dict(env),
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return Completed(127, "", type(error).__name__)
        return Completed(done.returncode, done.stdout, done.stderr)

    def spawn(self, args: Sequence[str], stderr_path: Path) -> Process:
        """Un proceso de fondo (el grabador). `umask=0o077`: lo que cree nace 0600 aunque el programa pida 0644."""
        with open(os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as stderr:
            popen = subprocess.Popen(  # noqa: S603
                list(args), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=stderr, umask=0o077
            )
        return _Child(popen)

    def interactive(self, args: Sequence[str]) -> int:
        """Un proceso con la terminal de la persona (su editor)."""
        try:
            return subprocess.run(list(args), check=False).returncode  # noqa: S603
        except OSError:
            return 127


def shown(value: object) -> str:
    """Un argumento rechazado, recortado, para el mensaje de error."""
    return repr(str(value)[:40])


def valid_pr(number: object) -> int:
    if (
        isinstance(number, bool)
        or not isinstance(number, int | str)
        or PR_NUMBER.fullmatch(str(number)) is None
    ):
        raise VozError(f"argumento rechazado: el numero de PR {shown(number)} no es un entero positivo")
    return int(number)


def valid_user(user: object) -> str:
    if not isinstance(user, str) or len(user) > 39 or GH_USER.fullmatch(user) is None:
        raise VozError(f"argumento rechazado: {shown(user)} no es un nombre de usuario de GitHub")
    return user


def valid_repo(repo: object) -> str:
    if (
        not isinstance(repo, str)
        or GH_REPO.fullmatch(repo) is None
        or repo.endswith("/.")
        or repo.endswith("/..")
    ):
        raise VozError(f"argumento rechazado: {shown(repo)} no es un repositorio `dueno/nombre`")
    return repo


def recorder_command(program: str, wav: Path, max_seconds: int) -> list[str]:
    """La orden del grabador: WAV de 16 kHz, mono, 16 bits, que es lo que Whisper lee sin convertir (no hace falta `ffmpeg`)."""
    if not wav.is_absolute():
        raise VozError("el archivo de audio debe ser una ruta absoluta")
    if program == "arecord":
        seconds = str(int(max_seconds))
        return [
            "arecord",
            "-q",
            "-t",
            "wav",
            "-f",
            "S16_LE",
            "-r",
            str(SAMPLE_RATE),
            "-c",
            "1",
            "-d",
            seconds,
            str(wav),
        ]
    if program == "pw-record":
        return ["pw-record", "--rate", str(SAMPLE_RATE), "--channels", "1", "--format", "s16", str(wav)]
    raise VozError(
        f"argumento rechazado: el grabador {shown(program)} no esta en la lista ({', '.join(RECORDERS)})"
    )


@dataclass(frozen=True)
class Account:
    login: str
    active: bool


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str
    title: str
    url: str
    author: str


class Gh:
    """Las cuatro ordenes de `gh`. `commands` guarda cada orden lanzada (las pruebas la leen)."""

    def __init__(self, runner: Runner, environ: Mapping[str, str], repo: str | None = None) -> None:
        self._runner = runner
        self._env = {key: value for key, value in environ.items() if key not in _GH_OVERRIDES}
        self._env.update({"GH_PROMPT_DISABLED": "1", "NO_COLOR": "1"})
        self._repo = None if repo is None else valid_repo(repo)
        self.commands: list[tuple[str, ...]] = []

    def _run(self, args: list[str]) -> Completed:
        self.commands.append(tuple(args))
        return self._runner.run(args, self._env)

    def _repo_tail(self) -> list[str]:
        return [] if self._repo is None else ["--repo", self._repo]

    def accounts(self) -> list[Account]:
        """Las cuentas con sesion valida en `gh` para github.com. Lectura."""
        done = self._run(
            ["gh", "auth", "status", "--hostname", HOST, "--json", "hosts", "--jq", _ACCOUNTS_JQ]
        )
        if done.returncode != 0:
            raise VozError(
                "`gh auth status` fallo: no se pudo leer con que cuenta se publicaria. Hace falta `gh` 2.81 o posterior "
                f"con sesion iniciada (`gh auth login --hostname {HOST}`)."
            )
        try:
            rows = json.loads(done.stdout or "[]")
            return [
                Account(valid_user(row["login"]), row["active"] is True)
                for row in rows
                if row.get("state") == "success"
            ]
        except (ValueError, KeyError, TypeError, AttributeError, VozError):
            raise VozError("`gh auth status` respondio algo que no se entiende: no se publica nada") from None

    def pr(self, number: int) -> PullRequest:
        """`gh pr view`: lectura."""
        number = valid_pr(number)
        done = self._run(
            ["gh", "pr", "view", str(number), "--json", "number,state,title,url,author"] + self._repo_tail()
        )
        if done.returncode != 0:
            detail = done.stderr.strip().splitlines()[-1][:200] if done.stderr.strip() else "sin detalle"
            raise VozError(
                f"no se pudo leer el PR #{number} con `gh pr view` ({detail}). Compruebe el numero y el repositorio."
            )
        try:
            data = json.loads(done.stdout)
            return PullRequest(
                int(data["number"]),
                str(data["state"]),
                str(data["title"]),
                str(data["url"]),
                str(data["author"]["login"]),
            )
        except (ValueError, KeyError, TypeError):
            raise VozError(f"`gh pr view {number}` respondio algo que no se entiende") from None

    def switch(self, user: str) -> bool:
        """`gh auth switch`: cambia la cuenta activa de `gh` en esta maquina. Devuelve si la orden termino bien."""
        user = valid_user(user)
        return self._run(["gh", "auth", "switch", "--hostname", HOST, "--user", user]).returncode == 0

    def review(self, number: int, body_file: Path, approve: bool) -> None:
        """`gh pr review`: la unica escritura en GitHub. El cuerpo va por archivo; el modo es `--comment` o `--approve`, nada mas."""
        number = valid_pr(number)
        if not body_file.is_absolute() or not body_file.is_file():
            raise VozError("el cuerpo de la nota debe ser un archivo existente con ruta absoluta")
        if approve:
            args = ["gh", "pr", "review", str(number), "--approve", "--body-file", str(body_file)]
        else:
            args = ["gh", "pr", "review", str(number), "--comment", "--body-file", str(body_file)]
        done = self._run(args + self._repo_tail())
        if done.returncode != 0:
            detail = done.stderr.strip().splitlines()[-1][:200] if done.stderr.strip() else "sin detalle"
            raise VozError(f"`gh pr review` fallo y la nota NO se publico ({detail})")
