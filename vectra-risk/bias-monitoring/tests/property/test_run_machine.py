"""PBT-U9-05 (stateful, PBT-06): secuencias de 1 a 40 corridas del CronJob contra los dobles de U3, U4, Keycloak y el Pushgateway.

Comandos: cambiar el nivel de disparidad de una version (modelo y decisiones humanas), retirar una version, avanzar el dia,
reactivar una version congelada (cumplimiento) y correr, con lecturas fallidas, Keycloak sin token, agregador atrasado,
invalidas por encima y por debajo del 1 % y respuestas de `freeze` (exito, 409, 5xx, timeout, 403) por version.
El modelo en memoria predice cada llamada; los invariantes de la BLM §3 se comprueban despues de cada corrida.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

from builders import ensure_batch
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
from scenario import clear, make_deps, seed
from vectra_bias.run import run_once
from world import World, freeze_record

VERSIONS = ("va", "vb")
LEVELS = st.sampled_from(["low", "high"])
FAULTS = st.sampled_from(["none"] * 6 + ["registry", "keycloak", "lag", "invalid_high", "invalid_low"])
MODES = st.sampled_from(["ok"] * 5 + ["409", "5xx", "timeout", "403"])
FAILING = {"5xx": 4, "timeout": 4, "403": 1}  # llamadas que hace `freeze_client` hasta rendirse
REASON = {
    "registry": "lectura",
    "keycloak": "token",
    "lag": "agregador_atrasado",
    "invalid_high": "invalidas",
}
HISTORY_DAYS = 4
MAX_RUNS = 40
FOREIGN = ("otro-job", "freeze-vz")
STATS = {"examples": 0, "runs": 0, "max_runs": 0}


class RunMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        ensure_batch()
        self.world = World()
        self.now = datetime(2026, 11, 9, 0, 0, tzinfo=UTC)
        self.level = dict.fromkeys(VERSIONS, "low")
        self.human = dict.fromkeys(VERSIONS, "low")
        self.active = dict.fromkeys(VERSIONS, True)
        self.window_start = dict.fromkeys(VERSIONS, date(1970, 1, 1))
        self.frozen: set[str] = set()
        self.groups: set[str] = set()
        self.runs = 0
        self.last_success: str | None = None
        self.world.governance.on_freeze = self._frozen_hook
        self.world.pushgateway.put_group(*FOREIGN)
        self._rewrite()

    # --- estado del mundo ---------------------------------------------------------------------------------------------

    def _frozen_hook(self, version: str) -> None:
        self.world.registry.freezes.append(freeze_record(version, self.now))

    def _rewrite(self) -> None:
        for v in VERSIONS:
            clear(self.world, v)
            if self.active[v]:
                seed(
                    self.world,
                    v,
                    self.now.date(),
                    days=HISTORY_DAYS,
                    model=self.level[v],
                    human=self.human[v],
                )

    @property
    def today(self) -> date:
        return self.now.date()

    # --- comandos -----------------------------------------------------------------------------------------------------

    @rule(v=st.sampled_from(VERSIONS), model=LEVELS, human=LEVELS)
    def set_level(self, v, model, human):
        self.active[v] = True
        self.level[v], self.human[v] = model, human
        self._rewrite()

    @rule(v=st.sampled_from(VERSIONS))
    def retire(self, v):
        self.active[v] = False
        self._rewrite()

    @precondition(lambda self: self.now.date() < date(2026, 11, 12))
    @rule()
    def next_day(self):
        self.now = datetime.combine(self.today + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        self._rewrite()

    @rule(v=st.sampled_from(VERSIONS))
    def reactivate(self, v):
        """Cumplimiento reactiva una version congelada: la ventana empieza al dia siguiente (BR-U9-08)."""
        if v not in self.frozen:
            return
        record = [r for r in self.world.registry.freezes if r["model_version_id"] == v][-1]
        record["resolutions"].append({"action": "reactivar", "recorded_at": self.now.isoformat()})
        self.world.governance.frozen.discard(v)
        self.frozen.discard(v)
        self.window_start[v] = max(self.window_start[v], self.today + timedelta(days=1))

    @precondition(lambda self: self.runs < MAX_RUNS)
    @rule(fault=FAULTS, mode_a=MODES, mode_b=MODES)
    def run(self, fault, mode_a, mode_b):
        world = self.world
        self.now += timedelta(minutes=15)
        # La razon de inválidas (BR-U9-09) tiene en el denominador las entradas de los rangos «despues» mas las no atribuibles:
        # sin ningun rango de version (ninguna evaluada, o todas reactivadas hoy) una sola no atribuible es el 100 %.
        has_ranges = any(self.active[v] and self.today >= self.window_start[v] for v in VERSIONS)
        if fault == "invalid_low" and not has_ranges:
            fault = "invalid_high"
        modes = {"va": mode_a, "vb": mode_b}
        self._apply(fault, modes)
        calls_before = {v: len(world.governance.freeze_calls(v)) for v in VERSIONS}
        total_before = len(world.governance.calls)
        registry_before = len(world.registry.calls)
        outcome = asyncio.run(run_once(make_deps(world, lambda: self.now)))
        self._revert(fault)
        self.runs += 1

        evaluated = [v for v in VERSIONS if self.active[v]]
        precalc_failure = fault in REASON
        attempted = (
            []
            if precalc_failure
            else [v for v in evaluated if self.level[v] == "high" and self.today >= self.window_start[v]]
        )
        succeeded = {
            v for v in attempted if modes[v] in ("ok", "409") or (modes[v] == "ok" and v in self.frozen)
        }
        failed = [v for v in attempted if v not in succeeded]
        complete = not precalc_failure and not failed

        # La llamada a `freeze`: solo a las versiones del modelo que cumplen la regla, nunca con datos parciales ni de `humana`.
        expected_calls = {
            v: (1 if v in succeeded else FAILING[modes[v]]) if v in attempted else 0 for v in VERSIONS
        }
        for v in VERSIONS:
            made = len(world.governance.freeze_calls(v)) - calls_before[v]
            assert made == expected_calls[v], (v, fault, modes[v], made)
            assert made <= 4  # como maximo 4 llamadas por version y corrida
        assert len(world.governance.calls) - total_before == sum(expected_calls.values())
        if precalc_failure:
            assert len(world.governance.calls) == total_before
        if fault == "keycloak":
            assert len(world.registry.calls) == registry_before  # sin token no hay ni lectura
        for v in succeeded:
            if modes[v] == "ok":
                self.frozen.add(v)
        assert world.governance.frozen == self.frozen

        # Resultado y publicacion: `last_success` avanza <=> la corrida fue completa; el grupo `run` siempre.
        assert outcome.report.complete is complete
        assert world.pushgateway.value("run", "vectra_bias_last_run_ok") == str(int(complete))
        stamp = str(int(self.now.timestamp()))
        if complete:
            self.last_success = stamp
        assert world.pushgateway.value("success", "vectra_bias_last_success_timestamp") == self.last_success
        reason = REASON.get(fault) or ("freeze" if failed else None)
        assert outcome.report.failure_reason == reason
        if reason:
            assert world.pushgateway.value("run", "vectra_bias_last_run_failure", reason=reason) == "1"

        # Ciclo de vida del grupo `freeze-<v>` (revision del Infrastructure Design de U10, 2026-10-10).
        if not precalc_failure:
            for v in VERSIONS:
                if v in attempted:
                    (self.groups.discard if v in succeeded else self.groups.add)(v)
                elif complete:
                    self.groups.discard(v)
        present = {n.removeprefix("freeze-") for n in world.pushgateway.names() if n.startswith("freeze-")}
        assert present == self.groups
        assert ("job", FOREIGN[0]) in {k[0] for k in world.pushgateway.groups}  # ningun DELETE toca otro job

    def _apply(self, fault, modes):
        w = self.world
        w.registry.status = 503 if fault == "registry" else None
        w.keycloak.down = fault == "keycloak"
        w.registry.lag_seconds = 45 * 60 if fault == "lag" else 0
        w.registry.unattributable.clear()
        if fault == "invalid_high":
            w.registry.unattributable[self.today] = 10**7
        elif fault == "invalid_low":
            w.registry.unattributable[self.today] = 1
        for v, mode in modes.items():
            if mode in FAILING:
                w.governance.script[v] = [mode] * 8
            elif mode == "409":
                w.governance.script[v] = ["409"]

    def _revert(self, fault):
        w = self.world
        w.registry.status = None
        w.keycloak.down = False
        w.governance.script.clear()

    def teardown(self) -> None:
        STATS["examples"] += 1
        STATS["runs"] += self.runs
        STATS["max_runs"] = max(STATS["max_runs"], self.runs)

    # --- invariantes de toda la historia ------------------------------------------------------------------------------

    @invariant()
    def only_freeze_is_called_on_governance_and_only_reads_on_the_registry(self):
        for c in self.world.governance.calls:
            assert c.method == "POST" and c.path.endswith("/freeze")
        for c in self.world.registry.calls:
            assert (c.method, c.path) in {
                ("GET", "/v1/monitoring/freezes"),
                ("POST", "/v1/monitoring/daily:query"),
            }

    @invariant()
    def no_delete_touches_a_group_that_is_not_a_freeze_group_of_the_bias_job(self):
        for c in self.world.pushgateway.calls:
            if c.method == "DELETE":
                assert c.path.startswith("/metrics/job/bias-monitoring/group/freeze-")


RunMachine.TestCase.settings = settings(max_examples=120, stateful_step_count=80, deadline=None)
TestRunMachine = RunMachine.TestCase


def test_the_machine_explored_sequences_of_many_runs():
    print(f"run_machine_stats={STATS}")
    assert STATS["examples"] >= 100
    assert STATS["max_runs"] >= 10
