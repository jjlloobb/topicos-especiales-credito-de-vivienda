"""Append contra PostgreSQL real con primaria y standby sincrono (Paso 7 del plan de U3; BR-U3-03..07, 16; P-U3-02, 04; US-401, 404).

Un caso por vinheta de la aceptacion del Paso 7 (la lista viñeta -> caso esta en `bitacoras/U03-T03.md`). Cada escritura pasa por
la app de `create_app` con un token firmado con las llaves de prueba de U0, y cada lectura es SQL real sobre la base.
"""

import asyncio
import hashlib
import json
import time
import uuid
from datetime import timedelta
from typing import Any

import psycopg
import pytest
import vectra_contracts
from conftest import APPEND_SCOPE, Env
from entries import BUSINESS_TYPES, CRO, GOVERNANCE_TYPES, NOW, entry_dict, iso, payload_for
from service_harness import APPEND_CASE, APPEND_GOVERNANCE, APPEND_SCORING
from vectra_registry import append
from vectra_registry.chain import canonicalize, decode
from vectra_registry.locks import APPEND_LOCK

pytestmark = pytest.mark.integration

SCOPES = (APPEND_SCORING, APPEND_CASE, APPEND_GOVERNANCE)
ALLOWED = {
    APPEND_SCORING: {"recommendation", "fail_closed"},
    APPEND_CASE: {"human_decision", "explanation_view", "fail_closed"},
    APPEND_GOVERNANCE: set(GOVERNANCE_TYPES),
}
GENESIS_PAYLOAD = {"schema_version": "1", "contract_version": "0.1.0", "checkpoint_key_fingerprint": "ab" * 32}
CHECKPOINT_PAYLOAD = {"checkpoint_seq": 0, "checkpoint_hash": "00" * 32, "signature": "AAAA", "key_fingerprint": "ab" * 32}


def fail_closed(**fields: Any) -> dict[str, Any]:
    return {"cause": "timeout", "retryable": True, "attempt": 1, **fields}


def escalated(env: Env) -> dict[str, Any]:
    """El escalamiento de case (BR-U8-09): `local_cause` con `escalated_at`, sin `cause`."""
    return {"local_cause": "scoring_rejected", "retryable": False, "attempt": 3, "escalated_at": iso(env.clock.now)}


def count(env: Env) -> int:
    return int(env.cdb.db.query("SELECT count(*) FROM registry_entries")[0][0])  # type: ignore[call-overload]


# --- BR-U3-04: lo que se escribe ----------------------------------------------------------------------------------------------


async def test_br_u3_04_un_append_nuevo_escribe_la_fila_encadenada_y_devuelve_el_ack(env: Env) -> None:
    genesis = env.cdb.db.query("SELECT seq, hash, recorded_at FROM registry_entries WHERE seq = 0")[0]
    ack = await env.append("recommendation")
    assert (ack["seq"], ack["registry_entry_id"]) == (1, "1")
    seq, prev_hash, hash_, canonical, recorded_at, version, kind, role = env.cdb.db.query(
        "SELECT seq, prev_hash, hash, canonical, recorded_at, contract_version, actor_kind, actor_role "
        "FROM registry_entries WHERE seq = 1"
    )[0]
    assert bytes(prev_hash) == bytes(genesis[1])  # type: ignore[call-overload]
    assert bytes(hash_) == hashlib.sha256(bytes(prev_hash) + bytes(canonical)).digest()  # type: ignore[call-overload]
    body = decode(bytes(canonical))  # type: ignore[call-overload]
    assert (body["seq"], body["entry_type"], body["idempotency_key"]) == (1, "recommendation", ack["idempotency_key"])
    assert body["recorded_at"].endswith("Z") and body["contract_version"] == version == vectra_contracts.__version__
    assert canonicalize(body) == bytes(canonical)  # type: ignore[call-overload]  # los bytes guardados son un punto fijo de JCS
    assert (kind, role) == ("service", None)
    assert recorded_at >= genesis[2]  # type: ignore[operator]


