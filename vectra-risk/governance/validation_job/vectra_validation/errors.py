"""Errores del Job. Un fallo termina el proceso con codigo distinto de 0 y sin informe: governance lo ve vencer (BR-U4-05)."""


class ValidationJobError(Exception):
    """Fallo del Job; el mensaje es un codigo estable, nunca datos del dataset."""
