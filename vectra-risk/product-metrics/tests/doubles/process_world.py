"""Un proceso de U11 armado en memoria con el doble de U3 y un reloj simulado (Paso 6): estado, planificador, series de operacion y
`collector` registrados en el registro de U0, que es el que sirve `create_ops_app`. `close()` los desregistra: el registro es global."""

from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from datetime import datetime
from typing import Any

import httpx
from entries import NOW
from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families
from registry_double import FakeToken, RegistryDouble
from vectra_common import process
from vectra_common.metrics import REGISTRY
from vectra_product.collector import Collector, Holder, Operations, register
from vectra_product.main import make_readiness
from vectra_product.model import Params
from vectra_product.reader import Reader, build_client
from vectra_product.scheduler import Scheduler
from vectra_product.state import ProductState
from virtual_time import VirtualClock


async def ops_get(app: Any, path: str) -> httpx.Response:
    """Una peticion al `ops_server` (app ASGI de `create_ops_app`) sin abrir un puerto."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ops") as client:
        return await client.get(path)


PARAMS = Params(0.6, 3, 50, 1.0, 1.0, 0.8, 0.7, None)

Samples = dict[str, list[tuple[dict[str, str], float]]]


def scrape(registry: Any = REGISTRY) -> Samples:
    """`/metrics` como lo lee Prometheus: nombre de muestra -> [(etiquetas, valor)]."""
    out: Samples = defaultdict(list)
    for family in text_string_to_metric_families(generate_latest(registry).decode()):
        for sample in family.samples:
            out[sample.name].append((dict(sample.labels), sample.value))
    return out


def value(samples: Samples, name: str, **labels: str) -> float:
    found = [v for lab, v in samples.get(name, []) if lab == labels]
    assert len(found) == 1, f"{name}{labels}: {len(found)} muestras"
    return found[0]


class World:
    def __init__(
        self,
        entries: list[dict[str, Any]] | None = None,
        *,
        double: RegistryDouble | None = None,
        page_size: int = 3,
        start: datetime = NOW,
        seed: int = 1,
        params: Params = PARAMS,
    ) -> None:
        process.reset_for_tests()
        process.init("service")
        self.clock = VirtualClock(start)
        self.double = double or RegistryDouble(entries, sleep=self.clock.sleep)
        client = build_client(
            "http://registry.invalid",
            token_source=FakeToken(),
            transport=self.double.transport(),
            clock=self.clock.monotonic,
        )
        self.reader = Reader(client, page_size=page_size)
        self.operations = Operations()
        self.holder = Holder()
        self.collector: Collector = register(self.holder)
        self.state = ProductState(self.reader, self.clock.wall, self.operations.read)
        self.stop = asyncio.Event()
        self.scheduler = Scheduler(
            self.state,
            params,
            self.holder,
            self.operations,
            wall=self.clock.wall,
            monotonic=self.clock.monotonic,
            sleep=self.clock.sleep,
            rng=random.Random(seed),
            stop=self.stop,
        )
        self.ready = make_readiness(self.holder, self.reader)
        self.task: asyncio.Task[None] | None = None
        self._released = False

    async def start(self) -> None:
        self.task = asyncio.ensure_future(self.scheduler.run())
        await self.clock.settle()

    async def advance(self, seconds: float) -> None:
        await self.clock.advance(seconds)

    async def shutdown(self) -> None:
        """`SIGTERM`: activa `stop` y deja que el planificador termine."""
        self.stop.set()
        assert self.task is not None
        await self.clock.advance(0)
        await asyncio.wait_for(self.task, 5)

    def kill(self) -> None:
        """Descarta el proceso a mitad de lo que haga (sin `stop`): la prueba de reinicio."""
        assert self.task is not None
        self.task.cancel()

    def release_series(self) -> None:
        """Desregistra las series de este mundo (idempotente): el registro de U0 es global."""
        if not self._released:
            self._released = True
            REGISTRY.unregister(self.collector)
            self.operations.close()

    async def close(self) -> None:
        if self.task is not None and not self.task.done():
            self.task.cancel()
        if self.task is not None:
            await asyncio.gather(self.task, return_exceptions=True)
        self.release_series()

    def metrics(self) -> Samples:
        return scrape()
