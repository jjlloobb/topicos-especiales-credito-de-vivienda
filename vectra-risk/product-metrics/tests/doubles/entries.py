"""Constructores de entradas de la proyeccion `metrics` y generadores de Hypothesis (PBT-07 del business-logic-model §3).

Una `Spec` es la descripcion de una `human_decision` en terminos de negocio; `render` la convierte en el item crudo que sirve U3
(la misma forma que `_metrics` de `decision-registry`). Los oraculos de las propiedades cuentan sobre las `Spec`, nunca sobre `compute`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

from hypothesis import strategies as st

DECISIONS = ("sigue", "se_aparta", "resuelve_revision")
OUTCOMES = ("favorable", "desfavorable", "revision_requerida")
CHANNELS = ("web", "app", "manual")
MODELS = ("model-a", "model-b")
FACTOR_SETS = (("ninguno",), ("ingreso",), ("ingreso", "deuda"))
NOW = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)


def stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RecSpec:
    outcome: str = "favorable"
    model: str = "model-a"
    channel: str = "web"
    attempt: int = 1
    first_evaluation: bool = True
    evaluated: datetime = NOW - timedelta(days=1, hours=2)
    elapsed_s: int = 600
    seq: int = 1


@dataclass(frozen=True)
class Spec:
    seq: int
    decided: datetime
    delay_s: int = 60  # `recorded_at - decided_at`; valida si >= -300 (BR-U11-10)
    decision: str = "sigue"
    viewed: bool = True
    factors: tuple[str, ...] = ("ingreso",)
    rec: RecSpec | None = RecSpec()
    flaw: str | None = (
        None  # `decision` desconocida, `role` distinto de analista, `catalog` canal de mas de 40 caracteres (el contrato admite `""`)
    )

    @property
    def valid(self) -> bool:
        """Por definicion de BR-U11-10 (no por `parse_entry`)."""
        return self.flaw is None and self.delay_s >= -300


def render(spec: Spec) -> dict[str, Any]:
    """El item crudo de `GET /v1/entries?projection=metrics` para una `human_decision`."""
    recommendation: dict[str, Any] | None = None
    if spec.rec is not None:
        rec = spec.rec
        recommendation = {
            "seq": rec.seq,
            "outcome": rec.outcome,
            "model_version_id": rec.model,
            "evaluated_at": stamp(rec.evaluated),
            "received_at": stamp(rec.evaluated - timedelta(seconds=rec.elapsed_s)),
            "channel": "x" * 41 if spec.flaw == "catalog" else rec.channel,
            "attempt": rec.attempt,
            "first_evaluation": rec.first_evaluation,
        }
    return {
        "entry_type": "human_decision",
        "case_id": f"00000000-0000-4000-8000-{spec.seq:012d}",
        "recorded_at": stamp(spec.decided + timedelta(seconds=spec.delay_s)),
        "seq": spec.seq,
        "actor_role": "cro" if spec.flaw == "role" else "analista",
        "decision": "desconocida" if spec.flaw == "decision" else spec.decision,
        "final_outcome": "favorable",
        "used_factors": list(spec.factors),
        "explanation_viewed_before": spec.viewed,
        "decided_at": stamp(spec.decided),
        "recommendation_entry_id": str(spec.rec.seq) if spec.rec else "9999",
        "recommendation": recommendation,
    }


def day_at(offset_days: int, hour: int = 12, *, now: datetime = NOW) -> datetime:
    """El momento `hour`:00 UTC de `now.date() - offset_days`."""
    return datetime.combine(
        now.date() - timedelta(days=offset_days), datetime.min.time(), tzinfo=UTC
    ) + timedelta(hours=hour)


def specs_on(
    offset_days: int, count: int, first_seq: int, *, now: datetime = NOW, **changes: Any
) -> list[Spec]:
    base = Spec(seq=0, decided=day_at(offset_days, now=now))
    return [replace(base, seq=first_seq + index, **changes) for index in range(count)]


def us503_specs(first_seq: int = 1, offset_days: int = 1, *, now: datetime = NOW) -> list[Spec]:
    """El ejemplo de US-503 de business-logic-model §3: 10 decisiones, 4 con explicacion vista y factores (2 `sigue`, 1 `se_aparta`,
    1 `resuelve_revision`), 3 vistas con `["ninguno"]` y 3 sin vista: North Star 0,4 con el desglose 2, 1, 1."""
    return [
        *specs_on(offset_days, 2, first_seq, now=now, decision="sigue", viewed=True, factors=("ingreso",)),
        *specs_on(
            offset_days, 1, first_seq + 2, now=now, decision="se_aparta", viewed=True, factors=("deuda",)
        ),
        *specs_on(
            offset_days,
            1,
            first_seq + 3,
            now=now,
            decision="resuelve_revision",
            viewed=True,
            factors=("ingreso", "deuda"),
        ),
        *specs_on(offset_days, 3, first_seq + 4, now=now, viewed=True, factors=("ninguno",)),
        *specs_on(offset_days, 3, first_seq + 7, now=now, viewed=False),
    ]


# --- generadores --------------------------------------------------------------------------------------------------------

moments = st.datetimes(
    min_value=datetime(2026, 1, 1), max_value=datetime(2026, 12, 31, 23, 59, 59), timezones=st.just(UTC)
)


@st.composite
def rec_specs(draw: st.DrawFn) -> RecSpec:
    return RecSpec(
        outcome=draw(st.sampled_from(OUTCOMES)),
        model=draw(st.sampled_from(MODELS)),
        channel=draw(st.sampled_from(CHANNELS)),
        attempt=draw(st.integers(1, 3)),
        first_evaluation=draw(st.booleans()),
        evaluated=NOW,  # se corrige abajo, relativo a la decision
        elapsed_s=draw(st.sampled_from([0, 59, 600, 3599, 3600, 3601, 7200, 90000])),
        seq=draw(st.integers(0, 10_000)),
    )


@st.composite
def spec_lists(draw: st.DrawFn, now: datetime, max_size: int = 60) -> list[Spec]:
    """Decisiones con todas las combinaciones de `decision`, `used_factors`, vista previa, canal, resultado, intento y referencias
    validas o nulas; momentos de negocio de los ultimos ~7 meses con mas peso en los ultimos 40 dias; `recorded_at` hasta 24 h despues;
    algunas con defectos (BR-U11-10)."""
    size = draw(st.integers(0, max_size))
    out: list[Spec] = []
    for seq in range(size):
        seconds = draw(st.one_of(st.integers(0, 40 * 86400), st.integers(0, 230 * 86400)))
        decided = now - timedelta(seconds=seconds)
        rec = draw(st.one_of(st.none(), rec_specs()))
        if rec is not None:
            lag = draw(st.integers(0, 3 * 86400))
            rec = replace(rec, evaluated=decided - timedelta(seconds=lag))
        flaw = draw(st.sampled_from([None] * 12 + ["decision", "role", "catalog", "late"]))
        delay = draw(st.integers(-300, 86400))
        if flaw == "late":
            delay = draw(st.integers(-3600, -301))
            flaw = None
        out.append(
            Spec(
                seq=seq,
                decided=decided,
                delay_s=delay,
                decision=draw(st.sampled_from(DECISIONS)),
                viewed=draw(st.booleans()),
                factors=draw(st.sampled_from(FACTOR_SETS)),
                rec=rec,
                flaw=flaw if rec is not None or flaw != "catalog" else None,
            )
        )
    return out


def month_bounds(now: datetime) -> list[tuple[str, date, date]]:
    """Los 6 meses cerrados anteriores a `now`, del mas viejo al mas nuevo, calculados con `calendar` (no con `compute`)."""
    import calendar

    out: list[tuple[str, date, date]] = []
    year, month = now.year, now.month
    for _ in range(6):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        out.append(
            (
                f"{year:04d}-{month:02d}",
                date(year, month, 1),
                date(year, month, calendar.monthrange(year, month)[1]),
            )
        )
    return out[::-1]
