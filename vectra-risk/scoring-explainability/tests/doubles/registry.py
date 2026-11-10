"""Doble de U3 (decision-registry): `POST /v1/entries` con idempotencia y `GET /v1/entries` (proyeccion `explanation`).

Sigue a `vectra_registry.append`: la misma llave con los mismos campos de negocio devuelve el ack original; con otro contenido,
409. Un cuerpo que no valida (`cause` y `local_cause` a la vez, BR-U0-38) es 422 y un tipo que el scope no permite (`local_cause` sin
`cause`), 403 (candidata de U03-T03: BR-U7-16 decia 403 para el primero).
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from vectra_contracts.catalog import EntryType, Outcome
from vectra_contracts.models.explanation import Explanation, RegistryAck
from vectra_contracts.models.registry import RegistryEntryIn

from doubles import Faults, Recorder, problem


@dataclass
class Stored:
    seq: int
    entry: RegistryEntryIn
    ack: RegistryAck


def _business(entry: RegistryEntryIn) -> str:
    return json.dumps(
        entry.model_dump(mode="json", exclude={"occurred_at", "correlation_id"}), sort_keys=True
    )


class RegistryDouble:
    """`faults.delay` retrasa la respuesta; con `commit_first` la entrada ya se confirmo (el registro confirma tarde, P-U7-03)."""

    def __init__(self) -> None:
        self.stored: list[Stored] = []
        self._by_key: dict[str, Stored] = {}
        self.recorder = Recorder()
        self.faults = Faults()
        self.commit_first = True
        self.delay_first_n: int | None = (
            None  # el retraso solo afecta a las primeras N escrituras (None = todas)
        )
        self._posts = 0
        self.commit_then_fail: int = 0  # confirma y responde 503: el reintento debe recuperar el ack original
        self.reject_status: int | None = None  # un 4xx fijo, sin confirmar
        self.ignore_case_filter = False  # un registro defectuoso: devuelve la entrada aunque sea de otro caso
        self.app = Starlette(
            routes=[Route("/v1/entries", self._append, methods=["POST"]), Route("/v1/entries", self._list)]
        )

    @property
    def calls(self) -> list:  # type: ignore[type-arg]
        return self.recorder.calls

    def entries(self, entry_type: EntryType | None = None) -> list[Stored]:
        return [item for item in self.stored if entry_type is None or item.entry.entry_type == entry_type]

    def keys(self, entry_type: EntryType) -> list[str]:
        return [str(item.entry.idempotency_key) for item in self.entries(entry_type)]

    def _commit(self, entry: RegistryEntryIn) -> Stored:
        existing = self._by_key.get(str(entry.idempotency_key))
        if existing is not None:
            return existing
        seq = len(self.stored) + 1
        stored = Stored(
            seq, entry, RegistryAck(registry_entry_id=str(seq), seq=seq, recorded_at=datetime.now(UTC))
        )
        self.stored.append(stored)
        self._by_key[str(entry.idempotency_key)] = stored
        return stored

    async def _append(self, request: Request) -> Response:
        call = await self.recorder.record(request)
        if self.reject_status is not None:
            return JSONResponse(
                problem(self.reject_status, "validation_error"), status_code=self.reject_status
            )
        try:
            entry = RegistryEntryIn.model_validate_json(call.body)
        except ValidationError:
            return JSONResponse(problem(422, "validation_error"), status_code=422)
        payload: Any = entry.payload
        if entry.entry_type not in (EntryType.RECOMMENDATION, EntryType.FAIL_CLOSED) or (
            entry.entry_type == EntryType.FAIL_CLOSED
            and (payload.local_cause is not None or payload.escalated_at is not None)
        ):
            return JSONResponse(problem(403, "forbidden"), status_code=403)
        existing = self._by_key.get(str(entry.idempotency_key))
        if existing is not None and _business(existing.entry) != _business(entry):
            return JSONResponse(problem(409, "conflict_state"), status_code=409)
        if self.faults.fail_next > 0:
            self.faults.fail_next -= 1
            return Response(status_code=503)
        stored: Stored | None = None
        self._posts += 1
        if self.commit_first:
            stored = self._commit(entry)
        if self.faults.delay and (self.delay_first_n is None or self._posts <= self.delay_first_n):
            await asyncio.sleep(self.faults.delay)
        if self.faults.status is not None:
            return Response(status_code=self.faults.status)
        stored = stored or self._commit(entry)
        if self.commit_then_fail > 0:
            self.commit_then_fail -= 1
            return Response(status_code=503)
        return Response(stored.ack.model_dump_json(), media_type="application/json")

    async def _list(self, request: Request) -> Response:
        await self.recorder.record(request)
        if self.faults.status is not None:
            return Response(status_code=self.faults.status)
        if self.faults.delay:
            await asyncio.sleep(self.faults.delay)
        query = request.query_params
        items: list[dict[str, Any]] = []
        for stored in self.stored:
            entry = stored.entry
            if entry.entry_type != EntryType.RECOMMENDATION or str(stored.seq) != query.get("seq"):
                continue
            if not self.ignore_case_filter and str(entry.case_id) != query.get("case_id"):
                continue
            payload: Any = entry.payload
            items.append(
                {
                    "seq": stored.seq,
                    "case_id": str(entry.case_id),
                    "model_version_id": entry.model_version_id,
                    "payload": {"explanation": payload.explanation.model_dump(mode="json")},
                }
            )
        return JSONResponse({"items": items, "next_seq_after": None})


def seed_recommendation(
    registry: RegistryDouble, case_id: UUID, explanation: Explanation, model_version_id: str | None = None
) -> Stored:
    """Una entrada `recommendation` ya escrita por scoring (lo que lee F23)."""
    from vectra_contracts.models.features import MonitoringLabels
    from vectra_contracts.models.registry import Actor, RecommendationPayload

    from doubles.samples import NOW, POLICY, vector

    payload = RecommendationPayload(
        score="0.1000",
        confidence="0.9000",
        outcome=Outcome.FAVORABLE,
        reasons=[],
        feature_vector=vector(),
        feature_vector_hash="0" * 64,
        evaluated_at=NOW,
        monitoring_labels=MonitoringLabels(
            sexo="no_informado",
            rango_edad="36-45",
            region="andina",
            estrato="no_informado",
            banda_capacidad_pago="20_30",
        ),
        explanation=explanation,
        received_at=NOW,
        channel="web",
        attempt=1,
        first_evaluation=True,
    )
    entry = RegistryEntryIn(
        entry_type=EntryType.RECOMMENDATION,
        case_id=case_id,
        model_version_id=model_version_id or explanation.model_version_id,
        policy_version_id=POLICY,
        actor=Actor(kind="service", id="scoring-service"),
        occurred_at=NOW,
        correlation_id="0" * 32,
        idempotency_key=uuid4(),
        payload=payload,
    )
    return registry._commit(entry)  # noqa: SLF001