async def test_br_u3_04_el_payload_se_guarda_sin_perder_nada(env: Env) -> None:
    sent = entry_dict("model_event", now=env.clock.now, payload={"event": "registrado", "details": {"a": None, "b": [1, "x"], "c": {}}})
    assert (await env.post(sent)).status_code == 200
    stored = decode(bytes(env.cdb.db.query("SELECT canonical FROM registry_entries WHERE seq = 1")[0][0]))  # type: ignore[call-overload, arg-type]
    assert stored["payload"]["details"] == {"a": None, "b": [1, "x"], "c": {}}


async def test_br_u3_05_recorded_at_no_decrece_aunque_el_reloj_de_la_base_retroceda(env: Env) -> None:
    stamps = []
    for back in (0, 60, 3600):
        data = entry_dict("recommendation", now=env.clock.now)
        outcome = await append.append_entry(
            env.pools,
            append.RegistryEntryIn.model_validate_json(json.dumps(data)),
            clock=env.clock,
            db_clock=lambda back=back: NOW - timedelta(seconds=back),
        )
        stamps.append(outcome.ack.recorded_at)
    assert stamps == sorted(stamps) and len(set(stamps)) == 1  # el primero fija el piso (la base real es posterior a NOW)
    assert stamps[0] >= NOW or stamps[0] > NOW - timedelta(days=1)


# --- BR-U3-01 y BR-U3-02: solo INSERT y SELECT --------------------------------------------------------------------------------


@pytest.mark.parametrize("statement", ["UPDATE registry_entries SET actor_id = 'x'", "DELETE FROM registry_entries", "TRUNCATE registry_entries"])
async def test_br_u3_01_el_rol_del_servicio_no_actualiza_borra_ni_trunca_la_cadena(env: Env, statement: str) -> None:
    await env.append("recommendation")
    with psycopg.connect(env.cdb.dsn("append"), autocommit=True) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement)  # type: ignore[arg-type]


async def test_br_u3_02_ni_siquiera_un_superusuario_actualiza_una_entrada_sin_desactivar_el_trigger(env: Env) -> None:
    await env.append("recommendation")
    with env.cdb.db.connect() as conn, pytest.raises(psycopg.errors.RaiseException):
        conn.execute("UPDATE registry_entries SET actor_id = 'x' WHERE seq = 1")


# --- BR-U3-03: escritores autorizados -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("scope", SCOPES)
@pytest.mark.parametrize("entry_type", BUSINESS_TYPES)
async def test_br_u3_03_cada_scope_escribe_solo_sus_tipos(env: Env, scope: str, entry_type: str) -> None:
    if entry_type == "fail_closed" and scope == APPEND_CASE:
        payload = escalated(env)  # case solo escribe el escalamiento
    else:
        payload = None
    data = entry_dict(entry_type, now=env.clock.now, payload=payload)
    response = await env.post(data, scope)
    assert response.status_code == (200 if entry_type in ALLOWED[scope] else 403), response.text
    assert count(env) == (2 if entry_type in ALLOWED[scope] else 1)


@pytest.mark.parametrize("scope", SCOPES)
@pytest.mark.parametrize(("entry_type", "payload"), [("genesis", GENESIS_PAYLOAD), ("checkpoint", CHECKPOINT_PAYLOAD)])
async def test_br_u3_03_genesis_y_checkpoint_solo_los_escribe_el_registro(
    env: Env, scope: str, entry_type: str, payload: dict[str, Any]
) -> None:
    data = entry_dict(entry_type, now=env.clock.now, case_id=None, actor={"kind": "system", "id": "system"}, payload=payload)
    assert (await env.post(data, scope)).status_code == 403
    assert count(env) == 1


