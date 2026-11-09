"""Cliente minimo de Vault Transit para la CLI (Paso 11; BR-U3-08, 12; NFR-U3-50; P-U3-08).

Va por `vectra_common.deps.call` (timeout obligatorio, sin `hvac`). La CLI es un proceso `batch`: el breaker se desactiva y cada
invocacion hace pocas llamadas. La llave privada nunca sale de la boveda: aqui solo se pide **firmar** y **leer la llave publica**.
La identidad que llama decide que puede hacer (politicas HCL de `vault-policies/`): firmar solo `registry-checkpoint` y
`registry-archive`; `registry-verify` solo lee la llave publica.
"""

import base64
import json
from typing import Final

from vectra_common import process
from vectra_common.deps import DependencyClient, call
from vectra_contracts.errors import ContractViolation

#: Timeout de cada llamada a la boveda.
TIMEOUT: Final = 5.0
DEFAULT_MOUNT: Final = "transit"
DEFAULT_KEY: Final = "registry-checkpoints"
OK: Final = 200


class ExternalError(Exception):
    """Una dependencia externa (boveda o bucket) respondio con un error que no es de disponibilidad."""


def batch_client(name: str, base_url: str, max_connections: int = 4) -> DependencyClient:
    """Cliente de un proceso batch: sin breaker (NFR-U0-23 (f)). Inicializa el tipo de proceso la primera vez."""
    try:
        process.current()
    except ContractViolation:  # nadie llamo `init` todavia
        process.init("batch")
    return DependencyClient(name, base_url, "disabled", max_connections)


class Transit:
    """Firma y llave publica de una llave Ed25519 del motor Transit."""

    def __init__(
        self, client: DependencyClient, token: str, *, mount: str = DEFAULT_MOUNT, key: str = DEFAULT_KEY
    ) -> None:
        self._client = client
        self._headers = {"X-Vault-Token": token}
        self._mount = mount
        self._key = key

    async def sign(self, message: bytes) -> str:
        """Firma `message` (Ed25519 sin prehash) y devuelve `vault:vN:<base64>`."""
        body = json.dumps({"input": base64.b64encode(message).decode()}).encode()
        response = await call(
            self._client,
            "POST",
            f"/v1/{self._mount}/sign/{self._key}",
            timeout=TIMEOUT,
            headers=self._headers,
            content=body,
        )
        if response.status_code != OK:
            raise ExternalError(f"vault sign: HTTP {response.status_code}")
        signature = response.json()["data"]["signature"]
        if not isinstance(signature, str):
            raise ExternalError("vault sign: respuesta sin firma")
        return signature

    async def public_key(self) -> bytes:
        """Los 32 bytes de la llave publica de la version vigente."""
        response = await call(
            self._client, "GET", f"/v1/{self._mount}/keys/{self._key}", timeout=TIMEOUT, headers=self._headers
        )
        if response.status_code != OK:
            raise ExternalError(f"vault keys: HTTP {response.status_code}")
        data = response.json()["data"]
        latest = str(data["latest_version"])
        return base64.b64decode(data["keys"][latest]["public_key"], validate=True)
