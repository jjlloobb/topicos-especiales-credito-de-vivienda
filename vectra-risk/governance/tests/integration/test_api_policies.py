"""Paso 10 (U04-T04), politicas: propuesta, cuatro ojos, activacion y vigencia normativa. US-205, US-206.

BR-U4-10 (cuatro ojos, 409), BR-U4-11 (activacion y `normative_current`), BR-U4-12 (ningun servicio escribe politica).
"""

from datetime import date, timedelta

import pytest
from api_support import ApiWorld
from evidence_support import START, normative, policy_draft, to_activo

pytestmark = pytest.mark.integration


def body(**over: object) -> dict[str, object]:
    return {**policy_draft().model_dump(mode="json"), **over}


async def propose(world: ApiWorld, sub: str = "cro-1", **over: object) -> str:
    response = await world.client.post("/v1/policies", headers=world.user("cro", sub), json=body(**over))
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "propuesta" and response.json()["proposed_by"] == sub
    return str(response.json()["policy_version_id"])


async def approve(world: ApiWorld, policy_id: str, sub: str = "cro-2", **over: object):  # type: ignore[no-untyped-def]
    return await world.client.post(
        f"/v1/policies/{policy_id}/approval", headers=world.user("cro", sub), json={"decision": "aprobada", **over}
    )


async def test_us_205_a_second_policy_is_proposed_while_the_first_stays_active_and_services_cannot_write(world: ApiWorld) -> None:
    first = await propose(world)
    assert (await approve(world, first)).status_code == 204
    second = await propose(world, cutoff="0.6000")
    rows = {r["policy_version_id"]: r["state"] for r in world.sql("SELECT policy_version_id, state FROM policies")}
    assert rows == {first: "activa", second: "propuesta"}  # P1 sigue activa mientras P2 espera
    assert world.chain(second) == ["propuesta"]
    # FR-POL-04 / BR-U4-12: scoring (un servicio) no escribe politica; tampoco el ingeniero.
    scoring = world.service("scoring-service", "governance:read-serving")
    assert (await world.client.post("/v1/policies", headers=scoring, json=body())).status_code == 403
    assert (await world.client.post("/v1/policies", headers=world.user("ingeniero_riesgo"), json=body())).status_code == 403
    assert world.count("policies") == 2


async def test_us_206_another_cro_approves_p2_which_becomes_active_and_p1_historical(world: ApiWorld) -> None:
    to_activo(world.svc, "mv-2026-01-01-aaaaaaaa")
    first = await propose(world)
    await approve(world, first)
    second = await propose(world, cutoff="0.6000")
    before = world.sql("SELECT policy_version_id, etag FROM serving_config")[0]
    assert before["policy_version_id"] == first
    response = await approve(world, second, "cro-2")
    assert response.status_code == 204, response.text
    states = {r["policy_version_id"]: (r["state"], r["approved_by"]) for r in world.sql("SELECT * FROM policies")}
    assert states == {first: ("historica", "cro-2"), second: ("activa", "cro-2")}
    after = world.sql("SELECT policy_version_id, etag FROM serving_config")[0]  # serving-config recalculado
    assert after["policy_version_id"] == second and after["etag"] != before["etag"]
    assert world.chain(second) == ["propuesta", "activada"] and world.chain(first)[-1] == "historica"
    units = world.sql("SELECT unit_id FROM transitions WHERE to_state IN ('activa', 'historica') AND unit_id IS NOT NULL")
    assert len(units) == 2 and units[0]["unit_id"] == units[1]["unit_id"]  # una sola unidad de evidencia
    listing = await world.client.get("/v1/policies", headers=world.user("analista"))
    assert listing.status_code == 200 and {p["policy_version_id"]: p["state"] for p in listing.json()} == {first: "historica", second: "activa"}
    assert (await world.client.get("/v1/policies", headers=world.user("ingeniero_riesgo"))).status_code == 403


async def test_br_u4_10_the_same_cro_proposes_and_approves_is_409(world: ApiWorld) -> None:
    policy_id = await propose(world)
    response = await approve(world, policy_id, "cro-1")
    assert response.status_code == 409, response.text
    assert world.sql("SELECT state, approved_by FROM policies") == [{"state": "propuesta", "approved_by": None}]
    assert world.chain(policy_id) == ["propuesta"]  # ningun evento de activacion
    assert (await world.client.post(f"/v1/policies/{policy_id}/approval", headers=world.user("cumplimiento"), json={"decision": "aprobada"})).status_code == 403
    assert (await approve(world, "pol-no-existe")).status_code == 404


async def test_a_rejected_policy_needs_a_justification_and_never_activates(world: ApiWorld) -> None:
    policy_id = await propose(world)
    path = f"/v1/policies/{policy_id}/approval"
    assert (await world.client.post(path, headers=world.user("cro", "cro-2"), json={"decision": "rechazada"})).status_code == 422
    response = await world.client.post(
        path, headers=world.user("cro", "cro-2"), json={"decision": "rechazada", "justification": "umbral laxo"}
    )
    assert response.status_code == 204, response.text
    assert world.sql("SELECT state, rejection_justification FROM policies") == [
        {"state": "rechazada", "rejection_justification": "umbral laxo"}
    ]
    assert world.chain(policy_id) == ["propuesta", "rechazada"]
    assert (await approve(world, policy_id)).status_code == 409  # ya no esta `propuesta`


async def test_br_u4_11_an_expired_normative_gives_a_null_normative_current_and_a_current_one_gives_it(world: ApiWorld) -> None:
    today = START.date()
    expired = [normative(today - timedelta(days=400), today - timedelta(days=1))]
    current = [normative(today - timedelta(days=10), None)]
    scoring = world.service("scoring-service", "governance:read-serving")
    to_activo(world.svc, "mv-2026-01-01-aaaaaaaa")
    for label, vigencias in (("vigente", current), ("vencida", expired)):
        policy_id = await propose(world, "cro-1" if label == "vigente" else "cro-2", normative=[n.model_dump(mode="json") for n in vigencias])
        assert (await approve(world, policy_id, "cro-2" if label == "vigente" else "cro-1")).status_code == 204
        world.refresh()
        served = (await world.client.get("/v1/serving-config", headers=scoring)).json()
        stored = world.sql("SELECT normative_current, policy_version_id FROM serving_config")[0]
        assert stored["policy_version_id"] == policy_id == served["policy_version_id"]
        if label == "vigente":
            assert served["normative_current"]["effective_from"] == str(current[0].effective_from)
            assert stored["normative_current"] is not None
        else:
            assert "normative_current" not in served  # nulo: scoring da `revision_requerida` (U7)
            assert stored["normative_current"] is None


async def test_br_u4_11_a_future_normative_is_not_current_until_its_day(world: ApiWorld) -> None:
    today = date(2026, 11, 9)
    policy_id = await propose(world, normative=[normative(today + timedelta(days=5)).model_dump(mode="json")])
    assert (await approve(world, policy_id)).status_code == 204
    to_activo(world.svc, "mv-2026-01-01-aaaaaaaa")
    world.refresh()
    served = (await world.client.get("/v1/serving-config", headers=world.service("scoring-service", "governance:read-serving"))).json()
    assert "normative_current" not in served