async def test_br_u3_03_un_token_sin_scope_de_append_es_403(env: Env) -> None:
    assert (await env.post(entry_dict("recommendation", now=env.clock.now), "registry:read:metrics")).status_code == 403


async def test_br_u3_03_fail_closed_de_escalamiento_desde_scoring_es_403(env: Env) -> None:
    data = entry_dict("fail_closed", now=env.clock.now, payload=escalated(env))
    assert (await env.post(data, APPEND_SCORING)).status_code == 403


async def test_br_u3_03_f01_fail_closed_con_cause_y_escalated_at_desde_scoring_es_403(env: Env) -> None:
    """F-01: el escalamiento por reintentos agotados (`cause` + `escalated_at`, valido para U0) es de case, no de scoring.
    Mata la mutacion que exige solo `local_cause is None` y no `escalated_at is None`."""
    payload = {"cause": "timeout", "retryable": True, "attempt": 3, "escalated_at": iso(env.clock.now)}
    data = entry_dict("fail_closed", now=env.clock.now, payload=payload)
    assert (await env.post(data, APPEND_SCORING)).status_code == 403
    assert (await env.post(data, APPEND_CASE)).status_code == 200  # case si escribe el escalamiento
    assert count(env) == 2


async def test_br_u3_03_local_cause_sin_escalated_at_lo_rechaza_u0_con_422_antes_del_scope(env: Env) -> None:
    """F-03: el plan dice 403, pero U0 (BR-U0-38) rechaza ese payload con 422 antes del handler; no se escribe nada."""
    data = entry_dict("fail_closed", now=env.clock.now, payload={"local_cause": "scoring_rejected", "retryable": False, "attempt": 1})
    assert (await env.post(data, APPEND_SCORING)).status_code == 422  # lo rechaza U0 antes de llegar al scope
    only_escalation = entry_dict("fail_closed", now=env.clock.now, payload={**escalated(env), "attempt": 1})
    assert (await env.post(only_escalation, APPEND_SCORING)).status_code == 403


async def test_br_u3_03_fail_closed_sin_escalated_at_desde_case_es_403(env: Env) -> None:
    assert (await env.post(entry_dict("fail_closed", now=env.clock.now, payload=fail_closed()), APPEND_CASE)).status_code == 403


async def test_br_u3_03_cada_scope_con_su_forma_correcta_se_acepta(env: Env) -> None:
    assert (await env.post(entry_dict("fail_closed", now=env.clock.now, payload=fail_closed()), APPEND_SCORING)).status_code == 200
    assert (await env.post(entry_dict("fail_closed", now=env.clock.now, payload=escalated(env)), APPEND_CASE)).status_code == 200
    assert count(env) == 3


# --- BR-U3-16: eventos de gobierno (US-404) --------------------------------------------------------------------------------------


@pytest.mark.parametrize("entry_type", GOVERNANCE_TYPES)
async def test_br_u3_16_los_cinco_eventos_de_gobierno_se_aceptan_con_actor_y_rol(env: Env, entry_type: str) -> None:
    ack = await env.append(entry_type)
    row = env.cdb.db.query("SELECT actor_kind, actor_id, actor_role FROM registry_entries WHERE seq = %s", ack["seq"])[0]
    assert row[0] in ("user", "system") and row[1]
    if entry_type != "freeze":
        assert (row[0], row[2]) == ("user", "cro")  # el actor y el rol quedan en las columnas consultables


async def test_br_u3_16_un_evento_de_gobierno_de_una_persona_sin_rol_es_422(env: Env) -> None:
    actor = {k: v for k, v in CRO.items() if k != "role"}
    response = await env.post(entry_dict("model_event", now=env.clock.now, actor=actor))
    assert response.status_code == 422
    assert response.json()["invalid_params"] == [{"name": "actor.role", "reason_code": "role_required"}]


