"""Los bordes de `verify` que los 6 motivos y los 4 modos no recorren (Paso 16; NFR-U3-52; BR-U3-11, 12).

Cadenas en memoria con `chain_builder`: checkpoints con la carga mal formada, el ancla de un tramo borrada, filas que faltan al final,
copias del WORM fuera del tramo o que la cadena no puede leer, y una cadena de checkpoints que no avanza.
"""

from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from chain_builder import entry_fields, rewrite_from, row_of, worm_of
from test_verify_modes import CHECKPOINTS, NOW, ROWS, SIGNER, replaced, run
from vectra_registry.chain import Row, format_timestamp
from vectra_registry.verify import ListSource, sample_segments, verify


def rewritten(rows: list[Row], index: int, edit: Any) -> list[Row]:
    return rewrite_from(rows, index, edit)


def test_sample_segments_con_los_cubiertos_vacios_no_elige_nada() -> None:
    assert sample_segments([], 1) == []


def test_sample_segments_une_los_cubiertos_en_segmentos_consecutivos() -> None:
    chosen = sample_segments([10, 5, 5, 20], 1)
    assert len(chosen) == 1 and chosen[0] in [(0, 5), (5, 10), (10, 20)]
    assert sample_segments([0], 1) == [(0, 0)]


def test_un_momento_que_no_es_texto_es_column_mismatch() -> None:
    report = run(rewritten(ROWS, 10, lambda body: body.__setitem__("occurred_at", 123)))
    assert (report.first_inconsistent_seq, report.reason) == (10, "column_mismatch")


def test_un_checkpoint_con_la_carga_que_no_es_un_objeto_es_checkpoint_signature() -> None:
    c = CHECKPOINTS[1].seq
    report = run(rewritten(ROWS, c, lambda body: body.__setitem__("payload", "texto")))
    assert (report.first_inconsistent_seq, report.reason) == (c, "checkpoint_signature")


def test_un_checkpoint_con_tipos_incorrectos_es_checkpoint_signature() -> None:
    c = CHECKPOINTS[1].seq
    for field, value in (("checkpoint_seq", True), ("checkpoint_seq", "5"), ("signature", 7)):
        report = run(rewritten(ROWS, c, lambda body, f=field, v=value: body["payload"].__setitem__(f, v)))
        assert (report.first_inconsistent_seq, report.reason) == (c, "checkpoint_signature"), (field, value)


def test_el_ancla_borrada_de_un_tramo_es_seq_gap_en_el_primer_seq_del_tramo() -> None:
    rows = [r for r in ROWS if r.seq != 9]
    report = run(rows, "range", from_seq=10, to_seq=20)
    assert (report.first_inconsistent_seq, report.reason) == (10, "seq_gap")


def test_el_ancla_y_la_primera_fila_del_tramo_borradas_es_seq_gap_en_la_primera_que_queda() -> None:
    rows = [r for r in ROWS if r.seq not in (9, 10)]
    report = run(rows, "range", from_seq=10, to_seq=20)
    assert (report.first_inconsistent_seq, report.reason) == (11, "seq_gap")


def test_un_tramo_cuya_fuente_se_queda_sin_filas_es_seq_gap_en_la_primera_que_falta() -> None:
    class Truncated(ListSource):
        """La cabeza dice 72 pero las filas se acaban en 70."""

        def head(self) -> int | None:
            return 72

        def rows(self, from_seq: int, to_seq: int) -> Iterable[Row]:
            return [r for r in super().rows(from_seq, to_seq) if r.seq <= 70]

    report = verify("full", Truncated(ROWS), public_keys=[SIGNER.public], now=NOW)
    assert (report.first_inconsistent_seq, report.reason) == (71, "seq_gap")


def test_un_tramo_que_empieza_despues_de_la_cabeza_es_seq_gap() -> None:
    report = run(ROWS, "range", from_seq=100, to_seq=110)
    assert (report.result, report.first_inconsistent_seq, report.reason) == ("inconsistente", 100, "seq_gap")


