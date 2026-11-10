"""Cliente S3 del model-store (F47): lee los **bytes** de un paquete de U5 por URI `s3://model-store/<model_version_id>/<archivo>`.

- Firma AWS Signature V4 a mano (solo `GET`, `httpx`), como el lector del Job (`vectra_validation/s3.py`): no suma `boto3` a la
  imagen. La credencial es `minio-governance` (`governance-readonly`, U1): lectura.
- Timeouts de `httpx` (conexion 1 s, total 5 s; NFR-U4-25) y, con `https`, la CA interna (`VECTRA_CA_BUNDLE`); nunca se
  desactiva la verificacion.
- Contrato de errores (`PackageStore`): un objeto que no existe (o una URI fuera del bucket del model-store) es
  `FileNotFoundError`; cualquier otra cosa (red, timeout, 403, 5xx) es `DependencyUnavailable` (503 del contrato, nunca un 500 sin
  cuerpo). El mensaje no lleva la URI ni el cuerpo de la respuesta.
"""

import hashlib
import hmac
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from urllib.parse import quote, urlsplit

import httpx
from vectra_common.errors import DependencyUnavailable

REGION: Final = "us-east-1"
SERVICE: Final = "s3"
BUCKET: Final = "model-store"
TIMEOUT: Final = 5.0  # NFR-U4-25
CONNECT_TIMEOUT: Final = 1.0
EMPTY_SHA256: Final = hashlib.sha256(b"").hexdigest()


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def signing_key(secret: str, day: str) -> bytes:
    return _hmac(_hmac(_hmac(_hmac(("AWS4" + secret).encode("utf-8"), day), REGION), SERVICE), "aws4_request")


def sigv4_headers(
    method: str, host: str, path: str, access_key: str, secret_key: str, stamp: str, payload: bytes = b""
) -> dict[str, str]:
    """Las cabeceras de una solicitud firmada con SigV4 (`path` ya codificado). `stamp` es `YYYYMMDDTHHMMSSZ`."""
    day = stamp[:8]
    digest = hashlib.sha256(payload).hexdigest() if payload else EMPTY_SHA256
    headers = {"host": host, "x-amz-content-sha256": digest, "x-amz-date": stamp}
    names = ";".join(sorted(headers))
    canonical = "\n".join([method, path, "", *(f"{k}:{headers[k]}" for k in sorted(headers)), "", names, digest])
    scope = f"{day}/{REGION}/{SERVICE}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode("utf-8")).hexdigest()])
    signature = hmac.new(signing_key(secret_key, day), to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "x-amz-content-sha256": digest,
        "x-amz-date": stamp,
        "Authorization": f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={names}, Signature={signature}",
    }


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


class S3PackageStore:
    """`PackageStore` sobre el MinIO del model-store. Un `httpx.Client` por proceso; seguro entre hilos."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        *,
        bucket: str = BUCKET,
        verify: bool | str = True,
        timeout: float = TIMEOUT,
        transport: httpx.BaseTransport | None = None,
        stamp: Callable[[], str] = _utc_stamp,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._host = urlsplit(endpoint).netloc
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket = bucket
        self._stamp = stamp
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT), verify=verify, transport=transport
        )

    def read(self, uri: str) -> bytes:
        parts = urlsplit(uri)
        key = parts.path.lstrip("/")
        if parts.scheme != "s3" or parts.netloc != self._bucket or not key or any(p in ("", ".", "..") for p in key.split("/")):
            raise FileNotFoundError  # fuera del model-store: no se lee con esta credencial
        path = quote(f"/{self._bucket}/{key}", safe="/-_.~")
        headers = sigv4_headers("GET", self._host, path, self._access_key, self._secret_key, self._stamp())
        try:
            response = self._client.get(f"{self._endpoint}{path}", headers=headers)
        except httpx.HTTPError as error:
            raise DependencyUnavailable() from error
        if response.status_code == 404:
            raise FileNotFoundError
        if response.status_code != 200:
            raise DependencyUnavailable()
        return response.content

    def close(self) -> None:
        self._client.close()
