"""Respuestas validas de los destinos del BFF, construidas con los modelos de U0 (los de la ruta del destino).

Cada constructor arma un `dict` JSON y lo **valida** con el modelo del contrato antes de devolverlo: si un contrato cambia, el
doble deja de construir y la prueba falla (tarea U10-T02, «Dobles»). Los datos de base se copian de
`contracts/tests/strategies/domain.py` (`application_dict`, `case_detail_data`) y de `bias-monitoring/tests/doubles/world.py`
(`freeze_record`, el paquete minimo).
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from strategies.domain import application_dict
from vectra_contracts.models import api as api_models
from vectra_contracts.models import application as app_models
from vectra_contracts.models import governance as gov
from vectra_contracts.models import monitoring as mon
from vectra_contracts.models import registry as reg
from vectra_contracts.models.application import ApplicationView

NOW = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
SHA = "a" * 64
CASE_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
OTHER_CASE_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
IDENTIFIERS = {
    "full_name": "Ana María Gómez",
    "document_type": "CC",
    "document_number": "1020304050",
    "birth_date": "1985-03-14",
    "phone": "3001234567",
    "email": "ana.gomez@example.com",
    "address": "Cra 7 # 45-10",
    "municipality_code": "11001",
}


def check[M: BaseModel](model: type[M], data: Any) -> Any:
    """Valida `data` con las reglas de JSON del contrato y lo devuelve como `data` (JSON), no como instancia."""
    model.model_validate_json(json.dumps(data, default=str))
    return data


def ts(minutes: int = 0) -> str:
    return (NOW + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def case_summary(case_id: str = CASE_ID, state: str = "listo") -> dict[str, Any]:
    return check(
        app_models.CaseSummary,
        {
            "case_id": case_id,
            "state": state,
            "channel": "web",
            "created_at": ts(),
            "applicant_display": "A. G.",
        },
    )


def case_detail(
    case_id: str = CASE_ID,
    state: str = "listo",
    *,
    anonymized: bool = False,
    final_outcome: str | None = None,
    entry_id: str | None = "7",
) -> dict[str, Any]:
    """`CaseDetail` sin `recommendation` (el detalle de un caso no listo, o uno que no la trae)."""
    raw = {k: v for k, v in application_dict().items() if k in ApplicationView.model_fields}
    data: dict[str, Any] = {
        **case_summary(case_id, state),
        "application": raw,
        "model_frozen_after_recommendation": False,
        "anonymized": anonymized,
        "attempts": 0,
    }
    if entry_id is not None:
        data["recommendation_entry_id"] = entry_id
    if final_outcome is not None:
        data["decision"] = {
            "decision": "sigue",
            "final_outcome": final_outcome,
            "used_factors": [],
            "justification": "",
            "decided_at": ts(),
            "decided_by": "user-1",
        }
    return check(api_models.CaseDetail, data)


def case_identifiers(case_id: str = CASE_ID, *, anonymized: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {"case_id": case_id, "anonymized": anonymized}
    if not anonymized:
        data["identifiers"] = IDENTIFIERS
    return check(app_models.CaseIdentifiers, data)


def case_ref(case_id: str = CASE_ID, state: str = "en_evaluacion") -> dict[str, Any]:
    return check(app_models.CaseRef, {"case_id": case_id, "state": state})


def decision_ref(case_id: str = CASE_ID) -> dict[str, Any]:
    return check(api_models.DecisionRef, {"case_id": case_id, "registry_entry_id": "9", "recorded_at": ts()})


def persistent_failure(case_id: str = CASE_ID) -> dict[str, Any]:
    return check(
        app_models.PersistentFailure,
        {
            "case_id": case_id,
            "channel": "web",
            "created_at": ts(),
            "attempts": 12,
            "last_cause": "timeout",
            "since": ts(),
        },
    )


def applicant_summary(case_id: str = CASE_ID) -> dict[str, Any]:
    return check(
        api_models.ApplicantSummary,
        {
            "case_id": case_id,
            "factors": [{"label_es": "Relación cuota ingreso", "direction": "aumenta"}],
            "posthoc_notice": "Explicación posterior a la decisión.",
            "generated_at": ts(),
        },
    )


def registry_dossier(case_id: str = CASE_ID) -> dict[str, Any]:
    entry = {
        "entry_type": "explanation_view",
        "case_id": case_id,
        "actor": {"kind": "user", "id": "user-1", "role": "analista", "acr": "mfa", "auth_time": ts()},
        "occurred_at": ts(),
        "correlation_id": "0" * 31 + "1",
        "idempotency_key": "11111111-1111-4111-8111-111111111111",
        "payload": {"viewed_at": ts(), "recommendation_entry_id": "7"},
        "seq": 8,
        "prev_hash": SHA,
        "hash": SHA,
        "recorded_at": ts(),
        "contract_version": "1.0.0",
        "canonical": "{}",
    }
    return check(
        reg.RegistryDossier,
        {
            "case_id": case_id,
            "entries": [entry],
            "integrity": {
                "status": "verified",
                "from_checkpoint_seq": 0,
                "to_checkpoint_seq": "head",
                "entries_checked": 1,
            },
            "last_full_verification": None,
        },
    )


def integrity_ref(*, already_active: bool = False) -> dict[str, Any]:
    return check(
        reg.IntegrityCheckRef,
        {"check_id": "chk-1", "mode": "full", "requested_at": ts(), "already_active": already_active},
    )


def integrity_status(status: str = "en_curso") -> dict[str, Any]:
    return check(
        reg.IntegrityCheckStatus,
        {
            "check_id": "chk-1",
            "mode": "full",
            "status": status,
            "progress": {"checked": 1, "total": 10},
            "requested_at": ts(),
        },
    )


def model_version(model_version_id: str = "mv-1", state: str = "activo", **over: Any) -> dict[str, Any]:
    data = {
        "model_version_id": model_version_id,
        "state": state,
        "artifact_uri": "s3://models/a.onnx",
        "artifact_format": "onnx",
        "artifact_sha256": SHA,
        "explainer_uri": "s3://models/e.bin",
        "explainer_sha256": SHA,
        "inference_service": "isvc-0a1b2c3d",
        "manifest_uri": "s3://models/m.json",
        "manifest_sha256": SHA,
        "feature_dictionary_version": "fd-1",
        "data_sources": [],
        "registered_by": "user-2",
        "investigation": False,
        "created_at": ts(),
        "updated_at": ts(),
    }
    return check(gov.ModelVersionDetail, {**data, **over})


def page(items: list[Any]) -> dict[str, Any]:
    return {"items": items, "page": 1, "total": len(items)}


def policy_version(policy_version_id: str = "pv-1", state: str = "propuesta") -> dict[str, Any]:
    return check(
        gov.PolicyVersion,
        {
            "policy_version_id": policy_version_id,
            "state": state,
            "proposed_by": "user-3",
            "created_at": ts(),
            "cutoff": "0.5000",
            "low_confidence_threshold": "0.6000",
            "channel_rules": [],
            "normative": [],
        },
    )


def disparity_result(version: str, population: str = "modelo") -> dict[str, Any]:
    return {
        "population": population,
        "model_version_id": version,
        "window_from": "2026-10-13",
        "window_to": "2026-11-11",
        "attributes": [],
    }


def data_source(ds_id: str = "ds-1", state: str = "en_evaluacion", *, report: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ds_id": ds_id,
        "name": "Buró alterno",
        "description": "Fuente candidata",
        "provides_features": ["bureau_score"],
        "owner": "riesgos",
        "proposed_by": "user-2",
        "state": state,
    }
    if report:
        zero = disparity_result("mv-1")
        data["pre_post_report"] = {
            "source_id": ds_id,
            "pre": zero,
            "post": zero,
            "delta": {"attributes": []},
            "threshold_pp": "5.0000",
            "n_min": 30,
            "truncated": False,
            "disclaimer": "Informe antes y después.",
        }
    return check(gov.DataSource, data)


def validation_run(model_version_id: str = "mv-1") -> dict[str, Any]:
    return check(
        gov.ValidationRun,
        {
            "run_id": "run-1",
            "model_version_id": model_version_id,
            "job_name": "validate-1",
            "mode": "validacion",
            "state": "lanzado",
            "started_at": ts(),
            "deadline_at": ts(30),
        },
    )


def disparity_view(version: str = "mv-1") -> dict[str, Any]:
    return check(
        mon.DisparityView,
        {
            "model_version_id": version,
            "window": {"from_day": "2026-10-13", "to_day": "2026-11-11"},
            "computed_at": ts(),
            "model": disparity_result(version, "modelo"),
            "human": disparity_result(version, "humana"),
            "threshold_pp": "5.0000",
            "n_min": 30,
            "window_days": 30,
            "schedule": "2,17,32,47 * * * *",
            "stale_after_s": 3600,
            "invalid_entries": 0,
            "disclaimer": "Vigilancia de disparidad.",
        },
    )


def freeze_summary(version: str = "mv-1") -> dict[str, Any]:
    return check(
        mon.FreezeSummary,
        {
            "freeze_id": f"freeze-{version}",
            "model_version_id": version,
            "frozen_at": ts(),
            "trigger_attribute": "region",
        },
    )


def freeze_record(version: str = "mv-1") -> dict[str, Any]:
    empty = disparity_result(version)
    package = {
        "model_version_id": version,
        "computed_at": ts(),
        "threshold_pp": "5.0000",
        "n_min": 30,
        "window_days": 30,
        "schedule": "2,17,32,47 * * * *",
        "stale_after_s": 3600,
        "library_version": "1.0.0",
        "window_start": "2026-10-13",
        "before": "sin_datos",
        "after": empty,
        "last_7_days": "sin_datos",
        "trigger_attribute": "region",
        "implicated": [],
        "affected_volume": {"total": 1, "favorable": 1},
        "truncated": False,
        "data_sources": [],
        "initial_disparity": {"attributes": []},
    }
    return check(
        mon.FreezeRecord,
        {
            "freeze_id": f"freeze-{version}",
            "model_version_id": version,
            "frozen_at": ts(),
            "context_package": package,
            "resolutions": [],
        },
    )


def uuid_of(n: int) -> str:
    return str(UUID(int=n))
