"""El cliente real del registro (`POST /v1/entries`, U3), la llave y la armadura de la entrada, sin red ni base."""

import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from vectra_governance.evidence import (
    HttpRegistryClient,
    RegistryConflict,
    RegistryUnavailable,
    build_entry,
    idempotency_key,
)
from vectra_governance.k8s_jobs import JobInfo, reason_of

ACK = {"registry_entry_id": "7", "seq": 7, "recorded_at": "2026-11-09T15:00:00Z"}


def client(handler: httpx.MockTransport) -> HttpRegistryClient:
    return HttpRegistryClient("http://registry", lambda: "tok", transport=handler)


@pytest.mark.parametrize("status", [200, 201])
def test_un_ack_es_un_registry_ack(status: int) -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=ACK)

    ack = client(httpx.MockTransport(handle)).append({"entry_type": "model_event"})
    assert (ack.seq, ack.registry_entry_id) == (7, "7")
    assert seen[0].url.path == "/v1/entries" and seen[0].headers["authorization"] == "Bearer tok"
    assert json.loads(seen[0].content) == {"entry_type": "model_event"}


def test_409_es_un_conflicto_y_el_resto_es_no_disponible() -> None:
    assert_raises(409, RegistryConflict)
    for status in (400, 403, 422, 500, 503):
        assert_raises(status, RegistryUnavailable)


def assert_raises(status: int, error: type[Exception]) -> None:
    with pytest.raises(error):
        client(httpx.MockTransport(lambda _: httpx.Response(status, json={}))).append({})


def test_un_timeout_o_una_red_caida_es_no_disponible() -> None:
    def boom(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("lento")

    with pytest.raises(RegistryUnavailable):
        client(httpx.MockTransport(boom)).append({})


def test_la_llave_es_determinista_y_distingue_el_tipo_de_entidad() -> None:
    assert idempotency_key("model_version", "mv-1", 3) == idempotency_key("model_version", "mv-1", 3)
    assert idempotency_key("policy", "x", 1) != idempotency_key("data_source", "x", 1)
    assert idempotency_key("model_version", "mv-1", 3) == uuid.UUID("35cb2877-a92f-58da-bab1-6c8d4eda7976")  # valor fijo de la formula de Q-3


def row(entry_type: str, actor: dict[str, str]) -> dict[str, object]:
    return {
        "actor": actor,
        "correlation_id": "a" * 32,
        "idempotency_key": uuid.UUID(int=5),
        "event_payload": {"entry": {"entry_type": entry_type, "payload": {}}},
    }


def test_el_freeze_viaja_como_system_y_cada_intento_lleva_su_occurred_at() -> None:
    now = datetime(2026, 11, 9, 15, tzinfo=UTC)
    freeze = build_entry(row("freeze", {"kind": "service", "sub": "bias-monitoring-job"}), now)  # type: ignore[arg-type]
    assert freeze["actor"] == {"kind": "system", "id": "bias-monitoring-job"}  # BR-U3-16
    assert freeze["occurred_at"] == "2026-11-09T15:00:00+00:00" and freeze["idempotency_key"] == str(uuid.UUID(int=5))
    later = build_entry(row("freeze", {"kind": "service", "sub": "bias-monitoring-job"}), now.replace(hour=16))  # type: ignore[arg-type]
    assert later["occurred_at"] != freeze["occurred_at"] and later["correlation_id"] == freeze["correlation_id"]
    user = build_entry(
        row("model_event", {"kind": "user", "sub": "u", "role": "cro", "acr": "mfa", "auth_time": "t"}), now  # type: ignore[arg-type]
    )
    assert user["actor"] == {"kind": "user", "id": "u", "role": "cro", "acr": "mfa", "auth_time": "t"}


def test_el_motivo_del_job_vencido() -> None:
    assert reason_of(JobInfo(deadline_exceeded=True, failed=True)) == "deadline"
    assert reason_of(JobInfo(failed=True)) == "failed"
    assert reason_of(JobInfo()) == "sin informe"
    assert reason_of(None) == "sin informe"  # el TTL ya borro el Job
