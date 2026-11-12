"""Paso 17: `core-banking-mock` (BR-U8-22; INF-U8-02; INF-U8-03, primera capa: el mock; P-U8-06; NFR-U8-26, NFR-U8-45; US-603).

Sin Keycloak, sin proxy de Linkerd, sin base. La alerta `CoreWriteAttempt` (INF-U8-03) es del Paso 21; aqui se prueba la metrica que la alimenta.
"""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from core_banking_mock.app import build_app
from core_banking_mock.metrics import WRITE_ATTEMPTS
from mock_auth import OTHER_KEY, authenticator, bearer
from prometheus_client.parser import text_string_to_metric_families
from vectra_case.credit import CreditReader
from vectra_contracts.catalog import CreditStatus
from vectra_contracts.models.api import CreditStatusView
from vectra_contracts.routes import REGISTRY

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "credits.json"
CREDITS = {row["case_id"]: row["status"] for row in json.loads(FIXTURES.read_text())}
KNOWN = "22222222-2222-4222-8222-222222222222"  # aprobado
MISSING = "99999999-9999-4999-8999-999999999999"
WRITE_PATH = "/v1/credits/{id}/status"


def logs(out: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://core")


async def ops_metric(app: Any, name: str) -> float:
    """La metrica se lee de `GET /metrics` del puerto de sondas, no de la variable del modulo."""
    async with client(app.state.ops_app) as ops:
        response = await ops.get("/metrics")
    assert response.status_code == 200
    for family in text_string_to_metric_families(response.text):
        for sample in family.samples:
            if sample.name == name and not sample.labels:
                return float(sample.value)
    raise AssertionError(f"{name} no aparece en /metrics")


def make_app() -> Any:
    return build_app(authenticator(), fixtures=FIXTURES)


def test_the_app_has_exactly_the_two_routes_of_the_contract() -> None:
    app = build_app()  # sin entorno ni archivo: no lee nada al construirse
    paths = {(m, r.path) for r in app.routes for m in getattr(r, "methods", ())}
    assert paths == {(r.method, r.path) for r in REGISTRY["core-banking-mock"]} and len(paths) == 2


def test_the_fixture_has_one_credit_per_core_status() -> None:
    assert set(CREDITS.values()) == {"en_estudio", "aprobado", "desembolsado", "rechazado", "cancelado"}


async def test_the_write_attempts_series_exists_without_labels_and_only_moves_with_a_write() -> None:
    """F-03 (ronda 1): el contador es global al proceso, asi que no se afirma un valor absoluto (dependeria del orden de las pruebas):
    la serie existe desde el arranque, su valor es el del contador del proceso y una lectura permitida no lo mueve."""
    app = make_app()
    before = float(WRITE_ATTEMPTS._value.get())  # type: ignore[attr-defined]
    assert await ops_metric(app, "vectra_core_write_attempts_total") == before
    async with client(app) as c:
        r = await c.get(f"/v1/credits/{KNOWN}", headers=bearer("core:read-credit"))
    assert r.status_code == 200
    assert float(WRITE_ATTEMPTS._value.get()) == before  # type: ignore[attr-defined]
    assert await ops_metric(app, "vectra_core_write_attempts_total") == before


async def test_get_with_core_read_credit_returns_a_valid_credit_status_view_for_every_fixture_credit() -> (
    None
):
    async with client(make_app()) as c:
        for credit_id, status in CREDITS.items():
            r = await c.get(f"/v1/credits/{credit_id}", headers=bearer("core:read-credit"))
            assert r.status_code == 200
            view = CreditStatusView.model_validate_json(r.content)
            assert view.credit_id == credit_id and view.status == CreditStatus(status)


async def test_get_of_an_id_that_is_not_in_the_fixture_is_404() -> None:
    async with client(make_app()) as c:
        r = await c.get(f"/v1/credits/{MISSING}", headers=bearer("core:read-credit"))
    assert r.status_code == 404


async def test_get_without_core_read_credit_is_403() -> None:
    async with client(make_app()) as c:
        r = await c.get(f"/v1/credits/{KNOWN}", headers=bearer("case:recommend"))
    assert r.status_code == 403


async def test_a_token_for_another_audience_is_401() -> None:
    async with client(make_app()) as c:
        r = await c.get(f"/v1/credits/{KNOWN}", headers=bearer("core:read-credit", aud="otro-servicio"))
    assert r.status_code == 401


async def test_a_token_signed_with_another_key_or_missing_is_401() -> None:
    async with client(make_app()) as c:
        forged = await c.get(f"/v1/credits/{KNOWN}", headers=bearer("core:read-credit", key=OTHER_KEY))
        anonymous = await c.get(f"/v1/credits/{KNOWN}")
    assert forged.status_code == 401 and anonymous.status_code == 401


async def test_post_with_any_valid_token_is_403_one_write_attempt_in_the_log_and_the_metric_at_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = make_app()
    before = await ops_metric(app, "vectra_core_write_attempts_total")
    capsys.readouterr()
    async with client(app) as c:
        r = await c.post(
            f"/v1/credits/{KNOWN}/status",
            json={"credit_id": KNOWN, "status": "desembolsado"},
            headers=bearer("core:read-credit", sub="case-service-sa"),
        )
    assert r.status_code == 403
    denied = [e for e in logs(capsys.readouterr().out) if e.get("event") == "authz.denied"]
    assert len(denied) == 1  # un WriteAttempt: el `authz.denied` de U0 en ese 403 (P-4 (a))
    assert denied[0]["route_template"] == WRITE_PATH and denied[0]["principal_subject"] == "case-service-sa"
    assert denied[0]["error_code"] == "forbidden"
    assert await ops_metric(app, "vectra_core_write_attempts_total") == before + 1


async def test_post_with_a_token_that_does_carry_core_write_credit_is_also_403_and_counts() -> None:
    app = make_app()
    before = WRITE_ATTEMPTS._value.get()  # type: ignore[attr-defined]
    async with client(app) as c:
        r = await c.post(
            f"/v1/credits/{KNOWN}/status",
            json={"credit_id": KNOWN, "status": "desembolsado"},
            headers=bearer("core:write-credit core:read-credit"),
        )
    assert r.status_code == 403 and r.json()["code"] == "forbidden"
    assert await ops_metric(app, "vectra_core_write_attempts_total") == before + 1


async def test_post_with_an_invalid_or_empty_body_and_a_valid_token_is_403_not_422() -> None:
    app = make_app()
    before = await ops_metric(app, "vectra_core_write_attempts_total")
    async with client(app) as c:
        headers = bearer("core:read-credit")
        empty = await c.post(f"/v1/credits/{KNOWN}/status", headers=headers)
        invalid = await c.post(f"/v1/credits/{KNOWN}/status", json={"status": 7}, headers=headers)
        garbage = await c.post(
            f"/v1/credits/{KNOWN}/status",
            content=b"{no json",
            headers={**headers, "content-type": "application/json"},
        )
    assert (empty.status_code, invalid.status_code, garbage.status_code) == (403, 403, 403)
    assert (
        await ops_metric(app, "vectra_core_write_attempts_total") == before + 3
    )  # la autorizacion va antes que el cuerpo


async def test_a_post_without_a_token_is_401_and_does_not_count_as_a_write_attempt() -> None:
    app = make_app()
    before = await ops_metric(app, "vectra_core_write_attempts_total")
    async with client(app) as c:
        r = await c.post(f"/v1/credits/{KNOWN}/status", json={"credit_id": KNOWN, "status": "aprobado"})
    assert r.status_code == 401
    assert await ops_metric(app, "vectra_core_write_attempts_total") == before


async def test_a_get_never_counts_as_a_write_attempt() -> None:
    app = make_app()
    before = await ops_metric(app, "vectra_core_write_attempts_total")
    async with client(app) as c:
        await c.get(f"/v1/credits/{KNOWN}", headers=bearer("core:read-credit"))
        await c.get(f"/v1/credits/{MISSING}", headers=bearer("core:read-credit"))
    assert await ops_metric(app, "vectra_core_write_attempts_total") == before


class FixedToken:
    """`TokenSource` de la prueba: el token de `core:read-credit` firmado con la llave de la prueba."""

    async def token(self) -> str:
        return bearer("core:read-credit")["authorization"].removeprefix("Bearer ")

    def invalidate(self) -> None:
        return None


async def test_credit_reader_of_case_service_against_the_real_mock_app_in_process() -> None:
    app = make_app()
    reader = CreditReader(True, "http://core", FixedToken(), transport=httpx.ASGITransport(app=app))
    try:
        assert await reader.status(UUID(KNOWN)) == CreditStatus.APROBADO
        assert await reader.status(UUID(MISSING)) == CreditStatus.SIN_CREDITO
    finally:
        await reader.aclose()
