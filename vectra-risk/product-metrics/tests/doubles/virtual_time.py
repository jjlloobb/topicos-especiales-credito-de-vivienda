"""Reloj simulado para las pruebas del proceso: tiempo de pared y monotono que solo avanzan cuando la prueba lo manda.

`sleep` registra al que espera; `advance` despierta a los que vencen, en orden y de uno en uno, dejando que el resto de las tareas
corra entre uno y otro (`settle`). Ninguna prueba duerme minutos reales.
"""

from __future__ import annotations

import asyncio
import heapq
import itertools
from datetime import datetime, timedelta


class VirtualClock:
    def __init__(self, start: datetime) -> None:
        self.start = start
        self.t = 0.0  # segundos simulados desde `start`
        self._waiters: list[tuple[float, int, asyncio.Future[None]]] = []
        self._counter = itertools.count()

    def wall(self) -> datetime:
        return self.start + timedelta(seconds=self.t)

    def monotonic(self) -> float:
        return self.t

    async def sleep(self, seconds: float) -> None:
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        heapq.heappush(self._waiters, (self.t + max(0.0, seconds), next(self._counter), future))
        await future

    @staticmethod
    async def settle(rounds: int = 60) -> None:
        """Cede el control hasta que las tareas listas se quedan esperando algo que solo el reloj puede dar."""
        for _ in range(rounds):
            await asyncio.sleep(0)

    async def advance(self, seconds: float) -> None:
        target = self.t + seconds
        while True:
            await self.settle()
            while self._waiters and self._waiters[0][2].cancelled():
                heapq.heappop(self._waiters)
            if not self._waiters or self._waiters[0][0] > target:
                break
            due, _, future = heapq.heappop(self._waiters)
            self.t = max(self.t, due)
            future.set_result(None)
        self.t = max(self.t, target)
        await self.settle()
