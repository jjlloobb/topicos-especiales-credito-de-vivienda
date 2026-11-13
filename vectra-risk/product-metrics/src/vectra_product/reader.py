"""Lectura de la proyeccion `metrics` del registro (F28): `GET /v1/entries?projection=metrics&entry_type=human_decision&...`.

- Una pagina a la vez (P-U11-01, NFR-U11-01): la siguiente se pide cuando el consumidor termino con la anterior.
- Un `asyncio.Lock` unico (P-U11-02) que toman la pasada completa (espera) y la lectura incremental (no espera: si esta tomado,
  se omite sin leer).
- `vectra_common.deps.call`, con timeout de 5 s por pagina, sin reintentos dentro del ciclo (NFR-U11-09) y el breaker de U0 en modo
  `consecutive_failures` (U11 no tiene uno propio). Ningun modulo de U11 importa `httpx`.
- Valida el sobre de la pagina (`items` y `next_seq_after`) y entrega cada item crudo: `model.parse_entry` decide, entrada por
  entrada, si es valida (BR-U11-10).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final
from urllib.parse import urlencode

from vectra_common import deps
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_common.service_token import provider_from_env
from vectra_contracts.routes import REGISTRY

from vectra_product import config

_ACCEPT: Final = {"accept": "application/json"}


def _entries_path() -> str:
    """La ruta del contrato de U3 para `GET` que termina en `/entries`; ningun modulo de U11 escribe una ruta como literal."""
    found = [
        r.path for r in REGISTRY[config.REGISTRY_SERVICE] if r.method == "GET" and r.path.endswith("/entries")
    ]
    if len(found) != 1:
        raise LookupError(f"{config.REGISTRY_SERVICE} GET .../entries: {len(found)} rutas en el contrato")
    return found[0]


ENTRIES_PATH: Final = _entries_path()


class ReadError(Exception):
    """Una pagina no se pudo leer o no es valida: la lectura falla, `last_seq` no avanza mas alla de la ultima pagina confirmada."""


@dataclass(frozen=True, slots=True)
class RawPage:
    items: list[Mapping[str, Any]]  # items crudos, con `seq` entero y en orden
    next_seq_after: int | None


def build_client(
    base_url: str,
    *,
    token_source: deps.TokenSource | None = None,
    transport: Any = None,  # un `httpx.AsyncBaseTransport` (pruebas); este modulo no importa `httpx`
    clock: Callable[[], float] = time.monotonic,
) -> deps.DependencyClient:
    """El cliente hacia U3: una conexion, el breaker en modo `consecutive_failures` y el token del cliente `product-metrics`
    (un solo scope, `registry:read:metrics`; NFR-U11-20). Sin `token_source`, el token sale de las variables `VECTRA_*` de U0."""
    return deps.DependencyClient(
        config.BREAKER_DEPENDENCY,
        base_url,
        deps.BreakerConfig(
            open_for=config.BREAKER_OPEN_FOR_SECONDS,
            consecutive_failures=config.BREAKER_CONSECUTIVE_FAILURES,
            close_after=config.BREAKER_CLOSE_AFTER,
        ),
        config.MAX_CONNECTIONS,
        clock=clock,
        transport=transport,
        token_source=token_source or provider_from_env(config.REGISTRY_SERVICE, config.SCOPES),
    )


def _query(seq_after: int | None, recorded_from: datetime | None, limit: int) -> str:
    params: dict[str, str | int] = {"projection": "metrics", "entry_type": "human_decision", "limit": limit}
    if recorded_from is not None:
        params["recorded_from"] = recorded_from.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if seq_after is not None:
        params["seq_after"] = seq_after
    return f"{ENTRIES_PATH}?{urlencode(params)}"


def _is_seq(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _envelope(body: bytes, cursor: int | None, limit: int) -> RawPage:
    try:
        decoded = json.loads(body)
    except ValueError as error:
        raise ReadError("page_not_json") from error
    if not isinstance(decoded, dict) or not isinstance(decoded.get("items"), list):
        raise ReadError("page_invalid")
    items = decoded["items"]
    following = decoded.get("next_seq_after")
    if len(items) > limit or (following is not None and not _is_seq(following)):
        raise ReadError("page_invalid")
    previous = -1 if cursor is None else cursor
    for item in items:
        if not isinstance(item, dict) or not _is_seq(item.get("seq")) or item["seq"] <= previous:
            raise ReadError(
                "page_order"
            )  # sin `seq` entero, o fuera de orden: no se puede avanzar `last_seq` con seguridad
        previous = item["seq"]
    if following is not None and following <= (-1 if cursor is None else cursor):
        raise ReadError("page_no_progress")
    return RawPage(items, following)


class Reader:
    def __init__(self, client: deps.DependencyClient, *, page_size: int = config.PAGE_SIZE) -> None:
        self._client = client
        self._page_size = page_size
        self._lock = asyncio.Lock()

    @property
    def locked(self) -> bool:
        return self._lock.locked()

    @property
    def breaker_state(self) -> deps.CircuitState:
        assert self._client.breaker is not None  # el cliente de U11 siempre lleva breaker
        return self._client.breaker.state

    @asynccontextmanager
    async def exclusive(self) -> AsyncIterator[None]:
        """El candado para la pasada completa: espera a que se libere."""
        async with self._lock:
            yield

    @asynccontextmanager
    async def try_exclusive(self) -> AsyncIterator[bool]:
        """El candado para la lectura incremental: no espera. `False` si esta tomado (ciclo omitido, sin leer)."""
        if self._lock.locked():
            yield False
            return
        async with self._lock:
            yield True

    async def _fetch(self, seq_after: int | None, recorded_from: datetime | None) -> RawPage:
        path = _query(seq_after, recorded_from, self._page_size)
        try:
            response = await deps.call(
                self._client, "GET", path, timeout=config.PAGE_TIMEOUT_SECONDS, headers=_ACCEPT
            )
        except (DependencyTimeout, DependencyUnavailable) as error:
            raise ReadError(type(error).__name__) from error
        if response.status_code != 200:
            raise ReadError(f"status_{response.status_code}")
        return _envelope(response.content, seq_after, self._page_size)

    async def pages(self, seq_after: int | None, recorded_from: datetime | None) -> AsyncIterator[RawPage]:
        """Las paginas en orden de `seq`, desde `seq_after` (sin incluirlo), hasta que `next_seq_after` es `null`.

        Hay que tener el candado (`exclusive` o `try_exclusive`). La pagina siguiente se pide solo despues de que el consumidor
        proceso la anterior: nunca hay dos en vuelo.
        """
        if not self._lock.locked():
            raise RuntimeError("la lectura exige tener el candado del reader")
        cursor = seq_after
        while True:
            page = await self._fetch(cursor, recorded_from)
            yield page
            if page.next_seq_after is None:
                return
            cursor = page.next_seq_after
