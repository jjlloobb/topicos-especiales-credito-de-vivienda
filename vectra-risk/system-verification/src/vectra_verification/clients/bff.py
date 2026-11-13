"""Cliente del BFF de la consola (U12 Paso 5; INF-U12-03; BR-U12-03) por el gateway: `/api/console/...` con el token de un usuario sintetico.

`resolve_frozen` llama antes a `guard.check_reactivation` (solo dentro de la seccion `rt2`) y exige una sesion de step-up (MFA reciente): lo usa U12-T03.
"""

from __future__ import annotations

import ssl
from typing import Protocol
from uuid import UUID

import httpx
from vectra_contracts.catalog import CaseState
from vectra_contracts.models.api import CaseDetail, DecisionIn, DecisionRef, Page, SessionInfo
from vectra_contracts.models.application import CaseSummary
from vectra_contracts.models.governance import (
    FrozenResolutionIn,
    ModelApprovalIn,
    ModelRegistration,
    ModelVersion,
    ModelVersionDetail,
    ValidationRun,
)

from vectra_verification import guard
from vectra_verification.clients._api import ApiClient, ApiError, RunTag
from vectra_verification.guard import Environment

BASE = "/api/console"


class Session(Protocol):
    """Lo que el cliente necesita de una sesion (la implementa `oidc.UserSession`)."""

    user: str
    step_up: bool

    def bearer(self) -> str: ...

    def refresh(self) -> None: ...


class BffClient(ApiClient):
    def __init__(
        self,
        environment: Environment,
        session: Session,
        tag: RunTag,
        *,
        transport: httpx.BaseTransport | None = None,
        verify: ssl.SSLContext | bool = True,
    ) -> None:
        super().__init__(environment, session.bearer, tag, transport=transport, verify=verify)
        self.session = session

    def me(self) -> SessionInfo:
        return self._parse(self._send("GET", f"{BASE}/me"), SessionInfo)

    def list_cases(
        self, state: CaseState | None = None, page: int = 1, page_size: int = 20
    ) -> Page[CaseSummary]:
        params: dict[str, str | int] = {"page": page, "page_size": page_size}
        if state is not None:
            params["state"] = state.value
        return self._parse(self._send("GET", f"{BASE}/cases", params=params), Page[CaseSummary])

    def get_case(self, case_id: UUID | str) -> CaseDetail:
        return self._parse(self._send("GET", f"{BASE}/cases/{case_id}"), CaseDetail)

    def record_explanation_view(self, case_id: UUID | str) -> None:
        self._send("POST", f"{BASE}/cases/{case_id}/explanation-views")

    def record_decision(self, case_id: UUID | str, decision: DecisionIn) -> DecisionRef:
        return self._parse(self._send("POST", f"{BASE}/cases/{case_id}/decision", body=decision), DecisionRef)

    def _require_step_up(self) -> None:
        """Las escrituras con MFA (`register_model`, `start_validation`, `approve_model`, `resolve_frozen`) exigen una sesion de step-up: sin ella no sale ninguna solicitud."""
        if not self.session.step_up:
            raise ApiError(0, "step_up_required")

    def list_models(self, state: str | None = None, page: int = 1, page_size: int = 50) -> Page[ModelVersion]:
        """`GET /api/console/models` (`ingeniero_riesgo`, `cro`, `cumplimiento`); `state` es un estado de `ModelState`."""
        params: dict[str, str | int] = {"page": page, "page_size": page_size}
        if state is not None:
            params["state"] = state
        return self._parse(self._send("GET", f"{BASE}/models", params=params), Page[ModelVersion])

    def get_model(self, model_version_id: str) -> ModelVersionDetail:
        return self._parse(self._send("GET", f"{BASE}/models/{model_version_id}"), ModelVersionDetail)

    def register_model(self, registration: ModelRegistration) -> ModelVersion:
        """`POST /api/console/models`: solo `ingeniero_riesgo`, con MFA (U4 puede responder 422 `validation_error` con `invalid_params`, o 409)."""
        self._require_step_up()
        return self._parse(self._send("POST", f"{BASE}/models", body=registration), ModelVersion)

    def start_validation(self, model_version_id: str) -> ValidationRun:
        self._require_step_up()
        return self._parse(self._send("POST", f"{BASE}/models/{model_version_id}/validations"), ValidationRun)

    def approve_model(self, model_version_id: str, approval: ModelApprovalIn) -> None:
        """`POST .../approval` (204): solo `cro`, con MFA, distinto de quien registro (si no, 409)."""
        self._require_step_up()
        self._send("POST", f"{BASE}/models/{model_version_id}/approval", body=approval)

    def resolve_frozen(self, model_version_id: str, resolution: FrozenResolutionIn, section: str) -> None:
        """Reactivar, descartar o investigar un modelo congelado: solo dentro de `rt2`, con step-up y por el BFF. Si la barrera se niega no sale ninguna solicitud."""
        guard.check_reactivation(self._environment, section)
        self._require_step_up()
        self._send("POST", f"{BASE}/models/{model_version_id}/frozen-resolution", body=resolution)


__all__ = ["BffClient", "Session"]
