"""Tipos compactos de U11 y la validacion entrada por entrada (BR-U11-10; P-U11-04). Sin E/S.

`MetricsProjection` de U0 es un `StrictModel`: validar la pagina entera con el haria que una sola entrada con un `decision`
desconocido tumbara la pagina, y BR-U11-10 exige excluirla y contarla. Por eso el `reader` entrega cada item crudo y aqui cada
uno se convierte en una `Decision` compacta o en una `InvalidEntry` con su `seq` (que va solo al log, nunca a una etiqueta).

NFR-U11-21: este modulo no abre ningun puerto ni hace E/S; el unico acceso HTTP de U11 es `vectra_common.deps` (lo hace cumplir
`.importlinter`: ningun modulo importa `httpx`).
"""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from vectra_contracts.catalog import Decision as DecisionCatalog
from vectra_contracts.catalog import EntryType, Outcome, Role
from vectra_contracts.validation import check_used_factors

from vectra_product import config

#: Codigos enteros del catalogo de U0 (P-U11-04): el orden de las enumeraciones de `vectra_contracts.catalog`.
DECISION_NAMES: Final = tuple(member.value for member in DecisionCatalog)
DECISION_CODES: Final = {name: code for code, name in enumerate(DECISION_NAMES)}
SIGUE: Final = DECISION_CODES[DecisionCatalog.SIGUE.value]
SE_APARTA: Final = DECISION_CODES[DecisionCatalog.SE_APARTA.value]
RESUELVE_REVISION: Final = DECISION_CODES[DecisionCatalog.RESUELVE_REVISION.value]
OUTCOME_NAMES: Final = tuple(member.value for member in Outcome)
OUTCOME_CODES: Final = {name: code for code, name in enumerate(OUTCOME_NAMES)}
REVISION_REQUERIDA: Final = OUTCOME_CODES[Outcome.REVISION_REQUERIDA.value]
ANALISTA: Final = Role.ANALISTA.value
NO_FACTORS: Final = "ninguno"
MANUAL: Final = "manual"
MAX_CHANNEL_LENGTH: Final = 40
NO_OUTCOME: Final = -1

#: Etiquetas de los contadores plegados (`compute.fold`).
DEN: Final = 0  # decisiones atribuibles
NUM: Final = 1  # numerador de la North Star
BRK: Final = 2  # desglose del numerador, por `decision`
SUS: Final = 3  # decisiones `sigue`
VIEW: Final = 4  # decisiones atribuibles con la explicacion vista
#: (etiqueta, canal, resultado, modelo o decision): conteo. Los meses cerrados son un `Counter` de estas llaves.
Key = tuple[int, str, int, str | int]
Counts = Counter[Key]


class Decision:
    """Una `human_decision` valida, con solo los campos de domain-entities §1 y los valores de catalogo como enteros."""

    __slots__ = (
        "attributable",
        "channel",
        "day",
        "decision",
        "elapsed",
        "eval_day",
        "first_evaluation",
        "model",
        "no_factors",
        "outcome",
        "seq",
        "viewed",
    )

    def __init__(
        self,
        seq: int,
        day: int,
        decision: int,
        viewed: bool,
        no_factors: bool,
        attributable: bool = False,
        outcome: int = NO_OUTCOME,
        model: str = "",
        channel: str = "",
        eval_day: int = 0,
        elapsed: float = 0.0,
        first_evaluation: bool = False,
    ) -> None:
        self.seq = seq
        self.day = day  # ordinal del dia UTC de `decided_at`
        self.decision = decision
        self.viewed = viewed
        self.no_factors = no_factors
        self.attributable = attributable  # la recomendacion resuelta no es `null`
        self.outcome = outcome
        self.model = model
        self.channel = channel
        self.eval_day = eval_day  # ordinal del dia UTC de `evaluated_at` de la recomendacion
        self.elapsed = elapsed  # segundos de `received_at` a `evaluated_at`
        self.first_evaluation = first_evaluation

    def __repr__(self) -> str:
        return f"Decision(seq={self.seq}, day={self.day}, decision={self.decision}, attributable={self.attributable})"

    @property
    def standard(self) -> bool:
        """BR-U11-05: `channel` distinto de `manual`, `outcome` distinto de `revision_requerida` y `first_evaluation`."""
        return (
            self.attributable
            and self.channel != MANUAL
            and self.outcome != REVISION_REQUERIDA
            and self.first_evaluation
        )


class InvalidEntry:
    """Una entrada excluida (BR-U11-10). `day` es el dia de `decided_at`, o el de `recorded_at`, o `None` si ninguno se puede leer."""

    __slots__ = ("day", "seq")

    def __init__(self, seq: int, day: int | None) -> None:
        self.seq = seq
        self.day = day

    def __repr__(self) -> str:
        return f"InvalidEntry(seq={self.seq}, day={self.day})"