def test_la_verificacion_nocturna_de_una_cadena_vacia_no_tiene_genesis() -> None:
    report = run([], "nightly")
    assert (report.first_inconsistent_seq, report.reason) == (0, "seq_gap")


# --- WORM: copias que la cadena no puede leer o que caen fuera del tramo -----------------------------------------------------


def test_worm_con_un_checkpoint_ilegible_en_la_cadena_se_ignora_y_lo_demas_se_compara() -> None:
    c = CHECKPOINTS[2].seq
    broken = replaced(ROWS, c, canonical=b"no es json")
    report = run(broken, worm=worm_of(ROWS))
    assert (report.first_inconsistent_seq, report.reason) == (c, "hash")  # el hash de la fila ilegible falla primero


def test_worm_con_un_checkpoint_de_carga_mal_formada_en_la_cadena_se_ignora() -> None:
    c = CHECKPOINTS[2].seq
    report = run(rewritten(ROWS, c, lambda body: body.__setitem__("payload", "texto")), worm=worm_of(ROWS))
    assert report.first_inconsistent_seq == c  # lo delata la firma; el WORM no agrega nada


def test_worm_con_un_checkpoint_de_la_cadena_fuera_del_tramo_no_se_compara() -> None:
    worm = worm_of(ROWS)
    worm[CHECKPOINTS[5].seq - 1] = {**worm[CHECKPOINTS[5].seq - 1], "signature": "alterada"}
    report = run(ROWS, "range", from_seq=0, to_seq=10, worm=worm)
    assert report.result == "integra"


def test_worm_con_un_checkpoint_que_la_cadena_no_tiene_y_cae_fuera_del_tramo_no_se_informa() -> None:
    worm = worm_of(ROWS)
    worm[500] = {"checkpoint_seq": 500, "checkpoint_hash": "00" * 32, "signature": "x", "key_fingerprint": "y", "recorded_at": "z"}
    assert run(ROWS, "range", from_seq=0, to_seq=10, worm=worm).result == "integra"
    assert run(ROWS, "range", from_seq=499, to_seq=501, worm=worm).first_inconsistent_seq == 499  # fuera de la cadena: seq_gap primero


# --- Verificacion nocturna: la cadena de checkpoints --------------------------------------------------------------------------


def test_nocturna_con_un_checkpoint_ilegible_o_mal_formado_sigue_con_los_demas() -> None:
    c = CHECKPOINTS[2].seq
    unreadable = run(replaced(ROWS, c, canonical=b"no es json"), "nightly")
    assert (unreadable.first_inconsistent_seq, unreadable.reason) == (c, "hash")
    malformed = run(rewritten(ROWS, c, lambda body: body.__setitem__("payload", "texto")), "nightly")
    assert (malformed.first_inconsistent_seq, malformed.reason) == (c, "checkpoint_signature")


def test_nocturna_exige_que_la_cadena_de_checkpoints_avance() -> None:
    """Un checkpoint bien firmado que cubre otra vez lo ya cubierto: la cadena de checkpoints no avanza (BR-U3-11)."""
    first = CHECKPOINTS[0]
    again = first.seq - 1  # el seq que cubre el primer checkpoint
    rows = [r for r in ROWS if r.seq <= first.seq]
    stamp = rows[-1].recorded_at + timedelta(minutes=10)
    covered = rows[again]
    payload = {
        "checkpoint_seq": again,
        "checkpoint_hash": covered.hash.hex(),
        "signature": SIGNER.sign(again, covered.hash.hex(), format_timestamp(stamp)),
        "key_fingerprint": SIGNER.fingerprint,
    }
    rows.append(row_of(entry_fields(first.seq + 1, "checkpoint", payload, stamp), rows[-1].hash))
    report = run(rows, "nightly")
    assert (report.first_inconsistent_seq, report.reason) == (first.seq + 1, "checkpoint_mismatch")

