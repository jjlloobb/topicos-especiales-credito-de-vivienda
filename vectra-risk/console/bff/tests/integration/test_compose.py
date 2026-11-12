"""Paso 5 (CA-1): las composiciones del BFF y los dos endpoints de integridad (BR-U10-03; P-U10-02, 05; NFR-U10-02; US-402, US-403).

`get_dossier` con las dos llamadas en paralelo; `get_disparity` en serie y sin cache; `run_integrity_check` con `already_active`.
"""

import time

import bff_builders as b
import bff_tokens
import bff_world as w
import pytest
from bff_doubles import problem
from bff_support import Bff

CRO = bff_tokens.bearer(["cro"])
CUMPLIMIENTO = bff_tokens.bearer(["cumplimiento"])
DOSSIER = f"/api/console/cases/{w.CASE_LISTO}/dossier"
REGISTRY_DOSSIER = ("GET", "/v1/dossiers/{case_id}")
CASE_IDENTIFIERS = ("GET", "/v1/cases/{id}/identifiers")


# --- get_dossier ------------------------------------------------------------------------------------------------------


async def test_dossier_with_a_healthy_case_has_the_identifiers(bff: Bff) -> None:
    response = await bff.client.get(DOSSIER, headers=CUMPLIMIENTO)
    assert response.status_code == 200
    body = response.json()
    assert body["identifiers"]["document_number"] == "1020304050" and body["identifiers_unavailable"] is False
    assert body["anonymized"] is False and body["dossier"]["case_id"] == w.CASE_LISTO


async def test_the_two_branches_of_the_dossier_run_in_parallel(bff: Bff) -> None:
    """NFR-U10-02: dobles de 500 ms en las dos ramas -> < 700 ms (en serie serian >= 1 s)."""
    bff.doubles.registry.override(*REGISTRY_DOSSIER, delay=0.5)
    bff.doubles.case.override(*CASE_IDENTIFIERS, delay=0.5)
    started = time.monotonic()
    response = await bff.client.get(DOSSIER, headers=CUMPLIMIENTO)
    elapsed = time.monotonic() - started
    assert response.status_code == 200 and response.json()["identifiers_unavailable"] is False
    assert elapsed < 0.7, elapsed
    assert bff.doubles.registry.completed == 1 and bff.doubles.case.completed == 1


async def test_registry_down_is_503_and_the_case_call_is_cancelled(bff: Bff) -> None:
    """P-U10-02: el registro responde un 5xx con la llamada a case en vuelo -> 503 y esa llamada se cancela, sin esperar su timeout."""
    bff.doubles.registry.override(
        *REGISTRY_DOSSIER, status=503, payload=problem(503, "dependency_unavailable"), delay=0.15
    )
    bff.doubles.case.override(*CASE_IDENTIFIERS, hang=True)  # no termina nunca
    started = time.monotonic()
    response = await bff.client.get(DOSSIER, headers=CUMPLIMIENTO)
    elapsed = time.monotonic() - started
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
    assert (
        bff.doubles.case.count() == 1 and bff.doubles.case.cancelled == 1 and bff.doubles.case.completed == 0
    )
    assert elapsed < 1.0, elapsed  # no espero el timeout de 1,5 s de case


@pytest.mark.parametrize("failure", ["down", "5xx"])
async def test_registry_without_an_answer_is_503(bff: Bff, failure: str) -> None:
    """Conexion o 5xx del registro: 503 `dependency_unavailable` (el timeout de 5 s lo cubre `test_clients.py`)."""
    registry = bff.doubles.registry
    if failure == "down":
        registry.down()
    else:
        registry.reply(
            *REGISTRY_DOSSIER, 500, problem(500, "internal_error")
        )  # un 5xx cualquiera es «sin respuesta»
    response = await bff.client.get(DOSSIER, headers=CUMPLIMIENTO)
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"


@pytest.mark.parametrize(("status", "code"), [(403, "forbidden"), (404, "not_found")])
async def test_registry_403_and_404_are_that_error(bff: Bff, status: int, code: str) -> None:
    bff.doubles.registry.reply(*REGISTRY_DOSSIER, status, problem(status, code))
    response = await bff.client.get(DOSSIER, headers=CUMPLIMIENTO)
    assert response.status_code == status and response.json()["code"] == code


