"""Verificador de la cadena (Paso 4 del plan; BR-U3-11, 12; NFR-U3-33; US-402).

Funcion pura sobre filas y checkpoints: no abre conexiones. Las filas llegan por un `RowSource` (la CLI de los CronJobs lo
implementa leyendo tramos de la replica; las pruebas, con `ListSource`). Detecta los 6 motivos de BR-U3-12 y devuelve el
`IntegrityReport` de U0 con el **primer** `seq` inconsistente (el menor de todos los hallazgos) y su motivo.

Nunca vuelve a serializar una entrada (BR-U3-09): el hash y las columnas se comprueban sobre los bytes de `canonical`.
"""

import base64
import binascii
import bisect
import hashlib
import math
import random
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from vectra_contracts.canonical import canonicalize as jcs
from vectra_contracts.models.registry import IntegrityReason, IntegrityReport

from vectra_registry.chain import GENESIS_PREV_HASH, Row, decode, link

Mode = Literal["incremental", "nightly", "full", "range"]

#: BR-U3-11: la verificacion `nightly` re-hashea los ultimos 7 dias y el 1 % de los segmentos mas antiguos.
RECENT_DAYS = 7
SAMPLE_FRACTION = 0.01
#: Hashes recientes que se recuerdan mientras se recorre: casi siempre un checkpoint cubre la fila anterior (BR-U3-08).
HASH_WINDOW = 64
#: Orden de los motivos de BR-U3-12 en una misma fila (los pasos 1 a 6).
ORDER: dict[IntegrityReason, int] = {
    "seq_gap": 0,
    "link": 1,
    "hash": 2,
    "column_mismatch": 3,
    "checkpoint_signature": 4,
    "checkpoint_mismatch": 5,
}


class RowSource(Protocol):
    """Lo que el verificador lee de la cadena. Las filas salen ordenadas por `seq`; las que no existen, no salen."""

    def head(self) -> int | None:
        """`seq` de la cabeza, o `None` si no hay filas."""

    def rows(self, from_seq: int, to_seq: int) -> Iterable[Row]:
        """Las filas con `from_seq <= seq <= to_seq`."""

    def checkpoints(self) -> Iterable[Row]:
        """Las filas `checkpoint` de toda la cadena, ordenadas por `seq`."""


class ListSource:
    """`RowSource` en memoria (pruebas y tramos ya leidos)."""

    def __init__(self, rows: Sequence[Row]) -> None:
        self._rows = sorted(rows, key=lambda row: row.seq)
        self._seqs = [row.seq for row in self._rows]

    def head(self) -> int | None:
        return self._seqs[-1] if self._seqs else None

    def rows(self, from_seq: int, to_seq: int) -> Iterable[Row]:
        return self._rows[bisect.bisect_left(self._seqs, from_seq) : bisect.bisect_right(self._seqs, to_seq)]

    def checkpoints(self) -> Iterable[Row]:
        return [row for row in self._rows if row.entry_type == "checkpoint"]


def nightly_seed(day: date) -> int:
    """Semilla de la muestra de la noche de `day`: distinta cada noche y reproducible con solo la fecha."""
    return day.toordinal()


def sample_segments(covered_seqs: Iterable[int], seed: int) -> list[tuple[int, int]]:
    """El 1 % (al menos uno) de los segmentos entre checkpoints, elegido con `seed`.

    `covered_seqs` son los `checkpoint_seq` de los checkpoints; el segmento `i` va de la cubierta anterior (0 para el primero)
    a la cubierta `i`, ambas incluidas.
    """
    segments: list[tuple[int, int]] = []
    previous = 0
    for covered in sorted(set(covered_seqs)):
        if not segments or covered > previous:
            segments.append((previous, covered))
            previous = covered
    if not segments:
        return []
    chosen = random.Random(seed).sample(range(len(segments)), math.ceil(len(segments) * SAMPLE_FRACTION))  # noqa: S311
    return sorted(segments[i] for i in chosen)


