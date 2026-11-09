"""Lectura de objetos de MinIO (F31 `validation-datasets` y el model-store) con AWS Signature V4, solo `GET` y solo `httpx`.

La credencial es `minio-validation` (`validation-readonly`, U1): lectura. Se firma a mano para no sumar `boto3` a la imagen.
"""

import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit

import httpx

from vectra_validation.errors import ValidationJobError

REGION = "us-east-1"
SERVICE = "s3"
TIMEOUT = 30.0
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def signing_key(secret: str, day: str) -> bytes:
    return _hmac(_hmac(_hmac(_hmac(("AWS4" + secret).encode("utf-8"), day), REGION), SERVICE), "aws4_request")


class S3Reader:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        now: "type[datetime] | None" = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._host = urlsplit(endpoint).netloc
        self._access_key = access_key
        self._secret_key = secret_key
        self._now = now or datetime
        self._client = httpx.Client(timeout=httpx.Timeout(TIMEOUT), transport=transport)

    def _authorization(self, path: str, stamp: str) -> dict[str, str]:
        day = stamp[:8]
        headers = {"host": self._host, "x-amz-content-sha256": _EMPTY_SHA256, "x-amz-date": stamp}
        names = ";".join(sorted(headers))
        canonical = "\n".join(
            ["GET", path, "", *(f"{k}:{headers[k]}" for k in sorted(headers)), "", names, _EMPTY_SHA256]
        )
        scope = f"{day}/{REGION}/{SERVICE}/aws4_request"
        to_sign = "\n".join(["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode("utf-8")).hexdigest()])
        signature = hmac.new(signing_key(self._secret_key, day), to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            "x-amz-content-sha256": _EMPTY_SHA256,
            "x-amz-date": stamp,
            "Authorization": f"AWS4-HMAC-SHA256 Credential={self._access_key}/{scope}, SignedHeaders={names}, Signature={signature}",
        }

    def read(self, uri: str) -> bytes:
        """Los bytes de `s3://bucket/clave`. Cualquier respuesta distinta de 200 es `object_unreadable` (sin la URI ni el cuerpo)."""
        parts = urlsplit(uri)
        if parts.scheme != "s3" or not parts.netloc or not parts.path.strip("/"):
            raise ValidationJobError("object_uri_invalid")
        path = quote(f"/{parts.netloc}{parts.path}", safe="/-_.~")
        stamp = self._now.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        try:
            response = self._client.get(f"{self._endpoint}{path}", headers=self._authorization(path, stamp))
        except httpx.HTTPError as error:
            raise ValidationJobError("object_store_unavailable") from error
        if response.status_code != 200:
            raise ValidationJobError("object_unreadable")
        return response.content
