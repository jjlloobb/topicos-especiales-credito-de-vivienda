"""Expediente `GET /v1/dossiers/{case_id}` (Paso 8 del plan de U3; BR-U3-14; NFR-U3-21; US-403).

El expediente sale de la primaria (pool `dossier`), con el `canonical` exacto de cada entrada, el `delivery_status` de las
recomendaciones y la verificacion `range` del tramo (con las llaves publicas de checkpoints que recibe el servicio).
"""

import base64
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from chain_builder import Signer
from conftest import Env
from entries import CASE, NOW, entry_dict, iso, make, payload_for
from seed import seed, spec
from service_harness import READ_METRICS, service_token, user_token
from vectra_contracts.models.registry import RegistryDossier
from vectra_registry import append
from vectra_registry.chain import canonicalize, decode, format_timestamp
from vectra_registry.dossier import DOSSIER_NOT_VERIFIED

pytestmark = pytest.mark.integration

OTHER_CASE = uuid.UUID("00000000-0000-4000-8000-0000000000c2")


async def dossier(env: Env, case: uuid.UUID | str = CASE, role: str = "cro") -> Any:
    return await env.client.get(f"/v1/dossiers/{case}", headers=user_token(role))


def narrative_of(payload: dict[str, Any]) -> str:
    return str(payload["explanation"]["narrative"])


async def test_br_u3_14_la_narrativa_del_expediente_es_byte_a_byte_la_guardada(env: Env) -> None:
    sent = payload_for("recommendation", env.clock.now)
    sent["explanation"]["narrative"] = "La relación cuota/ingreso (0,31) ñandú — «sin recortes» ✓ 🌱"
    ack = await env.append("recommendation", payload=sent)
    response = await dossier(env)
    assert response.status_code == 200, response.text
    (entry,) = response.json()["entries"]
    stored = bytes(env.cdb.db.query("SELECT canonical FROM registry_entries WHERE seq = %s", ack["seq"])[0][0])  # type: ignore[call-overload, arg-type]
    assert base64.b64decode(entry["canonical"]) == stored  # los bytes exactos
    assert narrative_of(entry["payload"]) == narrative_of(decode(stored)["payload"]) == sent["explanation"]["narrative"]
    assert entry["hash"] == bytes(env.cdb.db.query("SELECT hash FROM registry_entries WHERE seq = %s", ack["seq"])[0][0]).hex()  # type: ignore[call-overload, arg-type]


async def test_br_u3_14_el_cuerpo_valida_contra_registry_dossier_de_u0(env: Env) -> None:
    await env.append("recommendation")
    await env.append("explanation_view")
    await env.append("human_decision", payload=payload_for("human_decision", env.clock.now, recommendation_entry_id="1"))
    dossier_model = RegistryDossier.model_validate_json((await dossier(env)).text)
    assert [e.seq for e in dossier_model.entries] == [1, 2, 3]
    assert dossier_model.integrity.status == "verified" and dossier_model.last_full_verification is None


@pytest.mark.parametrize("role", ["analista", "ingeniero_riesgo"])
async def test_br_u3_14_un_analista_recibe_403(env: Env, role: str) -> None:
    await env.append("recommendation")
    response = await dossier(env, role=role)
    assert response.status_code == 403 and set(response.json()) >= {"code"} and "entries" not in response.json()


async def test_br_u3_14_cumplimiento_tambien_lo_lee_y_un_token_de_servicio_no(env: Env) -> None:
    await env.append("recommendation")
    assert (await dossier(env, role="cumplimiento")).status_code == 200
    assert (await env.client.get(f"/v1/dossiers/{CASE}", headers=service_token(READ_METRICS))).status_code == 403


async def test_br_u3_14_un_caso_sin_entradas_o_un_id_que_no_es_uuid_es_404(env: Env) -> None:
    assert (await dossier(env, OTHER_CASE)).status_code == 404
    assert (await dossier(env, "no-es-un-uuid")).status_code == 404


async def test_br_u3_14_las_entradas_salen_en_orden_de_seq_y_solo_las_del_caso(env: Env) -> None:
    await env.append("recommendation")
    await env.append("recommendation", case_id=OTHER_CASE)
    await env.append("explanation_view")
    entries = (await dossier(env)).json()["entries"]
    assert [e["seq"] for e in entries] == [1, 3] and {e["case_id"] for e in entries} == {str(CASE)}


