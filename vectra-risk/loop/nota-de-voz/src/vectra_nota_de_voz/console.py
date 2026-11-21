"""La terminal de la persona: decir, preguntar y esperar a Enter. Se inyecta; las pruebas usan una falsa."""

from __future__ import annotations

import select
import sys
from typing import Protocol


class Console(Protocol):
    def say(self, text: str) -> None: ...

    def ask(self, prompt: str) -> str: ...

    def wait_enter(self, seconds: float) -> bool: ...

    def interactive(self) -> bool: ...


class Terminal:  # pragma: no cover - la terminal real; las pruebas inyectan una falsa
    def say(self, text: str) -> None:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    def ask(self, prompt: str) -> str:
        """Una linea de la persona. Sin entrada (fin de archivo) la respuesta es vacia, que nunca confirma nada."""
        try:
            return input(prompt)
        except EOFError:
            return ""

    def wait_enter(self, seconds: float) -> bool:
        ready, _, _ = select.select([sys.stdin], [], [], seconds)
        if ready:
            sys.stdin.readline()
        return bool(ready)

    def interactive(self) -> bool:
        return sys.stdin.isatty() and sys.stdout.isatty()
