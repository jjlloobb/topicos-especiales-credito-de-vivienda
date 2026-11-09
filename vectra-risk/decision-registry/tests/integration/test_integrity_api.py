"""Verificacion bajo demanda `POST/GET /v1/integrity-checks` (Paso 8 del plan de U3; BR-U3-13b; NFR-U3-43; US-402).

La API **solo registra** la solicitud en `integrity_checks`; la ejecuta el CronJob `registry-verify-ondemand` (Bloque E). Una sola
verificacion activa a la vez, de cualquier modo.
"""

import asyncio
import json
import uuid
from datetime import timedelta
from typing import Any

import pytest
from conftest import Env
from entries import NOW, iso
from service_harness import READ_METRICS, service_token, user_token
from vectra_contracts.models.registry import IntegrityCheckRef, IntegrityCheckStatus

pytestmark = pytest.mark.integration


async def post(env: Env, body: dict[str, Any], role: str = "cro", **token: Any) -> Any:
    headers = user_token(role, **token) if role else service_token(READ_METRICS)
    return await env.client.post("/v1/integrity-checks", content=json.dumps(body), headers={**headers, "content-type": "application/json"})


def checks(env: Env) -> list[tuple[object, ...]]:
    return env.cdb.db.query("SELECT check_id, mode, status, from_seq, to_seq, requested_by, requested_at FROM integrity_checks ORDER BY requested_at")


async def test_br_u3_13b_sin_otra_activa_responde_202_y_deja_una_fila_pendiente(env: Env) -> None:
    response = await post(env, {"mode": "full"})
    assert response.status_code == 202, response.text
    ref = IntegrityCheckRef.model_validate_json(response.text)
    assert ref.already_active is False and ref.mode == "full" and ref.requested_at == NOW
    (row,) = checks(env)
    assert (str(row[0]), row[1], row[2], row[3], row[4], row[5]) == (ref.check_id, "full", "pendiente", None, None, "user-cro")


async def test_br_u3_13b_un_range_guarda_from_seq_y_to_seq(env: Env) -> None:
    response = await post(env, {"mode": "range", "from_seq": 10, "to_seq": 99})
    assert response.status_code == 202
    (row,) = checks(env)
    assert (row[1], row[2], row[3], row[4]) == ("range", "pendiente", 10, 99)


@pytest.mark.parametrize("active_status", ["pendiente", "en_curso"])
@pytest.mark.parametrize(("active_mode", "asked"), [("full", {"mode": "range", "from_seq": 1, "to_seq": 2}), ("range", {"mode": "full"}), ("full", {"mode": "full"})])
async def test_br_u3_13b_con_una_activa_de_cualquier_modo_responde_200_con_la_activa_y_sin_fila_nueva(
    env: Env, active_status: str, active_mode: str, asked: dict[str, Any]
) -> None:
    active_id = uuid.uuid4()
    with env.cdb.db.connect() as conn:
        conn.execute(
            "INSERT INTO integrity_checks (check_id, mode, from_seq, to_seq, requested_by, requested_at, status, started_at, heartbeat_at) "
            "VALUES (%s, %s, %s, %s, 'cron', %s, %s, %s, %s)",
            (
                active_id, active_mode, 0 if active_mode == "range" else None, 5 if active_mode == "range" else None,
                NOW - timedelta(minutes=3), active_status, NOW if active_status == "en_curso" else None,
                NOW if active_status == "en_curso" else None,
            ),
        )  # fmt: skip
    response = await post(env, asked)
    assert response.status_code == 200, response.text
    ref = IntegrityCheckRef.model_validate_json(response.text)
    assert (ref.check_id, ref.mode, ref.already_active) == (str(active_id), active_mode, True)
    assert ref.requested_at == NOW - timedelta(minutes=3)
    assert len(checks(env)) == 1  # sin fila nueva


async def test_br_u3_13b_una_verificacion_terminada_o_fallida_no_ocupa_el_cupo(env: Env) -> None:
    with env.cdb.db.connect() as conn:
        conn.execute("INSERT INTO integrity_checks (check_id, mode, requested_by, requested_at, status, report) VALUES (gen_random_uuid(), 'full', 'x', %s, 'terminada', '{\"result\": \"integra\"}')", (NOW,))
        conn.execute("INSERT INTO integrity_checks (check_id, mode, requested_by, requested_at, status, reason) VALUES (gen_random_uuid(), 'full', 'x', %s, 'fallida', 'interrumpida')", (NOW,))
    assert (await post(env, {"mode": "full"})).status_code == 202
    assert len(checks(env)) == 3