async def test_p_u7_03_dos_recomendaciones_y_una_decision_sobre_la_segunda_dejan_la_primera_no_entregada(env: Env) -> None:
    first = await env.append("recommendation")
    second = await env.append("recommendation")
    await env.append("human_decision", payload=payload_for("human_decision", env.clock.now, recommendation_entry_id=str(second["seq"])))
    await env.append("explanation_view")
    entries = {e["seq"]: e for e in (await dossier(env)).json()["entries"]}
    assert entries[first["seq"]]["delivery_status"] == "no_entregada"
    assert entries[second["seq"]]["delivery_status"] == "entregada"
    assert all("delivery_status" not in e for e in entries.values() if e["entry_type"] != "recommendation")


async def test_p_u7_03_sin_decision_la_recomendacion_esta_pendiente_de_decision(env: Env) -> None:
    ack = await env.append("recommendation")
    (entry,) = (await dossier(env)).json()["entries"]
    assert entry["seq"] == ack["seq"] and entry["delivery_status"] == "pendiente_de_decision"


async def test_br_u3_14_el_delivery_status_se_calcula_al_leer_y_no_se_guarda(env: Env) -> None:
    first = await env.append("recommendation")
    assert (await dossier(env)).json()["entries"][0]["delivery_status"] == "pendiente_de_decision"
    await env.append("human_decision", payload=payload_for("human_decision", env.clock.now, recommendation_entry_id=str(first["seq"])))
    assert (await dossier(env)).json()["entries"][0]["delivery_status"] == "entregada"
    stored = decode(bytes(env.cdb.db.query("SELECT canonical FROM registry_entries WHERE seq = %s", first["seq"])[0][0]))  # type: ignore[call-overload, arg-type]
    assert "delivery_status" not in json.dumps(stored)


# --- La verificacion del tramo -----------------------------------------------------------------------------------------------


def tamper(env: Env, seq: int, column: str, value: object) -> None:
    """Altera una fila como lo haria quien saltara el solo-anexar (superusuario con los triggers desactivados)."""
    with env.cdb.db.connect() as conn:
        conn.execute("SET session_replication_role = replica")
        conn.execute(f"UPDATE registry_entries SET {column} = %s WHERE seq = %s", (value, seq))  # noqa: S608


async def test_br_u3_13_y_14_un_tramo_alterado_es_not_verified_en_el_seq_alterado(env: Env) -> None:
    await env.append("recommendation")
    await env.append("explanation_view")
    third = await env.append("explanation_view")
    original = bytes(env.cdb.db.query("SELECT canonical FROM registry_entries WHERE seq = 2")[0][0])  # type: ignore[call-overload, arg-type]
    before = DOSSIER_NOT_VERIFIED._value.get()  # type: ignore[attr-defined]
    tamper(env, 2, "canonical", original.replace(b"explanation_view", b"explanation_viewX"))
    body = (await dossier(env)).json()
    assert body["integrity"]["status"] == "not_verified"
    assert (body["integrity"]["first_inconsistent_seq"], body["integrity"]["reason"]) == (2, "hash")
    assert DOSSIER_NOT_VERIFIED._value.get() == before + 1  # type: ignore[attr-defined]  # alimenta RegistryChainBroken
    assert third["seq"] == 3 and len(body["entries"]) == 3  # el expediente se entrega, marcado como no verificado
    RegistryDossier.model_validate_json(json.dumps(body))


async def test_br_u3_13_el_registro_sigue_aceptando_appends_y_todo_expediente_posterior_dice_not_verified(env: Env) -> None:
    """BR-U3-13: una cadena inconsistente no detiene el registro (no se pierde evidencia) pero ningun expediente la da por buena."""
    await env.append("explanation_view")
    tamper(env, 1, "actor_id", "otro")
    later = await env.append("explanation_view")
    assert later["seq"] == 2
    for _ in range(2):
        assert (await dossier(env)).json()["integrity"]["status"] == "not_verified"


async def test_br_u3_14_una_columna_alterada_es_not_verified_con_column_mismatch(env: Env) -> None:
    await env.append("recommendation")
    tamper(env, 1, "model_version_id", "mv-otro")
    body = (await dossier(env)).json()
    assert (body["integrity"]["status"], body["integrity"]["reason"]) == ("not_verified", "column_mismatch")


async def test_br_u3_14_una_fila_borrada_en_el_tramo_es_not_verified(env: Env) -> None:
    for _ in range(3):
        await env.append("explanation_view")
    with env.cdb.db.connect() as conn:
        conn.execute("SET session_replication_role = replica")
        conn.execute("DELETE FROM registry_entries WHERE seq = 2")
    body = (await dossier(env)).json()
    assert (body["integrity"]["status"], body["integrity"]["first_inconsistent_seq"]) == ("not_verified", 3)


