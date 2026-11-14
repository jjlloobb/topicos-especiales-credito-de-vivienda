"""Filtro de evidencias (U12 Paso 2; NFR-U12-05). Toda salida que va a una evidencia pasa por `prepare`.

Dos partes y la regla comun de **fallar cerrado**. `scrub` quita el valor de las cabeceras `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie` y
`X-Vault-Token` (tambien en la forma `nombre=valor`) hasta el fin de la linea, con comillas o sin ellas, y los campos `access_token`, `refresh_token`,
`id_token`, `client_assertion`, `client_secret` y `password` (en JSON, con las comillas escapadas bien leidas, y en formularios). `ensure_clean` **falla**
si despues queda un JWT (tambien partido por saltos de linea o espacios) o cualquier secreto cargado por `credentials` (semillas, contraseñas, llaves, el
token de la boveda) en alguna de sus formas: literal, escapado en JSON, codificado en URL, sin espacios ni saltos de linea, sin distinguir mayusculas si es
Base32, o un trozo reconocible (>= 8 caracteres entre comillas, barras o espacios del secreto). El mensaje de error nunca repite lo hallado. La escritura de los
archivos de evidencia por seccion es del Paso 13: aqui queda la funcion por la que esa escritura tendra que pasar.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Final
from urllib.parse import quote, quote_plus

REDACTED: Final = "[REDACTADO]"
MIN_FRAGMENT: Final = 8

_HEADER_NAMES: Final = r"authorization|proxy-authorization|cookie|set-cookie|x-vault-token"
_FIELD_NAMES: Final = (
    r"access_token|refresh_token|id_token|client_assertion|client_secret|password|code_verifier|otp"
)
# `pre`: comilla (o comilla escapada) que abre la cabecera o la clave; `post`: la que la cierra (clave de JSON).
_HEADERS: Final = re.compile(
    rf"""(?i) (?<![A-Za-z0-9_]) (?P<pre>\\?["']?) (?P<key>{_HEADER_NAMES}) (?P<post>\\?["']?) (?P<sep>[ \t]*[:=][ \t]*)""",
    re.X,
)
_FIELDS: Final = re.compile(
    rf"""(?i) (?<![A-Za-z0-9_]) (?P<pre>\\?["']?) (?P<key>{_FIELD_NAMES}) (?P<post>\\?["']?) (?P<sep>\s*[:=]\s*)""",
    re.X,
)
# F-08: las cabeceras como tupla (`('Cookie', 'x')`, `(b'cookie', b'x')`: httpx y h11) y como objeto de HAR (`{"name": "Cookie", "value": "x"}`: Playwright); y el `code` de
# una URL o de un formulario (`?code=`, `&code=`). `code` no es un campo general: es el nombre del codigo de error de `Problem` y no se puede borrar de las evidencias.
_QUOTED_VALUE: Final = r"""b?(?P<vq>["'])(?:\\.|(?!(?P=vq)).)*(?P=vq)"""
_TUPLE_HEADERS: Final = re.compile(
    rf"""(?i)(?P<head>[(\[]\s*b?(?P<q>["'])(?:{_HEADER_NAMES})(?P=q)\s*,\s*){_QUOTED_VALUE}"""
)
# Un objeto de HAR (`{"name": "Cookie", "value": "x"}`) con **cualquier orden de claves** y claves de mas: se mira cada objeto plano `{...}`; si su `name` es una cabecera o un campo de credencial, se quita su `value`.
_FLAT_OBJECT: Final = re.compile(r"\{[^{}]*\}")
_HAR_NAME: Final = re.compile(
    rf"""(?i)["']name["']\s*:\s*(?P<q>["'])(?:{_HEADER_NAMES}|{_FIELD_NAMES})(?P=q)"""
)
_HAR_VALUE: Final = re.compile(rf"""(?i)(?P<head>["']value["']\s*:\s*){_QUOTED_VALUE}""")
# `code=` en una URL o formulario: tras `?`, `&`, `#`, el principio del texto o un espacio; no `http_code=` ni `error_code=`.
_URL_CODE: Final = re.compile(r"(?i)(?P<head>(?<![\w-])code=)[^&\s\"'#]*")
_JWT: Final = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
_PEM_ARMOR: Final = re.compile(r"-----(?:BEGIN|END)[A-Z ]*-----")
_ESCAPED_WHITESPACE: Final = re.compile(r"\\[nrt]")
_WHITESPACE: Final = re.compile(r"\s+")
_BASE32: Final = re.compile(r"[A-Z2-7]+=*")


class EvidenceError(Exception):
    """La salida contiene un secreto; el mensaje no lo repite."""


def _quoted_end(text: str, start: int, quote_char: str, escaped: bool) -> int | None:
    """El indice de la comilla que cierra la cadena que empieza en `start`, leyendo `\\x` como un caracter; `None` si no cierra en la linea."""
    closing = "\\" + quote_char if escaped else quote_char
    i = start
    while i < len(text) and text[i] not in "\r\n":
        if text.startswith(closing, i):
            return i
        i += 2 if text[i] == "\\" and not escaped else 1
    return None


def _eol(text: str, start: int) -> int:
    end = start
    while end < len(text) and text[end] not in "\r\n":
        end += 1
    return end


def _consume(text: str, match: re.Match[str], *, header: bool) -> tuple[str, int]:
    """El texto que reemplaza a `match` y el indice donde sigue el original. El valor que se quita incluye sus comillas si las trae."""
    start = match.end()
    pre, post = match.group("pre"), match.group("post")
    head = text[match.start() : start]
    escaped = pre.startswith("\\")
    quote_char = pre[-1] if pre else ""
    value_quote = ""
    if text.startswith('\\"', start) or text.startswith("\\'", start):
        value_quote, value_escaped = text[start + 1], True
    elif text[start : start + 1] in ('"', "'"):
        value_quote, value_escaped = text[start], False
    else:
        value_escaped = False
    if value_quote and (post or not header):  # un campo o la clave de un JSON: el valor es la cadena entera
        offset = start + (2 if value_escaped else 1)
        end = _quoted_end(text, offset, value_quote, value_escaped)
        if end is not None:
            close = 2 if value_escaped else 1
            opening = text[start:offset]
            return head + opening + REDACTED + text[end : end + close], end + close
        return head + REDACTED, _eol(text, start)
    if quote_char and not post:  # `-H "Cookie: ..."`: hasta la comilla que cierra el argumento
        end = _quoted_end(text, start, quote_char, escaped)
        return head + REDACTED, end if end is not None else _eol(text, start)
    if header:  # sin comillas alrededor: hasta el fin de la linea, con o sin comillas dentro del valor
        return head + REDACTED, _eol(text, start)
    stop = re.compile(r"[\s,}\]]" if quote_char else r"[\s&]")
    found = stop.search(text, start)
    return head + REDACTED, found.start() if found else len(text)


def _scrub_with(pattern: re.Pattern[str], text: str, *, header: bool) -> str:
    out: list[str] = []
    position = 0
    while (match := pattern.search(text, position)) is not None:
        out.append(text[position : match.start()])
        replacement, position = _consume(text, match, header=header)
        out.append(replacement)
    out.append(text[position:])
    return "".join(out)


def _quoted_value(match: re.Match[str]) -> str:
    quote_char = match.group("vq")
    return f"{match.group('head')}{quote_char}{REDACTED}{quote_char}"


def _har_object(match: re.Match[str]) -> str:
    obj = match.group(0)
    return _HAR_VALUE.sub(_quoted_value, obj) if _HAR_NAME.search(obj) else obj


# U12-T04 (F-N4 de la ronda 2 de U12-T02): `{[^{}]*}` no ve un objeto con una llave dentro del valor ni con otro objeto anidado. Un recorrido que sabe de cadenas (comillas dobles o simples, `\x` como un
# solo caracter) lleva la pila de objetos y, al cerrar cada uno, mira **sus** claves `name` y `value`: asi la llave de un valor no cuenta y un objeto anidado no tapa al de afuera.
_SENSITIVE_NAME: Final = re.compile(rf"(?i)(?:{_HEADER_NAMES}|{_FIELD_NAMES})")
_NAME_THEN_VALUE: Final = re.compile(
    rf"""(?i)["']name["']\s*:\s*(?P<q>["'])(?:{_HEADER_NAMES}|{_FIELD_NAMES})(?P=q)\s*,\s*(?P<head>["']value["']\s*:\s*){_QUOTED_VALUE}"""
)


def _string_end(text: str, start: int) -> int | None:
    """El indice de la comilla que cierra la cadena que abre en `start` (en la misma linea), leyendo `\\x` como un caracter; `None` si no cierra."""
    quote_char = text[start]
    i = start + 1
    while i < len(text) and text[i] not in "\r\n":
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote_char:
            return i
        i += 1
    return None


class _Frame:
    __slots__ = ("pending", "values")

    def __init__(self) -> None:
        self.pending: str | None = None
        self.values: dict[str, tuple[int, int]] = {}


def _har_spans(text: str) -> list[tuple[int, int]]:
    """Los intervalos (sin comillas) de los `value` cuyo objeto tiene un `name` de cabecera o de campo de credencial, en cualquier orden y con cualquier anidamiento."""
    spans: list[tuple[int, int]] = []
    stack: list[_Frame | None] = []
    i = 0
    while i < len(text):
        char = text[i]
        top = stack[-1] if stack else None
        if char in "\"'":
            end = _string_end(text, i)
            if end is None:
                i += 1
                continue
            after = end + 1
            while after < len(text) and text[after] in " \t":
                after += 1
            if top is not None and after < len(text) and text[after] == ":":
                top.pending = text[i + 1 : end].lower()
            elif top is not None and top.pending is not None:
                top.values[top.pending] = (i + 1, end)
                top.pending = None
            i = end + 1
            continue
        if char == "{":
            stack.append(_Frame())
        elif char == "[":
            stack.append(None)
        elif char in "}]":
            frame = stack.pop() if stack else None
            if frame is not None and "name" in frame.values and "value" in frame.values:
                name_start, name_end = frame.values["name"]
                if _SENSITIVE_NAME.fullmatch(text[name_start:name_end]):
                    spans.append(frame.values["value"])
            if stack and stack[-1] is not None:
                stack[-1].pending = None
        elif top is not None and char not in " \t\r\n:":
            top.pending = None
        i += 1
    return spans


def _har_walk(text: str) -> str:
    out = text
    for start, end in sorted(_har_spans(text), reverse=True):
        out = out[:start] + REDACTED + out[end:]
    return out


def scrub(text: str) -> str:
    """Quita las cabeceras y los campos de credenciales; una salida limpia queda igual."""
    text = _NAME_THEN_VALUE.sub(_quoted_value, _har_walk(text))
    text = _TUPLE_HEADERS.sub(_quoted_value, _FLAT_OBJECT.sub(_har_object, text))
    text = _URL_CODE.sub(lambda m: f"{m.group('head')}{REDACTED}", text)
    return _scrub_with(_FIELDS, _scrub_with(_HEADERS, text, header=True), header=False)


def _compact(text: str) -> str:
    """El texto sin espacios, saltos de linea ni `\\n` escapados: asi no se esconde un secreto partiendolo."""
    return _WHITESPACE.sub("", _ESCAPED_WHITESPACE.sub("", text))


def _forms(secret: str) -> set[str]:
    """Las formas en que un secreto cargado puede aparecer en una salida (ya compactadas)."""
    raw = {
        secret,
        json.dumps(secret)[1:-1],
        json.dumps(secret, ensure_ascii=False)[1:-1],
        quote(secret, safe=""),
        quote_plus(secret),
    }
    return {_compact(form) for form in raw if form}


def _fragments(secret: str) -> set[str]:
    """Los trozos del secreto que quedan si un filtro lo parte en una comilla, una barra o un espacio. La armadura PEM (`-----BEGIN … KEY-----`) no cuenta: la lleva
    cualquier certificado y no es secreta (F-07); el cuerpo de la llave si."""
    body = _PEM_ARMOR.sub(" ", secret)
    return {chunk for chunk in re.split(r"""[\s"'\\]+""", body) if len(chunk) >= MIN_FRAGMENT}


def _contains(text: str, compact_text: str, secret: str) -> bool:
    folded = _BASE32.fullmatch(secret) is not None  # una semilla Base32 no distingue mayusculas
    haystack, compact_haystack = (text.upper(), compact_text.upper()) if folded else (text, compact_text)
    for form in _forms(secret):
        needle = form.upper() if folded else form
        if needle in compact_haystack:
            return True
    return any((chunk.upper() if folded else chunk) in haystack for chunk in _fragments(secret))


def ensure_clean(text: str, secrets: Iterable[str]) -> None:
    """Falla si `text` contiene un JWT o alguno de los `secrets` cargados por `credentials`, en cualquiera de sus formas."""
    compact_text = _compact(text)
    if _JWT.search(text) or _JWT.search(compact_text):
        raise EvidenceError("evidence_contains_jwt")
    if any(secret and _contains(text, compact_text, secret) for secret in secrets):
        raise EvidenceError("evidence_contains_secret")


def prepare(text: str, secrets: Iterable[str]) -> str:
    """El texto listo para escribirse como evidencia: filtrado, y verificado sin JWT ni secretos."""
    cleaned = scrub(text)
    ensure_clean(cleaned, secrets)
    return cleaned
