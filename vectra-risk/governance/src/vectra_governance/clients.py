"""Clientes salientes del servicio: el model-store (F47) y `compare_source` de bias (F25).

- `PackageStore` (F47): lee **bytes** del model-store por URI. Nunca los interpreta como un modelo (BR-U4-06). El cliente
  S3 real es del cableado del servicio (chart, Paso 16); el servicio solo depende de este contrato.
- `SourceComparer` (F25): `POST /v1/source-comparisons` de U9 con `httpx` y timeouts (NFR-U4-25 y el patron de
  `HttpRegistryClient`). U9 todavia no esta en main: las pruebas usan un doble.
"""

from collections.abc import Callable
from typing import Protocol

import httpx
from vectra_common.errors import DependencyUnavailable
from vectra_contracts.models.monitoring import CompareSourceRequest, PrePostReport


class PackageStore(Protocol):
    def read(self, uri: str) -> bytes:
        """Los bytes del objeto, o `FileNotFoundError` si no existe. `DependencyUnavailable` si el store no responde."""
        ...


class SourceComparer(Protocol):
    def compare_source(self, request: CompareSourceRequest) -> PrePostReport:
        """F25: el `PrePostReport` de las tablas de conteo `pre` y `post`. `DependencyUnavailable` si U9 no responde."""
        ...


class HttpSourceComparer:
    """`POST /v1/source-comparisons` de `bias-monitoring-service`. La autenticacion (token de servicio) es del llamador."""

    def __init__(
        self,
        base_url: str,
        token: Callable[[], str],
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._token = token
        self._client = httpx.Client(
            base_url=base_url, timeout=httpx.Timeout(timeout, connect=1.0), transport=transport
        )

    def compare_source(self, request: CompareSourceRequest) -> PrePostReport:
        try:
            response = self._client.post(
                "/v1/source-comparisons",
                content=request.model_dump_json(),
                headers={"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json"},
            )
        except httpx.HTTPError as error:
            raise DependencyUnavailable() from error
        if response.status_code != 200:
            raise DependencyUnavailable()
        return PrePostReport.model_validate_json(response.content)

    def close(self) -> None:
        self._client.close()
