"""Tipos que comparten las fixtures de `conftest.py` y las pruebas (no se importa `conftest`: el nombre choca con el de `contracts/tests`)."""

from dataclasses import dataclass
from typing import Any

import httpx
from bff_doubles import Doubles
from fastapi import FastAPI


@dataclass
class Bff:
    client: httpx.AsyncClient
    app: FastAPI
    doubles: Doubles


class EventLog:
    """Los eventos de `log_event` de la solicitud (nombre y campos), sin perder la validacion del modo strict."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, Any]]] = []

    def named(self, event: str) -> list[dict[str, Any]]:
        return [fields for name, fields in self.records if name == event]

    def clear(self) -> None:
        self.records.clear()
