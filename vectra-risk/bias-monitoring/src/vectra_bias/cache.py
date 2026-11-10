"""Cache del dashboard por replica (P-U9-03; NFR-U9-02): LRU de `config.CACHE_ENTRIES` entradas con vencimiento de
`config.CACHE_TTL_S` y *single-flight*.

- Llave: `(version, atributo, ventana)`. Con la version ausente la llave usa `None` («sin version»): resolver la version
  mas reciente exige leer el registro, y leerlo es justo lo que el *single-flight* evita repetir. La respuesta cacheada ya
  resolvio la version, asi que dura a lo mas `CACHE_TTL_S` (la misma frescura que cualquier otra entrada).
- *Single-flight*: con la misma llave y sin entrada, una sola corrutina lee el registro; las demas esperan su resultado o su
  error. Un error no se guarda: la siguiente consulta vuelve a leer.
- Solo guarda la respuesta ya suprimida (P-U9-04): el valor que recibe es el `DisparityView` terminado.
- Metricas en el registro de U0 (`vectra_common.metrics.REGISTRY`), sin identificadores en las etiquetas (NFR-U9-41):
  `vectra_bias_cache_lookups_total{result="hit|miss|coalesced"}` y `vectra_bias_cache_entries`.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from typing import Any, Final

from prometheus_client import Counter, Gauge
from vectra_common.metrics import REGISTRY

from vectra_bias import config

HIT: Final = "hit"
MISS: Final = "miss"
COALESCED: Final = "coalesced"

LOOKUPS: Final = Counter(
    "vectra_bias_cache_lookups_total", "Consultas a la cache del dashboard", ["result"], registry=REGISTRY
)
ENTRIES: Final = Gauge("vectra_bias_cache_entries", "Entradas de la cache del dashboard", registry=REGISTRY)
for _result in (HIT, MISS, COALESCED):
    LOOKUPS.labels(result=_result)  # la serie existe desde el arranque, aun en 0


class SingleFlightCache:
    """LRU con vencimiento y *single-flight*. Pensada para un solo bucle de eventos (un proceso de `uvicorn`)."""

    def __init__(
        self,
        max_entries: int = config.CACHE_ENTRIES,
        ttl_s: float = config.CACHE_TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_entries
        self._ttl = ttl_s
        self._clock = clock
        self._entries: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._inflight: dict[Hashable, asyncio.Task[Any]] = {}
        ENTRIES.set(0)

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, key: Hashable) -> bool:
        return key in self._entries

    def _lookup(self, key: Hashable) -> tuple[bool, Any]:
        item = self._entries.get(key)
        if item is None:
            return False, None
        expires_at, value = item
        if self._clock() >= expires_at:
            del self._entries[key]
            ENTRIES.set(len(self._entries))
            return False, None
        self._entries.move_to_end(key)
        return True, value

    def _store(self, key: Hashable, task: asyncio.Task[Any]) -> None:
        self._inflight.pop(key, None)
        if task.cancelled() or task.exception() is not None:
            return  # un error no se guarda
        self._entries[key] = (self._clock() + self._ttl, task.result())
        self._entries.move_to_end(key)
        while len(self._entries) > self._max:
            self._entries.popitem(last=False)  # la menos usada
        ENTRIES.set(len(self._entries))

    async def get(self, key: Hashable, load: Callable[[], Awaitable[Any]]) -> Any:
        """El valor de `key`: de la cache, del vuelo en curso de otra consulta o de `load()` (que corre una sola vez)."""
        found, value = self._lookup(key)
        if found:
            LOOKUPS.labels(result=HIT).inc()
            return value
        task = self._inflight.get(key)
        if task is None:
            LOOKUPS.labels(result=MISS).inc()
            task = asyncio.ensure_future(load())
            self._inflight[key] = task
            task.add_done_callback(lambda done, k=key: self._store(k, done))
        else:
            LOOKUPS.labels(result=COALESCED).inc()
        return await asyncio.shield(task)
