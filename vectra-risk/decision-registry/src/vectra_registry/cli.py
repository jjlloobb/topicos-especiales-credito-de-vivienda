"""CLI `vectra-registry` (Paso 11; BR-U3-08, 11, 12, 13, 17; NFR-U3-04, 12, 40; P-U3-03, 07; US-402).

    vectra-registry verify --mode incremental|nightly|full|range [--source db|archive] [--month AAAA-MM]
    vectra-registry archive --month AAAA-MM
    vectra-registry aggregator run [--until-head]
    vectra-registry aggregator reset

Codigos de salida (BR-U3-13): `0` integra, `1` inconsistente (alerta `RegistryChainBroken`, SEV1) y `2` error de ejecucion (la base o
el bucket no responden; alerta `RegistryVerificationFailed`, SEV2). El informe sale por stdout en JSON; los avisos, por stderr.

`checkpoint` (BR-U3-08) **no esta**: la firma cubre el `recorded_at` de la propia entrada y el append lo asigna dentro del lock, asi que
la CLI no puede firmarlo antes. Es una decision de diseno pendiente (CANDIDATAS.md, U03-T03 y U03-T04).

Configuracion por variables de entorno (las entrega el chart con los Secrets de ESO):

- `REGISTRY_RO_VERIFIER_DSN` (verify, archive: replica con `registry_verifier`), `REGISTRY_AGGREGATOR_DSN` (`aggregator run`),
  `REGISTRY_MIGRATOR_DSN` (`aggregator reset`);
- `REGISTRY_CHECKPOINT_PUBLIC_KEYS`: llaves publicas Ed25519 en base64, separadas por comas (sin ella se pide a la boveda);
- `VECTRA_VAULT_ADDR` y `VECTRA_VAULT_TOKEN` (o `VECTRA_VAULT_TOKEN_FILE`), `REGISTRY_TRANSIT_MOUNT` y `REGISTRY_TRANSIT_KEY`;
- `REGISTRY_S3_ENDPOINT`, `REGISTRY_S3_ACCESS_KEY`, `REGISTRY_S3_SECRET_KEY`, `REGISTRY_S3_CHECKPOINT_BUCKET` y
  `REGISTRY_S3_ARCHIVE_BUCKET`.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast

import psycopg
from psycopg import errors as pg_errors
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_contracts.models.registry import IntegrityReport

from vectra_registry import aggregator, archive
from vectra_registry.chain import Row
from vectra_registry.vault import ExternalError, Transit, batch_client
from vectra_registry.verify import Mode, nightly_seed, verify
from vectra_registry.worm import S3, read_checkpoints

EXIT_OK: Final = 0
EXIT_INCONSISTENT: Final = 1
EXIT_ERROR: Final = 2
#: P-U3-07, BR-U3-13b: tramos de <= 10 000 entradas, cada uno en su transaccion, con 3 intentos si la replica cancela la consulta.
CHUNK: Final = 10_000
ATTEMPTS: Final = 3
DEFAULT_CHECKPOINT_BUCKET: Final = "vectra-registry-checkpoints"
DEFAULT_ARCHIVE_BUCKET: Final = "vectra-registry-archive"

COLUMNS: Final = (
    "seq, idempotency_key, entry_type, case_id, model_version_id, policy_version_id, actor_kind, actor_id, actor_role, "
    "occurred_at, recorded_at, correlation_id, contract_version, canonical, prev_hash, hash"
)


class ConfigError(Exception):
    """Falta una variable de entorno o es invalida."""


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"falta la variable de entorno {name}")
    return value


def _out(text: str) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _log(level: str, event: str, **fields: object) -> None:
    sys.stderr.write(json.dumps({"level": level, "event": event, **fields}, default=str, sort_keys=True) + "\n")


# --- Lectura de la cadena (replica, en tramos) -------------------------------------------------------------------------------


def _row(values: Sequence[Any]) -> Row:
    return Row(
        seq=values[0], idempotency_key=values[1], entry_type=values[2], case_id=values[3], model_version_id=values[4],
        policy_version_id=values[5], actor_kind=values[6], actor_id=values[7], actor_role=values[8], occurred_at=values[9],
        recorded_at=values[10], correlation_id=values[11], contract_version=values[12], canonical=bytes(values[13]),
        prev_hash=bytes(values[14]), hash=bytes(values[15]),
    )  # fmt: skip


class DbSource:
    """`RowSource` sobre PostgreSQL: lee en tramos de <= 10 000 entradas por `seq`, cada uno en su transaccion corta.

    Un tramo cancelado por un conflicto de recuperacion en la replica (`max_standby_streaming_delay = 2s`) se reintenta hasta 3 veces.
    """

    def __init__(self, dsn: str, chunk: int = CHUNK, attempts: int = ATTEMPTS) -> None:
        self._conn = psycopg.connect(dsn, connect_timeout=5, autocommit=True)
        self._chunk = chunk
        self._attempts = attempts

    def close(self) -> None:
        self._conn.close()

    def _query(self, statement: str, params: Sequence[object] = ()) -> list[tuple[Any, ...]]:
        for attempt in range(1, self._attempts + 1):
            try:
                with self._conn.transaction():
                    return self._conn.execute(statement, params).fetchall()
            except (pg_errors.QueryCanceled, pg_errors.SerializationFailure):
                if attempt == self._attempts:
                    raise
                time.sleep(0.2 * attempt)
        raise AssertionError("inalcanzable")  # pragma: no cover

    def head(self) -> int | None:
        value = self._query("SELECT max(seq) FROM registry_entries")[0][0]
        return None if value is None else int(value)

    def rows(self, from_seq: int, to_seq: int) -> Iterator[Row]:
        low = from_seq
        while low <= to_seq:
            high = min(low + self._chunk - 1, to_seq)
            found = self._query(
                f"SELECT {COLUMNS} FROM registry_entries WHERE seq BETWEEN %s AND %s ORDER BY seq",  # noqa: S608
                (low, high),
            )
            yield from (_row(r) for r in found)
            low = high + 1

    def checkpoints(self) -> Iterator[Row]:
        yield from (
            _row(r)
            for r in self._query(f"SELECT {COLUMNS} FROM registry_entries WHERE entry_type = 'checkpoint' ORDER BY seq")  # noqa: S608
        )

    def month_range(self, start: datetime, end: datetime) -> tuple[int, int] | None:
        """Primer y ultimo `seq` registrados en `[start, end)`; `recorded_at` no decrece con `seq` (BR-U3-05)."""
        low, high = self._query(
            "SELECT min(seq), max(seq) FROM registry_entries WHERE recorded_at >= %s AND recorded_at < %s", (start, end)
        )[0]
        return None if low is None else (int(low), int(high))


# --- Configuracion de la boveda y del bucket ---------------------------------------------------------------------------------


def _vault_token() -> str:
    path = os.environ.get("VECTRA_VAULT_TOKEN_FILE")
    return Path(path).read_text().strip() if path else _env("VECTRA_VAULT_TOKEN")


def transit() -> Transit:
    client = batch_client("vault", _env("VECTRA_VAULT_ADDR"))
    return Transit(
        client,
        _vault_token(),
        mount=os.environ.get("REGISTRY_TRANSIT_MOUNT", "transit"),
        key=os.environ.get("REGISTRY_TRANSIT_KEY", "registry-checkpoints"),
    )


def s3() -> S3:
    endpoint = _env("REGISTRY_S3_ENDPOINT")
    return S3(batch_client("s3", endpoint), endpoint, _env("REGISTRY_S3_ACCESS_KEY"), _env("REGISTRY_S3_SECRET_KEY"))


def public_keys() -> list[bytes]:
    """Las llaves publicas de checkpoints: del entorno (ConfigMap) o, sin ellas, la vigente en la boveda."""
    raw = os.environ.get("REGISTRY_CHECKPOINT_PUBLIC_KEYS", "")
    keys = [base64.b64decode(part, validate=True) for part in raw.split(",") if part.strip()]
    if keys or not os.environ.get("VECTRA_VAULT_ADDR"):
        return keys
    return [asyncio.run(transit().public_key())]


def _worm() -> dict[int, dict[str, object]] | None:
    """Las copias del bucket de checkpoints si el bucket esta configurado (paso 6 de BR-U3-12); si no, no se compara."""
    if not os.environ.get("REGISTRY_S3_ENDPOINT"):
        return None
    bucket = os.environ.get("REGISTRY_S3_CHECKPOINT_BUCKET", DEFAULT_CHECKPOINT_BUCKET)
    return asyncio.run(read_checkpoints(s3(), bucket))


# --- Comandos ----------------------------------------------------------------------------------------------------------------


def _code(report: IntegrityReport) -> int:
    if report.result == "integra":
        return EXIT_OK
    _log("error", "RegistryChainBroken", severity="SEV1", first_inconsistent_seq=report.first_inconsistent_seq, reason=report.reason)
    return EXIT_INCONSISTENT


def _last_cover(source: DbSource) -> int:
    """`incremental` parte de la cubierta del ultimo checkpoint de la cadena (0 si no hay): lo anterior lo cubre su firma."""
    last = 0
    for row in source.checkpoints():
        fields = archive.checkpoint_fields_of(row)
        if fields is not None:
            last = fields[0]
    return last


def cmd_verify(args: argparse.Namespace, clock: Callable[[], datetime]) -> int:
    keys = public_keys()
    if args.source == "archive":
        return _verify_archive(args, keys)
    source = DbSource(args.dsn or _env("REGISTRY_RO_VERIFIER_DSN"))
    try:
        worm = _worm()
        mode = cast(Mode, args.mode)
        now = clock()
        extra: dict[str, Any] = {}
        if mode == "incremental":
            extra["from_seq"] = args.from_seq if args.from_seq is not None else _last_cover(source)
        elif mode == "range":
            extra.update(from_seq=args.from_seq, to_seq=args.to_seq)
        elif mode == "nightly":
            extra.update(
                seed=nightly_seed(now.date()),
                record_sample=lambda seed, segments: _log("info", "nightly_sample", seed=seed, segments=segments),
            )
        report = verify(mode, source, public_keys=keys, worm=worm, now=now, **extra)
    finally:
        source.close()
    _out(report.model_dump_json())
    return _code(report)


def _verify_archive(args: argparse.Namespace, keys: list[bytes]) -> int:
    month = args.month
    bucket = os.environ.get("REGISTRY_S3_ARCHIVE_BUCKET", DEFAULT_ARCHIVE_BUCKET)

    async def fetch() -> tuple[bytes, bytes]:
        client = s3()
        return await client.get(bucket, archive.archive_key(month)), await client.get(bucket, archive.manifest_key(month))

    data, manifest_bytes = asyncio.run(fetch())
    try:
        manifest = json.loads(manifest_bytes)
    except ValueError as error:
        raise ExternalError("el manifiesto no es JSON") from error
    report = archive.verify_archive(data, manifest, keys)
    _out(report.model_dump_json())
    return _code(report)


def _month_rows(source: DbSource, start: datetime, end: datetime) -> tuple[archive.Writer, int]:
    """Lee el mes (mas el ancla) en tramos y arma el archivo. Devuelve el escritor y el primer `seq` del mes."""
    found = source.month_range(start, end)
    if found is None:
        raise ConfigError(f"no hay entradas registradas entre {start:%Y-%m-%d} y {end:%Y-%m-%d}")
    low, high = found
    covers = [f[0] for r in source.checkpoints() if low <= r.seq <= high and (f := archive.checkpoint_fields_of(r))]
    first = max(0, min([low - 1, *covers]))
    writer = archive.Writer()
    writer.add(source.rows(first, high))
    return writer, low


def cmd_archive(args: argparse.Namespace) -> int:
    start, end = archive.month_bounds(args.month)
    source = DbSource(args.dsn or _env("REGISTRY_RO_VERIFIER_DSN"))
    try:
        writer, from_seq = _month_rows(source, start, end)
    finally:
        source.close()
    data = writer.finish()
    bucket = os.environ.get("REGISTRY_S3_ARCHIVE_BUCKET", DEFAULT_ARCHIVE_BUCKET)

    async def export() -> tuple[bytes, dict[str, Any], bytes, bytes]:
        vault, client = transit(), s3()
        public = await vault.public_key()
        manifest = archive.build_manifest(writer, data, args.month, from_seq, hashlib.sha256(public).hexdigest())
        manifest["signature"] = await vault.sign(archive.manifest_message(manifest))
        await client.put(bucket, archive.archive_key(args.month), data)
        await client.put(bucket, archive.manifest_key(args.month), json.dumps(manifest, sort_keys=True).encode())
        # Se vuelve a descargar lo subido y se verifica sin base de datos (P-U3-07, pasos 4 y 5).
        downloaded = await client.get(bucket, archive.archive_key(args.month))
        return public, manifest, downloaded, await client.get(bucket, archive.manifest_key(args.month))

    public, manifest, downloaded, stored_bytes = asyncio.run(export())
    stored = json.loads(stored_bytes)
    report = archive.verify_archive(downloaded, stored, [public])
    _out(report.model_dump_json())
    if report.result != "integra":
        _log("error", "ArchiveExportFailed", severity="SEV2", month=args.month, reason=report.reason)
        return EXIT_INCONSISTENT
    _log("info", "archive_closed", month=args.month, from_seq=manifest["from_seq"], to_seq=manifest["to_seq"])
    return EXIT_OK


def cmd_aggregator(args: argparse.Namespace) -> int:
    if args.action == "run":
        report = aggregator.run(args.dsn or _env("REGISTRY_AGGREGATOR_DSN"), until_head=args.until_head)
        _out(report.as_json())
        return EXIT_OK
    mark = aggregator.reset(args.dsn or _env("REGISTRY_MIGRATOR_DSN"))
    _out(json.dumps({"watermark": mark}))
    return EXIT_OK


# --- Entrada -----------------------------------------------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="vectra-registry", description="CLI del registro de decisiones (U3)")
    sub = root.add_subparsers(dest="command", required=True)

    v = sub.add_parser("verify", help="verifica la cadena (BR-U3-11, 12)")
    v.add_argument("--mode", choices=["incremental", "nightly", "full", "range"], required=True)
    v.add_argument("--source", choices=["db", "archive"], default="db")
    v.add_argument("--from-seq", type=int)
    v.add_argument("--to-seq", type=int)
    v.add_argument("--month", help="AAAA-MM del archivo (con --source archive)")
    v.add_argument("--dsn")

    a = sub.add_parser("archive", help="archivo mensual de largo plazo (P-U3-07)")
    a.add_argument("--month", required=True, help="AAAA-MM")
    a.add_argument("--dsn")

    g = sub.add_parser("aggregator", help="agregador de monitoreo (BR-U3-17)")
    actions = g.add_subparsers(dest="action", required=True)
    r = actions.add_parser("run", help="itera lotes hasta la cabeza o 240 s")
    r.add_argument("--until-head", action="store_true", help="sin tope de tiempo (Job de reconstruccion)")
    r.add_argument("--dsn")
    z = actions.add_parser("reset", help="vacia las tablas derivadas (solo registry_migrator)")
    z.add_argument("--dsn")
    return root


def _validate(args: argparse.Namespace, root: argparse.ArgumentParser) -> None:
    if args.command != "verify":
        return
    if args.source == "archive" and (args.month is None or args.mode != "full"):
        root.error("--source archive exige --mode full y --month")
    if args.mode == "range" and args.source == "db" and (args.from_seq is None or args.to_seq is None):
        root.error("--mode range exige --from-seq y --to-seq")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def main(argv: Sequence[str] | None = None, *, clock: Callable[[], datetime] = _utc_now) -> int:
    root = parser()
    args = root.parse_args(argv)
    _validate(args, root)
    try:
        if args.command == "verify":
            return cmd_verify(args, clock)
        if args.command == "archive":
            return cmd_archive(args)
        return cmd_aggregator(args)
    except aggregator.RebuildInProgress as error:
        _log("error", "RebuildInProgress", error=str(error))
    except (
        psycopg.Error,
        ExternalError,
        ConfigError,
        DependencyUnavailable,
        DependencyTimeout,
        OSError,
        ValueError,
    ) as error:
        _log("error", "RegistryVerificationFailed", severity="SEV2", error=f"{type(error).__name__}: {error}")
    return EXIT_ERROR


__all__ = ["DbSource", "main", "parser"]

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
