"""El mundo de las pruebas con navegador de la consola (U10-T04; solo pruebas): los dobles de U10-T02 con datos para recorrer **todas** las
vistas que entran (bandeja con casos en cada estado, detalle `listo`, `en_sincronizacion`, `decidido` y `modelo_congelado`, un caso con
`<script>` en `free_text`, uno con baja confianza, uno `revision_requerida`, modelos con informe, un congelamiento con paquete completo y una
celda `muestra_insuficiente`). Cada dato se construye y **valida** con los modelos de U0 (`bff_builders.check`).

`populate_demo(doubles)` parte de `bff_world.populate` y reemplaza lo que hace falta; el doble de `case` pasa a:
- filtrar `GET /v1/cases` por `state` (como el servicio real: por omision la bandeja pide todos menos `vencido`);
- pasar un caso `listo` a `decidido` al recibir su decision (para que la recarga de la SPA vea la decision registrada).
"""

import json
from typing import Any

import bff_builders as b
import bff_world
from bff_doubles import Call, Doubles, Reply, problem
from vectra_contracts.models import api as api_models
from vectra_contracts.models import monitoring as mon
from vectra_contracts.outcome import read_wire

CASE_LISTO = bff_world.CASE_LISTO
CASE_NO_DISPONIBLE = bff_world.CASE_NO_DISPONIBLE
CASE_DECIDIDO = bff_world.CASE_DECIDIDO
CASE_ANONIMIZADO = bff_world.CASE_ANONIMIZADO
CASE_SYNC = b.uuid_of(5)
CASE_FROZEN = b.uuid_of(6)
CASE_REVISION = b.uuid_of(7)
CASE_VENCIDO = b.uuid_of(8)
CASE_LOW_CONFIDENCE = b.uuid_of(9)
SCRIPT_TEXT = "<script>alert(1)</script>"
FREEZE_MODEL = "mv-congelado"
FREEZE_ID = f"freeze-{FREEZE_MODEL}"
FACTORS = ("installment_to_income", "loan_to_value")


def explanation(version: str = "mv-activo") -> dict[str, Any]:
    return {
        "model_version_id": version,
        "method": "shap",
        "shap_vector": [
            {
                "feature_id": FACTORS[0],
                "value": {"type": "decimal", "value": "0.3200"},
                "contribution": "0.1200",
            },
            {
                "feature_id": FACTORS[1],
                "value": {"type": "decimal", "value": "0.8000"},
                "contribution": "-0.0450",
            },
        ],
        "base_value": "0.0500",
        "narrative": "La relación cuota/ingreso aumenta el riesgo; el valor del inmueble frente al crédito lo reduce.",
        "narrative_generator": "template:v1",
        "feature_dictionary_version": "d1",
        "posthoc_notice": "Aproximación posterior a la decisión del modelo.",
        "factuality_check": "passed",
    }


def recommendation(case_id: str, outcome: str, reasons: tuple[str, ...]) -> dict[str, Any]:
    return {
        "kind": "recommendation",
        "case_id": case_id,
        "outcome": outcome,
        "score": "0.7312",
        "confidence": "0.8800",
        "reasons": list(reasons),
        "model_version_id": "mv-activo",
        "policy_version_id": "pv-1",
        "feature_vector_hash": "a" * 64,
        "evaluated_at": b.ts(),
        "registry_entry_id": "7",
        "explanation": explanation(),
    }


def detail(
    case_id: str,
    state: str,
    *,
    outcome: str | None = None,
    reasons: tuple[str, ...] = (),
    credit: str | None = None,
    free_text: str | None = None,
    frozen_after: bool = False,
    decision: dict[str, Any] | None = None,
    display: str = "A. G.",
) -> dict[str, Any]:
    data = b.case_detail(case_id, state, entry_id="7" if outcome else None)
    data["applicant_display"] = display
    if free_text is not None:
        data["application"]["free_text"] = free_text
    if outcome is not None:
        data["outcome"] = outcome
        data["score"] = "0.7312"
        data["recommendation"] = recommendation(case_id, outcome, reasons)
    if credit is not None:
        data["credit_status"] = credit
    data["model_frozen_after_recommendation"] = frozen_after
    if decision is not None:
        data["decision"] = decision
    read_wire(
        api_models.CaseDetail, json.dumps(data, default=str)
    )  # `CaseDetail` contiene `Recommendation`: solo se lee con `read_wire` (U00-T03)
    return data


def decision_view(
    decision: str = "sigue", final: str = "desfavorable", justification: str = ""
) -> dict[str, Any]:
    return {
        "decision": decision,
        "final_outcome": final,
        "used_factors": ["ninguno"],
        "justification": justification,
        "decided_at": b.ts(),
        "decided_by": "user-1",
    }


def disparity_result(version: str) -> dict[str, Any]:
    """Un atributo con una celda suficiente y una `muestra_insuficiente` (BR-U10-15)."""
    return {
        "population": "modelo",
        "model_version_id": version,
        "window_from": "2026-10-13",
        "window_to": "2026-11-11",
        "attributes": [
            {
                "attribute": "region",
                "cells": [
                    {"group": "andina", "band": "20_30", "n": 120, "rate": "0.6200", "status": "suficiente"},
                    {
                        "group": "caribe",
                        "band": "20_30",
                        "n": 4,
                        "rate": None,
                        "status": "muestra_insuficiente",
                    },
                ],
                "bands": [
                    {
                        "band": "20_30",
                        "difference": "0.0800",
                        "extreme_pair": ["andina", "caribe"],
                        "n_band": 124,
                    }
                ],
                "aggregate": "0.6000",
                "population_difference_partial": False,
            }
        ],
    }


