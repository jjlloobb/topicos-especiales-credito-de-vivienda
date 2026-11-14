"""Conductor de decisiones (U12 Paso 6; BR-U12-03, BR-U12-06; business-logic-model §2.2; NFR-U12-10, NFR-U12-50; PBT-U12-03).

`analista-1` y `analista-2` deciden por el BFF, con el login OIDC de `clients.oidc`. La **mezcla** es una funcion pura, sin E/S (`plan`): `(DecisionMix, hechos del caso, generador con semilla) -> DecisionIn o
«no decide»`, mas si abre la explicacion; el azar es `random.Random(seed)`, nunca el generador global. Semantica de `DecisionMix` (P-6 (a)): en `favorable` y `desfavorable`, `sigue` con probabilidad
`p_sigue / (p_sigue + p_se_aparta)` (si ambas son 0, `sigue`) y si no `se_aparta`; en `revision_requerida`, con probabilidad `p_resuelve_revision` decide `resuelve_revision` (con `final_outcome` al azar) y si no
**no decide** y el caso se cuenta como visto (en la seccion `decisions` vale 1). `used_factors`: con probabilidad `p_factors`, una muestra sin repeticion de 1 a 20 `feature_id` del `shap_vector` del caso;
si no, exactamente `["ninguno"]`. Cumple BR-U0-35 (la decision coincide con el `outcome`), BR-U0-36 (justificacion de 20 a 2 000 caracteres en `se_aparta` y `resuelve_revision`) y BR-U8-16.

Recorrido: por cada caso `listo` de la bandeja que este entre los pedidos, `get_case`; con probabilidad `p_view`, `record_explanation_view`; despues `record_decision`. Los casos se reparten entre los dos
analistas de forma determinista (por posicion en la bandeja). Un 409 y un 422 se cuentan y el conductor sigue con el caso siguiente: **nunca** se reintenta con otro contenido. Un 401 renueva el token **una vez** y repite
la misma solicitud; un segundo 401 es un error. El gateway limita `/api/console` a 20/s por usuario: el conductor espacia sus solicitudes con el reloj inyectado, por debajo de ese limite.

Volumen de demostracion (BR-U12-06): `run_decisions` compone la seccion `decisions` (el simulador `normal` con `DEMO_VOLUME` = 2 000 casos y despues el conductor sobre los `case_ids` del `RunReport`) y devuelve
los dos informes y un registro con **el numero enviado y el decidido**. Se corre con el modelo de referencia activo y antes de RT-2: ese orden es el de la CLI (Paso 13) y el del operador (Paso 18).
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Concatenate, Final

import httpx
from vectra_contracts.catalog import CaseState, Decision, FinalOutcome, Outcome
from vectra_contracts.models.api import CaseDetail, DecisionIn

from vectra_verification import guard
from vectra_verification.clients._api import ApiError, RunTag
from vectra_verification.clients.bff import BffClient, Session
from vectra_verification.clock import Clock
from vectra_verification.guard import Environment
from vectra_verification.simulator import DEFAULT_RATE, RunReport, SimulationResult, Simulator, pace

ANALYSTS: Final = ("analista-1", "analista-2")
DRIVER_RATE: Final = 10.0  # por usuario; el gateway limita `/api/console` a 20/s
DEMO_VOLUME: Final = 2000  # BR-U12-06
CASE_SIZE_CASES: Final = 1000  # los primeros 1 000, en orden de envio, son los de `CASE-SIZE`
MAX_FACTORS: Final = 20
PAGE_SIZE: Final = 100
MAX_PAGES: Final = 1000
JUSTIFICATION: Final = "Decision de prueba de la verificacion del sistema: sin datos del solicitante."


class DriverError(Exception):
    """El conductor no puede seguir (por ejemplo, un segundo 401 tras renovar el token)."""


@dataclass(frozen=True)
class DecisionMix:
    p_view: float
    p_sigue: float
    p_se_aparta: float
    p_resuelve_revision: float
    p_factors: float
    seed: int

    def __post_init__(self) -> None:
        for name in ("p_view", "p_sigue", "p_se_aparta", "p_resuelve_revision", "p_factors"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"mix_probability_out_of_range:{name}")


DEMO_MIX: Final = DecisionMix(
    p_view=0.5, p_sigue=0.8, p_se_aparta=0.2, p_resuelve_revision=1.0, p_factors=0.7, seed=20261101
)


@dataclass(frozen=True)
class CaseFacts:
    """Lo unico del caso que la mezcla necesita: el `outcome` de la recomendacion y los `feature_id` de su `shap_vector`."""

    outcome: Outcome
    feature_ids: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    open_explanation: bool
    decision: DecisionIn | None  # `None`: no decide (revision requerida que la mezcla no resuelve)


def facts_of(detail: CaseDetail) -> CaseFacts | None:
    recommendation = detail.recommendation
    if recommendation is None:
        return None
    return CaseFacts(
        recommendation.outcome, tuple(c.feature_id for c in recommendation.explanation.shap_vector)
    )


def _factors(mix: DecisionMix, facts: CaseFacts, rng: random.Random) -> list[str]:
    if facts.feature_ids and rng.random() < mix.p_factors:
        return rng.sample(list(facts.feature_ids), rng.randint(1, min(MAX_FACTORS, len(facts.feature_ids))))
    return ["ninguno"]


def plan(mix: DecisionMix, facts: CaseFacts, rng: random.Random) -> Plan:
    """La mezcla pura (PBT-U12-03). El orden de las extracciones del generador es fijo: explicacion, decision, factores."""
    open_explanation = rng.random() < mix.p_view
    if facts.outcome is Outcome.REVISION_REQUERIDA:
        if not rng.random() < mix.p_resuelve_revision:
            return Plan(open_explanation, None)
        final = rng.choice([FinalOutcome.FAVORABLE, FinalOutcome.DESFAVORABLE])
        decision = Decision.RESUELVE_REVISION
    else:
        favorable = facts.outcome is Outcome.FAVORABLE
        same = FinalOutcome.FAVORABLE if favorable else FinalOutcome.DESFAVORABLE
        opposite = FinalOutcome.DESFAVORABLE if favorable else FinalOutcome.FAVORABLE
        weight = mix.p_sigue + mix.p_se_aparta
        follows = True if weight == 0 else rng.random() < mix.p_sigue / weight
        decision, final = (Decision.SIGUE, same) if follows else (Decision.SE_APARTA, opposite)
    justification = "" if decision is Decision.SIGUE else JUSTIFICATION
    return Plan(
        open_explanation,
        DecisionIn(
            decision=decision,
            final_outcome=final,
            used_factors=_factors(mix, facts, rng),
            justification=justification,
        ),
    )


@dataclass(frozen=True)
class DriverReport:
    """domain-entities §2. Solo `case_id` y conteos: ningun dato del solicitante."""

    cases_seen: int
    decisions_by_kind: dict[str, int]
    views: int
    conflicts_409: int
    invalid_422: int
    started_at: datetime
    finished_at: datetime
    errors_by_status: dict[str, int]
    not_decided: int  # revision requerida que la mezcla no resolvio
    not_ready: int  # pedidos que la bandeja `listo` no tenia
    decided_case_ids: tuple[str, ...]


class Driver:
    def __init__(
        self,
        environment: Environment,
        sessions: dict[str, Session],
        tag: RunTag,
        clock: Clock,
        mix: DecisionMix,
        *,
        transport: httpx.BaseTransport | None = None,
        rate: float = DRIVER_RATE,
    ) -> None:
        guard.check_known(environment)
        if set(sessions) != set(ANALYSTS):
            raise DriverError("sessions_must_be_the_two_analysts")
        self._clock = clock
        self._mix = mix
        self._rate = rate
        self._clients = {
            user: BffClient(environment, sessions[user], tag, transport=transport) for user in ANALYSTS
        }
        self._sessions = sessions
        self._last: dict[str, float | None] = {user: None for user in ANALYSTS}

    def close(self) -> None:
        for client in self._clients.values():
            client.close()

    def _call[**P, T](
        self, user: str, method: Callable[Concatenate[BffClient, P], T], *args: P.args, **kwargs: P.kwargs
    ) -> T:
        """Una solicitud con el ritmo por usuario; un 401 renueva el token una vez y repite **la misma** solicitud."""
        client = self._clients[user]
        for attempt in (1, 2):
            self._last[user] = pace(self._clock, self._rate, self._last[user])
            try:
                return method(client, *args, **kwargs)
            except ApiError as error:
                if error.status != 401:
                    raise
                if attempt == 2:
                    raise DriverError("unauthorized_after_refresh") from None
                self._sessions[user].refresh()
        raise DriverError("unreachable")  # pragma: no cover

    def _ready(self, wanted: set[str] | None) -> list[str]:
        ids: list[str] = []
        for page in range(1, MAX_PAGES + 1):
            listing = self._call(ANALYSTS[0], BffClient.list_cases, CaseState.LISTO, page, PAGE_SIZE)
            ids.extend(str(item.case_id) for item in listing.items)
            if len(listing.items) < PAGE_SIZE:
                break
        return [i for i in ids if wanted is None or i in wanted]

    def run(self, case_ids: Sequence[str] | None = None) -> DriverReport:
        """Decide los casos `listo` de la bandeja (solo los de `case_ids` si se dan)."""
        started = self._clock.now()
        rng = random.Random(self._mix.seed)  # noqa: S311 - mezcla reproducible con semilla, no criptografia
        wanted = set(case_ids) if case_ids is not None else None
        ready = self._ready(wanted)
        decisions: Counter[str] = Counter()
        errors: Counter[str] = Counter()
        decided: list[str] = []
        views = conflicts = invalid = not_decided = 0
        for index, case_id in enumerate(ready):
            user = ANALYSTS[index % len(ANALYSTS)]
            try:
                detail = self._call(user, BffClient.get_case, case_id)
                facts = facts_of(detail)
                if facts is None:
                    errors["no_recommendation"] += 1
                    continue
                chosen = plan(self._mix, facts, rng)
                if chosen.open_explanation:
                    self._call(user, BffClient.record_explanation_view, case_id)
                    views += 1
                if chosen.decision is None:
                    not_decided += 1
                    continue
                decision = chosen.decision
                self._call(user, BffClient.record_decision, case_id, decision)
                decisions[decision.decision.value] += 1
                decided.append(case_id)
            except ApiError as error:
                if error.status == 409:
                    conflicts += 1
                elif error.status == 422:
                    invalid += 1
                else:
                    errors[str(error.status) if error.status else (error.code or "error")] += 1
        return DriverReport(
            cases_seen=len(ready),
            decisions_by_kind=dict(decisions),
            views=views,
            conflicts_409=conflicts,
            invalid_422=invalid,
            started_at=started,
            finished_at=self._clock.now(),
            errors_by_status=dict(errors),
            not_decided=not_decided,
            not_ready=len(wanted) - len(ready) if wanted is not None else 0,
            decided_case_ids=tuple(decided),
        )


@dataclass(frozen=True)
class DecisionsRecord:
    """Lo que U12-T04 escribira en el manifiesto: el numero enviado y el decidido, y los primeros 1 000 `case_ids` (en orden de envio) para `CASE-SIZE`."""

    sent: int
    accepted: int
    decided: int
    case_size_case_ids: tuple[str, ...]


@dataclass(frozen=True)
class DecisionsResult:
    simulation: SimulationResult
    driver: DriverReport
    record: DecisionsRecord


def default_volume(environment: Environment) -> int:
    """2 000 en kind; en staging la barrera lo baja a 100 (`guard.STAGING_MAX_DECISIONS`)."""
    guard.check_known(environment)
    return DEMO_VOLUME if environment.name == guard.KIND.name else guard.STAGING_MAX_DECISIONS


def run_decisions(
    simulator: Simulator,
    driver: Driver,
    seed: int,
    *,
    volume: int | None = None,
    rate: float = DEFAULT_RATE,
    environment: Environment,
    settle: Callable[[RunReport], None] | None = None,
) -> DecisionsResult:
    """La seccion `decisions`: simulador `normal` y despues el conductor sobre los `case_ids` del `RunReport`. Con el modelo de referencia activo y antes de RT-2.

    `settle` (U12-T04, F-04 de la ronda 1 de U12-T02): un paso entre el simulador y el conductor. El conductor solo decide los casos que ya estan en `listo`; sin esperar, los que siguen `en_evaluacion` quedan
    sin decidir y se cuentan como `not_ready` sin que nadie los vuelva a mirar. La CLI pasa aqui la espera (sondeo con el reloj inyectado hasta que ninguno este `en_evaluacion`, o hasta un plazo)."""
    count = default_volume(environment) if volume is None else volume
    simulation = simulator.run("normal", count, seed, rate=rate, section="decisions")
    report = simulation.report
    if settle is not None:
        settle(report)
    driven = driver.run(report.case_ids)
    record = DecisionsRecord(
        report.sent, report.accepted, len(driven.decided_case_ids), report.case_ids[:CASE_SIZE_CASES]
    )
    return DecisionsResult(simulation, driven, record)
