"""Logger JSON con allowlist (P-U0-04, BR-U0-50..53, NFR-U0-13)."""

import logging as std_logging
import os
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any, Final, TextIO

import structlog
from vectra_contracts.catalog import LOG_RECORD_FIELDS, LogEvent
from vectra_contracts.errors import ContractViolation

from vectra_common.metrics import LOG_FIELDS_DROPPED

correlation_id_var: Final[ContextVar[str | None]] = ContextVar("correlation_id", default=None)
span_id_var: Final[ContextVar[str | None]] = ContextVar("span_id", default=None)
trace_sampled_var: ContextVar[bool] = ContextVar("trace_sampled", default=True)
_OWN_KEY: Final = "_vectra_own"
_EVENTS: Final = frozenset(event.value for event in LogEvent)
_service: dict[str, str] = {"name": "unknown"}


class LogContractViolation(Exception):  # noqa: N818 - nombre del patron P-U0-04
    """Modo `strict`: un campo fuera de la allowlist hace fallar la prueba."""


def _strict() -> bool:
    return os.environ.get("VECTRA_LOG_STRICT") == "1"


def allowlist_filter(
    _logger: object, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Procesador final: conserva solo las claves de `LogRecord`; el resto se descarta."""
    own = event_dict.pop(_OWN_KEY, False)
    event = event_dict.get("event")
    if event not in _EVENTS:
        # Mensajes de terceros y el log de acceso: el texto nunca se emite (BR-U0-51).
        event_dict.pop("event", None)
    label = str(event_dict.get("event", ""))
    dropped = [key for key in event_dict if key not in LOG_RECORD_FIELDS]
    for key in dropped:
        if own and _strict():
            raise LogContractViolation(f"campo fuera de la allowlist: {key}")
        del event_dict[key]
        LOG_FIELDS_DROPPED.labels(service=_service["name"], event=label).inc()
    return event_dict


def _add_context(
    _logger: object, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    event_dict["service"] = _service["name"]
    correlation = correlation_id_var.get()
    span = span_id_var.get()
    if correlation:
        event_dict["correlation_id"] = correlation
    if span:
        event_dict["span_id"] = span
    return event_dict


def _rename_level(
    _logger: object, method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    event_dict.setdefault("level", method)
    return event_dict


def configure(service: str, stream: TextIO | None = None) -> None:
    """Configura structlog y redirige el `logging` de terceros al mismo pipeline."""
    _service["name"] = service
    shared: list[Any] = [
        _rename_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        _add_context,
    ]
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            allowlist_filter,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )
    handler = std_logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(formatter)
    root = std_logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(std_logging.INFO)
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )


def log_event(event: LogEvent, **fields: Any) -> None:
    """Un evento del catalogo (BR-U0-51); otro valor no se acepta."""
    if not isinstance(event, LogEvent):
        raise ContractViolation("event fuera del catalogo de domain-entities §8.1")
    _emit(event.value, fields)


def log_access(**fields: Any) -> None:
    """Log de peticion comun: `event` vacio (domain-entities §8.1)."""
    _emit("", fields)


def log_exception(exc: BaseException, error_code: str) -> None:
    """BR-U0-52: tipo y `error_code`; nunca `str(exc)` ni la traza."""
    _emit("", {"error_code": error_code, "exception_type": type(exc).__name__})


def _emit(event: str, fields: dict[str, Any]) -> None:
    if _strict():
        extra = [key for key in fields if key not in LOG_RECORD_FIELDS]
        if extra:
            raise LogContractViolation(f"campo fuera de la allowlist: {extra[0]}")
    structlog.get_logger("vectra").info(event, **fields)
