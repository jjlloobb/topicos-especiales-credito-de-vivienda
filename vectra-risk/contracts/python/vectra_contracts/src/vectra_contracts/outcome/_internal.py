"""Token privado de construccion (P-U0-03, capa 2). Solo lo importa `outcome`."""

from typing import Final


class _Token:
    __slots__ = ()


CONSTRUCTION_TOKEN: Final = _Token()