@dataclass(frozen=True, slots=True)
class Snapshot:
    """La instantanea que `state` entrega a `compute` (P-1, opcion a): decisiones de 35 dias y contadores de los meses."""

    entries: Mapping[int, Decision | InvalidEntry]  # por `seq`
    months: Mapping[int, Counts]  # indice de mes (`ano * 12 + mes - 1`) -> contadores


@dataclass(frozen=True, slots=True)
class Params:
    """Parametros de cumplimiento de `values-product-metrics-policy.yaml` (BR-U11-09; domain-entities §4). `params.py` los carga y
    los valida; viven aqui para que `compute` los use sin importar nada con E/S."""

    noise_floor: float  # F, 0 < F < 1
    noise_sustain_days: int  # S, 1..14
    noise_min_decisions: int  # N >= 30
    target_complete_response: float  # 0..1
    target_origination_hours: float  # > 0
    target_origination_ratio: float  # 0..1
    target_sustained_ratio_month6: float  # 0..1
    target_north_star: float | None  # null o 0..1


class _Reject(Exception):  # noqa: N818 - uso interno
    """La entrada se excluye."""


def _stamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise _Reject
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise _Reject from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _Reject
    return parsed.astimezone(UTC)


def _integer(value: object, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise _Reject
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise _Reject
    return value


def _catalog(value: object, codes: Mapping[str, int]) -> int:
    if not isinstance(value, str) or value not in codes:
        raise _Reject
    return codes[value]


def _text(value: object, maximum: int | None = None) -> str:
    """Un `str` como el contrato de U0: `channel` admite `""` y hasta 40 caracteres; `model_version_id` no tiene tope."""
    if not isinstance(value, str) or (maximum is not None and len(value) > maximum):
        raise _Reject
    return sys.intern(value)


def _used_factors(value: object) -> bool:
    """`True` si es exactamente `["ninguno"]`."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise _Reject
    try:
        check_used_factors(value)
    except ValueError:
        raise _Reject from None
    return value == [NO_FACTORS]


def _decision(seq: int, raw: Mapping[str, Any]) -> Decision:
    if raw.get("entry_type") != EntryType.HUMAN_DECISION.value:
        raise _Reject
    decision = _catalog(raw.get("decision"), DECISION_CODES)
    no_factors = _used_factors(raw.get("used_factors"))
    viewed = _boolean(raw.get("explanation_viewed_before"))
    if (
        raw.get("actor_role") != ANALISTA
    ):  # solo el analista decide (C03); otro rol, o uno fuera del catalogo, se excluye
        raise _Reject
    decided_at = _stamp(raw.get("decided_at"))
    recorded_at = _stamp(raw.get("recorded_at"))
    if decided_at > recorded_at + config.MAX_DECIDED_AHEAD:
        raise _Reject
    if "recommendation" not in raw:
        raise _Reject
    reference = raw["recommendation"]
    if reference is None:  # no atribuible (BR-U11-01): valida, pero no entra en ningun cociente
        return Decision(seq, decided_at.toordinal(), decision, viewed, no_factors)
    if not isinstance(reference, Mapping):
        raise _Reject
    _integer(reference.get("seq"), 0)
    outcome = _catalog(reference.get("outcome"), OUTCOME_CODES)
    model = _text(reference.get("model_version_id"))
    evaluated_at = _stamp(reference.get("evaluated_at"))
    received_at = _stamp(reference.get("received_at"))
    channel = _text(reference.get("channel"), MAX_CHANNEL_LENGTH)
    _integer(reference.get("attempt"), 1)
    first_evaluation = _boolean(reference.get("first_evaluation"))
    return Decision(
        seq,
        decided_at.toordinal(),
        decision,
        viewed,
        no_factors,
        True,
        outcome,
        model,
        channel,
        evaluated_at.toordinal(),
        (evaluated_at - received_at).total_seconds(),
        first_evaluation,
    )


def _best_day(raw: Mapping[str, Any]) -> int | None:
    for name in ("decided_at", "recorded_at"):
        try:
            return _stamp(raw.get(name)).toordinal()
        except _Reject:
            continue
    return None


def parse_entry(seq: int, raw: Mapping[str, Any]) -> Decision | InvalidEntry:
    """Una entrada de la proyeccion `metrics` (item crudo, con su `seq` ya validado por el `reader`) como decision o como invalida.

    Se excluye: un valor fuera del catalogo de U0 (`decision`, `used_factors`, `channel`, `outcome`, `actor_role`), `actor_role`
    distinto de `analista`, `decided_at > recorded_at + 5 min`, un campo obligatorio ausente o con el tipo equivocado (BR-U11-10).
    El resultado no depende de `recorded_at` salvo por ese margen (PBT-U11-03).
    """
    try:
        return _decision(seq, raw)
    except _Reject:
        return InvalidEntry(seq, _best_day(raw))
