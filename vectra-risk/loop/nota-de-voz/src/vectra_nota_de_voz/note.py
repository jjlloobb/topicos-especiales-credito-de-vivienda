"""El texto de la nota. Lo que sale del transcriptor es contenido no confiable: aqui solo se limpia, se recorta y se pega bajo la cabecera.

Nada de este texto se ejecuta ni se interpreta como orden o como opcion: no llega a ninguna linea de ordenes (viaja en un archivo) y la herramienta no
busca instrucciones en el. GitHub lo mostrara como Markdown, igual que cualquier comentario que la persona escriba a mano.
"""

from __future__ import annotations

import unicodedata
from typing import Final

MAX_CHARS: Final = 4000


def printable(text: str) -> str:
    """Sin caracteres de control (secuencias de escape de terminal incluidas). Conserva saltos de linea y tabuladores."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        ch for ch in text if ch in "\n\t" or unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn")
    )


def one_line(text: str, limit: int = 120) -> str:
    """Un texto ajeno (el titulo del PR) para mostrarlo en una linea de la terminal."""
    return " ".join(printable(text).split())[:limit]


def clean(text: str) -> tuple[str, bool]:
    """El texto limpio y como mucho de `MAX_CHARS` caracteres, y si hubo que recortarlo."""
    text = printable(text).strip()
    if len(text) <= MAX_CHARS:
        return text, False
    return text[:MAX_CHARS].rstrip(), True


def header(model_label: str, audio_kept_by_user: bool) -> str:
    """La cabecera fija. Con `--audio` el archivo es de la persona y la herramienta no lo borra: no se afirma que no se conserva."""
    base = (
        f"**Nota de voz del revisor humano**, transcrita en local con Whisper (`{model_label}`) y revisada y confirmada "
        "por la persona antes de publicarla."
    )
    return base if audio_kept_by_user else f"{base} El audio no se conserva."


def body(text: str, model_label: str, audio_kept_by_user: bool) -> str:
    """El cuerpo del comentario: la cabecera, el texto confirmado y nada mas."""
    return f"{header(model_label, audio_kept_by_user)}\n\n{text}\n"
