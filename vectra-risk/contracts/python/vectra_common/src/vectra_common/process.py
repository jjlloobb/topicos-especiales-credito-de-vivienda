"""Tipo de proceso, declarado una sola vez (NFR-U0-23 (f))."""

from typing import Literal

from vectra_contracts.errors import ContractViolation

ProcessKind = Literal["service", "batch"]
_kind: ProcessKind | None = None


def init(kind: ProcessKind) -> None:
    """Un proceso batch la llama antes de crear clientes; inicializar dos veces falla."""
    global _kind  # noqa: PLW0603
    if _kind is not None:
        raise ContractViolation("process.init ya se llamo en este proceso")
    _kind = kind


def ensure_service() -> None:
    """`create_app` fija `service`; un proceso batch no puede crear una app."""
    global _kind  # noqa: PLW0603
    if _kind == "batch":
        raise ContractViolation("un proceso batch no crea apps de servicio")
    _kind = "service"


def current() -> ProcessKind:
    if _kind is None:
        raise ContractViolation("proceso sin inicializar: llama process.init o create_app")
    return _kind


def reset_for_tests() -> None:
    global _kind  # noqa: PLW0603
    _kind = None
