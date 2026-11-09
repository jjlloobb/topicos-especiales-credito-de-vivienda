"""Buckets WORM por la API S3 (Paso 11; BR-U3-08, NFR-U3-04; INF-U3-01; F77..F79, F118).

Cliente minimo de S3 con firma SigV4, sobre `vectra_common.deps.call` (sin `boto3`: una dependencia menos en el lock). Sirve igual
para MinIO (kind, por F118) y para el S3 del banco (staging y produccion). Solo implementa lo que usa la CLI: escribir un objeto con
retencion (`COMPLIANCE`), leerlo, listar por prefijo y crear un bucket con object lock (para MinIO de las pruebas).

Los checkpoints del bucket `vectra-registry-checkpoints` son `checkpoints/{checkpoint_seq}.json`: el payload del checkpoint de la
cadena mas su `recorded_at` (la firma lo cubre; `verify` lo compara con la entrada).
"""

import base64
import hashlib
import hmac
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from html import unescape
from typing import Final
from urllib.parse import quote, urlsplit

import httpx
from vectra_common.deps import DependencyClient, call

from vectra_registry.vault import ExternalError

TIMEOUT: Final = 30.0
REGION: Final = "us-east-1"
OK: Final = 200
NOT_FOUND: Final = 404
#: INF-U3-01: 10 anios de retencion en modo `COMPLIANCE`.
RETENTION: Final = timedelta(days=3650)
CHECKPOINT_PREFIX: Final = "checkpoints/"
_EMPTY_SHA256: Final = hashlib.sha256(b"").hexdigest()


def _hmac(key: bytes, text: str) -> bytes:
    return hmac.new(key, text.encode(), hashlib.sha256).digest()


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class S3:
    """Un cliente S3 con path-style (`/bucket/key`), el que aceptan MinIO y el S3 del banco."""

    def __init__(
        self,
        client: DependencyClient,
        base_url: str,
        access_key: str,
        secret_key: str,
        *,
        region: str = REGION,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        parts = urlsplit(base_url)
        default = 443 if parts.scheme == "https" else 80
        self._host = parts.hostname if parts.port in (None, default) else f"{parts.hostname}:{parts.port}"
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        self._clock = clock or (lambda: datetime.now(UTC))

    def _signing_key(self, day: str) -> bytes:
        key = _hmac(("AWS4" + self._secret_key).encode(), day)
        for part in (self._region, "s3", "aws4_request"):
            key = _hmac(key, part)
        return key

    def sign(
        self, method: str, path: str, query: Mapping[str, str], headers: Mapping[str, str], body: bytes, now: datetime
    ) -> dict[str, str]:
        """Las cabeceras de la solicitud con `Authorization` (AWS Signature Version 4)."""
        stamp = _timestamp(now).replace("-", "").replace(":", "").replace(".000", "")
        day = stamp[:8]
        payload = hashlib.sha256(body).hexdigest() if body else _EMPTY_SHA256
        signed = {k.lower(): v.strip() for k, v in headers.items()}
        signed.update({"host": str(self._host), "x-amz-content-sha256": payload, "x-amz-date": stamp})
        names = sorted(signed)
        canonical_query = "&".join(
            f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(query.items())
        )
        canonical = "\n".join(
            [
                method,
                quote(path, safe="/-_.~"),
                canonical_query,
                "".join(f"{name}:{signed[name]}\n" for name in names),
                ";".join(names),
                payload,
            ]
        )
        scope = f"{day}/{self._region}/s3/aws4_request"
        to_sign = "\n".join(["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
        signature = hmac.new(self._signing_key(day), to_sign.encode(), hashlib.sha256).hexdigest()
        out = {k: v for k, v in signed.items() if k != "host"}
        out["Authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self._access_key}/{scope}, SignedHeaders={';'.join(names)}, Signature={signature}"
        )
        return out

    async def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        body: bytes = b"",
    ) -> httpx.Response:
        query = dict(query or {})
        signed = self.sign(method, path, query, headers or {}, body, self._clock())
        url = quote(path, safe="/-_.~")
        if query:
            url += "?" + "&".join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(query.items()))
        return await call(self._client, method, url, timeout=TIMEOUT, headers=signed, content=body or None)

    async def make_bucket(self, bucket: str, *, object_lock: bool = True) -> None:
        """Crea un bucket (con object lock, que exige versionado). Lo usan las pruebas: en kind y produccion lo crea U1."""
        headers = {"x-amz-bucket-object-lock-enabled": "true"} if object_lock else {}
        response = await self.request("PUT", f"/{bucket}", headers=headers)
        if response.status_code != OK:
            raise ExternalError(f"s3 make_bucket {bucket}: HTTP {response.status_code}")

    async def put(self, bucket: str, key: str, data: bytes, *, retain_until: datetime | None = None) -> None:
        """Escribe un objeto con retencion `COMPLIANCE` hasta `retain_until` (por omision, 10 anios)."""
        until = retain_until or (self._clock() + RETENTION)
        headers = {
            "x-amz-object-lock-mode": "COMPLIANCE",
            "x-amz-object-lock-retain-until-date": _timestamp(until),
            "content-md5": base64.b64encode(hashlib.md5(data, usedforsecurity=False).digest()).decode(),
        }
        response = await self.request("PUT", f"/{bucket}/{key}", headers=headers, body=data)
        if response.status_code != OK:
            raise ExternalError(f"s3 put {bucket}/{key}: HTTP {response.status_code}")

    async def get(self, bucket: str, key: str) -> bytes:
        response = await self.request("GET", f"/{bucket}/{key}")
        if response.status_code != OK:
            raise ExternalError(f"s3 get {bucket}/{key}: HTTP {response.status_code}")
        return response.content

    async def keys(self, bucket: str, prefix: str) -> list[str]:
        """Las llaves con ese prefijo, en orden, recorriendo las paginas."""
        found: list[str] = []
        token: str | None = None
        while True:
            query = {"list-type": "2", "prefix": prefix}
            if token:
                query["continuation-token"] = token
            response = await self.request("GET", f"/{bucket}", query=query)
            if response.status_code != OK:
                raise ExternalError(f"s3 list {bucket}: HTTP {response.status_code}")
            found += [unescape(k) for k in re.findall(r"<Key>(.*?)</Key>", response.text)]
            more = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", response.text)
            if not more:
                return sorted(found)
            token = unescape(more.group(1))


def checkpoint_key(checkpoint_seq: int) -> str:
    return f"{CHECKPOINT_PREFIX}{checkpoint_seq}.json"


def checkpoint_object(payload: Mapping[str, object], recorded_at: str) -> bytes:
    """El contenido de `checkpoints/{checkpoint_seq}.json`: el payload del checkpoint y el `recorded_at` que la firma cubre."""
    return json.dumps({**payload, "recorded_at": recorded_at}, sort_keys=True).encode()


async def read_checkpoints(s3: S3, bucket: str) -> dict[int, dict[str, object]]:
    """Todas las copias del bucket de checkpoints, por `checkpoint_seq` (paso 6 de BR-U3-12)."""
    copies: dict[int, dict[str, object]] = {}
    for key in await s3.keys(bucket, CHECKPOINT_PREFIX):
        value = json.loads(await s3.get(bucket, key))
        if not isinstance(value, dict) or isinstance(value.get("checkpoint_seq"), bool):
            raise ExternalError(f"objeto WORM mal formado: {key}")
        copies[int(value["checkpoint_seq"])] = value
    return copies