@pytest.mark.parametrize(
    ("entry_type", "payload", "actor"),
    [
        ("freeze", None, {"kind": "service", "id": "bias-monitoring-service"}),  # antes de U9 H4 ya no es la identidad que congela
        ("model_event", {"event": "registrado", "details": {}}, {"kind": "service", "id": "model-validation-job"}),
        ("model_event", {"event": "informe_validacion", "details": {}}, {"kind": "service", "id": "otro-job"}),
        ("policy_event", {"event": "activada", "policy_version_id": "pv-1"}, {"kind": "system", "id": "governance-service"}),
    ],
)
async def test_br_u3_16_un_actor_de_servicio_fuera_de_las_excepciones_es_403(
    env: Env, entry_type: str, payload: dict[str, Any] | None, actor: dict[str, Any]
) -> None:
    assert (await env.post(entry_dict(entry_type, now=env.clock.now, payload=payload, actor=actor))).status_code == 403


@pytest.mark.parametrize(
    ("entry_type", "payload", "actor"),
    [
        ("freeze", None, {"kind": "system", "id": "bias-monitoring-job"}),
        ("model_event", {"event": "informe_validacion", "details": {}}, {"kind": "service", "id": "model-validation-job"}),
        ("model_event", {"event": "validacion_fallida", "details": {}}, {"kind": "service", "id": "model-validation-job"}),
        ("model_event", {"event": "validacion_fallida", "details": {}}, {"kind": "system", "id": "governance-service"}),
        ("model_event", {"event": "transicion_descartada", "details": {}}, {"kind": "system", "id": "governance-service"}),
    ],
)
async def test_br_u3_16_las_excepciones_de_servicio_y_sistema_se_aceptan(
    env: Env, entry_type: str, payload: dict[str, Any] | None, actor: dict[str, Any]
) -> None:
    assert (await env.post(entry_dict(entry_type, now=env.clock.now, payload=payload, actor=actor))).status_code == 200


# --- BR-U3-07: tamano --------------------------------------------------------------------------------------------------------


def padded_model_event(env: Env, size: int, key: uuid.UUID) -> dict[str, Any]:
    """Un `model_event` cuyo `canonical` mide exactamente `size` bytes cuando se escribe como `seq = 1`."""
    base = entry_dict("model_event", now=env.clock.now, key=key, payload={"event": "registrado", "details": {"relleno": ""}})
    entry = append.RegistryEntryIn.model_validate_json(json.dumps(base))
    probe = len(append.build_canonical(entry, 1, env.clock.now))
    base["payload"]["details"]["relleno"] = "x" * (size - probe)
    return base


async def test_br_u3_07_un_canonical_de_exactamente_64_kib_se_acepta(env: Env) -> None:
    data = padded_model_event(env, append.MAX_CANONICAL, uuid.uuid4())
    response = await env.post(data)
    assert response.status_code == 200, response.text
    assert env.cdb.db.query("SELECT octet_length(canonical) FROM registry_entries WHERE seq = 1")[0][0] == 65536


async def test_br_u3_07_un_canonical_de_un_byte_mas_es_413_y_no_escribe(env: Env) -> None:
    response = await env.post(padded_model_event(env, append.MAX_CANONICAL + 1, uuid.uuid4()))
    assert response.status_code == 413 and response.json()["code"] == "payload_too_large"
    assert count(env) == 1


async def test_br_u3_07_un_cuerpo_de_mas_de_80_kib_lo_rechaza_la_fabrica_con_413(env: Env) -> None:
    data = entry_dict("model_event", now=env.clock.now, payload={"event": "registrado", "details": {"x": "y" * 90_000}})
    assert (await env.post(data)).status_code == 413


async def test_br_u3_07_la_metrica_de_tamano_registra_la_entrada(env: Env) -> None:
    before = append.ENTRY_SIZE._sum.get()  # type: ignore[attr-defined]
    await env.append("recommendation")
    assert append.ENTRY_SIZE._sum.get() > before  # type: ignore[attr-defined]


