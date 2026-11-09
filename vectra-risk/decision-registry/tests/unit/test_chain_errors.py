"""Los errores de `chain` (Paso 16; NFR-U3-52): sellos sin zona, `prev_hash` corto, JSON con flotantes y canonicos que no son objetos."""

from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from vectra_registry.chain import GENESIS_PREV_HASH, canonicalize, decode, format_timestamp, link


def test_un_sello_sin_zona_horaria_es_un_error() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        format_timestamp(datetime(2026, 1, 1, 12, 0, 0))  # noqa: DTZ001 - es el caso


def test_link_exige_un_prev_hash_de_32_bytes() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        link(b"corto", b"{}")
    assert len(link(GENESIS_PREV_HASH, b"{}")) == 32


@pytest.mark.parametrize("text", [b'{"x":1.5}', b'{"x":NaN}', b'{"x":Infinity}'])
def test_decode_rechaza_los_flotantes(text: bytes) -> None:
    with pytest.raises(ValueError, match="flotantes"):
        decode(text)


@pytest.mark.parametrize("text", [b"[1,2]", b'"texto"', b"3"])
def test_decode_exige_un_objeto_json(text: bytes) -> None:
    with pytest.raises(ValueError, match="objeto JSON"):
        decode(text)


@pytest.mark.parametrize("text", [b"\xff\xfe", b"{no json"])
def test_decode_rechaza_lo_que_no_es_json_utf8(text: bytes) -> None:
    with pytest.raises(ValueError, match="no es JSON valido"):
        decode(text)


def test_canonicalize_fija_fechas_uuid_y_secuencias() -> None:
    body = canonicalize(
        {"d": date(2026, 1, 2), "u": UUID(int=1), "t": (1, 2), "l": [datetime(2026, 1, 1, tzinfo=UTC)], "m": {"a": date(2026, 1, 3)}}
    )
    assert decode(body) == {
        "d": "2026-01-02",
        "u": "00000000-0000-0000-0000-000000000001",
        "t": [1, 2],
        "l": ["2026-01-01T00:00:00.000000Z"],
        "m": {"a": "2026-01-03"},
    }
