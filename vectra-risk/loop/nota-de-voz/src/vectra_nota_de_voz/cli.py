"""`vectra-nota-de-voz <PR>`: comprobar, grabar, transcribir en local, dejar corregir, preguntar y, solo con un «s» explicito, publicar.

El orden importa: antes de la pregunta final no hay ninguna escritura en GitHub (solo `gh auth status` y `gh pr view`), y la cuenta de `gh` solo se
cambia (`--as`) durante la publicacion, despues de la confirmacion, y se restaura siempre. El audio y los temporales viven en `private_dir`, que se
borra al salir del bloque: en exito, en error y con Ctrl-C.
"""

from __future__ import annotations

import argparse
import os
import shlex
import signal
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Final

from vectra_nota_de_voz import note
from vectra_nota_de_voz.audio import (
    MAX_AUDIO_SECONDS,
    pick_recorder,
    private_dir,
    record,
    wav_seconds,
    write_private,
)
from vectra_nota_de_voz.commands import HOST, RECORDERS, Gh, Runner, SubprocessRunner, valid_pr, valid_user
from vectra_nota_de_voz.console import Console, Terminal
from vectra_nota_de_voz.errors import Cancelled, VozError
from vectra_nota_de_voz.transcriber import (
    DEFAULT_MODEL,
    MODELS,
    FasterWhisperTranscriber,
    Transcriber,
    valid_language,
)

YES: Final = frozenset({"s", "si", "sí"})
APPROVE_WORD: Final = "aprobar"
TRUNCATED: Final = (
    f"AVISO: el texto pasaba de {note.MAX_CHARS} caracteres y se recorto a ese limite. Revise el final."
)


@dataclass(frozen=True)
class Deps:
    runner: Runner
    console: Console
    environ: Mapping[str, str]
    make_transcriber: Callable[[str, Path | None], Transcriber]


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vectra-nota-de-voz",
        description="Nota de voz del revisor humano: graba, transcribe en local con Whisper y publica en el PR solo el texto que usted confirma.",
    )
    p.add_argument("pr", help="numero del pull request")
    p.add_argument(
        "--audio",
        type=Path,
        help="usar esta grabacion (WAV PCM, 16 kHz, mono, 16 bits) en vez del microfono; no se borra",
    )
    p.add_argument(
        "--max-seconds", type=int, default=120, help="duracion maxima de la grabacion (por omision 120)"
    )
    p.add_argument(
        "--recorder",
        default="auto",
        choices=("auto", *RECORDERS),
        help="grabador (por omision, el primero disponible)",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=tuple(MODELS),
        help=f"modelo de Whisper (por omision {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--model-path", type=Path, help="directorio local de un modelo de faster-whisper: funciona sin red"
    )
    p.add_argument("--language", default="es", help="idioma del audio (por omision es; `auto` lo detecta)")
    p.add_argument(
        "--as",
        dest="as_user",
        metavar="USUARIO",
        help="publicar con esta cuenta, que ya debe tener sesion en `gh`",
    )
    p.add_argument(
        "--repo", metavar="DUENO/NOMBRE", help="repositorio del PR (por omision, el del directorio actual)"
    )
    p.add_argument(
        "--approve", action="store_true", help="ofrecer ademas aprobar el PR (pide su propia confirmacion)"
    )
    p.add_argument("--dry-run", action="store_true", help="hacer todo menos publicar")
    return p


def run(argv: Sequence[str], deps: Deps) -> int:
    """El flujo completo. 0: publicado (o `--dry-run`); 1: no se confirmo; 2: falta algo o se rechazo un argumento; 130: interrumpido."""
    say = deps.console.say
    try:
        return _flow(parser().parse_args(list(argv)), deps)
    except VozError as error:
        say(f"error: {error}")
        return 2
    except Cancelled as reason:
        say(f"{reason} No se publico nada.")
        return 1
    except KeyboardInterrupt:
        say("\nInterrumpido. No se publico nada mas; el audio y los temporales se borraron.")
        return 130


