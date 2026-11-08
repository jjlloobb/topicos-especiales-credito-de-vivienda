"""PBT-U3-04 y PBT-U3-05 sobre `chain` (Paso 3 del plan de U3; BR-U3-09, 10; domain-entities §1.1).

`HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_chain.py` (500 ejemplos, semilla impresa).
"""

import hashlib
from datetime import UTC, datetime, timedelta, timezone

import pytest
from chain_builder import Signer, build_chain
from hypothesis import given
from hypothesis import strategies as st

from vectra_registry import chain, verify
from vectra_registry.chain import GENESIS_PREV_HASH, canonicalize, decode, link

ENTRY_TYPES = [
    "recommendation", "fail_closed", "human_decision", "explanation_view", "model_event", "policy_event",
    "data_source_event", "freeze", "frozen_resolution", "genesis", "checkpoint",
]  # fmt: skip

# Texto con Unicode (incluidos fuera del plano basico y controles) y decimales de U0 como cadenas ("0.1234").
texts = st.text(max_size=30)
decimals = st.decimals(min_value=0, max_value=1, places=4, allow_nan=False).map(str)
ints = st.integers(min_value=-(2**53 - 1), max_value=2**53 - 1)
scalars = st.one_of(st.none(), st.booleans(), ints, texts, decimals)
json_values = st.recursive(
    scalars,
    lambda inner: st.one_of(st.lists(inner, max_size=4), st.dictionaries(texts, inner, max_size=4)),
    max_leaves=12,
)
timestamps = st.datetimes(
    min_value=datetime(2020, 1, 1), max_value=datetime(2040, 1, 1), timezones=st.just(UTC)
)

entries = st.fixed_dictionaries(
    {
        "seq": st.integers(min_value=0, max_value=10**9),
        "entry_type": st.sampled_from(ENTRY_TYPES),
        "idempotency_key": st.uuids().map(str),
        "actor": st.fixed_dictionaries({"kind": st.sampled_from(["user", "service", "system"]), "id": texts}),
        "occurred_at": timestamps,
        "recorded_at": timestamps,
        "correlation_id": st.text("0123456789abcdef", min_size=32, max_size=32),
        "contract_version": st.just("0.1.0"),
        "payload": st.dictionaries(texts, json_values, max_size=5),
    },
    optional={"case_id": st.uuids().map(str), "model_version_id": texts, "policy_version_id": texts},
)


@given(entries)
def test_pbt_u3_04_los_bytes_guardados_son_un_punto_fijo_de_jcs(entry: dict[str, object]) -> None:
    """PBT-U3-04 (BR-U3-09): `canonicalize(decode(canonical)) == canonical` para entradas de todos los tipos."""
    canonical = canonicalize(entry)
    assert canonicalize(decode(canonical)) == canonical


@given(entries, st.binary(min_size=32, max_size=32), st.binary(min_size=32, max_size=32))
def test_el_hash_depende_de_prev_hash_y_de_canonical(entry: dict[str, object], prev: bytes, other: bytes) -> None:
    """BR-U3-09: `hash = SHA-256(prev_hash || canonical)`; un `prev_hash` distinto da otro hash."""
    canonical = canonicalize(entry)
    assert link(prev, canonical) == hashlib.sha256(prev + canonical).digest()
    if other != prev:
        assert link(other, canonical) != link(prev, canonical)
    assert link(prev, canonical) != link(prev, canonical + b" ")


@given(st.lists(st.sampled_from(ENTRY_TYPES[:-2]), min_size=1, max_size=40), st.integers(0, 5))
def test_pbt_u3_05_un_contrato_mas_nuevo_no_cambia_el_resultado(kinds: list[str], seed: int) -> None:
    """PBT-U3-05 (BR-U3-09): la cadena escrita con el contrato X se verifica igual si el codigo tiene el contrato X+1.

    El contrato nuevo agrega un campo opcional (`campo_nuevo`) que el serializador nuevo escribiria como `null`. Si el
    verificador volviera a serializar, el `canonical` resultante difiere del guardado y el hash dejaria de coincidir.
    """
    signer = Signer(seed)
    rows = build_chain(kinds, signer, checkpoint_every=4)
    keys = [signer.public]
    before = verify.verify("full", verify.ListSource(rows), public_keys=keys, now=rows[-1].recorded_at)
    assert before.result == "integra"

    def canonicalize_v2(value: object) -> bytes:
        assert isinstance(value, dict)
        return canonicalize({**value, "campo_nuevo": None})

    # El serializador nuevo si cambiaria los bytes (la prueba no seria vacua)...
    assert canonicalize_v2(decode(rows[1].canonical)) != rows[1].canonical
    # ...y aun asi el verificador (que no serializa) da el mismo informe, aunque `chain.canonicalize` sea el nuevo.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(chain, "canonicalize", canonicalize_v2)
        after = verify.verify("full", verify.ListSource(rows), public_keys=keys, now=rows[-1].recorded_at)
    assert after.model_dump(exclude={"started_at", "finished_at"}) == before.model_dump(
        exclude={"started_at", "finished_at"}
    )


@given(st.lists(st.sampled_from(ENTRY_TYPES[:-2]), min_size=1, max_size=15))
def test_la_genesis_enlaza_con_treinta_y_dos_ceros(kinds: list[str]) -> None:
    """BR-U3-10: la genesis (`seq = 0`) tiene `prev_hash` de 32 bytes en cero; las demas, el hash de la anterior."""
    rows = build_chain(kinds, Signer())
    assert rows[0].entry_type == "genesis" and rows[0].prev_hash == GENESIS_PREV_HASH == bytes(32)
    assert all(b.prev_hash == a.hash for a, b in zip(rows, rows[1:], strict=False))
    assert [r.entry_type for r in rows].count("genesis") == 1


@given(timestamps, st.integers(min_value=-12, max_value=14))
def test_los_sellos_de_tiempo_salen_en_utc_con_microsegundos_y_z(stamp: datetime, offset: int) -> None:
    """`canonicalize` fija ISO 8601 UTC con microsegundos y `Z`, sea cual sea la zona del `datetime` de entrada."""
    local = stamp.astimezone(timezone(timedelta(hours=offset)))
    text = chain.format_timestamp(local)
    assert len(text) == len("2026-01-01T00:00:00.000000Z") and text.endswith("Z")
    assert datetime.fromisoformat(text) == stamp
    assert canonicalize({"t": local}) == canonicalize({"t": text})
