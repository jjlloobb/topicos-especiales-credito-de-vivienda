"""Filtro de evidencias (U12 Paso 2; NFR-U12-05). Toda salida que va a una evidencia pasa por `prepare`.

Dos partes: `scrub` quita las cabeceras `Authorization`, `Cookie` y `Set-Cookie` y los campos `access_token`, `refresh_token`, `id_token`,
`client_assertion` y `password`; `ensure_clean` **falla** si despues queda un JWT (tres segmentos en base64url que empiezan por `eyJ`) o cualquier secreto
cargado por `credentials` (semillas, contraseñas, llaves, el token de la boveda). El mensaje de error nunca repite lo hallado. La escritura de los archivos de
evidencia por seccion es del Paso 13: aqui queda la funcion por la que esa escritura tendra que pasar.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

REDACTED: Final = "[REDACTADO]"

_HEADERS: Final = re.compile(
    r"""(?ix) (["']?(?:authorization|cookie|set-cookie)["']?) (\s*:\s*) ("[^"]*"|'[^']*'|[^\r\n"']*)"""
)
_FIELDS: Final = re.compile(
    r"""(?ix) (["']?(?:access_token|refresh_token|id_token|client_assertion|password)["']?\s*[:=]\s*) ("[^"]*"|'[^']*'|[^\s&,;}"']+)"""
)
_JWT: Final = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")


class EvidenceError(Exception):
    """La salida contiene un secreto; el mensaje no lo repite."""


def _redact(match: re.Match[str]) -> str:
    key, separator, value = match.group(1), match.group(2), match.group(3)
    quote = value[0] if value[:1] in ('"', "'") else ""
    return f"{key}{separator}{quote}{REDACTED}{quote}"


def _redact_field(match: re.Match[str]) -> str:
    key, value = match.group(1), match.group(2)
    quote = value[0] if value[:1] in ('"', "'") else ""
    return f"{key}{quote}{REDACTED}{quote}"


def scrub(text: str) -> str:
    """Quita las cabeceras y los campos de credenciales; una salida limpia queda igual."""
    return _FIELDS.sub(_redact_field, _HEADERS.sub(_redact, text))


def ensure_clean(text: str, secrets: Iterable[str]) -> None:
    """Falla si `text` contiene un JWT o alguno de los `secrets` cargados por `credentials`."""
    if _JWT.search(text):
        raise EvidenceError("evidence_contains_jwt")
    if any(secret and secret in text for secret in secrets):
        raise EvidenceError("evidence_contains_secret")


def prepare(text: str, secrets: Iterable[str]) -> str:
    """El texto listo para escribirse como evidencia: filtrado, y verificado sin JWT ni secretos."""
    cleaned = scrub(text)
    ensure_clean(cleaned, secrets)
    return cleaned
