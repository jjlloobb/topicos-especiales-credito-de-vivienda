"""Los 6 motivos de BR-U3-12 y los 4 modos de BR-U3-11 de `verify` (Paso 4 del plan de U3; NFR-U3-33; US-402).

Un caso por motivo y por modo; los modos prueban lo que revisan y lo que, por diseno (NFR-U3-33), no revisan.
"""

import math
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from chain_builder import Signer, build_chain, entry_fields, rewrite_from, row_of, worm_of

from vectra_registry.chain import Row, canonicalize, decode, format_timestamp, link
from vectra_registry.verify import ListSource, nightly_seed, sample_segments, verify

SIGNER = Signer(3)
OTHER = Signer(4)
KINDS = ["recommendation", "human_decision", "explanation_view", "model_event"] * 15  # 60 entradas
ROWS = build_chain(KINDS, SIGNER, checkpoint_every=5)  # 60 + genesis + 12 checkpoints = 73 filas
CHECKPOINTS = [r for r in ROWS if r.entry_type == "checkpoint"]
NOW = ROWS[-1].recorded_at


def run(rows: list[Row], mode: str = "full", keys: list[bytes] | None = None, **kwargs: Any) -> Any:
    kwargs.setdefault("now", NOW)
    if mode == "nightly":
        kwargs.setdefault("seed", 1)
    return verify(mode, ListSource(rows), public_keys=keys or [SIGNER.public], **kwargs)  # type: ignore[arg-type]


def replaced(rows: list[Row], index: int, **changes: Any) -> list[Row]:
    return [*rows[:index], replace(rows[index], **changes), *rows[index + 1 :]]


def flip(data: bytes) -> bytes:
    return bytes([data[0] ^ 1]) + data[1:]


# --- Los 6 motivos de BR-U3-12 ----------------------------------------------------------------------------------------------


def test_cadena_integra() -> None:
    report = run(ROWS)
    assert (report.result, report.first_inconsistent_seq, report.reason) == ("integra", None, None)
    assert (report.mode, report.from_seq, report.to_seq) == ("full", 0, 72)
    assert report.entries_checked == 73 and report.checkpoints_checked == 12


def test_motivo_1_seq_gap() -> None:
    report = run(ROWS[:10] + ROWS[11:])
    assert (report.result, report.first_inconsistent_seq, report.reason) == ("inconsistente", 11, "seq_gap")


def test_motivo_2_link() -> None:
    # `prev_hash` no es el hash de la anterior, pero el hash de la fila se recalcula con el: solo el enlace falla.
    bad_prev = bytes([1]) * 32
    row = ROWS[10]
    report = run(replaced(ROWS, 10, prev_hash=bad_prev, hash=link(bad_prev, row.canonical)))
    assert (report.first_inconsistent_seq, report.reason) == (10, "link")


def test_motivo_2_la_genesis_exige_prev_hash_en_cero() -> None:
    bad_prev = bytes([1]) * 32
    report = run(replaced(ROWS, 0, prev_hash=bad_prev, hash=link(bad_prev, ROWS[0].canonical)))
    assert (report.first_inconsistent_seq, report.reason) == (0, "link")


def test_motivo_3_hash() -> None:
    report = run(replaced(ROWS, 10, hash=flip(ROWS[10].hash)))
    assert (report.first_inconsistent_seq, report.reason) == (10, "hash")


def test_motivo_4_column_mismatch() -> None:
    report = run(replaced(ROWS, 10, actor_id="otro"))
    assert (report.first_inconsistent_seq, report.reason) == (10, "column_mismatch")


def test_motivo_4_el_verificador_lee_los_bytes_guardados_con_otro_formato_de_sello() -> None:
    """BR-U3-09: un `canonical` con sellos sin microsegundos (otro formato, de un contrato anterior) sigue siendo valido."""
    base = ROWS[1]
    body = decode(base.canonical)
    body["recorded_at"] = "2026-01-01T12:10:00Z"  # el mismo instante que la columna `recorded_at`
    stored = canonicalize(body)
    assert stored != base.canonical and b'"recorded_at":"2026-01-01T12:10:00Z"' in stored
    row = replace(base, canonical=stored, hash=link(base.prev_hash, stored))
    report = run([ROWS[0], row], "range", from_seq=0, to_seq=1)
    assert (report.result, report.entries_checked) == ("integra", 2)


def test_motivo_5a_checkpoint_signature_con_otra_llave() -> None:
    report = run(ROWS, keys=[OTHER.public])
    assert (report.first_inconsistent_seq, report.reason) == (CHECKPOINTS[0].seq, "checkpoint_signature")


