"""CLI `vectra-registry` (Paso 11 del plan de U3; BR-U3-08, 11, 12, 13, 17; NFR-U3-04, 12, 40; P-U3-03, 07; US-402).

Con Testcontainers: PostgreSQL, MinIO con object lock y Vault dev (Transit Ed25519). Una prueba por viñeta de aceptacion del Paso 11.

`checkpoint` no esta en esta tarea: la firma cubre el `recorded_at` de la propia entrada y el append lo asigna dentro del lock
(decision de diseno pendiente, CANDIDATAS.md). Sus dos viñetas (dos `checkpoint` en la misma hora -> uno; Vault caido -> el
checkpoint falla con alerta) quedan sin caso; `test_checkpoint_no_existe_hasta_decidir_la_firma` fija ese estado.
"""

import asyncio
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from cli_support import (
    add_checkpoint,
    checkpoint_copy,
    dsn,
    seed_events,
    seed_specs,
    tamper,
)
from entries import entry_dict
from registry_pg import Db
from registry_services import ARCHIVE_BUCKET, CHECKPOINT_BUCKET, Minio, Vault
from testcontainers.postgres import PostgresContainer
from vectra_registry import archive, cli
from vectra_registry.chain import canonicalize, decode, link
from vectra_registry.worm import checkpoint_key

pytestmark = pytest.mark.integration

START = datetime(2030, 1, 15, 12, 0, tzinfo=UTC)
MONTH = "2030-01"


