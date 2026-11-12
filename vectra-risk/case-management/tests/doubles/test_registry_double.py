"""El doble del registro pasa los ejemplos de append de U3 (NFR-U8-53; PBT-U8-07; BLM §4).

Copiados y adaptados de `decision-registry/tests/integration/test_append.py` (Paso 7 de U3); el nombre de la prueba de origen va en cada
docstring. No se importan por ruta. Se usan entradas de las tres clases que escribe `case-service` (`human_decision`,
`explanation_view`, `fail_closed`).
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from registry_double import RegistryDouble

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
CASE = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
USER = {
    "kind": "user",
    "id": "analista-1",
    "role": "analista",
    "acr": "1",
    "auth_time": "2026-11-10T11:00:00+00:00",
}
SERVICE = {"kind": "service", "id": "case-worker"}


def iso(moment: datetime) -> str:
    return moment.isoformat()


def payload_for(entry_type: str, now: datetime = NOW, **over: Any) -> dict[str, Any]:
    if entry_type == "human_decision":
        data: dict[str, Any] = {
            "decision": "sigue",
            "final_outcome": "favorable",
            "used_factors": ["ninguno"],
            "justification": "",
            "explanation_viewed_before": True,
            "decided_at": iso(now),
            "recommendation_entry_id": "1",
        }
    elif entry_type == "explanation_view":
        data = {"viewed_at": iso(now), "recommendation_entry_id": "1"}
    else:
        data = {
            "local_cause": "scoring_unreachable",
            "retryable": True,
            "attempt": 6,
            "escalated_at": iso(now),
        }
    return {**data, **over}


def entry_dict(
    entry_type: str, *, key: uuid.UUID | None = None, now: datetime = NOW, **over: Any
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "entry_type": entry_type,
        "case_id": CASE,
        "actor": SERVICE if entry_type == "fail_closed" else USER,
        "occurred_at": iso(now),
        "correlation_id": uuid.uuid4().hex,
        "idempotency_key": str(key or uuid.uuid4()),
        "payload": payload_for(entry_type, now),
        "model_version_id": "mv-1",
        "policy_version_id": "pv-1",
    }
    return {**data, **over}


class Env:
    def __init__(self) -> None:
        self.now = NOW
        self.double = RegistryDouble(clock=lambda: self.now)
        self.client = httpx.AsyncClient(transport=self.double.transport(), base_url="http://registry")

    async def post(self, data: dict[str, Any]) -> httpx.Response:
        return await self.client.post("/v1/entries", content=json.dumps(data))

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def env() -> Env:
    return Env()


async def test_br_u3_04_un_append_nuevo_escribe_la_fila_y_devuelve_el_ack(env: Env) -> None:
    """Origen: test_br_u3_04_un_append_nuevo_escribe_la_fila_encadenada_y_devuelve_el_ack."""
    response = await env.post(entry_dict("human_decision"))
    assert response.status_code == 200
    assert response.json()["seq"] == 1 and len(env.double.entries) == 1


async def test_br_u3_06_el_reintento_con_la_misma_llave_devuelve_el_ack_original_y_una_sola_fila(
    env: Env,
) -> None:
    """Origen: test_br_u3_06_el_reintento_con_la_misma_llave_devuelve_el_ack_original_y_una_sola_fila."""
    key = uuid.uuid4()
    first = await env.post(entry_dict("explanation_view", key=key))
    again = await env.post(entry_dict("explanation_view", key=key))  # otra traza: otro `correlation_id`
    assert again.status_code == 200 and again.json() == first.json()
    assert len(env.double.entries) == 1


async def test_br_u3_06_a_los_10_min_con_otro_occurred_at_y_correlation_id_es_el_ack_original(
    env: Env,
) -> None:
    """Origen: test_br_u3_06_a_los_10_min_con_otro_occurred_at_correlation_id_y_contract_version_es_el_ack_original."""
    key = uuid.uuid4()
    payload = payload_for("human_decision", env.now)
    first = await env.post(entry_dict("human_decision", key=key, payload=payload))
    env.advance(minutes=10)
    retry = await env.post(entry_dict("human_decision", key=key, now=env.now, payload=payload))
    assert retry.status_code == 200 and retry.json()["seq"] == first.json()["seq"]
    assert len(env.double.entries) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"payload": payload_for("human_decision", NOW, justification="otra")},
        {"actor": {**USER, "id": "u-otro"}},
        {"model_version_id": "mv-2"},
        {"policy_version_id": "pv-9"},
        {"case_id": "00000000-0000-4000-8000-0000000000c2"},
    ],
    ids=["payload", "actor", "model_version_id", "policy_version_id", "case_id"],
)
async def test_br_u3_06_la_misma_llave_con_otro_contenido_es_409_y_no_escribe(
    env: Env, change: dict[str, Any]
) -> None:
    """Origen: test_br_u3_06_la_misma_llave_con_otro_contenido_es_409_y_no_escribe."""
    key = uuid.uuid4()
    await env.post(entry_dict("human_decision", key=key))
    response = await env.post(entry_dict("human_decision", key=key, **change))
    assert response.status_code == 409 and response.json()["code"] == "conflict_state"
    assert len(env.double.entries) == 1


async def test_br_u3_06_la_misma_llave_con_otro_tipo_es_409(env: Env) -> None:
    """Origen: test_br_u3_06_la_misma_llave_con_otro_tipo_es_409."""
    key = uuid.uuid4()
    await env.post(entry_dict("human_decision", key=key))
    assert (await env.post(entry_dict("explanation_view", key=key))).status_code == 409


async def test_br_u3_06_dos_reintentos_concurrentes_producen_una_sola_entrada(env: Env) -> None:
    """Origen: test_br_u3_06_dos_reintentos_concurrentes_producen_una_sola_entrada."""
    data = entry_dict("explanation_view")
    responses = await asyncio.gather(*(env.post(data) for _ in range(6)))
    assert {r.status_code for r in responses} == {200}
    assert len({r.json()["seq"] for r in responses}) == 1 and len(env.double.entries) == 1


async def test_br_u3_05_una_llave_nueva_con_occurred_at_de_hace_6_min_es_422(env: Env) -> None:
    """Origen: test_br_u3_05_una_llave_nueva_con_occurred_at_de_hace_6_min_es_422."""
    data = entry_dict("explanation_view", occurred_at=iso(NOW - timedelta(minutes=6)))
    data["payload"] = payload_for("explanation_view", NOW - timedelta(minutes=7))
    assert (await env.post(data)).status_code == 422
    assert not env.double.entries


@pytest.mark.parametrize(("offset", "status"), [(-300, 200), (300, 200), (-301, 422), (301, 422), (0, 200)])
async def test_br_u3_05_la_ventana_es_de_mas_menos_300_s(env: Env, offset: int, status: int) -> None:
    """Origen: test_br_u3_05_la_ventana_es_de_mas_menos_300_s (el momento de negocio queda antes del `occurred_at`)."""
    data = entry_dict("explanation_view", occurred_at=iso(NOW + timedelta(seconds=offset)))
    data["payload"] = payload_for("explanation_view", NOW - timedelta(seconds=400))
    assert (await env.post(data)).status_code == status


async def test_br_u3_05_la_ventana_no_se_aplica_a_una_llave_existente(env: Env) -> None:
    """Origen: test_br_u3_05_la_ventana_no_se_aplica_a_una_llave_existente."""
    key = uuid.uuid4()
    first = await env.post(entry_dict("explanation_view", key=key))
    env.advance(hours=3)
    stale = entry_dict("explanation_view", key=key)  # `occurred_at` de hace tres horas
    response = await env.post(stale)
    assert response.status_code == 200 and response.json()["seq"] == first.json()["seq"]
    assert (
        await env.post(entry_dict("explanation_view", now=NOW))
    ).status_code == 422  # una llave nueva si cae fuera


async def test_br_u3_05_un_momento_de_negocio_de_hace_8_dias_es_422_para_una_llave_nueva(env: Env) -> None:
    """Origen: test_br_u3_05_un_momento_de_negocio_de_hace_8_dias_es_422_para_una_llave_nueva."""
    payload = payload_for("human_decision", NOW, decided_at=iso(NOW - timedelta(days=8)))
    assert (await env.post(entry_dict("human_decision", payload=payload))).status_code == 422
    assert not env.double.entries


async def test_br_u3_05_un_momento_de_negocio_posterior_a_occurred_at_es_422(env: Env) -> None:
    """Origen: test_br_u3_05_un_momento_de_negocio_posterior_a_occurred_at_es_422."""
    payload = payload_for("explanation_view", NOW, viewed_at=iso(NOW + timedelta(seconds=1)))
    assert (await env.post(entry_dict("explanation_view", payload=payload))).status_code == 422


async def test_br_u3_05_el_reenvio_de_una_llave_existente_con_un_momento_de_hace_8_dias_es_el_ack_original(
    env: Env,
) -> None:
    """Origen: test_br_u3_05_el_reenvio_de_una_llave_existente_con_un_momento_de_hace_8_dias_es_el_ack_original."""
    key = uuid.uuid4()
    payload = payload_for("human_decision", NOW, decided_at=iso(NOW - timedelta(days=6)))
    first = await env.post(entry_dict("human_decision", key=key, payload=payload))
    env.advance(days=2, minutes=1)  # el momento de negocio ya tiene mas de 7 dias
    resend = await env.post(entry_dict("human_decision", key=key, now=env.now, payload=payload))
    assert resend.status_code == 200 and resend.json()["seq"] == first.json()["seq"]


async def test_br_u3_05_el_escalamiento_de_case_lleva_escalated_at_dentro_de_la_cota(env: Env) -> None:
    """Origen: test_br_u3_05_received_at_de_hace_30_dias_no_entra_en_check_business_time (aqui, `escalated_at` de un `fail_closed`)."""
    assert (await env.post(entry_dict("fail_closed"))).status_code == 200
    old = payload_for("fail_closed", NOW, escalated_at=iso(NOW - timedelta(days=30)))
    assert (await env.post(entry_dict("fail_closed", payload=old))).status_code == 422


async def test_ack_perdido_escribe_y_responde_503_y_el_reintento_da_el_ack_original(env: Env) -> None:
    """Origen: test_p_u3_02_con_el_standby_pausado_responde_503_en_menos_de_2_5_s_y_el_reintento_da_el_ack_original."""
    key = uuid.uuid4()
    env.double.lose_ack_next = 1
    assert (await env.post(entry_dict("human_decision", key=key))).status_code == 503
    assert len(env.double.entries) == 1
    retry = await env.post(entry_dict("human_decision", key=key))
    assert retry.status_code == 200 and retry.json()["seq"] == 1 and len(env.double.entries) == 1