@pytest.mark.parametrize("failure", ["down", "5xx"])
async def test_case_without_an_answer_gives_the_dossier_with_identifiers_unavailable(
    bff: Bff, failure: str
) -> None:
    if failure == "down":
        bff.doubles.case.down()
    else:
        bff.doubles.case.reply(*CASE_IDENTIFIERS, 503, problem(503, "dependency_unavailable"))
    response = await bff.client.get(DOSSIER, headers=CUMPLIMIENTO)
    assert response.status_code == 200
    body = response.json()
    assert body["identifiers_unavailable"] is True and "identifiers" not in body
    assert body["anonymized"] is False  # no se sabe
    assert body["dossier"]["case_id"] == w.CASE_LISTO


async def test_case_with_an_open_circuit_gives_identifiers_unavailable_without_calling_case(bff: Bff) -> None:
    bff.doubles.case.down()
    for _ in range(20):
        await bff.client.get("/api/console/cases", headers=bff_tokens.bearer(["analista"]))
    before = bff.doubles.case.count()
    response = await bff.client.get(DOSSIER, headers=CUMPLIMIENTO)
    assert response.status_code == 200 and response.json()["identifiers_unavailable"] is True
    assert bff.doubles.case.count() == before


@pytest.mark.parametrize(("status", "code"), [(403, "forbidden"), (404, "not_found")])
async def test_case_403_and_404_are_that_error_never_identifiers_unavailable(
    bff: Bff, status: int, code: str
) -> None:
    bff.doubles.case.reply(*CASE_IDENTIFIERS, status, problem(status, code))
    response = await bff.client.get(DOSSIER, headers=CUMPLIMIENTO)
    assert response.status_code == status and response.json()["code"] == code
    assert "identifiers_unavailable" not in response.text


async def test_an_anonymized_case_gives_anonymized_true_without_identifiers(bff: Bff) -> None:
    case_id = w.CASE_ANONIMIZADO
    response = await bff.client.get(f"/api/console/cases/{case_id}/dossier", headers=CRO)
    assert response.status_code == 200
    body = response.json()
    assert (
        body["anonymized"] is True and "identifiers" not in body and body["identifiers_unavailable"] is False
    )


async def test_a_dossier_id_that_is_not_a_uuid_is_404_without_calls(bff: Bff) -> None:
    response = await bff.client.get("/api/console/cases/no-es-un-uuid/dossier", headers=CRO)
    assert response.status_code == 404
    assert bff.doubles.registry.count() == 0 and bff.doubles.case.count() == 0


async def test_a_dossier_that_does_not_validate_is_500_internal_error(bff: Bff) -> None:
    """BR-U10-04: un 2xx que no valida contra el contrato no pasa crudo."""
    bff.doubles.registry.reply(*REGISTRY_DOSSIER, 200, {"case_id": w.CASE_LISTO, "inventado": True})
    response = await bff.client.get(DOSSIER, headers=CUMPLIMIENTO)
    assert response.status_code == 500 and response.json()["code"] == "internal_error"
    assert "inventado" not in response.text


# --- get_disparity -----------------------------------------------------------------------------------------------------


async def test_disparity_twice_is_two_calls_to_governance_and_two_to_bias_without_cache(bff: Bff) -> None:
    for _ in range(2):
        response = await bff.client.get("/api/console/disparity", headers=CRO)
        assert response.status_code == 200
    gov, bias = bff.doubles.governance, bff.doubles.bias
    assert gov.count("GET", "/v1/models") == 2 and bias.count("GET", "/v1/disparity") == 2
    assert (
        gov.calls[0].seq < bias.calls[0].seq < gov.calls[1].seq < bias.calls[1].seq
    )  # governance y despues bias, en serie


async def test_disparity_asks_governance_for_the_serviceable_states_and_sends_that_version_to_bias(
    bff: Bff,
) -> None:
    response = await bff.client.get("/api/console/disparity?attribute=region&window=30", headers=CRO)
    assert response.status_code == 200
    listing = bff.doubles.governance.calls[0]
    assert sorted(listing.query["state"]) == ["activo", "congelado"]
    sent = bff.doubles.bias.calls[0].query
    assert sent["version"] == ["mv-activo"] and sent["attribute"] == ["region"] and sent["window"] == ["30"]
    assert response.json()["model_version_id"] == "mv-activo"


