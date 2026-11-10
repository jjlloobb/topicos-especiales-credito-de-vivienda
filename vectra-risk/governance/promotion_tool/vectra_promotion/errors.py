"""Error unico de la CLI: el mensaje es un codigo estable y nunca lleva el token."""


class PromotionError(Exception):
    """Una precondicion o una llamada fallo; la CLI termina con codigo 1 y este mensaje."""