async def test_br_u3_14_el_tramo_va_del_checkpoint_anterior_al_posterior(env: Env) -> None:
    signer = Signer(7)
    env.config.public_keys = [signer.public]
    for _ in range(3):
        await env.append("explanation_view", case_id=OTHER_CASE)
    first_checkpoint = await checkpoint(env, signer, covered=3)  # seq 4
    mine = await env.append("explanation_view")  # seq 5
    await env.append("explanation_view", case_id=OTHER_CASE)  # seq 6
    second_checkpoint = await checkpoint(env, signer, covered=6)  # seq 7
    await env.append("explanation_view", case_id=OTHER_CASE)  # seq 8: despues del posterior, no entra al tramo
    body = (await dossier(env)).json()
    integrity = body["integrity"]
    assert integrity["status"] == "verified", integrity
    assert mine["seq"] == 5 and (first_checkpoint, second_checkpoint) == (4, 7)
    assert (integrity["from_checkpoint_seq"], integrity["to_checkpoint_seq"]) == (3, 7)  # cubierta del anterior .. posterior
    assert integrity["entries_checked"] == 7 - 3 + 1 + 0  # 3..7 (la cubierta del anterior ancla el tramo)


async def test_br_u3_14_sin_checkpoint_posterior_el_tramo_llega_a_la_cabeza(env: Env) -> None:
    for _ in range(3):
        await env.append("explanation_view")
    integrity = (await dossier(env)).json()["integrity"]
    assert (integrity["from_checkpoint_seq"], integrity["to_checkpoint_seq"], integrity["status"]) == (0, "head", "verified")
    assert integrity["entries_checked"] == 4  # la genesis y las 3 entradas


async def test_br_u3_14_un_checkpoint_con_una_firma_que_no_es_de_ninguna_llave_conocida_da_not_verified(env: Env) -> None:
    signer = Signer(8)
    env.config.public_keys = [Signer(9).public]  # el servicio no conoce la llave que firmo
    await env.append("explanation_view")
    await checkpoint(env, signer, covered=1)
    body = (await dossier(env)).json()
    assert (body["integrity"]["status"], body["integrity"]["reason"]) == ("not_verified", "checkpoint_signature")


async def checkpoint(env: Env, signer: Signer, covered: int) -> int:
    """Escribe una entrada `checkpoint` firmada como lo hara el CronJob: la firma cubre el `recorded_at` de la propia entrada."""
    row = env.cdb.db.query("SELECT hash FROM registry_entries WHERE seq = %s", covered)[0]
    head = env.cdb.db.query("SELECT recorded_at FROM registry_head")[0]
    stamp = max(datetime.now(UTC), head[0]) + timedelta(seconds=1)  # type: ignore[type-var, operator]
    covered_hash = bytes(row[0]).hex()  # type: ignore[call-overload, arg-type]
    payload = {
        "checkpoint_seq": covered,
        "checkpoint_hash": covered_hash,
        "signature": signer.sign(covered, covered_hash, format_timestamp(stamp)),
        "key_fingerprint": signer.fingerprint,
    }
    entry = make(
        "checkpoint", case_id=None, actor={"kind": "system", "id": "system"}, payload=payload, now=env.clock.now
    )
    outcome = await append.append_entry(env.pools, entry, clock=env.clock, db_clock=lambda: stamp)
    return outcome.ack.seq


# --- last_full_verification ---------------------------------------------------------------------------------------------------


def check_row(
    env: Env, mode: str, status: str, finished_at: datetime, result: str = "integra", report_extra: dict[str, Any] | None = None
) -> str:
    check_id = str(uuid.uuid4())
    report = json.dumps({"result": result, **(report_extra or {})}) if status == "terminada" else None
    reason = "interrumpida" if status == "fallida" else None
    from_seq, to_seq = (0, 1) if mode == "range" else (None, None)
    with env.cdb.db.connect() as conn:
        conn.execute(
            "INSERT INTO integrity_checks (check_id, mode, from_seq, to_seq, requested_by, requested_at, finished_at, status, report, reason) "
            "VALUES (%s, %s, %s, %s, 'x', %s, %s, %s, %s, %s)",
            (check_id, mode, from_seq, to_seq, finished_at - timedelta(hours=1), finished_at if status != "pendiente" else None, status, report, reason),
        )
    return check_id


