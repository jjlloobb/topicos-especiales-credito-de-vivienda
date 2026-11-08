"""PBT-U3-02 y PBT-U3-03 sobre `verify` (Paso 4 del plan de U3; BR-U3-11, 12; NFR-U3-33).

`HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_verify.py` (500 ejemplos, semilla impresa).
"""

import uuid
from dataclasses import replace
from datetime import timedelta

from chain_builder import Signer, build_chain, rewrite_from, worm_of
from hypothesis import assume, given
from hypothesis import strategies as st

from vectra_registry.chain import Row, decode, link
from vectra_registry.verify import ListSource, verify

KINDS = ["recommendation", "human_decision", "explanation_view", "model_event", "freeze", "fail_closed"]
SIGNER = Signer(7)
KEYS = [SIGNER.public]

# Cadenas de 1 a 500 entradas; la mayoria cortas para que 500 ejemplos corran en segundos.
sizes = st.one_of(st.integers(1, 30), st.integers(1, 500))
short_sizes = st.integers(1, 100)  # PBT-U3-03 verifica tres veces y reescribe la cadena: cadenas mas cortas
every = st.one_of(st.none(), st.integers(1, 12))


@st.composite
def chains(draw: st.DrawFn, size: st.SearchStrategy[int] = sizes) -> list[Row]:
    n = draw(size)
    kinds = [draw(st.sampled_from(KINDS)) for _ in range(min(n, 40))] + ["model_event"] * max(0, n - 40)
    return build_chain(kinds, SIGNER, checkpoint_every=draw(every))


def run(rows: list[Row], mode: str = "full") -> object:
    return verify(mode, ListSource(rows), public_keys=KEYS, seed=1, now=rows[-1].recorded_at)  # type: ignore[arg-type]


def flip(data: bytes, index: int) -> bytes:
    index %= len(data)
    return data[:index] + bytes([data[index] ^ 0x01]) + data[index + 1 :]


COLUMN_CHANGES = {
    "actor_id": lambda r: replace(r, actor_id=r.actor_id + "x"),
    "actor_kind": lambda r: replace(r, actor_kind="user" if r.actor_kind != "user" else "system"),
    "correlation_id": lambda r: replace(r, correlation_id="f" * 32),
    "contract_version": lambda r: replace(r, contract_version="9.9.9"),
    "recorded_at": lambda r: replace(r, recorded_at=r.recorded_at + timedelta(microseconds=1)),
    "occurred_at": lambda r: replace(r, occurred_at=r.occurred_at + timedelta(seconds=1)),
    "idempotency_key": lambda r: replace(r, idempotency_key=uuid.uuid4()),
    "case_id": lambda r: replace(r, case_id=uuid.uuid4()),
    "model_version_id": lambda r: replace(r, model_version_id=(r.model_version_id or "") + "x"),
    "entry_type": lambda r: replace(r, entry_type="model_event" if r.entry_type != "model_event" else "freeze"),
}


@given(chains(), st.sampled_from(["canonical", "hash", "column", "prev_hash", "delete", "swap"]), st.data())
def test_pbt_u3_02_una_manipulacion_se_detecta_en_su_seq(rows: list[Row], kind: str, data: st.DataObject) -> None:
    """PBT-U3-02: una sola manipulacion (un byte de `canonical` o de `hash`, una columna, borrar o intercambiar filas)
    da `inconsistente` y el primer `seq` informado es el de la manipulacion (el siguiente, si se borro una fila)."""
    assert run(rows).result == "integra"  # type: ignore[attr-defined]
    last = len(rows) - 1
    if kind == "delete":
        # Una fila final borrada solo la delatan un checkpoint o el WORM (ver test_verify_modes), no la cadena.
        assume(last >= 1)
        m = data.draw(st.integers(0, last - 1))
        mutated = rows[:m] + rows[m + 1 :]
        expected = m + 1
    elif kind == "swap":
        assume(last >= 1)
        i = data.draw(st.integers(0, last - 1))
        j = data.draw(st.integers(i + 1, last))
        mutated = list(rows)
        # Intercambia el contenido de dos filas; `seq` es la llave y se queda donde esta.
        mutated[i] = replace(rows[j], seq=rows[i].seq)
        mutated[j] = replace(rows[i], seq=rows[j].seq)
        expected = i
    else:
        m = data.draw(st.integers(0, last))
        index = data.draw(st.integers(0, 10**6))
        row = rows[m]
        if kind == "canonical":
            new = replace(row, canonical=flip(row.canonical, index))
        elif kind == "hash":
            new = replace(row, hash=flip(row.hash, index))
        elif kind == "prev_hash":  # el hash se recalcula: solo el enlace falla
            bad_prev = flip(row.prev_hash, index)
            new = replace(row, prev_hash=bad_prev, hash=link(bad_prev, row.canonical))
        else:
            new = COLUMN_CHANGES[data.draw(st.sampled_from(sorted(COLUMN_CHANGES)))](row)
        mutated = list(rows)
        mutated[m] = new
        expected = m
    report = run(mutated)
    assert report.result == "inconsistente", (kind, expected)  # type: ignore[attr-defined]
    assert report.first_inconsistent_seq == expected  # type: ignore[attr-defined]
    if kind == "prev_hash":
        assert report.reason == "link"  # type: ignore[attr-defined]


@given(chains(short_sizes), st.data())
def test_pbt_u3_03_la_reescritura_completa_la_delata_un_checkpoint(rows: list[Row], data: st.DataObject) -> None:
    """PBT-U3-03: una cadena reescrita desde un `seq` k anterior a un checkpoint, con los hashes recalculados, da
    `inconsistente` con `checkpoint_mismatch` o `checkpoint_signature`, en `full` y en `nightly` (sin re-hash completo)."""
    covered = [int(decode(r.canonical)["payload"]["checkpoint_seq"]) for r in rows if r.entry_type == "checkpoint"]  # type: ignore[call-overload]
    assume(covered)
    candidates = [r.seq for r in rows if r.entry_type != "checkpoint" and r.seq <= max(covered)]
    k = data.draw(st.sampled_from(candidates))
    rewritten = rewrite_from(rows, k)
    assert rewritten[-1].hash != rows[-1].hash  # la reescritura es real
    # El primer checkpoint cuya fila cubierta es la reescrita o posterior: la cadena reescrita ya no coincide con su firma.
    first_checkpoint = min(
        r.seq for r in rows if r.entry_type == "checkpoint" and int(decode(r.canonical)["payload"]["checkpoint_seq"]) >= k  # type: ignore[call-overload]
    )
    for mode in ("full", "nightly"):
        report = run(rewritten, mode)
        assert report.result == "inconsistente", mode  # type: ignore[attr-defined]
        assert report.reason in {"checkpoint_mismatch", "checkpoint_signature"}, mode  # type: ignore[attr-defined]
        assert report.first_inconsistent_seq == first_checkpoint, mode  # type: ignore[attr-defined]
    # Con el WORM, la copia del checkpoint tambien delata la reescritura.
    report = verify(
        "full", ListSource(rewritten), public_keys=KEYS, worm=worm_of(rows), now=rows[-1].recorded_at
    )
    assert report.result == "inconsistente"