def test_motivo_5a_checkpoint_signature_con_firma_alterada_y_cadena_reenlazada() -> None:
    c = CHECKPOINTS[2].seq

    def edit(body: dict[str, Any]) -> None:
        payload = dict(body["payload"])
        payload["signature"] = OTHER.sign(payload["checkpoint_seq"], payload["checkpoint_hash"], body["recorded_at"])
        body["payload"] = payload

    report = run(rewrite_from(ROWS, c, edit))
    assert (report.first_inconsistent_seq, report.reason) == (c, "checkpoint_signature")


def test_motivo_5a_la_firma_cubre_recorded_at() -> None:
    """Una firma valida de la llave correcta, pero sobre otro `recorded_at`, no vale."""
    c = CHECKPOINTS[1].seq

    def edit(body: dict[str, Any]) -> None:
        payload = dict(body["payload"])
        payload["signature"] = SIGNER.sign(payload["checkpoint_seq"], payload["checkpoint_hash"], "2020-01-01T00:00:00.000000Z")
        body["payload"] = payload

    report = run(rewrite_from(ROWS, c, edit))
    assert (report.first_inconsistent_seq, report.reason) == (c, "checkpoint_signature")


def test_motivo_5b_checkpoint_mismatch_con_firma_valida_sobre_otro_hash() -> None:
    rows = ROWS[:6]
    stamp = rows[-1].recorded_at + timedelta(minutes=10)
    wrong = rows[3]  # el checkpoint dice cubrir el seq 5 pero lleva el hash del seq 3
    payload = {
        "checkpoint_seq": 5,
        "checkpoint_hash": wrong.hash.hex(),
        "signature": SIGNER.sign(5, wrong.hash.hex(), format_timestamp(stamp)),
        "key_fingerprint": SIGNER.fingerprint,
    }
    rows.append(row_of(entry_fields(6, "checkpoint", payload, stamp), rows[-1].hash))
    report = run(rows)
    assert (report.first_inconsistent_seq, report.reason) == (6, "checkpoint_mismatch")


def test_motivo_6_worm_con_una_copia_distinta() -> None:
    worm = worm_of(ROWS)
    cs = CHECKPOINTS[3].seq - 1
    worm[cs] = {**worm[cs], "signature": OTHER.sign(cs, str(worm[cs]["checkpoint_hash"]), str(worm[cs]["recorded_at"]))}
    report = run(ROWS, worm=worm)
    assert (report.first_inconsistent_seq, report.reason) == (CHECKPOINTS[3].seq, "checkpoint_mismatch")


def test_motivo_6_worm_con_un_checkpoint_que_la_cadena_ya_no_tiene() -> None:
    """Truncar el final de la cadena no rompe ningun enlace: solo el WORM lo delata."""
    truncated = ROWS[: CHECKPOINTS[-1].seq]  # sin el ultimo checkpoint
    assert run(truncated).result == "integra"
    report = run(truncated, worm=worm_of(ROWS))
    last_covered = CHECKPOINTS[-1].seq - 1
    assert (report.first_inconsistent_seq, report.reason) == (last_covered + 1, "checkpoint_mismatch")


def test_manipular_un_checkpoint_se_informa_en_el_seq_del_checkpoint_no_en_el_de_la_fila_cubierta() -> None:
    """Contraejemplo que halló PBT-U3-02: un byte del `checkpoint_hash` cambiado informaba la fila cubierta (un `seq` antes)."""
    c = CHECKPOINTS[0].seq
    canonical = ROWS[c].canonical
    at = canonical.index(b'"checkpoint_hash":"') + len(b'"checkpoint_hash":"')
    changed = canonical[:at] + (b"1" if canonical[at : at + 1] != b"1" else b"2") + canonical[at + 1 :]
    # Con el hash de la fila sin recalcular: falla `hash` en el seq del checkpoint.
    report = run(replaced(ROWS, c, canonical=changed))
    assert (report.first_inconsistent_seq, report.reason) == (c, "hash")
    # Con la cadena reenlazada despues del cambio: ya no coincide con lo firmado, en el seq del checkpoint.
    report = run(rewrite_from(ROWS, c, lambda b: b["payload"].update(checkpoint_hash=b["payload"]["checkpoint_hash"][::-1])))
    assert (report.first_inconsistent_seq, report.reason) == (c, "checkpoint_signature")


def test_el_primer_seq_inconsistente_es_el_menor_aunque_haya_varios_motivos() -> None:
    rows = replaced(replaced(ROWS, 40, hash=flip(ROWS[40].hash)), 20, actor_id="otro")
    report = run(rows)
    assert (report.first_inconsistent_seq, report.reason) == (20, "column_mismatch")


