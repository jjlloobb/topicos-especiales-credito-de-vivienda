"""Ejecutar texto de un documento con `bash` sin tocar nada real (U12-T09, R-01).

Una prueba de `system-verification` NUNCA corre texto de la guia, de un README o de un guion de `demos/` con el `PATH` ni el entorno reales: el 2026-11-16 un bloque mal recortado llevo un `kubectl delete`
real al cluster. Aqui el texto se comprueba **antes** de lanzar nada (solo ordenes de una lista corta) y corre con un `PATH` que es **solo** un directorio con (a) los binarios inofensivos de `HARMLESS`,
enlazados uno a uno, (b) los dobles que la prueba da y (c) centinelas para `kubectl`, `docker`, `argocd`, `helm` y `gh` que dejan constancia si alguien los llama; con un entorno armado desde cero.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path

HARMLESS = ("sh", "bash", "mkdir", "cat", "chmod", "dirname", "id", "printf", "rm", "env")
SENTINELS = ("kubectl", "docker", "argocd", "helm", "gh")


class UnsafeScript(Exception):
    """El texto trae una orden que la prueba no permite: no se lanzo nada."""


def _substitutions(script: str) -> tuple[str, list[str]]:
    """Saca de `script` cada `$(...)` (de adentro hacia afuera) y devuelve el resto y lo que habia dentro."""
    inner: list[str] = []
    pattern = re.compile(r"\$\(([^()]*)\)")
    while pattern.search(script):
        inner += pattern.findall(script)
        script = pattern.sub("X", script)
    return script, inner


def _simple_commands(script: str) -> list[list[str]]:
    script = script.replace("\\\n", " ")
    commands: list[list[str]] = []
    buffer, quote = "", ""
    for char in script + "\n":
        if quote:
            buffer += char
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
            buffer += char
        elif char in ";&|\n":
            if buffer.strip():
                commands.append(buffer.strip())  # type: ignore[arg-type]
            buffer = ""
        else:
            buffer += char
    result = []
    for text in commands:
        text = str(text)
        if text.startswith("#"):
            continue
        try:
            words = shlex.split(text, comments=False)
        except ValueError:
            words = text.split()
        result.append(words)
    return result


def command_words(script: str) -> set[str]:
    """La primera palabra de cada orden simple del texto (tras las asignaciones), incluidas las de `$(...)`."""
    top, inner = _substitutions(script)
    found: set[str] = set()
    for text in [top, *inner]:
        for words in _simple_commands(text):
            while words and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0]):
                words = words[1:]
            if not words or words[0] in ("{", "}", "(", ")", "then", "fi", "do", "done"):
                continue
            found.add(words[0].removesuffix("()"))
    return found


def disallowed(script: str, allowed: set[str] | frozenset[str]) -> set[str]:
    return {word for word in command_words(script) if word not in allowed}


def sandbox(tmp_path: Path, fakes: dict[str, str] | None = None) -> tuple[Path, dict[str, str], Path]:
    """`(directorio de ejecutables, entorno desde cero, registro de los centinelas)`."""
    bin_dir = tmp_path / "safe-bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "sentinel.log"
    log.write_text("", encoding="utf-8")
    for name in HARMLESS:
        found = shutil.which(name)
        if found and not (bin_dir / name).exists():
            (bin_dir / name).symlink_to(found)
    given = fakes or {}
    for name in SENTINELS:
        if name not in given:
            (bin_dir / name).write_text(
                f'#!/bin/sh\necho "{name} $*" >> "$SENTINEL_LOG"\nexit 99\n', encoding="utf-8"
            )
            (bin_dir / name).chmod(0o755)
    for name, text in given.items():
        (bin_dir / name).write_text(text, encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {"PATH": str(bin_dir), "HOME": str(home), "SENTINEL_LOG": str(log), "LANG": "C"}
    return bin_dir, env, log


def run_script(
    script: str,
    allowed: set[str] | frozenset[str],
    tmp_path: Path,
    *,
    fakes: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Comprueba el texto (falla sin ejecutar nada si trae una orden fuera de `allowed`), lo corre en el entorno aislado y afirma que ningun centinela fue llamado."""
    extra = disallowed(script, allowed)
    if extra:
        raise UnsafeScript(f"ordenes no permitidas, no se ejecuto nada: {sorted(extra)}")
    _, base, log = sandbox(tmp_path, fakes)
    done = subprocess.run(
        ["bash", "-c", script],
        env={**base, **(env or {})},
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd or tmp_path,
    )  # noqa: S603
    called = log.read_text(encoding="utf-8").strip()
    assert called == "", f"una herramienta del cluster fue llamada: {called}"
    return done