# --- BR-U3-06: idempotencia ---------------------------------------------------------------------------------------------------


async def test_br_u3_06_el_reintento_con_la_misma_llave_devuelve_el_ack_original_y_una_sola_fila(env: Env) -> None:
    key = uuid.uuid4()
    first = await env.append("recommendation", key=key)
    again = await env.post(entry_dict("recommendation", now=env.clock.now, key=key, payload=payload_for("recommendation", env.clock.now)))
    assert again.status_code == 200
    # El reintento es del mismo hecho con otra traza: `correlation_id` distinto; mismo contenido de negocio.
    assert again.json() == {k: first[k] for k in ("registry_entry_id", "seq", "recorded_at")} | {"recorded_at": again.json()["recorded_at"]}
    assert again.json()["seq"] == first["seq"] and again.json()["recorded_at"] == first["recorded_at"]
    assert count(env) == 2


async def test_br_u3_06_a_los_10_min_con_otro_occurred_at_correlation_id_y_contract_version_es_el_ack_original(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = uuid.uuid4()
    payload = payload_for("recommendation", env.clock.now)
    first = await env.append("recommendation", key=key, payload=payload)
    env.clock.advance(minutes=10)
    monkeypatch.setattr(vectra_contracts, "__version__", "9.9.9")
    retry = entry_dict("recommendation", now=env.clock.now, key=key, payload=payload)  # otro occurred_at y otro correlation_id
    assert retry["occurred_at"] != iso(NOW) and retry["correlation_id"]
    response = await env.post(retry)
    assert response.status_code == 200
    assert (response.json()["seq"], response.json()["recorded_at"]) == (first["seq"], first["recorded_at"])
    assert count(env) == 2
    assert env.cdb.db.query("SELECT contract_version FROM registry_entries WHERE seq = 1")[0][0] == "0.1.0"


@pytest.mark.parametrize(
    "change",
    [
        {"payload": {"event": "registrado", "details": {"version": "otra"}}},
        {"actor": {**CRO, "id": "u-otro"}},
        {"model_version_id": "mv-2"},
        {"policy_version_id": "pv-9"},
        {"case_id": "00000000-0000-4000-8000-0000000000c2"},
    ],
    ids=["payload", "actor", "model_version_id", "policy_version_id", "case_id"],
)
async def test_br_u3_06_la_misma_llave_con_otro_contenido_es_409_y_no_escribe(env: Env, change: dict[str, Any]) -> None:
    key = uuid.uuid4()
    await env.append("model_event", key=key)
    response = await env.post(entry_dict("model_event", now=env.clock.now, key=key, **change))
    assert response.status_code == 409 and response.json()["code"] == "conflict_state"
    assert count(env) == 2


async def test_br_u3_06_la_misma_llave_con_otro_tipo_es_409(env: Env) -> None:
    key = uuid.uuid4()
    await env.append("model_event", key=key)
    other = entry_dict("policy_event", now=env.clock.now, key=key)
    assert (await env.post(other)).status_code == 409


async def test_br_u3_06_dos_reintentos_concurrentes_producen_una_sola_entrada(env: Env) -> None:
    key = uuid.uuid4()
    data = entry_dict("recommendation", now=env.clock.now, key=key)
    responses = await asyncio.gather(*(env.post(data) for _ in range(6)))
    assert {r.status_code for r in responses} == {200}
    assert len({(r.json()["seq"], r.json()["recorded_at"]) for r in responses}) == 1
    assert count(env) == 2


# --- BR-U3-05: la ventana de occurred_at y check_business_time, solo para llaves nuevas ----------------------------------------


async def test_br_u3_05_una_llave_nueva_con_occurred_at_de_hace_6_min_es_422(env: Env) -> None:
    data = entry_dict("recommendation", now=env.clock.now, occurred_at=NOW - timedelta(minutes=6))
    response = await env.post(data)
    assert response.status_code == 422
    assert response.json()["invalid_params"] == [{"name": "occurred_at", "reason_code": "outside_window"}]
    assert count(env) == 1


@pytest.mark.parametrize(("offset", "status"), [(-300, 200), (300, 200), (-301, 422), (301, 422), (0, 200)])
async def test_br_u3_05_la_ventana_es_de_mas_menos_300_s(env: Env, offset: int, status: int) -> None:
    data = entry_dict("recommendation", now=env.clock.now, occurred_at=NOW + timedelta(seconds=offset))
    data["payload"] = payload_for("recommendation", NOW - timedelta(seconds=400))  # el momento de negocio no es lo que se prueba
    assert (await env.post(data)).status_code == status


async def test_br_u3_05_la_ventana_no_se_aplica_a_una_llave_existente(env: Env) -> None:
    key = uuid.uuid4()
    first = await env.append("recommendation", key=key)
    env.clock.advance(hours=3)
    stale = entry_dict("recommendation", now=NOW, key=key, payload=payload_for("recommendation", NOW))
    stale["occurred_at"] = iso(NOW)  # tres horas atras segun el reloj del servicio
    response = await env.post(stale)
    assert response.status_code == 200 and response.json()["seq"] == first["seq"]
    fresh_key = entry_dict("recommendation", now=NOW, occurred_at=NOW)  # una llave nueva con ese mismo occurred_at si cae fuera
    assert (await env.post(fresh_key)).status_code == 422


async def test_br_u3_05_un_momento_de_negocio_de_hace_8_dias_es_422_para_una_llave_nueva(env: Env) -> None:
    payload = payload_for("human_decision", env.clock.now, decided_at=iso(NOW - timedelta(days=8)))
    response = await env.post(entry_dict("human_decision", now=env.clock.now, payload=payload))
    assert response.status_code == 422
    assert response.json()["invalid_params"] == [{"name": "payload.decided_at", "reason_code": "older_than_7_days"}]
    assert count(env) == 1


async def test_br_u3_05_un_momento_de_negocio_posterior_a_occurred_at_es_422(env: Env) -> None:
    payload = payload_for("explanation_view", env.clock.now, viewed_at=iso(NOW + timedelta(seconds=1)))
    response = await env.post(entry_dict("explanation_view", now=env.clock.now, payload=payload))
    assert response.status_code == 422 and response.json()["invalid_params"][0]["reason_code"] == "after_occurred_at"


async def test_br_u3_05_el_reenvio_de_una_llave_existente_con_un_momento_de_hace_8_dias_es_el_ack_original(env: Env) -> None:
    key = uuid.uuid4()
    payload = payload_for("human_decision", env.clock.now, decided_at=iso(NOW - timedelta(days=6)))
    first = await env.append("human_decision", key=key, payload=payload)
    env.clock.advance(days=2, minutes=1)  # el momento de negocio ahora tiene mas de 8 dias
    resend = entry_dict("human_decision", now=env.clock.now, key=key, payload=payload)
    assert (NOW + timedelta(days=2) - (NOW - timedelta(days=6))) > timedelta(days=7)
    response = await env.post(resend)
    assert response.status_code == 200 and response.json()["seq"] == first["seq"]
    assert count(env) == 2


async def test_br_u3_05_received_at_de_hace_30_dias_no_entra_en_check_business_time(env: Env) -> None:
    """El caso que estuvo congelado: `received_at` de hace 30 dias y `evaluated_at` de ahora (revision del FD de U11)."""
    payload = payload_for("recommendation", env.clock.now, received_at=iso(NOW - timedelta(days=30)))
    response = await env.post(entry_dict("recommendation", now=env.clock.now, payload=payload))
    assert response.status_code == 200, response.text
    stored = decode(bytes(env.cdb.db.query("SELECT canonical FROM registry_entries WHERE seq = 1")[0][0]))  # type: ignore[call-overload, arg-type]
    assert stored["payload"]["received_at"] == iso(NOW - timedelta(days=30))


# --- BR-U3-04 y P-U3-02: el commit sincrono y los tiempos limite -------------------------------------------------------------


async def test_p_u3_02_con_el_standby_pausado_responde_503_en_menos_de_2_5_s_y_el_reintento_da_el_ack_original(
    env: Env,
) -> None:
    key = uuid.uuid4()
    data = entry_dict("recommendation", now=env.clock.now, key=key)
    cluster = env.cdb.cluster
    await env.post(entry_dict("recommendation", now=env.clock.now))  # abre las conexiones: se mide el commit, no el connect
    cluster.pause_standby()
    try:
        started = time.monotonic()
        response = await env.post(data)
        elapsed = time.monotonic() - started
    finally:
        cluster.resume_standby()
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
    assert elapsed <= 2.5, elapsed
    cluster.wait_streaming()
    retry = await env.post(data)
    assert retry.status_code == 200, retry.text
    assert env.cdb.db.query("SELECT count(*) FROM registry_entries WHERE idempotency_key = %s", key)[0][0] == 1
    assert retry.json()["seq"] == 2  # la fila que quedo escrita en local; el reintento no abre otra


async def test_br_u3_04_el_commit_es_remote_apply_no_basta_con_que_el_standby_reciba_el_wal(env: Env) -> None:
    """Con el *replay* del standby detenido el WAL llega y un commit `on` se confirmaria; `remote_apply` no."""
    await env.append("recommendation")
    env.cdb.cluster.replay("pause")
    try:
        started = time.monotonic()
        response = await env.post(entry_dict("recommendation", now=env.clock.now))
        elapsed = time.monotonic() - started
    finally:
        env.cdb.cluster.replay("resume")
    assert response.status_code == 503 and elapsed <= 2.5, (response.text, elapsed)


async def test_p_u3_02_el_ack_original_de_un_reintento_espera_a_que_la_fila_este_en_el_standby(env: Env) -> None:
    """Una fila escrita solo en la primaria (el commit se cancelo por tiempo) no se da por confirmada en el reintento."""
    from seed import seed

    data = entry_dict("recommendation", now=env.clock.now)
    env.cdb.cluster.replay("pause")
    try:
        seed(env.cdb, [(data, env.clock.now)], wait=False)  # la fila existe en la primaria y el standby no la ha aplicado
        started = time.monotonic()
        blocked = await env.post(data)
        elapsed = time.monotonic() - started
    finally:
        env.cdb.cluster.replay("resume")
    assert blocked.status_code == 503 and elapsed <= 2.5, (blocked.text, elapsed)
    confirmed = await env.post(data)
    assert confirmed.status_code == 200 and confirmed.json()["seq"] == 1 and count(env) == 2


async def test_p_u3_02_un_lock_ocupado_da_503_a_1_s_sin_reintento_interno(env: Env) -> None:
    await env.append("recommendation")  # conexiones abiertas
    holder = psycopg.connect(env.cdb.dsn("append"), autocommit=True)
    holder.execute("SELECT pg_advisory_lock(%s)", (APPEND_LOCK,))
    try:
        started = time.monotonic()
        response = await env.post(entry_dict("recommendation", now=env.clock.now))
        elapsed = time.monotonic() - started
    finally:
        holder.close()
    assert response.status_code == 503
    assert 0.9 <= elapsed <= 1.6, elapsed  # `lock_timeout` de 1 s
    assert count(env) == 2


async def test_p_u3_04_un_pool_append_lleno_da_503_a_los_500_ms(env: Env) -> None:
    """Dos solicitudes ocupan las 2 conexiones esperando el lock (1 s); la tercera no consigue conexion y falla a los 500 ms."""
    await env.append("recommendation")
    holder = psycopg.connect(env.cdb.dsn("append"), autocommit=True)
    holder.execute("SELECT pg_advisory_lock(%s)", (APPEND_LOCK,))

    async def timed() -> tuple[int, float]:
        started = time.monotonic()
        response = await env.post(entry_dict("recommendation", now=env.clock.now))
        return response.status_code, time.monotonic() - started

    try:
        first_two = [asyncio.create_task(timed()), asyncio.create_task(timed())]
        await asyncio.sleep(0.1)  # las dos ya tienen su conexion
        third = await timed()
        results = [await task for task in first_two]
    finally:
        holder.close()
    assert third[0] == 503 and 0.4 <= third[1] <= 0.9, third  # espera maxima del pool `append`: 500 ms
    assert {status for status, _ in results} == {503} and min(t for _, t in results) >= 0.9  # `lock_timeout` de 1 s
    assert env.pools.append.size == 2 and env.pools.append.wait_timeout == 0.5
    assert count(env) == 2


def test_p_u3_04_los_pools_suman_5_conexiones_por_replica() -> None:
    from vectra_registry.pools import POOL_SIZES

    assert {name: size for name, (size, _) in POOL_SIZES.items()} == {"append": 2, "dossier": 1, "projections": 1, "health": 1}
    assert sum(size for size, _ in POOL_SIZES.values()) == 5
    assert {name: wait for name, (_, wait) in POOL_SIZES.items()} == {"append": 0.5, "dossier": 2.0, "projections": 2.0, "health": 1.0}


def test_p_u3_02_los_limites_del_append() -> None:
    assert (append.LOCK_TIMEOUT_MS, append.STATEMENT_TIMEOUT_MS, append.HANDLER_TIMEOUT) == (1000, 2000, 2.5)


# --- Candidata de U03-T01 (F-05): no depende del nombre de la restriccion de unicidad ------------------------------------------


async def test_f_05_el_append_no_depende_del_nombre_de_la_restriccion_de_unicidad(env: Env) -> None:
    env.cdb.db.query("SELECT 1")
    with env.cdb.db.connect() as conn:
        conn.execute("ALTER INDEX registry_idempotency_keys_pkey RENAME TO otro_nombre_cualquiera")
    key = uuid.uuid4()
    first = await env.append("recommendation", key=key)
    again = await env.post(entry_dict("recommendation", now=env.clock.now, key=key, payload=payload_for("recommendation", env.clock.now)))
    assert again.status_code == 200 and again.json()["seq"] == first["seq"]
    assert (await env.post(entry_dict("recommendation", now=env.clock.now, key=key, model_version_id="mv-9"))).status_code == 409
    assert count(env) == 2


async def test_f_05_si_otra_escritura_gana_la_llave_sin_pasar_por_el_lock_se_repite_la_busqueda(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La busqueda no ve la fila (carrera), el `INSERT` choca con la unicidad de la llave sea cual sea su nombre, y el segundo
    intento resuelve por BR-U3-06."""
    key = uuid.uuid4()
    first = await env.append("recommendation", key=key)
    with env.cdb.db.connect() as conn:
        conn.execute("ALTER INDEX registry_idempotency_keys_pkey RENAME TO otro_nombre_cualquiera")
    real, calls = append._find, []

    async def blind_once(conn: Any, wanted: uuid.UUID) -> Any:
        calls.append(wanted)
        return None if len(calls) == 1 else await real(conn, wanted)

    monkeypatch.setattr(append, "_find", blind_once)
    response = await env.post(entry_dict("recommendation", now=env.clock.now, key=key, payload=payload_for("recommendation", env.clock.now)))
    assert response.status_code == 200 and response.json()["seq"] == first["seq"]
    assert len(calls) == 2 and count(env) == 2


def test_apendice_todos_los_scopes_de_append_estan_en_el_mapa() -> None:
    assert set(APPEND_SCOPE.values()) == set(SCOPES)
