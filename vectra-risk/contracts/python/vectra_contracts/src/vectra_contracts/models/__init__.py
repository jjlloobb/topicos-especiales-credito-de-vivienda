"""Tipos del contrato."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from vectra_contracts.models.application import *  # noqa: F403
from vectra_contracts.models.base import *  # noqa: F403
from vectra_contracts.models.explanation import *  # noqa: F403
from vectra_contracts.models.features import *  # noqa: F403
from vectra_contracts.models.governance import *  # noqa: F403
from vectra_contracts.models.monitoring import *  # noqa: F403
from vectra_contracts.models.registry import *  # noqa: F403

if TYPE_CHECKING:
    from vectra_contracts.models.api import *  # noqa: F403

# `models.api` importa `outcome`, y `outcome` importa `models.base` y otros: si este paquete cargara
# `api` al importarse, el ciclo `outcome -> models -> api -> outcome` dependeria del primer import.
# Los nombres de `api` se resuelven de forma perezosa (PEP 562) y la API publica no cambia.


def _api_names() -> list[str]:
    api = import_module("vectra_contracts.models.api")
    return [name for name in vars(api) if not name.startswith("_")]


def __getattr__(name: str) -> Any:
    if not name.startswith("_"):
        api = import_module("vectra_contracts.models.api")
        if name in vars(api):
            value = getattr(api, name)
            globals()[name] = value
            return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted({*globals(), *_api_names()})
