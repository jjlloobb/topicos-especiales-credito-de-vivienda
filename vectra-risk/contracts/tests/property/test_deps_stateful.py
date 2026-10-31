"""PBT-U0-14: breaker de `deps` contra un modelo de referencia (PBT-06)."""

import asyncio
from collections import deque
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from vectra_common import process
from vectra_common.deps import BreakerConfig, CircuitState, DependencyClient, call
from vectra_common.errors import DependencyUnavailable

NOW = datetime(2026, 10, 31, tzinfo=UTC)


class Model:
    """Referencia independiente de la implementacion."""

    def __init__(self, config):
        self.config = config
        self.state = "closed"
        self.opened_at = 0.0
        self.window = deque(maxlen=config.window_size or 1)
        self.consecutive = 0
        self.successes = 0

    def tick(self, now):
        if self.state == "open" and now - self.opened_at >= self.config.open_for:
            self.state = "half"
            self.successes = 0

    def open(self, now):
        self.state = "open"
        self.opened_at = now
        self.window.clear()
        self.consecutive = 0

    def success(self):
        if self.state == "half":
            self.successes += 1
            if self.successes >= self.config.close_after:
                self.state = "closed"
                self.window.clear()
                self.consecutive = 0
            return
        self.consecutive = 0
        if self.config.window_size:
            self.window.append(True)

    def failure(self, now):
        if self.state == "half":
            self.open(now)
            return
        if self.config.consecutive_failures:
            self.consecutive += 1
            if self.consecutive >= self.config.consecutive_failures:
                self.open(now)
            return
        self.window.append(False)
        if len(self.window) == self.config.window_size:
            if self.window.count(False) / self.config.window_size >= self.config.failure_ratio:
                self.open(now)


class Machine(RuleBasedStateMachine):
    @initialize(
        config=st.one_of(
            st.builds(BreakerConfig, open_for=st.floats(1, 100), window_size=st.integers(1, 10), failure_ratio=st.floats(0.1, 1.0)),
            st.builds(BreakerConfig, open_for=st.floats(1, 100), consecutive_failures=st.integers(1, 10), close_after=st.integers(1, 3)),
        )
    )
    def setup(self, config):
        process.reset_for_tests()
        process.ensure_service()
        self.now = 0.0
        self.calls = 0
        self.next = httpx.Response(200)
        self.requests = []
        self.model = Model(config)
        self.loop = asyncio.new_event_loop()
        self.client = DependencyClient(
            "stateful", "http://dep", config, 5, clock=lambda: self.now, wall_clock=lambda: NOW,
            transport=httpx.MockTransport(self._backend),
        )

    def teardown(self):
        if hasattr(self, "loop"):
            self.loop.close()
        process.reset_for_tests()

    def _backend(self, request):
        self.calls += 1
        self.requests.append(request)
        if isinstance(self.next, Exception):
            raise self.next
        return self.next

    def _do(self, outcome, deadline=None):
        self.model.tick(self.now)
        before = self.calls
        expect_call = self.model.state != "open"
        self.next = outcome
        try:
            self.loop.run_until_complete(call(self.client, "GET", "/", timeout=1.0, deadline=deadline))
        except DependencyUnavailable:
            pass
        assert (self.calls - before == 1) == expect_call, "en abierto nunca sale una llamada"
        if not expect_call:
            return
        if isinstance(outcome, Exception) or outcome.status_code >= 500:
            self.model.failure(self.now)
        else:
            self.model.success()

    @rule()
    def call_ok(self):
        self._do(httpx.Response(200))

    @rule(status=st.sampled_from([500, 502, 503]))
    def call_fail_5xx(self, status):
        self._do(httpx.Response(status))

    @rule()
    def call_fail_connection(self):
        self._do(httpx.ConnectError("x"))

    @rule()
    def call_timeout(self):
        self._do(httpx.ReadTimeout("x"))

    @rule(status=st.sampled_from([400, 404, 409, 422]))
    def call_4xx(self, status):
        self._do(httpx.Response(status))

    @rule(delta=st.floats(0, 150))
    def tick(self, delta):
        self.now += delta

    @rule(ms=st.integers(1, 5000))
    def call_with_deadline(self, ms):
        count = len(self.requests)
        self._do(httpx.Response(200), NOW + timedelta(milliseconds=ms))
        if len(self.requests) > count:
            read = self.requests[-1].extensions["timeout"]["read"]
            assert read <= ms / 1000 and read <= 1.0

    @invariant()
    def same_state(self):
        if not hasattr(self, "model"):
            return
        self.model.tick(self.now)
        expected = {"closed": CircuitState.CLOSED, "open": CircuitState.OPEN, "half": CircuitState.HALF_OPEN}[self.model.state]
        assert self.client.breaker.state is expected


Machine.TestCase.settings = settings(stateful_step_count=200, deadline=None)
TestBreaker = pytest.mark.common(Machine.TestCase)
