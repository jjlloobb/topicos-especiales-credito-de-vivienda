"""PBT-U11-02: `state` + `compute`. El resultado de leer de forma incremental es igual al de una recomputacion completa sobre la
union, tambien con pasadas completas intercaladas, fallos a mitad y avances del reloj (P-U11-02; ajuste 1 de Q6).

La maquina agrega lotes arbitrarios al doble de U3 (en orden de `seq`), lee con pasadas completas e incrementales (a veces en
carrera: las incrementales que llegan con la pasada leyendo se omiten), inyecta fallos en una pagina cualquiera y adelanta el
reloj. Despues de cada paso, `compute` sobre el estado es igual a `compute` sobre la instantanea completa de las entradas con
`seq <= last_seq` (la lectura nunca avanza `last_seq` mas alla de la ultima pagina confirmada), y el doble nunca vio dos lecturas a
la vez (si las hubiera visto, habria fallado con `SimultaneousConnections`).
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from entries import Spec, render, spec_lists
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, precondition, rule
from registry_double import FakeToken, RegistryDouble
from vectra_common import process
from vectra_product import config
from vectra_product.compute import compute, snapshot_of
from vectra_product.model import parse_entry
from vectra_product.params import Params
from vectra_product.reader import ReadError, Reader, build_client
from vectra_product.state import SKIPPED, ProductState

PARAMS = Params(0.6, 3, 30, 1.0, 1.0, 0.8, 0.7, None)
START = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)


class IncrementalEqualsFull(RuleBasedStateMachine):
    @initialize(page_size=st.integers(1, 4))
    def setup(self, page_size: int) -> None:
        process.reset_for_tests()
        process.init("service")
        self.loop = asyncio.new_event_loop()
        self.clock = START
        self.double = RegistryDouble()
        self.specs: dict[int, Spec] = {}
        self.mono = 0.0  # reloj monotono del breaker: tres fallos seguidos lo abren (U0) hasta que pasan 60 s
        client = build_client(
            "http://registry.invalid",
            token_source=FakeToken(),
            transport=self.double.transport(),
            clock=lambda: self.mono,
        )
        self.reader = Reader(client, page_size=page_size)
        self.state = ProductState(self.reader, lambda: self.clock)
        self.next_seq = 1
        self.baseline = False
        self.skipped = 0

    def teardown(self) -> None:
        self.loop.close()

    def run(self, awaitable: Any) -> Any:
        return self.loop.run_until_complete(awaitable)

    # -- reglas -------------------------------------------------------------------------------------------------------

    @rule(data=st.data())
    def add_batch(self, data: st.DataObject) -> None:
        batch = data.draw(spec_lists(self.clock, max_size=8))
        added = []
        for spec in batch:
            numbered = replace(spec, seq=self.next_seq)
            self.next_seq += 1
            self.specs[numbered.seq] = numbered
            added.append(render(numbered))
        self.double.add(added)

    def heal(self) -> None:
        """El registro vuelve: sin fallos inyectados y con el breaker (si abrio) ya semiabierto."""
        self.double.fail_requests = set()
        self.mono += config.BREAKER_OPEN_FOR_SECONDS

    @rule()
    def full_pass(self) -> None:
        self.heal()
        self.run(self.state.full_pass())
        self.baseline = True
        assert self.state.last_seq == max(self.specs, default=None)

    @precondition(lambda self: self.baseline)
    @rule()
    def incremental(self) -> None:
        self.heal()
        self.run(self.state.incremental())
        assert self.state.last_seq == max(self.specs, default=None)

    @rule(hours=st.integers(1, 80))
    def advance_clock(self, hours: int) -> None:
        self.clock += timedelta(hours=hours)

    @rule(kind=st.sampled_from(["full", "incremental"]), page=st.integers(1, 6))
    def read_with_a_failure_on_page(self, kind: str, page: int) -> None:
        """Una pagina falla a mitad de la lectura: nada avanza mas alla de la ultima pagina confirmada."""
        if kind == "incremental" and not self.baseline:
            return
        before_seq = self.state.last_seq
        before = self.state.snapshot()
        before_entries = None if before is None else dict(before.entries)
        self.double.fail_requests = {self.double.calls + page}
        try:
            self.run(self.state.full_pass() if kind == "full" else self.state.incremental())
        except ReadError:
            if kind == "full":  # la pasada fallida deja intacto el estado vigente
                after = self.state.snapshot()
                assert self.state.last_seq == before_seq
                assert (after is None and before is None) or (
                    after is not None and before_entries is not None and dict(after.entries) == before_entries
                )
            else:
                assert before_seq is None or (self.state.last_seq or 0) >= before_seq
        else:
            if kind == "full":
                self.baseline = True
        finally:
            self.double.fail_requests = set()

    @rule(order=st.sampled_from(["full_first", "incremental_first"]), cycles=st.integers(1, 3))
    def race_full_and_incrementals(self, order: str, cycles: int) -> None:
        """Pasadas completas intercaladas con ciclos incrementales: los ciclos que llegan con la pasada leyendo se omiten."""
        self.heal()
        self.double.latency = 0.0005

        async def go() -> list[Any]:
            full = self.state.full_pass()
            if not self.baseline:
                return await asyncio.gather(full)
            incrementals = [self.state.incremental() for _ in range(cycles)]
            tasks = [full, *incrementals] if order == "full_first" else [*incrementals, full]
            return await asyncio.gather(*tasks)

        results = self.run(go())
        self.double.latency = 0.0
        self.baseline = True
        self.skipped += sum(1 for r in results if r == SKIPPED)
        if order == "full_first" and len(results) > 1:
            assert all(r == SKIPPED for r in results[1:])
        assert self.state.last_seq == max(self.specs, default=None)

    # -- invariantes --------------------------------------------------------------------------------------------------

    @invariant()
    def never_two_reads_at_once(self) -> None:
        assert self.double.max_active <= 1

    @invariant()
    def incremental_equals_a_full_recompute_over_the_union(self) -> None:
        snapshot = self.state.snapshot()
        if snapshot is None:
            assert self.state.last_seq is None
            return
        last = self.state.last_seq
        union = [
            parse_entry(seq, render(spec))
            for seq, spec in sorted(self.specs.items())
            if last is not None and seq <= last  # sin `last_seq` no se leyo nada
        ]
        expected = compute(snapshot_of(union, self.clock), PARAMS, self.clock)
        assert compute(snapshot, PARAMS, self.clock) == expected


IncrementalEqualsFull.TestCase.settings = settings(stateful_step_count=20, deadline=None)
TestIncrementalEqualsFull = IncrementalEqualsFull.TestCase
