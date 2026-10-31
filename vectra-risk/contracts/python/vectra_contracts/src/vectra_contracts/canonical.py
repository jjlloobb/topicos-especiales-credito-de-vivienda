"""JSON canonico RFC 8785 (JCS) para valores sin flotantes (BR-U0-15)."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import cast

_MAX_SAFE_INT = 2**53 - 1


def _encode(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        if abs(value) > _MAX_SAFE_INT:
            raise ValueError("entero fuera del rango seguro de JCS")
        return str(value)
    if isinstance(value, float):
        raise TypeError("el contrato no admite flotantes en JSON canonico")
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        items = sorted(mapping.items(), key=lambda kv: kv[0].encode("utf-16-be"))
        return "{" + ",".join(f"{json.dumps(k, ensure_ascii=False)}:{_encode(v)}" for k, v in items) + "}"
    if isinstance(value, Sequence):
        return "[" + ",".join(_encode(v) for v in cast(Sequence[object], value)) + "]"
    raise TypeError(f"tipo no admitido en JSON canonico: {type(value).__name__}")


def canonicalize(value: object) -> bytes:
    return _encode(value).encode("utf-8")


def sha256_hex(value: object) -> str:
    return hashlib.sha256(canonicalize(value)).hexdigest()