class Cli:
    """Una invocacion de `vectra-registry main()` con su entorno; devuelve el codigo de salida, stdout y stderr."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        self.mp = monkeypatch
        self.capsys = capsys

    def env(self, **values: str) -> None:
        for name, value in values.items():
            self.mp.setenv(name, value)

    def run(self, *argv: str) -> tuple[int, str, str]:
        self.capsys.readouterr()
        try:
            code = cli.main(list(argv))
        except SystemExit as exit_:  # argparse
            code = int(exit_.code or 0)
        out = self.capsys.readouterr()
        return code, out.out, out.err


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], pg: PostgresContainer, db: Db, vault: Vault) -> Cli:
    runner = Cli(monkeypatch, capsys)
    runner.env(
        REGISTRY_RO_VERIFIER_DSN=dsn(pg, db, "registry_verifier"),
        REGISTRY_AGGREGATOR_DSN=dsn(pg, db, "registry_aggregator"),
        REGISTRY_MIGRATOR_DSN=dsn(pg, db, "registry_migrator"),
        REGISTRY_CHECKPOINT_PUBLIC_KEYS=vault.public_key_b64,
        VECTRA_VAULT_ADDR=vault.url,
        VECTRA_VAULT_TOKEN="root-token",
    )
    return runner


@pytest.fixture
def worm(run: Cli, minio: Minio) -> Minio:
    run.env(**minio.env())
    return minio


def chain(db: Db, vault: Vault, entries: int = 12, checkpoints: int = 2) -> list[int]:
    """Una cadena con `checkpoints` checkpoints firmados por la boveda, repartidos entre las entradas."""
    seqs: list[int] = []
    per = entries // checkpoints
    clock = START
    for _ in range(checkpoints):
        seqs += seed_events(db, per, clock)
        clock += timedelta(minutes=per + 1)
        seqs.append(add_checkpoint(db, vault))
    return seqs


def report(out: str) -> dict[str, Any]:
    return json.loads(out)  # type: ignore[no-any-return]


# --- verify: codigos 0, 1 y 2 -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["incremental", "nightly", "full"])
def test_verify_sobre_una_cadena_integra_sale_con_0(run: Cli, db: Db, vault: Vault, mode: str) -> None:
    chain(db, vault)
    code, out, err = run.run("verify", "--mode", mode)
    assert code == 0, err
    assert report(out)["result"] == "integra"
    assert report(out)["mode"] == mode


def test_verify_range_sobre_una_cadena_integra_sale_con_0(run: Cli, db: Db, vault: Vault) -> None:
    seqs = chain(db, vault)
    code, out, err = run.run("verify", "--mode", "range", "--from-seq", str(seqs[2]), "--to-seq", str(seqs[-1]))
    assert code == 0, err
    assert (report(out)["from_seq"], report(out)["to_seq"]) == (seqs[2], seqs[-1])


@pytest.mark.parametrize("mode", ["full", "incremental"])
def test_verify_sobre_una_cadena_alterada_sale_con_1_y_el_primer_seq(run: Cli, db: Db, vault: Vault, mode: str) -> None:
    seqs = chain(db, vault)
    victim = seqs[-2]  # despues del ultimo checkpoint cubierto cuando es incremental
    tamper(db, victim, "canonical", b'{"seq":%d,"alterada":true}' % victim)
    code, out, err = run.run("verify", "--mode", mode, *(["--from-seq", "0"] if mode == "incremental" else []))
    assert code == 1
    assert report(out)["result"] == "inconsistente"
    assert report(out)["first_inconsistent_seq"] == victim
    assert report(out)["reason"] == "hash"
    assert "RegistryChainBroken" in err


def test_verify_con_la_base_caida_sale_con_2(run: Cli, db: Db) -> None:
    run.env(REGISTRY_RO_VERIFIER_DSN="postgresql://registry_verifier:x@127.0.0.1:1/nada")
    code, out, err = run.run("verify", "--mode", "full")
    assert code == 2
    assert out == ""
    assert "RegistryVerificationFailed" in err


def test_verify_sin_la_variable_de_la_base_sale_con_2(run: Cli, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGISTRY_RO_VERIFIER_DSN")
    code, _, err = run.run("verify", "--mode", "full")
    assert code == 2
    assert "REGISTRY_RO_VERIFIER_DSN" in err


@pytest.mark.parametrize(
    "argv",
    [
        ["verify", "--mode", "range"],
        ["verify", "--mode", "incremental", "--source", "archive"],
        ["verify", "--mode", "otro"],
        [],
    ],
)
def test_argumentos_invalidos_salen_con_2(run: Cli, argv: list[str]) -> None:
    code, _, _ = run.run(*argv)
    assert code == 2


def test_verify_incremental_parte_de_la_cubierta_del_ultimo_checkpoint(run: Cli, db: Db, vault: Vault) -> None:
    seqs = chain(db, vault)
    tamper(db, 1, "canonical", b"{}")  # antes de la cubierta del ultimo checkpoint: incremental no mira ahi, full si
    covered = checkpoint_copy(db, seqs[-1])[0]
    code, out, _ = run.run("verify", "--mode", "incremental")
    assert code == 0, out
    assert report(out)["from_seq"] == covered
    assert run.run("verify", "--mode", "full")[0] == 1


# --- verify contra el bucket WORM (paso 6 de BR-U3-12) ---------------------------------------------------------------------


def export_checkpoints(db: Db, minio: Minio, seqs: list[int]) -> None:
    async def put() -> None:
        client = minio.client()
        for seq in seqs:
            cover, data = checkpoint_copy(db, seq)
            await client.put(CHECKPOINT_BUCKET, checkpoint_key(cover), data)

    asyncio.run(put())


def checkpoint_seqs(db: Db) -> list[int]:
    return [int(r[0]) for r in db.query("SELECT seq FROM registry_entries WHERE entry_type = 'checkpoint' ORDER BY seq")]  # type: ignore[call-overload]


def test_verify_compara_los_checkpoints_del_bucket_con_la_cadena(run: Cli, worm: Minio, db: Db, vault: Vault) -> None:
    chain(db, vault)
    export_checkpoints(db, worm, checkpoint_seqs(db))
    code, out, err = run.run("verify", "--mode", "full")
    assert code == 0, err
    assert report(out)["checkpoints_checked"] == 2


def test_verify_con_una_copia_alterada_en_el_bucket_sale_con_1(run: Cli, worm: Minio, db: Db, vault: Vault) -> None:
    chain(db, vault)
    seqs = checkpoint_seqs(db)
    export_checkpoints(db, worm, seqs)
    cover, data = checkpoint_copy(db, seqs[0])
    forged = json.loads(data)
    forged["signature"] = "A" * 86 + "=="
    asyncio.run(worm.client().put(CHECKPOINT_BUCKET, checkpoint_key(cover), json.dumps(forged).encode()))
    code, out, _ = run.run("verify", "--mode", "full")
    assert code == 1
    assert report(out)["reason"] == "checkpoint_mismatch"
    assert report(out)["first_inconsistent_seq"] == seqs[0]


def test_verify_con_el_bucket_caido_sale_con_2(run: Cli, worm: Minio, db: Db, vault: Vault) -> None:
    chain(db, vault)
    run.env(REGISTRY_S3_ENDPOINT="http://127.0.0.1:1")
    code, _, err = run.run("verify", "--mode", "full")
    assert code == 2
    assert "RegistryVerificationFailed" in err


# --- archive: NDJSON + zstd, manifiesto firmado, subida, descarga y verificacion -------------------------------------------


def archive_run(run: Cli, minio: Minio, vault: Vault, db: Db) -> list[int]:
    seqs = chain(db, vault, entries=14, checkpoints=2)
    run.env(**minio.env())
    code, out, err = run.run("archive", "--month", MONTH)
    assert code == 0, err
    assert report(out)["result"] == "integra"
    return seqs


def test_archive_sube_descarga_y_verifica_con_exit_0(run: Cli, minio: Minio, db: Db, vault: Vault) -> None:
    seqs = archive_run(run, minio, vault, db)

    async def objects() -> tuple[bytes, dict[str, Any]]:
        client = minio.client()
        return await client.get(ARCHIVE_BUCKET, archive.archive_key(MONTH)), json.loads(
            await client.get(ARCHIVE_BUCKET, archive.manifest_key(MONTH))
        )

    data, manifest = asyncio.run(objects())
    rows = archive.read_rows(data)
    assert rows[-1].seq == seqs[-1] == manifest["to_seq"]
    assert manifest["head_hash"] == rows[-1].hash.hex()
    assert manifest["checkpoints"] == [r.seq for r in rows if r.entry_type == "checkpoint"]
    assert manifest["contract_versions"] and manifest["signature"].startswith("vault:v1:")
    # El archivo se verifica **sin base de datos**.
    run.env(REGISTRY_RO_VERIFIER_DSN="postgresql://x:x@127.0.0.1:1/nada")
    code, out, err = run.run("verify", "--mode", "full", "--source", "archive", "--month", MONTH)
    assert code == 0, err
    assert report(out)["result"] == "integra"


def put_archive(minio: Minio, data: bytes | None = None, manifest: dict[str, Any] | None = None) -> None:
    async def put() -> None:
        client = minio.client()
        if data is not None:
            await client.put(ARCHIVE_BUCKET, archive.archive_key(MONTH), data)
        if manifest is not None:
            await client.put(ARCHIVE_BUCKET, archive.manifest_key(MONTH), json.dumps(manifest).encode())

    asyncio.run(put())


def stored(minio: Minio) -> tuple[bytes, dict[str, Any]]:
    async def get() -> tuple[bytes, bytes]:
        client = minio.client()
        return await client.get(ARCHIVE_BUCKET, archive.archive_key(MONTH)), await client.get(
            ARCHIVE_BUCKET, archive.manifest_key(MONTH)
        )

    data, manifest = asyncio.run(get())
    return data, json.loads(manifest)


def test_archivo_con_un_byte_alterado_sale_con_1(run: Cli, minio: Minio, db: Db, vault: Vault) -> None:
    archive_run(run, minio, vault, db)
    data, _ = stored(minio)
    put_archive(minio, data=data[:40] + bytes([data[40] ^ 1]) + data[41:])
    code, out, err = run.run("verify", "--mode", "full", "--source", "archive", "--month", MONTH)
    assert code == 1
    assert report(out)["reason"] == "hash"
    assert "RegistryChainBroken" in err


def test_archivo_reescrito_y_con_el_manifiesto_refirmado_sale_con_1_por_la_cadena(
    run: Cli, minio: Minio, db: Db, vault: Vault
) -> None:
    """Quien tiene la boveda (o la reescribe) y rehace sha256 y firma, igual no oculta una entrada alterada: el enlace se rompe."""
    archive_run(run, minio, vault, db)
    data, manifest = stored(minio)
    rows = archive.read_rows(data)
    writer = archive.Writer()
    victim = rows[len(rows) // 2]
    body = decode(victim.canonical)
    body["payload"] = {**body["payload"], "alterado": True}
    forged = canonicalize(body)
    writer.add([r if r.seq != victim.seq else _with_canonical(r, forged) for r in rows])
    new_data = writer.finish()
    manifest = {**manifest, "sha256": hashlib.sha256(new_data).hexdigest()}
    manifest.pop("signature")
    manifest["signature"] = vault.sign(archive.manifest_message(manifest))
    put_archive(minio, data=new_data, manifest=manifest)
    code, out, _ = run.run("verify", "--mode", "full", "--source", "archive", "--month", MONTH)
    assert code == 1
    assert report(out)["first_inconsistent_seq"] == victim.seq
    assert report(out)["reason"] == "hash"


def _with_canonical(row: Any, canonical: bytes) -> Any:
    return replace(row, canonical=canonical)


def test_archivo_con_el_manifiesto_alterado_sale_con_1_por_la_firma(run: Cli, minio: Minio, db: Db, vault: Vault) -> None:
    archive_run(run, minio, vault, db)
    _, manifest = stored(minio)
    put_archive(minio, manifest={**manifest, "to_seq": manifest["to_seq"] + 1})
    code, out, _ = run.run("verify", "--mode", "full", "--source", "archive", "--month", MONTH)
    assert code == 1
    assert report(out)["reason"] == "checkpoint_signature"


def test_archivo_inexistente_sale_con_2(run: Cli, minio: Minio, db: Db, vault: Vault) -> None:
    chain(db, vault)
    run.env(**minio.env())
    code, _, err = run.run("verify", "--mode", "full", "--source", "archive", "--month", "1999-01")
    assert code == 2
    assert "RegistryVerificationFailed" in err


def test_archive_con_la_boveda_caida_sale_con_2_y_no_sube_nada(run: Cli, minio: Minio, db: Db, vault: Vault) -> None:
    chain(db, vault)
    run.env(**minio.env(), VECTRA_VAULT_ADDR="http://127.0.0.1:1")
    code, _, err = run.run("archive", "--month", MONTH)
    assert code == 2
    assert "RegistryVerificationFailed" in err
    assert asyncio.run(minio.client().keys(ARCHIVE_BUCKET, "registry-1999")) == []


def test_archive_de_un_mes_sin_entradas_sale_con_2(run: Cli, minio: Minio, db: Db, vault: Vault) -> None:
    run.env(**minio.env())
    code, _, err = run.run("archive", "--month", "1999-01")
    assert code == 2
    assert "no hay entradas" in err


def test_el_objeto_del_archivo_tiene_object_lock_compliance(run: Cli, minio: Minio, db: Db, vault: Vault) -> None:
    archive_run(run, minio, vault, db)

    async def head() -> Any:
        return await minio.client().request("HEAD", f"/{ARCHIVE_BUCKET}/{archive.archive_key(MONTH)}")

    response = asyncio.run(head())
    assert response.headers["x-amz-object-lock-mode"] == "COMPLIANCE"
    retain = datetime.fromisoformat(response.headers["x-amz-object-lock-retain-until-date"])
    assert retain - datetime.now(UTC) > timedelta(days=3649)


# --- aggregator reset (BR-U3-17) --------------------------------------------------------------------------------------------


def derived_counts(db: Db) -> list[int]:
    tables = ("monitoring_daily", "monitoring_entry_totals", "monitoring_case_index", "monitoring_invalid")
    return [int(db.query(f"SELECT count(*) FROM {t}")[0][0]) for t in tables]  # type: ignore[call-overload]  # noqa: S608


def watermark(db: Db) -> int:
    return int(db.query("SELECT last_seq FROM monitoring_watermark WHERE id = 1")[0][0])  # type: ignore[call-overload]


def test_aggregator_reset_con_migrator_vacia_las_cuatro_tablas_y_deja_la_marca_antes_de_los_181_dias(
    run: Cli, db: Db
) -> None:
    now = datetime.now(UTC)
    old = [(entry_dict("recommendation", now=now - timedelta(days=200, minutes=i)), now - timedelta(days=200, minutes=i)) for i in range(3)]
    recent = [(entry_dict("recommendation", now=now - timedelta(days=100, minutes=i)), now - timedelta(days=100, minutes=i)) for i in range(3)]
    tamper(db, 0, "recorded_at", now - timedelta(days=300))  # la genesis es la entrada mas vieja de un registro real
    seqs = seed_specs(db, old + recent)
    assert run.run("aggregator", "run")[0] == 0
    assert watermark(db) == seqs[-1]
    before = derived_counts(db)
    assert sum(before) > 0
    code, out, err = run.run("aggregator", "reset")
    assert code == 0, err
    assert derived_counts(db) == [0, 0, 0, 0]
    assert watermark(db) == seqs[3] - 1  # justo antes de la primera entrada de los ultimos 181 dias
    assert json.loads(out)["watermark"] == seqs[3] - 1


def test_aggregator_reset_con_el_registro_mas_corto_que_181_dias_deja_la_marca_en_0(run: Cli, db: Db) -> None:
    seed_events(db, 3, datetime.now(UTC))
    assert run.run("aggregator", "run")[0] == 0
    assert watermark(db) > 0
    assert run.run("aggregator", "reset")[0] == 0
    assert watermark(db) == 0


def test_aggregator_reset_con_registry_aggregator_es_permission_denied(run: Cli, db: Db, pg: PostgresContainer) -> None:
    seqs = seed_events(db, 3, datetime.now(UTC))
    assert run.run("aggregator", "run")[0] == 0
    mark = watermark(db)
    assert mark == seqs[-1]
    code, _, err = run.run("aggregator", "reset", "--dsn", dsn(pg, db, "registry_aggregator"))
    assert code == 2
    assert "permission denied" in err
    assert watermark(db) == mark  # la transaccion se deshizo


def test_aggregator_run_informa_lotes_marca_y_atraso(run: Cli, db: Db) -> None:
    seqs = seed_events(db, 5, datetime.now(UTC))
    code, out, err = run.run("aggregator", "run")
    assert code == 0, err
    result = report(out)
    assert (result["watermark"], result["reached_head"], result["lag_seconds"]) == (seqs[-1], True, 0)


def test_dos_reset_a_la_vez_el_segundo_termina_con_error_sin_cambios(run: Cli, db: Db, pg: PostgresContainer) -> None:
    seed_events(db, 3, datetime.now(UTC))
    assert run.run("aggregator", "run")[0] == 0
    mark = watermark(db)
    with psycopg.connect(dsn(pg, db, "registry_migrator"), autocommit=True) as holder:
        assert holder.execute("SELECT pg_try_advisory_lock(1448214530)").fetchone() == (True,)
        code, _, err = run.run("aggregator", "reset")
        assert code == 2
        assert "RebuildInProgress" in err
    assert watermark(db) == mark
    assert run.run("aggregator", "reset")[0] == 0  # suelto el lock, el reset corre


def test_run_until_head_con_una_reconstruccion_en_curso_termina_con_error(run: Cli, db: Db, pg: PostgresContainer) -> None:
    seed_events(db, 3, datetime.now(UTC))
    with psycopg.connect(dsn(pg, db, "registry_migrator"), autocommit=True) as holder:
        holder.execute("SELECT pg_advisory_lock(1448214530)")
        code, _, err = run.run("aggregator", "run", "--until-head")
        assert code == 2
        assert "RebuildInProgress" in err
        assert watermark(db) == 0
        assert run.run("aggregator", "run")[0] == 0  # el CronJob no toma ese lock


# --- checkpoint: pendiente de la decision de diseno --------------------------------------------------------------------------


def test_checkpoint_no_existe_hasta_decidir_la_firma(run: Cli) -> None:
    code, _, _ = run.run("checkpoint")
    assert code == 2


def test_la_cli_arranca_como_modulo_y_sale_con_el_codigo_del_comando() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "vectra_registry.cli", "verify", "--mode", "full"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin"},
        check=False,
    )
    assert result.returncode == 2
    assert "REGISTRY_RO_VERIFIER_DSN" in result.stderr


def test_link_de_la_cadena_sembrada_coincide_con_el_de_chain(db: Db) -> None:
    """La siembra de las pruebas escribe lo mismo que el append: `hash = link(prev_hash, canonical)` en cada fila."""
    seed_events(db, 3, START)
    for seq, prev, canonical, hash_ in db.query("SELECT seq, prev_hash, canonical, hash FROM registry_entries WHERE seq > 0"):
        assert link(bytes(prev), bytes(canonical)) == bytes(hash_), seq  # type: ignore[call-overload]


# --- politicas HCL aplicadas en una boveda real (P-U3-08) --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("identity", "signs", "reads"),
    [
        ("registry-checkpoint", True, True),
        ("registry-archive", True, True),
        ("registry-verify", False, True),
        ("decision-registry-service", False, False),
        ("registry-aggregator", False, False),
    ],
)
def test_las_politicas_hcl_en_vault_firma_solo_checkpoint_y_archivo(vault: Vault, identity: str, signs: bool, reads: bool) -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "vault-policies" / f"{identity}.hcl").read_text()
    assert vault.api("PUT", f"sys/policies/acl/{identity}", json={"policy": text}).status_code == 204
    created = vault.api("POST", "auth/token/create", json={"policies": [identity], "no_default_policy": True})
    token = created.json()["auth"]["client_token"]
    sign = vault.api("POST", "transit/sign/registry-checkpoints", token, json={"input": "aGE="})
    assert (sign.status_code == 200) is signs, sign.text
    key = vault.api("GET", "transit/keys/registry-checkpoints", token)
    assert (key.status_code == 200) is reads, key.text