def test_una_fuente_vacia_no_tiene_genesis() -> None:
    report = run([])
    assert (report.result, report.first_inconsistent_seq, report.reason) == ("inconsistente", 0, "seq_gap")


# --- Los 4 modos de BR-U3-11 -------------------------------------------------------------------------------------------------


def test_modo_full_re_hashea_todo_desde_el_seq_0() -> None:
    report = run(replaced(ROWS, 2, hash=flip(ROWS[2].hash)))
    assert (report.mode, report.from_seq, report.first_inconsistent_seq) == ("full", 0, 2)


def test_modo_incremental_desde_el_ultimo_checkpoint_verificado() -> None:
    since = 30
    report = run(ROWS, "incremental", from_seq=since)
    assert (report.mode, report.from_seq, report.to_seq, report.result) == ("incremental", 30, 72, "integra")
    assert report.entries_checked == 72 - 30 + 1
    # Lo anterior al checkpoint verificado no se vuelve a mirar; lo posterior si.
    assert run(replaced(ROWS, 10, actor_id="otro"), "incremental", from_seq=since).result == "integra"
    late = run(replaced(ROWS, 40, actor_id="otro"), "incremental", from_seq=since)
    assert (late.result, late.first_inconsistent_seq, late.reason) == ("inconsistente", 40, "column_mismatch")
    # Sin checkpoint previo, empieza en el seq 0.
    assert run(ROWS, "incremental").from_seq == 0


def test_modo_incremental_enlaza_con_la_fila_anterior_al_tramo() -> None:
    report = run(replaced(ROWS, 30, hash=flip(ROWS[30].hash)), "incremental", from_seq=31)
    assert (report.first_inconsistent_seq, report.reason) == (31, "link")


def test_modo_range_entre_dos_extremos() -> None:
    report = run(ROWS, "range", from_seq=12, to_seq=20)
    assert (report.mode, report.from_seq, report.to_seq, report.entries_checked) == ("range", 12, 20, 9)
    assert report.result == "integra"
    assert run(replaced(ROWS, 15, actor_id="otro"), "range", from_seq=12, to_seq=20).first_inconsistent_seq == 15
    assert run(replaced(ROWS, 25, actor_id="otro"), "range", from_seq=12, to_seq=20).result == "integra"
    assert run(replaced(ROWS, 5, actor_id="otro"), "range", from_seq=12, to_seq=20).result == "integra"


def test_modo_range_comprueba_los_checkpoints_del_tramo_contra_la_cadena() -> None:
    c = CHECKPOINTS[2].seq
    report = run(ROWS, "range", from_seq=c - 1, to_seq=c)
    assert report.checkpoints_checked == 1
    assert run(ROWS, "range", from_seq=c - 1, to_seq=c, keys=[OTHER.public]).reason == "checkpoint_signature"


@pytest.mark.parametrize("args", [{}, {"from_seq": 3}, {"to_seq": 9}, {"from_seq": 9, "to_seq": 3}])
def test_modo_range_exige_extremos_ordenados(args: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="range"):
        run(ROWS, "range", **args)


def test_el_modo_nightly_exige_una_semilla() -> None:
    with pytest.raises(ValueError, match="semilla"):
        verify("nightly", ListSource(ROWS), public_keys=[SIGNER.public], now=NOW)


# nightly: 2 400 entradas, un checkpoint cada 8 (2 701 filas), una hora entre filas (~112 dias): 300 segmentos.
LONG = build_chain(["model_event"] * 2400, SIGNER, checkpoint_every=8, step=timedelta(hours=1))
LONG_NOW = LONG[-1].recorded_at
LONG_COVERED = [int(decode(r.canonical)["payload"]["checkpoint_seq"]) for r in LONG if r.entry_type == "checkpoint"]
SEED = 11


def long_run(rows: list[Row], seed: int = SEED, **kwargs: Any) -> Any:
    return verify("nightly", ListSource(rows), public_keys=[SIGNER.public], seed=seed, now=LONG_NOW, **kwargs)


def recent_start() -> int:
    cutoff = LONG_NOW - timedelta(days=7)
    return max(r_cov for r, r_cov in zip((r for r in LONG if r.entry_type == "checkpoint"), LONG_COVERED, strict=True) if r.recorded_at < cutoff)


def test_nightly_integra_no_re_hashea_toda_la_cadena() -> None:
    report = long_run(LONG)
    assert (report.mode, report.result, report.from_seq, report.to_seq) == ("nightly", "integra", 0, len(LONG) - 1)
    assert report.checkpoints_checked == len(LONG_COVERED)
    assert report.entries_checked < len(LONG) / 2  # 7 dias + 1 % de los segmentos + los pares de cada checkpoint


