"""Doble de la API KV v2 de la boveda (NFR-U12-04), en proceso: un transporte de `httpx` que cuenta las solicitudes y comprueba montaje, ruta y cabecera."""

import base64

import httpx

TOKEN = "hvs.token-del-operador-0001"
ADDR = "http://vault.test"


class VaultDouble(httpx.BaseTransport):
    def __init__(self, mount: str, secrets: dict[str, dict[str, str]], token: str = TOKEN) -> None:
        self.mount = mount
        self.secrets = secrets
        self.token = token
        self.requests: list[httpx.Request] = []
        self.forbidden: set[str] = set()

    @property
    def count(self) -> int:
        return len(self.requests)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        prefix = f"/v1/{self.mount}/data/"
        if request.headers.get("X-Vault-Token") != self.token or not request.url.path.startswith(prefix):
            return httpx.Response(403, json={"errors": ["permission denied"]})
        path = request.url.path.removeprefix(prefix)
        if path in self.forbidden:
            return httpx.Response(403, json={"errors": ["permission denied"]})
        if path not in self.secrets:
            return httpx.Response(404, json={"errors": []})
        return httpx.Response(200, json={"data": {"data": self.secrets[path], "metadata": {"version": 1}}})


class CountingTransport(httpx.BaseTransport):
    """Un transporte que solo cuenta: sirve para probar «cero solicitudes»."""

    def __init__(self) -> None:
        self.count = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.count += 1
        return httpx.Response(200, json={})


def synthetic_secrets() -> dict[str, dict[str, str]]:
    users = ("ANALISTA_1", "ANALISTA_2", "INGENIERO_1", "CRO_1", "CUMPLIMIENTO_1", "CUMPLIMIENTO_2")
    synthetic = {}
    for user in users:
        synthetic[f"SYNTH_{user}_PASSWORD"] = f"pw-{user.lower()}-Zq81xk"
        synthetic[f"SYNTH_{user}_TOTP_SEED"] = (
            base64.b32encode(f"semilla-{user}".encode()).decode().rstrip("=")
        )
    return {
        "identity/synthetic-users": synthetic,
        "identity/clients/channel-simulator": {
            "private-key": "-----BEGIN PRIVATE KEY-----chan-sim-key",
            "jwks": "{}",
        },
        "identity/clients/verification-reader": {
            "private-key": "-----BEGIN PRIVATE KEY-----ver-reader-key",
            "jwks": "{}",
        },
    }