async def test_nfr_u3_43_dos_solicitudes_a_la_vez_dejan_una_sola_activa(env: Env) -> None:
    responses = await asyncio.gather(*(post(env, {"mode": "full"}) for _ in range(5)))
    assert sorted(r.status_code for r in responses) == [200, 200, 200, 200, 202]
    assert len({r.json()["check_id"] for r in responses}) == 1
    assert len(checks(env)) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"mode": "range"},
        {"mode": "range", "to_seq": 5},
        {"mode": "range", "from_seq": 5},
        {"mode": "range", "from_seq": 9, "to_seq": 2},
        {"mode": "full", "from_seq": 1},
        {"mode": "full", "to_seq": 1},
        {"mode": "incremental"},
        {},
    ],
)
async def test_br_u3_13b_una_solicitud_mal_formada_es_422_y_no_escribe(env: Env, body: dict[str, Any]) -> None:
    assert (await post(env, body)).status_code == 422
    assert checks(env) == []


async def test_br_u3_13b_un_range_sin_from_seq_es_422(env: Env) -> None:
    response = await post(env, {"mode": "range", "to_seq": 5})
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


@pytest.mark.parametrize("role", ["analista", "ingeniero_riesgo", "cumplimiento"])
async def test_br_u3_13b_otro_rol_que_no_es_cro_es_403(env: Env, role: str) -> None:
    assert (await post(env, {"mode": "full"}, role)).status_code == 403
    assert checks(env) == []


async def test_br_u3_13b_un_token_de_servicio_es_403(env: Env) -> None:
    assert (await post(env, {"mode": "full"}, "")).status_code == 403


async def test_br_u3_13b_el_cro_sin_mfa_vigente_es_rechazado_y_no_escribe(env: Env) -> None:
    response = await post(env, {"mode": "full"}, mfa=False)
    assert response.status_code in (401, 403) and response.json()["code"] == "mfa_required"
    assert checks(env) == []


async def test_br_u3_13b_la_api_solo_registra_no_verifica_ni_escribe_entradas(env: Env) -> None:
    await env.append("recommendation")
    await post(env, {"mode": "full"})
    (row,) = checks(env)
    assert row[2] == "pendiente"
    assert env.cdb.db.query("SELECT count(*) FROM registry_entries")[0][0] == 2  # la genesis y la recomendacion


async def test_br_u3_13b_get_devuelve_el_estado_de_una_pendiente(env: Env) -> None:
    ref = (await post(env, {"mode": "full"})).json()
    response = await env.client.get(f"/v1/integrity-checks/{ref['check_id']}", headers=user_token("cro"))
    assert response.status_code == 200, response.text
    status = IntegrityCheckStatus.model_validate_json(response.text)
    assert (status.status, status.mode, status.progress.checked, status.progress.total) == ("pendiente", "full", 0, 0)
    assert status.report is None and status.reason is None and status.started_at is None


async def test_br_u3_13b_get_devuelve_el_informe_de_una_terminada_y_el_motivo_de_una_fallida(env: Env) -> None:
    done, failed = uuid.uuid4(), uuid.uuid4()
    report = {
        "mode": "full", "from_seq": 0, "to_seq": 7, "entries_checked": 8, "checkpoints_checked": 1, "result": "integra",
        "started_at": iso(NOW - timedelta(hours=2)), "finished_at": iso(NOW - timedelta(hours=1)),
    }  # fmt: skip
    with env.cdb.db.connect() as conn:
        conn.execute(
            "INSERT INTO integrity_checks (check_id, mode, requested_by, requested_at, started_at, finished_at, status, "
            "progress_checked, progress_total, report) VALUES (%s, 'full', 'x', %s, %s, %s, 'terminada', 8, 8, %s)",
            (done, NOW - timedelta(hours=3), NOW - timedelta(hours=2), NOW - timedelta(hours=1), json.dumps(report)),
        )
        conn.execute(
            "INSERT INTO integrity_checks (check_id, mode, requested_by, requested_at, status, reason, progress_checked, progress_total) "
            "VALUES (%s, 'full', 'x', %s, 'fallida', 'plazo_vencido', 3, 9)",
            (failed, NOW - timedelta(hours=9)),
        )
    ok = IntegrityCheckStatus.model_validate_json((await env.client.get(f"/v1/integrity-checks/{done}", headers=user_token("cro"))).text)
    assert ok.status == "terminada" and ok.report is not None and ok.report.result == "integra"
    assert (ok.progress.checked, ok.progress.total) == (8, 8) and ok.finished_at == NOW - timedelta(hours=1)
    bad = IntegrityCheckStatus.model_validate_json((await env.client.get(f"/v1/integrity-checks/{failed}", headers=user_token("cro"))).text)
    assert (bad.status, bad.reason, bad.report) == ("fallida", "plazo_vencido", None)


async def test_br_u3_13b_get_de_una_verificacion_inexistente_o_con_id_invalido_es_404(env: Env) -> None:
    for wanted in (uuid.uuid4(), "no-es-un-uuid"):
        assert (await env.client.get(f"/v1/integrity-checks/{wanted}", headers=user_token("cro"))).status_code == 404


@pytest.mark.parametrize("role", ["analista", "cumplimiento", "ingeniero_riesgo"])
async def test_br_u3_13b_get_es_solo_del_cro(env: Env, role: str) -> None:
    ref = (await post(env, {"mode": "full"})).json()
    assert (await env.client.get(f"/v1/integrity-checks/{ref['check_id']}", headers=user_token(role))).status_code == 403