async def test_disparity_with_an_explicit_version_does_not_consult_governance(bff: Bff) -> None:
    """P-6 (a): con `version` en el filtro, governance caido no tumba la consulta."""
    bff.doubles.governance.down()
    response = await bff.client.get("/api/console/disparity?version=mv-7", headers=CRO)
    assert response.status_code == 200 and response.json()["model_version_id"] == "mv-7"
    assert bff.doubles.governance.count() == 0 and bff.doubles.bias.calls[0].query["version"] == ["mv-7"]


async def test_disparity_with_governance_down_and_no_version_is_503_and_bias_is_not_called(bff: Bff) -> None:
    """No se cae a «bias sin version»: mostraria la version anterior tras un congelamiento (P-U10-02, Q7)."""
    bff.doubles.governance.down()
    response = await bff.client.get("/api/console/disparity", headers=CRO)
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
    assert bff.doubles.bias.count() == 0


async def test_disparity_with_no_serviceable_version_calls_bias_without_version(bff: Bff) -> None:
    bff.doubles.governance.models.clear()
    response = await bff.client.get("/api/console/disparity", headers=CRO)
    assert response.status_code == 200
    assert "version" not in bff.doubles.bias.calls[0].query


async def test_disparity_with_several_serviceable_versions_sends_the_active_one(bff: Bff) -> None:
    bff.doubles.governance.add_model("mv-congelado-2", "congelado", updated_at=b.ts(60))
    response = await bff.client.get("/api/console/disparity", headers=CRO)
    assert response.status_code == 200
    assert bff.doubles.bias.calls[0].query["version"] == ["mv-activo"]


async def test_disparity_with_only_frozen_versions_sends_the_most_recent_one(bff: Bff) -> None:
    gov = bff.doubles.governance
    gov.models.clear()
    gov.add_model("mv-a", "congelado", updated_at=b.ts(1))
    gov.add_model("mv-b", "congelado", updated_at=b.ts(5))
    response = await bff.client.get("/api/console/disparity", headers=CRO)
    assert response.status_code == 200 and bff.doubles.bias.calls[0].query["version"] == ["mv-b"]


async def test_disparity_error_of_bias_is_translated(bff: Bff) -> None:
    bff.doubles.bias.reply("GET", "/v1/disparity", 403, problem(403, "forbidden"))
    response = await bff.client.get("/api/console/disparity", headers=CRO)
    assert response.status_code == 403 and response.json()["code"] == "forbidden"


# --- integridad --------------------------------------------------------------------------------------------------------


async def test_run_integrity_check_202_when_nothing_is_active(bff: Bff) -> None:
    bff.doubles.registry.integrity_status = 202
    response = await bff.client.post("/api/console/integrity-checks", headers=CRO, json={"mode": "full"})
    assert response.status_code == 202
    assert response.json()["already_active"] is False and response.json()["check_id"] == "chk-1"
    assert bff.doubles.registry.calls[0].json() == {"mode": "full"}


async def test_run_integrity_check_200_with_the_active_one(bff: Bff) -> None:
    bff.doubles.registry.integrity_status = 200
    response = await bff.client.post(
        "/api/console/integrity-checks", headers=CRO, json={"mode": "range", "from_seq": 1, "to_seq": 9}
    )
    assert response.status_code == 200 and response.json()["already_active"] is True
    assert bff.doubles.registry.calls[0].json() == {"mode": "range", "from_seq": 1, "to_seq": 9}


async def test_run_integrity_check_with_an_undeclared_success_status_is_500(bff: Bff) -> None:
    bff.doubles.registry.integrity_status = 201
    response = await bff.client.post("/api/console/integrity-checks", headers=CRO, json={"mode": "full"})
    assert response.status_code == 500 and response.json()["code"] == "internal_error"


async def test_get_integrity_check_is_passed_through_for_each_state(bff: Bff) -> None:
    for state in ("pendiente", "en_curso"):
        bff.doubles.registry.reply("GET", "/v1/integrity-checks/{id}", 200, b.integrity_status(state))
        response = await bff.client.get("/api/console/integrity-checks/chk-1", headers=CRO)
        assert response.status_code == 200 and response.json()["status"] == state
    assert bff.doubles.registry.calls[-1].path == "/v1/integrity-checks/chk-1"


async def test_integrity_with_the_registry_down_is_503(bff: Bff) -> None:
    bff.doubles.registry.down()
    assert (
        await bff.client.post("/api/console/integrity-checks", headers=CRO, json={"mode": "full"})
    ).status_code == 503
    assert (await bff.client.get("/api/console/integrity-checks/chk-1", headers=CRO)).status_code == 503
