"""Entradas validas de U0 (`RegistryEntryIn`) de los 9 tipos de negocio, para las pruebas del servicio.

Los payloads se construyen con los modelos de U0 (`vectra_contracts.models`), asi que si el contrato cambia, estas entradas dejan
de validar y la prueba lo dice. `occurred_at` y los momentos de negocio salen de `NOW`, que las pruebas fijan con un reloj.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from strategies.domain import explanation
from vectra_contracts.models.registry import RegistryEntryIn

NOW = datetime(2026, 11, 8, 12, 0, 0, tzinfo=UTC)
CASE = uuid.UUID("00000000-0000-4000-8000-0000000000c1")
LABELS = {"sexo": "F", "rango_edad": "26-35", "region": "andina", "estrato": "3", "banda_capacidad_pago": "lt_20"}
USER = {"kind": "user", "id": "u-1", "role": "analista", "acr": "mfa", "auth_time": "2026-11-08T11:30:00Z"}
CRO = {"kind": "user", "id": "u-cro", "role": "cro", "acr": "mfa", "auth_time": "2026-11-08T11:30:00Z"}
SERVICE = {"kind": "service", "id": "scoring-service"}
SYSTEM = {"kind": "system", "id": "bias-monitoring-job"}
GOVERNANCE_TYPES = ("model_event", "policy_event", "data_source_event", "freeze", "frozen_resolution")
BUSINESS_TYPES = ("recommendation", "fail_closed", "human_decision", "explanation_view", *GOVERNANCE_TYPES)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def disparity(version: str) -> dict[str, Any]:
    return {
        "population": "modelo",
        "model_version_id": version,
        "window_from": "2026-10-01",
        "window_to": "2026-10-31",
        "attributes": [],
    }


def freeze_package(version: str = "mv-1") -> dict[str, Any]:
    return {
        "model_version_id": version,
        "computed_at": iso(NOW),
        "threshold_pp": "0.0500",
        "n_min": 30,
        "window_days": 30,
        "schedule": "diario",
        "stale_after_s": 3600,
        "library_version": "1.0.0",
        "window_start": "2026-10-01",
        "before": "sin_datos",
        "after": disparity(version),
        "last_7_days": "sin_datos",
        "trigger_attribute": "sexo",
        "implicated": [],
        "affected_volume": {"total": 10, "favorable": 4},
        "truncated": False,
        "data_sources": [],
        "initial_disparity": {"attributes": []},
    }


def payload_for(entry_type: str, now: datetime = NOW, **over: Any) -> dict[str, Any]:
    match entry_type:
        case "recommendation":
            data: dict[str, Any] = {
                "score": "0.5000", "confidence": "0.9000", "outcome": "favorable", "reasons": ["vis"],
                "feature_vector": {"features": {}}, "feature_vector_hash": "a" * 64, "evaluated_at": iso(now),
                "monitoring_labels": LABELS, "explanation": json.loads(explanation().model_dump_json()),
                "received_at": iso(now - timedelta(seconds=2)), "channel": "web", "attempt": 1, "first_evaluation": True,
            }  # fmt: skip
        case "fail_closed":
            data = {"cause": "timeout", "retryable": True, "attempt": 1}
        case "human_decision":
            data = {
                "decision": "sigue", "final_outcome": "favorable", "used_factors": ["ninguno"], "justification": "",
                "explanation_viewed_before": True, "decided_at": iso(now), "recommendation_entry_id": "1",
            }  # fmt: skip
        case "explanation_view":
            data = {"viewed_at": iso(now), "recommendation_entry_id": "1"}
        case "model_event":
            data = {"event": "registrado", "details": {"version": "mv-1"}}
        case "policy_event":
            data = {"event": "propuesta", "policy_version_id": "pv-1"}
        case "data_source_event":
            data = {"event": "propuesta", "source_id": "ds-1"}
        case "freeze":
            data = {"freeze_id": "fr-1", "frozen_at": iso(now), "context_package": freeze_package()}
        case "frozen_resolution":
            data = {"action": "reactivar", "justification": "La disparidad se corrigio con los datos nuevos."}
        case _:
            raise KeyError(entry_type)
    return {**data, **over}


def actor_for(entry_type: str) -> dict[str, Any]:
    match entry_type:
        case "recommendation" | "fail_closed":
            return SERVICE
        case "freeze":
            return SYSTEM
        case "human_decision" | "explanation_view":
            return USER
        case _:
            return CRO


def entry_dict(
    entry_type: str,
    *,
    key: uuid.UUID | None = None,
    now: datetime = NOW,
    occurred_at: datetime | None = None,
    case_id: uuid.UUID | None | str = "default",
    actor: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    **over: Any,
) -> dict[str, Any]:
    if case_id == "default":
        case_id = CASE if entry_type in ("recommendation", "fail_closed", "human_decision", "explanation_view") else None
    data: dict[str, Any] = {
        "entry_type": entry_type,
        "actor": actor or actor_for(entry_type),
        "occurred_at": iso(occurred_at or now),
        "correlation_id": uuid.uuid4().hex,
        "idempotency_key": str(key or uuid.uuid4()),
        "payload": payload if payload is not None else payload_for(entry_type, now),
    }
    if case_id is not None:
        data["case_id"] = str(case_id)
    if entry_type in ("recommendation", "freeze", "frozen_resolution", "model_event"):
        data["model_version_id"] = "mv-1"
    if entry_type == "policy_event":
        data["policy_version_id"] = "pv-1"
    return {**data, **over}


def make(entry_type: str, **kwargs: Any) -> RegistryEntryIn:
    return RegistryEntryIn.model_validate_json(json.dumps(entry_dict(entry_type, **kwargs)))