def test_nightly_la_cadena_de_checkpoints_delata_una_reescritura_antigua_sin_re_hash_completo() -> None:
    rewritten = rewrite_from(LONG, 4)
    report = long_run(rewritten)
    assert (report.result, report.reason) == ("inconsistente", "checkpoint_mismatch")
    assert report.first_inconsistent_seq == min(
        r.seq for r in LONG if r.entry_type == "checkpoint" and int(decode(r.canonical)["payload"]["checkpoint_seq"]) >= 4
    )
    assert report.entries_checked < len(LONG) / 2  # lo detectaron las firmas y los enlaces, no el re-hash


def test_nightly_re_hashea_los_ultimos_7_dias() -> None:
    m = len(LONG) - 40  # ~40 horas atras
    assert LONG[m].recorded_at > LONG_NOW - timedelta(days=7)
    report = long_run(replaced(LONG, m, actor_id="otro"))
    assert (report.first_inconsistent_seq, report.reason) == (m, "column_mismatch")


def old_segment_row(rows: list[Row], sampled: list[tuple[int, int]]) -> int:
    """Una fila antigua, de un segmento fuera de la muestra, que no es un checkpoint ni su cubierta ni la anterior."""
    skip = {s for lo, hi in sampled for s in range(lo, hi + 1)}
    skip |= {c + d for c in LONG_COVERED for d in (0, 1, 2)}
    skip |= {r.seq - 1 for r in rows if r.entry_type == "checkpoint"} | {r.seq for r in rows if r.entry_type == "checkpoint"}
    return next(r.seq for r in rows if r.seq > 20 and r.seq < recent_start() and r.seq not in skip)


def test_nightly_solo_re_hashea_una_muestra_de_los_segmentos_antiguos() -> None:
    sampled = sample_segments(LONG_COVERED[: LONG_COVERED.index(recent_start()) + 1], SEED)
    older = LONG_COVERED.index(recent_start()) + 1
    assert len(sampled) == math.ceil(0.01 * older) and older > 100
    m = old_segment_row(LONG, sampled)
    tampered = replaced(LONG, m, actor_id="otro")
    assert long_run(tampered).result == "integra"  # fuera de la muestra: la cadena de checkpoints no lo ve (NFR-U3-33)
    assert verify("full", ListSource(tampered), public_keys=[SIGNER.public]).first_inconsistent_seq == m  # `full` si
    # Dentro de la muestra: lo ve.
    lo, hi = sampled[0]
    inside = next(s for s in range(lo + 1, hi) if LONG[s].entry_type != "checkpoint" and LONG[s + 1].entry_type != "checkpoint")
    detected = long_run(replaced(LONG, inside, actor_id="otro"))
    assert (detected.first_inconsistent_seq, detected.reason) == (inside, "column_mismatch")


def test_nightly_la_muestra_es_del_1_por_ciento_y_depende_de_la_semilla() -> None:
    covered = list(range(5, 5 + 3 * 250, 3))  # 250 segmentos
    sample = sample_segments(covered, 1)
    assert len(sample) == math.ceil(0.01 * 250) == 3
    assert sample == sample_segments(covered, 1)  # la misma semilla reproduce la muestra
    assert len({tuple(sample_segments(covered, seed)) for seed in range(10)}) > 1  # distinta cada noche
    assert all(lo < hi for lo, hi in sample) and sample == sorted(sample)
    assert sample_segments([], 1) == [] and len(sample_segments([9], 1)) == 1
    assert nightly_seed(date(2026, 11, 8)) != nightly_seed(date(2026, 11, 9))


def test_nightly_registra_la_semilla_y_los_segmentos_muestreados() -> None:
    seen: list[tuple[int, list[tuple[int, int]]]] = []
    long_run(LONG, record_sample=lambda seed, segments: seen.append((seed, segments)))
    assert len(seen) == 1 and seen[0][0] == SEED and len(seen[0][1]) >= 2


def test_nightly_con_el_worm_comprueba_cada_checkpoint() -> None:
    worm = worm_of(LONG)
    assert long_run(LONG, worm=worm).result == "integra"
    first = min(worm)
    worm[first] = {**worm[first], "checkpoint_hash": "0" * 64}
    assert long_run(LONG, worm=worm).reason == "checkpoint_mismatch"


def test_nightly_con_pocos_datos_re_hashea_todo() -> None:
    """Sin un checkpoint de hace mas de 7 dias, los 7 dias cubren toda la cadena."""
    report = run(ROWS, "nightly")
    assert report.result == "integra" and report.entries_checked == len(ROWS)
    assert datetime(2026, 1, 1, tzinfo=UTC) < NOW
