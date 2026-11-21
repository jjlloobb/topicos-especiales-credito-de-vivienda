"""El unico error que la herramienta muestra a la persona: un mensaje, sin traza."""

from __future__ import annotations


class VozError(Exception):
    """Algo falta o un argumento se rechazo. El mensaje se muestra tal cual y la orden sale con codigo distinto de cero."""


class Cancelled(Exception):
    """La persona no confirmo. No se publica nada."""
