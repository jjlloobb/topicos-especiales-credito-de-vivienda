"""Cliente del gateway para la ingesta (U12 Paso 5; INF-U12-03): `POST /api/intake/v1/intake/applications` con el token de `channel-simulator`."""

from __future__ import annotations

from vectra_contracts.models.application import ApplicationIn, CaseRef

from vectra_verification.clients._api import IDEMPOTENCY_PATTERN, ApiClient, ApiError

INTAKE_PATH = "/api/intake/v1/intake/applications"


class GatewayClient(ApiClient):
    def submit_application(self, application: ApplicationIn, idempotency_key: str) -> CaseRef:
        """200 -> `CaseRef`. La `Idempotency-Key` cumple el patron de U8 antes de enviarse; el mismo cuerpo y la misma clave se pueden reenviar tal cual."""
        if not IDEMPOTENCY_PATTERN.fullmatch(idempotency_key):
            raise ApiError(0, "idempotency_key_invalid")
        response = self._send(
            "POST", INTAKE_PATH, body=application, headers={"Idempotency-Key": idempotency_key}
        )
        return self._parse(response, CaseRef)
