"""Cliente de governance por el gateway (F08): `GET /v1/models?state=aprobado` y `POST /v1/models/{id}/activation`.

El token del ingeniero (con MFA, `acr=mfa`) viaja solo en el encabezado `Authorization` de cada solicitud; ningun mensaje de error lo lleva.
"""

import httpx
from vectra_contracts.models.api import Page
from vectra_contracts.models.governance import ActivationIn, ModelVersion

from vectra_promotion.errors import PromotionError


class GovernanceApi:
    def __init__(self, base_url: str, token: str, transport: httpx.BaseTransport | None = None) -> None:
        """`base_url` es la del gateway para F08 (p. ej. `https://host/api/promotion`); sin barra final."""
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            transport=transport,
            timeout=10.0,
        )

    def list_promotable(self) -> list[ModelVersion]:
        """Las versiones `aprobado`, todas las paginas."""
        out: list[ModelVersion] = []
        page = 1
        while True:
            response = self._http.get("/v1/models", params={"state": "aprobado", "page": page})
            if response.status_code != 200:
                raise PromotionError(f"list_failed:{response.status_code}")
            body = Page[ModelVersion].model_validate_json(response.content)
            out.extend(body.items)
            if not body.items or len(out) >= (body.total or 0):
                return out
            page += 1

    def mark_active(self, model_version_id: str, evidence: str) -> None:
        body = ActivationIn(evidence=evidence)
        response = self._http.post(f"/v1/models/{model_version_id}/activation", json=body.model_dump(mode="json"))
        if response.status_code != 204:
            raise PromotionError(f"activation_failed:{response.status_code}")
