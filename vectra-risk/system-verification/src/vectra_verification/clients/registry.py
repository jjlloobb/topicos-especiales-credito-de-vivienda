"""Cliente de lectura del registro de decisiones (U12 Paso 5; INF-U12-03; NFR-U12-02, NFR-U12-50): `GET /v1/entries` con el token de `verification-reader`.

Por `kubectl port-forward` a **un pod** de `decision-registry-service` en `vectra-app` (`through_port_forward`). Pagina hasta agotar (`next_seq_after`) y devuelve proyecciones
validadas (`MetricsProjection`, `FreezeProjection`): una respuesta 2xx que no valida es un error. Los parametros de consulta son los de `contracts/openapi/decision-registry-service.yaml`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Final, Literal
from uuid import UUID

import httpx
from pydantic import ValidationError
from vectra_contracts.models.api import Page
from vectra_contracts.models.registry import FreezeProjection, FrozenResolutionProjection, MetricsProjection

from vectra_verification.clients._api import ApiError, error_of
from vectra_verification.clients.k8s_read import Forward, K8sRead

NAMESPACE: Final = "vectra-app"
SELECTOR: Final = "app.kubernetes.io/name=decision-registry-service"
REMOTE_PORT: Final = 8080  # `decision-registry/chart/values.yaml`: `port`
MAX_PAGES: Final = 10_000
Projection = Literal["metrics", "monitoring_freezes"]


class RegistryClient:
    def __init__(
        self, base_url: str, bearer: Callable[[], str], *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._bearer = bearer
        self._http = httpx.Client(base_url=base_url, transport=transport, timeout=30.0)
        self.requests_sent = 0
        self.forward: Forward | None = None

    @classmethod
    @contextmanager
    def through_port_forward(
        cls, k8s: K8sRead, bearer: Callable[[], str], *, transport: httpx.BaseTransport | None = None
    ) -> Iterator[RegistryClient]:
        with k8s.port_forward(NAMESPACE, SELECTOR, REMOTE_PORT) as forward:
            client = cls(forward.base_url, bearer, transport=transport)
            client.forward = forward
            try:
                yield client
            finally:
                client.close()

    def close(self) -> None:
        self._http.close()

    def _page(self, params: dict[str, str | int]) -> httpx.Response:
        self.requests_sent += 1
        try:
            response = self._http.get(
                "/v1/entries", params=params, headers={"Authorization": f"Bearer {self._bearer()}"}
            )
        except httpx.HTTPError as error:
            if self.forward is not None:
                self.forward.check()  # el reenvio cayo: error claro con el pod y el namespace, sin reintentar
            raise ApiError(0, f"transport_{type(error).__name__}") from None
        if not response.is_success:
            raise error_of(response)
        return response

    def _entries[T](
        self,
        projection: Projection,
        page_model: type[Page[T]],
        *,
        case_id: UUID | None,
        entry_type: str | None,
        recorded_from: datetime | None,
        recorded_to: datetime | None,
        seq_after: int | None,
        limit: int,
    ) -> list[T]:
        params: dict[str, str | int] = {"projection": projection, "limit": limit}
        if case_id is not None:
            params["case_id"] = str(case_id)
        if entry_type is not None:
            params["entry_type"] = entry_type
        if recorded_from is not None:
            params["recorded_from"] = recorded_from.isoformat()
        if recorded_to is not None:
            params["recorded_to"] = recorded_to.isoformat()
        cursor = seq_after
        items: list[T] = []
        for _ in range(MAX_PAGES):
            if cursor is not None:
                params["seq_after"] = cursor
            response = self._page(params)
            try:
                page = page_model.model_validate_json(response.content)
            except ValidationError:
                raise ApiError(response.status_code, "invalid_response") from None
            items.extend(page.items)
            if page.next_seq_after is None:
                return items
            if cursor is not None and page.next_seq_after <= cursor:
                raise ApiError(response.status_code, "pagination_stuck")
            cursor = page.next_seq_after
        raise ApiError(0, "pagination_unbounded")

    def metrics(
        self,
        *,
        case_id: UUID | None = None,
        entry_type: str | None = None,
        recorded_from: datetime | None = None,
        recorded_to: datetime | None = None,
        seq_after: int | None = None,
        limit: int = 1000,
    ) -> list[MetricsProjection]:
        """Proyeccion `metrics` (`registry:read:metrics`)."""
        return self._entries(
            "metrics",
            Page[MetricsProjection],
            case_id=case_id,
            entry_type=entry_type,
            recorded_from=recorded_from,
            recorded_to=recorded_to,
            seq_after=seq_after,
            limit=limit,
        )

    def freezes(
        self,
        *,
        recorded_from: datetime | None = None,
        recorded_to: datetime | None = None,
        seq_after: int | None = None,
        limit: int = 1000,
    ) -> list[FreezeProjection | FrozenResolutionProjection]:
        """Proyeccion `monitoring_freezes` (`registry:read:monitoring`): entradas `freeze` y `frozen_resolution`."""
        return self._entries(
            "monitoring_freezes",
            Page[FreezeProjection | FrozenResolutionProjection],
            case_id=None,
            entry_type=None,
            recorded_from=recorded_from,
            recorded_to=recorded_to,
            seq_after=seq_after,
            limit=limit,
        )

    def freezes_raw(
        self,
        *,
        recorded_from: datetime | None = None,
        recorded_to: datetime | None = None,
        seq_after: int | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """`monitoring_freezes` **sin validar** (U12-T03): el oraculo de RT-2 valida el `context_package` campo por campo y nombra el que falta; con `freezes` un paquete incompleto es `invalid_response` y no dice cual."""
        params: dict[str, str | int] = {"projection": "monitoring_freezes", "limit": limit}
        if recorded_from is not None:
            params["recorded_from"] = recorded_from.isoformat()
        if recorded_to is not None:
            params["recorded_to"] = recorded_to.isoformat()
        cursor = seq_after
        items: list[dict[str, Any]] = []
        for _ in range(MAX_PAGES):
            if cursor is not None:
                params["seq_after"] = cursor
            response = self._page(params)
            try:
                body = response.json()
                page_items, following = list(body["items"]), body.get("next_seq_after")
            except (ValueError, KeyError, TypeError):
                raise ApiError(response.status_code, "invalid_response") from None
            items.extend(item for item in page_items if isinstance(item, dict))
            if following is None:
                return items
            if cursor is not None and following <= cursor:
                raise ApiError(response.status_code, "pagination_stuck")
            cursor = int(following)
        raise ApiError(0, "pagination_unbounded")