def _flow(args: argparse.Namespace, deps: Deps) -> int:
    runner, console, say = deps.runner, deps.console, deps.console.say
    number = valid_pr(args.pr)
    as_user = None if args.as_user is None else valid_user(args.as_user)
    language = valid_language(args.language)
    if not 5 <= args.max_seconds <= MAX_AUDIO_SECONDS:
        raise VozError(f"argumento rechazado: --max-seconds debe estar entre 5 y {MAX_AUDIO_SECONDS}")

    # 1. Comprobaciones previas. Solo lecturas.
    if runner.which("gh") is None:
        raise VozError("no se encontro `gh` (GitHub CLI) en el PATH: https://cli.github.com")
    gh = Gh(runner, deps.environ, args.repo)
    accounts = gh.accounts()
    active = next((account.login for account in accounts if account.active), None)
    if active is None:
        raise VozError(
            f"`gh` no tiene una sesion activa en {HOST}. Iniciela con: gh auth login --hostname {HOST}"
        )
    target = active
    if as_user is not None:
        match = next(
            (account.login for account in accounts if account.login.lower() == as_user.lower()), None
        )
        if match is None:
            raise VozError(
                f"la cuenta {as_user} no tiene sesion en `gh` (con sesion: {', '.join(a.login for a in accounts)}). Iniciela con:\n"
                f"  gh auth login --hostname {HOST} --web      (entre en el navegador como {as_user})\n"
                f"  gh auth switch --hostname {HOST} --user {active}      (para dejar activa la cuenta de antes)\n"
                "y repita la orden. No se hizo nada."
            )
        target = match
    pr = gh.pr(number)
    if pr.state != "OPEN":
        raise VozError(
            f"el PR #{number} no esta abierto (estado: {note.one_line(pr.state, 20)}): no se deja una nota en el"
        )
    if args.approve and pr.author.lower() == target.lower():
        raise VozError(
            f"el PR #{number} lo abrio {target}: GitHub no deja aprobar un PR propio. Use `--as <la cuenta que revisa>` o quite `--approve`."
        )
    audio: Path | None = None
    recorder = ""
    if args.audio is not None:
        audio = args.audio.resolve()
        if not audio.is_file():
            raise VozError(f"no existe el archivo de audio {args.audio}")
        wav_seconds(audio)
    else:
        if not console.interactive():
            raise VozError(
                "para grabar hace falta una terminal interactiva (o pase una grabacion con `--audio archivo.wav`)"
            )
        recorder = pick_recorder(runner, args.recorder)
    transcriber = deps.make_transcriber(args.model, args.model_path)
    problem = transcriber.problem()
    if problem is not None:
        raise VozError(problem)

    say(
        f"PR #{pr.number}: {note.one_line(pr.title)} ({note.one_line(pr.url)}), abierto por {note.one_line(pr.author, 40)}"
    )
    if target == active:
        say(f"Se publicaria como: {target} (la cuenta activa de `gh`)")
    else:
        say(
            f"Se publicaria como: {target} (la cuenta activa de `gh` es {active}; se cambia solo al publicar y se restaura)"
        )
    say(
        f"Audio: {f'archivo {audio.name} (es suyo: no se borra)' if audio else f'microfono, con `{recorder}`'}"
    )
    say(
        f"Transcriptor: Whisper `{transcriber.label}` en esta maquina, idioma {language or 'auto'}. El audio no sale de aqui."
    )

    with private_dir(deps.environ) as directory:
        # 2. Grabar.
        if audio is None:
            say(
                f"Grabando. Hable y pulse Enter para terminar (maximo {args.max_seconds} s; Ctrl-C cancela)..."
            )
            wav = record(runner, console, recorder, directory, args.max_seconds)
            say(f"Grabados {wav_seconds(wav):.0f} s.")
        else:
            wav = audio
        # 3. Transcribir en local.
        say("Transcribiendo en local (puede tardar)...")
        raw = transcriber.transcribe(wav, language, say)
        if audio is None:
            wav.unlink(missing_ok=True)
            say("Audio borrado.")
        text, cut = note.clean(raw)
        if not text:
            raise VozError("la transcripcion salio vacia: no se entendio nada en el audio")
        if cut:
            say(TRUNCATED)
        # 4. Corregir y confirmar.
        text = _review(text, directory, deps)
        content = note.body(text, transcriber.label, audio_kept_by_user=audio is not None)
        say("\n----- Asi quedaria el comentario -----")
        say(content)
        say("--------------------------------------")
        if args.dry_run:
            say("--dry-run: no se pregunta y no se publica nada.")
            return 0
        approve = False
        if args.approve:
            answer = console.ask(
                f"¿Ademas APROBAR el PR #{number} como {target}? Escriba «{APPROVE_WORD}» para aprobar (cualquier otra cosa: solo comentario): "
            )
            approve = answer.strip().lower() == APPROVE_WORD
        mode = "APROBANDO el PR" if approve else "como comentario, sin aprobar"
        answer = console.ask(f"¿Publicar esta nota en el PR #{number} como {target}? ({mode}) [s/N] ")
        if answer.strip().lower() not in YES:
            raise Cancelled("No se confirmo.")
        # 5. Publicar: la unica escritura.
        body_file = directory / "cuerpo.md"
        write_private(body_file, content)
        _publish(gh, console, number, body_file, approve, active, target)
        say(f"Publicado en {note.one_line(pr.url)} como {target}{' (PR aprobado)' if approve else ''}.")
    return 0