def freeze_record() -> dict[str, Any]:
    """El paquete completo de BR-U10-13: `before` y `last_7_days` en `sin_datos`, `after` y la disparidad de validacion con celdas."""
    base = b.freeze_record(FREEZE_MODEL)
    package = base["context_package"]
    package["after"] = disparity_result(FREEZE_MODEL)
    package["implicated"] = [
        {
            "attribute": "region",
            "freeze_lower_limit": "0.0500",
            "bands": [{"band": "20_30", "difference": "0.0800", "extreme_pair": ["andina", "caribe"]}],
        }
    ]
    package["data_sources"] = [{"ds_id": "ds-1", "name": "Buró alterno", "state": "aprobada"}]
    package["initial_disparity"] = {"attributes": disparity_result(FREEZE_MODEL)["attributes"]}
    package["affected_volume"] = {"total": 124, "favorable": 80}
    return b.check(mon.FreezeRecord, base)


def validation_report() -> dict[str, Any]:
    return {
        "auc_roc": "0.8120",
        "auc_target": "0.7500",
        "auc_meets_target": True,
        "initial_disparity": {"attributes": disparity_result("mv-activo")["attributes"]},
        "sync_check": {
            "passed": True,
            "predictor_version": "p1",
            "explainer_version": "e1",
            "samples_checked": 50,
        },
        "dataset_ref": "dataset-2026-q3",
        "disclaimer": "Informe de validación: mide y alerta, no certifica.",
    }


def populate_demo(doubles: Doubles) -> None:
    bff_world.populate(doubles)
    case, gov, bias = doubles.case, doubles.governance, doubles.bias
    case.details = {
        CASE_LISTO: detail(
            CASE_LISTO,
            "listo",
            outcome="favorable",
            reasons=("score_sobre_corte",),
            credit="no_integrado",
            free_text=SCRIPT_TEXT,
        ),
        CASE_NO_DISPONIBLE: b.case_detail(CASE_NO_DISPONIBLE, "no_disponible", entry_id=None),
        CASE_DECIDIDO: detail(
            CASE_DECIDIDO,
            "decidido",
            outcome="desfavorable",
            reasons=("score_bajo_corte",),
            credit="en_estudio",
            decision=decision_view(),
            display="B. P.",
        ),
        CASE_ANONIMIZADO: b.case_detail(CASE_ANONIMIZADO, "no_disponible", anonymized=True, entry_id=None),
        CASE_SYNC: b.case_detail(CASE_SYNC, "en_sincronizacion", entry_id=None),
        CASE_FROZEN: detail(
            CASE_FROZEN,
            "modelo_congelado",
            outcome="favorable",
            reasons=("score_sobre_corte",),
            frozen_after=True,
            display="C. R.",
        ),
        CASE_REVISION: detail(
            CASE_REVISION, "listo", outcome="revision_requerida", reasons=("baja_confianza",), display="D. M."
        ),
        CASE_VENCIDO: b.case_detail(CASE_VENCIDO, "vencido", entry_id=None),
        CASE_LOW_CONFIDENCE: detail(
            CASE_LOW_CONFIDENCE,
            "listo",
            outcome="desfavorable",
            reasons=("score_bajo_corte", "baja_confianza"),
            display="E. S.",
        ),
    }
    case.responders[("GET", "/v1/cases")] = lambda c: _list_cases(case.details, c)
    case.responders[("POST", "/v1/cases/{id}/decision")] = lambda c: _decide(case.details, c)
    gov.models["mv-activo"] = b.model_version("mv-activo", "activo", validation_report=validation_report())
    gov.responders[("GET", "/v1/models")] = lambda c: _list_models(gov.models, c)
    bias.responders[("GET", "/v1/freezes")] = lambda c: (200, [b.freeze_summary(FREEZE_MODEL)])
    bias.responders[("GET", "/v1/freezes/{id}")] = lambda c: (200, freeze_record())


def _list_cases(details: dict[str, dict[str, Any]], call: Call) -> Reply:
    wanted = {s for value in call.query.get("state", []) for s in value.split(",")}
    items = [
        b.case_summary(d["case_id"], d["state"]) | {"applicant_display": d["applicant_display"]} | _scored(d)
        for d in details.values()
        if not wanted or d["state"] in wanted
    ]
    return 200, b.page(items)


def _scored(data: dict[str, Any]) -> dict[str, Any]:
    return {k: data[k] for k in ("outcome", "score") if k in data}


def _decide(details: dict[str, dict[str, Any]], call: Call) -> Reply:
    case_id = call.params["id"]
    body = call.json()
    found = details.get(case_id)
    if found is None:
        return 404, problem(404, "not_found")
    found["state"] = "decidido"
    found["decision"] = decision_view(body["decision"], body["final_outcome"], body["justification"]) | {
        "used_factors": body["used_factors"]
    }
    return 200, b.decision_ref(case_id)


def _list_models(models: dict[str, dict[str, Any]], call: Call) -> Reply:
    """La lista trae `ModelVersion`, sin el informe de validacion (que solo trae `get_model`, `ModelVersionDetail`)."""
    wanted = {s for value in call.query.get("state", []) for s in value.split(",")}
    items = [
        {k: v for k, v in m.items() if k != "validation_report"}
        for m in models.values()
        if not wanted or m["state"] in wanted
    ]
    return 200, b.page(items)