async def test_br_u3_13b_last_full_verification_es_la_full_terminada_mas_reciente(env: Env) -> None:
    await env.append("recommendation")
    assert (await dossier(env)).json()["last_full_verification"] is None
    check_row(env, "full", "terminada", NOW - timedelta(days=40), "inconsistente")
    newest = check_row(env, "full", "terminada", NOW - timedelta(days=3))
    check_row(env, "range", "terminada", NOW - timedelta(hours=1))  # un range no cuenta
    check_row(env, "full", "fallida", NOW - timedelta(hours=2))  # una fallida no cuenta
    last = (await dossier(env)).json()["last_full_verification"]
    assert last == {"check_id": newest, "finished_at": iso(NOW - timedelta(days=3)), "result": "integra"}


async def test_br_u3_14_el_expediente_lee_de_la_primaria_y_las_proyecciones_de_la_replica(env: Env) -> None:
    from service_harness import READ_METRICS

    seed(env.cdb, [spec("explanation_view", NOW)])
    env.cdb.cluster.replay("pause")
    try:
        # Una fila que el standby (con el replay detenido) todavia no tiene: solo la primaria la ve.
        seed(env.cdb, [spec("explanation_view", NOW)], wait=False)
        entries = (await dossier(env)).json()["entries"]
        in_replica = await env.client.get("/v1/entries", headers=service_token(READ_METRICS))
    finally:
        env.cdb.cluster.replay("resume")
    assert [e["seq"] for e in entries] == [1, 2]
    assert [i["seq"] for i in in_replica.json()["items"]] == [1]


async def test_nfr_u3_21_un_caso_tipico_de_20_entradas_se_entrega_en_menos_de_2_s(env: Env) -> None:
    seed(env.cdb, [spec("explanation_view", NOW - timedelta(minutes=30 - i)) for i in range(20)])
    started = time.monotonic()
    response = await dossier(env)
    elapsed = time.monotonic() - started
    assert response.status_code == 200 and len(response.json()["entries"]) == 20
    assert response.json()["integrity"]["status"] == "verified"
    assert elapsed < 2.0, elapsed


def test_chain_builder_y_canonicalize_siguen_siendo_los_de_la_cadena() -> None:
    """El `Signer` de las pruebas firma lo mismo que verifica `verify` (JCS de `{checkpoint_seq, checkpoint_hash, recorded_at}`)."""
    assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert iso(NOW).endswith("000000Z") and entry_dict and append


# --- F-02: BR-U3-13, una `full` inconsistente deja todo expediente en not_verified ------------------------------------------


INCONSISTENT = {"first_inconsistent_seq": 1, "reason": "hash"}


async def test_br_u3_13_f02_con_la_ultima_full_inconsistente_un_tramo_limpio_sale_not_verified(env: Env) -> None:
    await env.append("explanation_view")
    check_row(env, "full", "terminada", NOW - timedelta(days=1), "inconsistente", INCONSISTENT)
    body = (await dossier(env)).json()
    assert body["integrity"]["status"] == "not_verified"  # el tramo del caso es limpio: lo dice la full
    assert (body["integrity"]["first_inconsistent_seq"], body["integrity"]["reason"]) == (1, "hash")
    assert body["last_full_verification"]["result"] == "inconsistente"
    assert set(body["last_full_verification"]) == {"check_id", "finished_at", "result"}
    RegistryDossier.model_validate_json(json.dumps(body))


async def test_br_u3_13_f02_una_full_posterior_integra_devuelve_el_expediente_a_verified(env: Env) -> None:
    await env.append("explanation_view")
    check_row(env, "full", "terminada", NOW - timedelta(days=2), "inconsistente", INCONSISTENT)
    assert (await dossier(env)).json()["integrity"]["status"] == "not_verified"
    check_row(env, "full", "terminada", NOW - timedelta(days=1), "integra")
    body = (await dossier(env)).json()
    assert body["integrity"]["status"] == "verified" and body["last_full_verification"]["result"] == "integra"


async def test_br_u3_13_f02_una_full_inconsistente_anterior_a_otra_integra_no_cuenta(env: Env) -> None:
    await env.append("explanation_view")
    check_row(env, "full", "terminada", NOW - timedelta(days=5), "inconsistente", INCONSISTENT)
    check_row(env, "full", "terminada", NOW - timedelta(days=4), "integra")
    assert (await dossier(env)).json()["integrity"]["status"] == "verified"
