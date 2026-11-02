"""Contratos de Vectra Risk."""

# `models.api` importa `outcome` y `outcome` importa `models.*`. Cargar `models` primero fija el
# orden que resuelve el ciclo, sea cual sea el primer import del proceso (US-111).
from vectra_contracts import models as _models  # noqa: F401

__version__ = "0.1.0"