def _review(text: str, directory: Path, deps: Deps) -> str:
    """Muestra el texto y lo abre en el editor de la persona. Sin editor, lo deja como esta: la pregunta final decide."""
    say = deps.console.say
    say("\n----- Transcripcion -----")
    say(text)
    say("-------------------------")
    try:
        editor = shlex.split(deps.environ.get("VISUAL") or deps.environ.get("EDITOR") or "")
    except ValueError:
        editor = []
    if not editor or not deps.console.interactive() or deps.runner.which(editor[0]) is None:
        say(
            "No hay `$EDITOR` utilizable: aqui no se puede corregir. Si el texto no es correcto, responda N y repita con EDITOR definido."
        )
        return text
    draft = directory / "nota.md"
    write_private(draft, text + "\n")
    say(f"Se abre `{note.one_line(editor[0], 40)}`: corrija el texto, guarde y cierre.")
    code = deps.runner.interactive([*editor, str(draft)])
    if code != 0:
        raise Cancelled(f"El editor termino con codigo {code}.")
    edited, cut = note.clean(draft.read_text(encoding="utf-8", errors="replace"))
    if not edited:
        raise Cancelled("La nota quedo vacia.")
    if cut:
        say(TRUNCATED)
    return edited


def _active(gh: Gh) -> str | None:
    return next((account.login for account in gh.accounts() if account.active), None)


def _publish(
    gh: Gh, console: Console, number: int, body_file: Path, approve: bool, active: str, target: str
) -> None:
    """`gh pr review` con la cuenta `target`. Si no es la activa, cambia, comprueba el cambio, publica y restaura siempre."""
    if target == active:
        gh.review(number, body_file, approve)
        return
    console.say(f"Cambiando la cuenta activa de `gh` a {target} solo para publicar...")
    try:
        if not gh.switch(target) or _active(gh) != target:
            raise VozError(f"no se pudo cambiar `gh` a la cuenta {target}: no se publico nada")
        gh.review(number, body_file, approve)
    finally:
        restored = gh.switch(active)
        try:
            restored = restored and _active(gh) == active
        except VozError:
            restored = False
        if restored:
            console.say(f"Cuenta activa de `gh` restaurada: {active}.")
        else:
            console.say(
                f"ATENCION: no se pudo restaurar la cuenta activa de `gh`. Ejecute: gh auth switch --hostname {HOST} --user {active}"
            )


def _interrupt(_signum: int, _frame: FrameType | None) -> None:  # pragma: no cover - senales reales
    raise KeyboardInterrupt


def main() -> None:  # pragma: no cover - el arranque real; `run` es lo que cubren las pruebas
    """Punto de entrada de `vectra-nota-de-voz`. SIGTERM y SIGHUP se tratan como Ctrl-C para que el borrado ocurra."""
    signal.signal(signal.SIGTERM, _interrupt)
    signal.signal(signal.SIGHUP, _interrupt)
    sys.exit(run(sys.argv[1:], Deps(SubprocessRunner(), Terminal(), os.environ, FasterWhisperTranscriber)))
