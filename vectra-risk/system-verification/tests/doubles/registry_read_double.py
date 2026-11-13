"""Doble de lectura de `decision-registry-service` (U12-T02): `GET /v1/entries`, validado contra `contracts/openapi/decision-registry-service.yaml` (nombres de parametros) y con los modelos de U0."""

from __future__ import annotations

import json
from typing import Any

import httpx
import yaml
from contract_world import OPENAPI, ContractError
from external_paths import use_u10_doubles

use_u10_doubles()
import bff_builders  # noqa: E402

REGISTRY_SPEC = yaml.safe_load((OPENAPI / "decision-registry-service.yaml").read_text(encoding="utf-8"))
ENTRIES_PARAMS = {p["name"] for p in REGISTRY_SPEC["paths"]["/v1/entries"]["get"]["parameters"]}
CASE = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


def metrics_item(seq: int) -> dict[str, Any]:
    return {
        "entry_type": "recommendation",
        "seq": seq,
        "recorded_at": "2026-11-13T10:00:00Z",
        "case_id": CASE,
        "outcome": "favorable",
        "model_version_id": "mv-1",
    }


def freeze_item(seq: int) -> dict[str, Any]:
    record = bff_builders.freeze_record("mv-1")
    return {
        "seq": seq,
        "freeze_id": f"freeze-{seq}",
        "model_version_id": "mv-1",
        "frozen_at": "2026-11-13T10:00:00Z",
        "recorded_at": "2026-11-13T10:00:01Z",
        "context_package": record["context_package"],
    }


class RegistryReadDouble(httpx.BaseTransport):
    def __init__(self, token: str, items: list[dict[str, Any]]) -> None:
        self.token = token
        self.items = items
        self.requests: list[httpx.Request] = []
        self.corrupt = False

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("Authorization") != f"Bearer {self.token}":
            return httpx.Response(401, json={})
        names = set(request.url.params.keys())
        if request.url.path != "/v1/entries" or not names <= ENTRIES_PARAMS:
            raise ContractError(f"parametros fuera del contrato: {sorted(names - ENTRIES_PARAMS)}")
        limit = int(request.url.params.get("limit", "1000"))
        after = int(request.url.params.get("seq_after", "-1"))
        pending = [i for i in self.items if i["seq"] > after]
        page = pending[:limit]
        nxt = page[-1]["seq"] if len(pending) > limit else None
        if self.corrupt:
            page = [{**page[0], "inesperado": 1}]
        return httpx.Response(
            200,
            content=json.dumps({"items": page, "next_seq_after": nxt}).encode(),
            headers={"content-type": "application/json"},
        )