def _moment(text: object) -> datetime:
    if not isinstance(text, str):
        raise TypeError("sello de tiempo")
    return datetime.fromisoformat(text)


def _uuid(text: object) -> UUID:
    return UUID(str(text))


def columns_match(row: Row, body: Mapping[str, Any]) -> bool:
    """BR-U3-09: las columnas consultables coinciden con los valores decodificados de `canonical`."""
    try:
        actor = body["actor"]
        case = body.get("case_id")
        return (
            body["seq"] == row.seq
            and body["entry_type"] == row.entry_type
            and _uuid(body["idempotency_key"]) == row.idempotency_key
            and actor["kind"] == row.actor_kind
            and actor["id"] == row.actor_id
            and actor.get("role") == row.actor_role
            and _moment(body["occurred_at"]) == row.occurred_at
            and _moment(body["recorded_at"]) == row.recorded_at
            and body["correlation_id"] == row.correlation_id
            and (_uuid(case) if case is not None else None) == row.case_id
            and body.get("model_version_id") == row.model_version_id
            and body.get("policy_version_id") == row.policy_version_id
            and body["contract_version"] == row.contract_version
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _signature_ok(public_key: bytes, signature: str, message: bytes) -> bool:
    """La firma es base64 de los 64 bytes de Ed25519; la de Vault Transit trae el prefijo `vault:vN:`."""
    encoded = signature.rsplit(":", 1)[-1] if signature.startswith("vault:") else signature
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(base64.b64decode(encoded, validate=True), message)
    except (InvalidSignature, ValueError, binascii.Error):
        return False
    return True


def _checkpoint_fields(body: Mapping[str, Any]) -> tuple[int, str, str, str] | None:
    """`(checkpoint_seq, checkpoint_hash, signature, key_fingerprint)` del payload, o `None` si esta mal formado."""
    payload = body.get("payload")
    if not isinstance(payload, dict):
        return None
    covered, covered_hash = payload.get("checkpoint_seq"), payload.get("checkpoint_hash")
    signature, fingerprint = payload.get("signature"), payload.get("key_fingerprint")
    if (
        isinstance(covered, bool)
        or not isinstance(covered, int)
        or not all(isinstance(v, str) for v in (covered_hash, signature, fingerprint))
    ):
        return None
    return covered, str(covered_hash), str(signature), str(fingerprint)


class _Run:
    """El estado de una verificacion: el menor hallazgo, los conteos y los hashes recientes."""

    def __init__(self, source: RowSource, keys: Mapping[str, bytes], track_distinct: bool) -> None:
        self.source = source
        self.keys = keys
        self.best: tuple[int, int, IntegrityReason] | None = None
        self.hashes: dict[int, bytes] = {}
        self._rows = 0
        self._seen: set[int] | None = set() if track_distinct else None
        self.checkpoints_seen: set[int] = set()

    @property
    def entries_checked(self) -> int:
        return len(self._seen) if self._seen is not None else self._rows

    def count(self, seq: int) -> None:
        if self._seen is not None:
            self._seen.add(seq)
        else:
            self._rows += 1

    def add(self, seq: int, reason: IntegrityReason) -> None:
        found = (seq, ORDER[reason], reason)
        if self.best is None or found[:2] < self.best[:2]:
            self.best = found

    def remember(self, row: Row) -> None:
        self.hashes[row.seq] = row.hash
        self.hashes.pop(row.seq - HASH_WINDOW, None)

    def hash_of(self, seq: int) -> bytes | None:
        if seq in self.hashes:
            return self.hashes[seq]
        return next((row.hash for row in self.source.rows(seq, seq) if row.seq == seq), None)

    def check_checkpoint(self, row: Row, body: Mapping[str, Any]) -> None:
        """Paso 5 de BR-U3-12: firma valida con la llave vigente y `checkpoint_hash` = `hash` de `checkpoint_seq`."""
        self.checkpoints_seen.add(row.seq)
        fields = _checkpoint_fields(body)
        if fields is None:
            self.add(row.seq, "checkpoint_signature")
            return
        covered, covered_hash, signature, fingerprint = fields
        message = jcs({"checkpoint_seq": covered, "checkpoint_hash": covered_hash, "recorded_at": body.get("recorded_at")})
        key = self.keys.get(fingerprint)
        if key is None or not _signature_ok(key, signature, message):
            self.add(row.seq, "checkpoint_signature")
        stored = self.hash_of(covered) if 0 <= covered < row.seq else None
        if stored is None or stored.hex() != covered_hash:
            self.add(row.seq, "checkpoint_mismatch")  # la cadena ya no coincide con lo que el checkpoint firmo

    def scan(self, from_seq: int, to_seq: int) -> None:
        """Recorre `from_seq..to_seq` en orden de `seq` (pasos 1 a 5 de BR-U3-12). La fila `from_seq - 1`, si existe, solo ancla el enlace."""
        expected = from_seq
        prev: bytes | None = GENESIS_PREV_HASH if from_seq == 0 else None
        anchor_pending = from_seq > 0
        for row in self.source.rows(max(from_seq - 1, 0), to_seq):
            if anchor_pending:
                anchor_pending = False
                if row.seq == from_seq - 1:
                    prev = row.hash
                    self.remember(row)
                    continue
                if row.seq == from_seq:
                    self.add(from_seq, "seq_gap")  # la fila ancla (`from_seq - 1`) fue borrada
            if row.seq != expected:
                self.add(row.seq, "seq_gap")  # una fila borrada, repetida o fuera de lugar; el enlace no se puede juzgar
            elif prev is not None and row.prev_hash != prev:
                self.add(row.seq, "link")
            if link(row.prev_hash, row.canonical) != row.hash:
                self.add(row.seq, "hash")
            try:
                body = decode(row.canonical)
            except ValueError:
                body = None
            if body is None or not columns_match(row, body):
                self.add(row.seq, "column_mismatch")
            if body is not None and row.entry_type == "checkpoint":
                self.check_checkpoint(row, body)
            self.count(row.seq)
            self.remember(row)
            prev, expected = row.hash, row.seq + 1
        if expected <= to_seq:
            self.add(expected, "seq_gap")  # faltan filas al final del tramo

    def check_worm(self, from_seq: int, to_seq: int, worm: Mapping[int, Mapping[str, object]]) -> None:
        """Paso 6 de BR-U3-12: cada checkpoint del bucket WORM coincide con su entrada en la cadena.

        Un checkpoint que el bucket tiene y la cadena no se informa en `checkpoint_seq + 1`, el primer `seq` que ya no debio
        seguir a la fila cubierta.
        """
        in_chain: dict[int, tuple[int, Mapping[str, Any]]] = {}
        for row in self.source.checkpoints():
            try:
                chain_body = decode(row.canonical)
            except ValueError:
                continue
            fields = _checkpoint_fields(chain_body)
            if fields is not None:
                in_chain[fields[0]] = (row.seq, chain_body)
        for covered, copy in worm.items():
            if covered not in in_chain:
                if from_seq <= covered + 1 <= to_seq:
                    self.add(covered + 1, "checkpoint_mismatch")
                continue
            seq, body = in_chain[covered]
            if not from_seq <= seq <= to_seq:
                continue
            payload = body["payload"]
            same = copy.get("checkpoint_seq", covered) == covered and all(
                copy.get(name) == payload[name] for name in ("checkpoint_hash", "signature", "key_fingerprint")
            )
            if not same or copy.get("recorded_at") != body.get("recorded_at"):
                self.add(seq, "checkpoint_mismatch")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def verify(  # noqa: PLR0913
    mode: Mode,
    source: RowSource,
    *,
    public_keys: Iterable[bytes],
    worm: Mapping[int, Mapping[str, object]] | None = None,
    from_seq: int | None = None,
    to_seq: int | None = None,
    seed: int | None = None,
    now: datetime | None = None,
    record_sample: Callable[[int, list[tuple[int, int]]], None] | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> IntegrityReport:
    """Verifica la cadena en el `mode` pedido (BR-U3-11) y devuelve el `IntegrityReport` (domain-entities §5).

    - `full`: `seq = 0` hasta la cabeza, re-hash de todo.
    - `incremental`: desde `from_seq` (la cubierta del ultimo checkpoint verificado; 0 si no hay) hasta la cabeza.
    - `range`: `from_seq..to_seq` (el expediente: del checkpoint anterior al posterior o a la cabeza).
    - `nightly`: la cadena de checkpoints completa (firmas y enlaces) + re-hash de los ultimos 7 dias + re-hash del 1 % de los
      segmentos mas antiguos, elegido con `seed`, que es obligatoria; `record_sample` recibe la semilla y los segmentos para
      dejarlos registrados.

    `public_keys` son las llaves publicas Ed25519 (32 bytes) de los checkpoints; la huella de cada una es su SHA-256. `worm`
    son las copias del bucket, por `checkpoint_seq`. Las excepciones de la fuente no se atrapan: la CLI las traduce a `error`.
    """
    started = clock()
    if mode == "range" and (from_seq is None or to_seq is None or from_seq < 0 or from_seq > to_seq):
        raise ValueError("range exige from_seq y to_seq ordenados")
    if mode == "nightly" and seed is None:
        raise ValueError("nightly exige una semilla registrada")
    keys = {hashlib.sha256(key).hexdigest(): key for key in public_keys}
    head = source.head()
    last = head if head is not None else -1
    run = _Run(source, keys, track_distinct=mode == "nightly")

    if mode == "range":
        assert from_seq is not None and to_seq is not None
        low, high = from_seq, min(to_seq, last) if last >= 0 else to_seq
        if from_seq > last:
            run.add(from_seq, "seq_gap")
        else:
            run.scan(low, high)
        scope_end = to_seq
    elif mode == "nightly":
        assert seed is not None
        low, high, scope_end = 0, max(last, 0), last + 1
        _nightly(run, last, seed, now or clock(), record_sample)
    else:
        low = (from_seq or 0) if mode == "incremental" else 0
        high, scope_end = max(last, low), last + 1
        if last < low:
            run.add(low, "seq_gap")
        else:
            run.scan(low, last)
    if worm:
        run.check_worm(low, scope_end, worm)

    found = run.best
    return IntegrityReport(
        mode=mode,
        from_seq=low,
        to_seq=high,
        entries_checked=run.entries_checked,
        checkpoints_checked=len(run.checkpoints_seen),
        result="inconsistente" if found else "integra",
        first_inconsistent_seq=found[0] if found else None,
        reason=found[2] if found else None,
        started_at=started,
        finished_at=clock(),
    )


def _nightly(
    run: _Run, last: int, seed: int, now: datetime, record_sample: Callable[[int, list[tuple[int, int]]], None] | None
) -> None:
    """BR-U3-11, NFR-U3-33: cadena de checkpoints completa + ultimos 7 dias + 1 % de los segmentos mas antiguos."""
    if last < 0:
        run.add(0, "seq_gap")
        return
    cutoff = now - timedelta(days=RECENT_DAYS)
    covered_seqs: list[int] = []
    recent_start = 0
    previous_covered = -1
    for row in run.source.checkpoints():
        run.scan(row.seq, row.seq)  # el par (fila anterior, checkpoint): enlace, hash, columnas, firma y cubierta
        try:
            fields = _checkpoint_fields(decode(row.canonical))
        except ValueError:
            fields = None
        if fields is None:
            continue
        if fields[0] <= previous_covered:
            run.add(row.seq, "checkpoint_mismatch")  # la cadena de checkpoints avanza siempre
        previous_covered = max(previous_covered, fields[0])
        covered_seqs.append(fields[0])
        if row.recorded_at < cutoff:
            recent_start = max(recent_start, fields[0])
    run.scan(recent_start, last)
    older = [covered for covered in covered_seqs if covered <= recent_start]
    segments = sample_segments(older, seed)
    if record_sample is not None:
        record_sample(seed, segments)
    for low, high in segments:
        run.scan(low, high)
