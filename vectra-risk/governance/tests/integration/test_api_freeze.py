"""Paso 10 (U04-T04), `freeze` (BR-U4-04, 15, 16; US-305): el evento lleva el `FreezeContext` de bias mas `data_sources` e
`initial_disparity`, con la reduccion por tamano (60 y 64 KiB), y solo lo llama `bias-monitoring-job`.

El doble del registro rechaza (aserto) todo cuerpo de mas de 64 KiB: lo que llega, cabe siempre (BR-U3-07).
"""

import json
import uuid

import pytest
from api_support import ApiWorld, initial_disparity
from evidence_support import ING, VALIDATION_JOB, freeze_context, new_model, report, with_active_policy
from vectra_contracts.routes import REGISTRY
from vectra_contracts.models.monitoring import FreezeContext
from vectra_governance.evidence import MAX_EVENT_BYTES, SOFT_EVENT_BYTES, _aggregates_only, _freeze_entry, wire_size

pytestmark = pytest.mark.integration

MODEL = "mv-2026-01-01-aaaaaaaa"
FREEZE = f"/v1/models/{MODEL}/freeze"
JOB = ("bias-monitoring-job", "governance:freeze")


def activate(world: ApiWorld, *, initial_groups: int = 0, sources: dict[str, int] | None = None) -> None:
    """La version `MODEL` en `activo`, con su informe de validacion (`initial_groups` celdas) y las fuentes que declara."""
    for ds_id, groups in (sources or {}).items():
        world.put_source(ds_id, state="aprobada", groups=groups)
    new = new_model(MODEL)
    new = new.__class__(**{**new.__dict__, "registration": new.registration.model_copy(update={"data_sources": list(sources or {})})})
    world.svc.register(ING, new)
    world.svc.start_validation(ING, MODEL, job_name="job-1")
    run_id = str(world.sql("SELECT run_id FROM validation_runs")[0]["run_id"])
    full = report(True).model_copy(update={"initial_disparity": initial_disparity(initial_groups)})
    world.svc.receive_report(VALIDATION_JOB, MODEL, run_id, full)
    from evidence_support import CRO1

    world.svc.approve(CRO1, MODEL)
    world.svc.mark_active(ING, MODEL)


def context(*, padding: int = 0) -> dict[str, object]:
    """El paquete que manda bias: el `FreezeContext` (con `padding` bytes de `implicated`, que bias llena)."""
    package = freeze_context(MODEL).model_dump(mode="json")
    package["implicated"] = ["x" * 1000 for _ in range(padding // 1000)]
    return package


def freeze_event(world: ApiWorld) -> dict[str, object]:
    events = [w.entry for w in world.registry.events(MODEL) if w.entry["entry_type"] == "freeze"]
    assert len(events) == 1
    return events[0]["payload"]["context_package"]  # type: ignore[no-any-return]


async def test_br_u4_15_freeze_adds_data_sources_and_initial_disparity_to_the_bias_context(world: ApiWorld) -> None:
    with_active_policy(world.svc)
    activate(world, initial_groups=2, sources={"ds-1": 1})
    response = await world.client.post(FREEZE, headers=world.service(*JOB), json=context())
    assert response.status_code == 204 and response.content == b""  # el contrato no tiene cuerpo de respuesta
    assert world.state(MODEL) == "congelado"
    package = freeze_event(world)
    sent = context()
    assert {k: package[k] for k in sent} == {k: sent[k] for k in sent}  # el paquete de bias, tal cual
    assert [s["ds_id"] for s in package["data_sources"]] == ["ds-1"]  # type: ignore[index]
    assert package["data_sources"][0]["state"] == "aprobada" and package["data_sources"][0]["pre_post_report"]["source_id"] == "ds-1"  # type: ignore[index]
    stored = world.sql("SELECT report FROM validation_runs")[0]["report"]["initial_disparity"]
    assert package["initial_disparity"] == stored and len(package["initial_disparity"]["attributes"]) == 4  # type: ignore[index]
    assert world.sql("SELECT status FROM transitions WHERE to_state = 'congelado'") == [{"status": "confirmada"}]
    assert world.registry.largest <= MAX_EVENT_BYTES


async def test_br_u4_15_over_60_kib_initial_disparity_keeps_only_its_aggregates(world: ApiWorld) -> None:
    activate(world, initial_groups=140, sources={"ds-1": 1})
    assert unreduced_size(world) > SOFT_EVENT_BYTES  # el caso: mas de 60 KiB sin reducir...
    assert unreduced_size(world, aggregates_only=True) <= MAX_EVENT_BYTES  # ...y con las agregadas basta
    with_active_policy(world.svc)
    assert (await world.client.post(FREEZE, headers=world.service(*JOB), json=context())).status_code == 204
    package = freeze_event(world)
    attributes = package["initial_disparity"]["attributes"]  # type: ignore[index]
    assert len(attributes) == 4 and all(a["cells"] == [] and a["bands"] == [] and a["aggregate"] == "0.0100" for a in attributes)
    assert package["initial_disparity"]["model_aggregate"] == "0.0100"  # type: ignore[index]
    assert [s["ds_id"] for s in package["data_sources"]] == ["ds-1"]  # type: ignore[index]  # `data_sources` completas
    assert 0 < world.registry.largest <= MAX_EVENT_BYTES


async def test_br_u4_15_over_64_kib_data_sources_keep_only_their_ids_and_the_registry_never_sees_more(world: ApiWorld) -> None:
    activate(world, initial_groups=70, sources={"ds-1": 30, "ds-2": 30})
    assert unreduced_size(world, padding=20_000, aggregates_only=True) > MAX_EVENT_BYTES  # aun con las agregadas no cabe
    with_active_policy(world.svc)
    assert (await world.client.post(FREEZE, headers=world.service(*JOB), json=context(padding=20_000))).status_code == 204
    package = freeze_event(world)
    assert package["data_sources"] == ["ds-1", "ds-2"]  # solo ids
    assert all(a["cells"] == [] for a in package["initial_disparity"]["attributes"])  # type: ignore[index]
    assert 0 < world.registry.largest <= MAX_EVENT_BYTES
    assert world.sql("SELECT status FROM transitions WHERE to_state = 'congelado'") == [{"status": "confirmada"}]


def unreduced_size(world: ApiWorld, *, padding: int = 0, aggregates_only: bool = False) -> int:
    """Lo que pesaria el evento `freeze` de `MODEL` sin la reduccion (o con solo el primer paso): prueba que el caso es el que dice."""
    with world.svc.pools.read() as conn:
        model = conn.execute("SELECT * FROM model_versions WHERE model_version_id = %s", (MODEL,)).fetchone()
        conn.rollback()
        assert model is not None
        package = world.svc._freeze_package(conn, dict(model), FreezeContext.model_validate_json(json.dumps(context(padding=padding))))  # noqa: SLF001
    if aggregates_only:
        package = package.model_copy(update={"initial_disparity": _aggregates_only(package.initial_disparity)})
    return wire_size(_freeze_entry(MODEL, uuid.uuid4(), world.clock(), package))


async def test_br_u4_04_only_the_bias_job_freezes(world: ApiWorld) -> None:
    with_active_policy(world.svc)
    activate(world)
    body = context()
    denied = {
        "servicio HTTP de bias, sin el scope": world.service("bias-monitoring-service", "bias:compare"),
        "servicio HTTP de bias, con el scope por error": world.service("bias-monitoring-service", "governance:freeze"),
        "token de usuario cro": world.user("cro"),
        "sin scope": world.service("bias-monitoring-job"),
    }
    for who, headers in denied.items():
        response = await world.client.post(FREEZE, headers=headers, json=body)
        assert response.status_code == 403, (who, response.status_code)
        assert world.state(MODEL) == "activo", who
    assert [w for w in world.registry.chain if w.entry["entry_type"] == "freeze"] == []  # ninguno escribio el evento
    assert (await world.client.post(FREEZE, headers=world.service(*JOB), json=body)).status_code == 204
    assert world.state(MODEL) == "congelado"


async def test_br_u4_04_bias_can_call_nothing_but_freeze(world: ApiWorld) -> None:
    job = world.service(*JOB)
    for route in REGISTRY["governance-service"]:
        if route.path.endswith("/freeze"):
            continue
        path = route.path.replace("{id}", MODEL).replace("{run_id}", str(uuid.uuid4()))
        response = await world.client.request(route.method, path, headers=job, json={})
        assert response.status_code == 403, (route.method, route.path, response.status_code)


async def test_freeze_applies_even_when_the_registry_is_down_and_waits_for_the_reconciler(world: ApiWorld) -> None:
    with_active_policy(world.svc)
    activate(world)
    world.registry.mode = "down"
    assert (await world.client.post(FREEZE, headers=world.service(*JOB), json=context())).status_code == 204
    assert world.state(MODEL) == "congelado"  # BR-U4-15: aplica en la misma transaccion
    assert world.sql("SELECT status FROM transitions WHERE to_state = 'congelado'") == [{"status": "pendiente_registro"}]
    assert [w for w in world.registry.chain if w.entry["entry_type"] == "freeze"] == []
    world.refresh()
    assert world.cache.current().state == "congelado"


async def test_freeze_only_hits_the_active_version_and_its_own_context(world: ApiWorld) -> None:
    from evidence_support import to_aprobado

    with_active_policy(world.svc)
    to_aprobado(world.svc, MODEL)
    job = world.service(*JOB)
    assert (await world.client.post(FREEZE, headers=job, json=context())).status_code == 409  # no esta `activo`
    assert (await world.client.post("/v1/models/mv-no/freeze", headers=job, json=context())).status_code == 404
    activate_second = "mv-2026-02-01-bbbbbbbb"
    from evidence_support import to_activo

    to_activo(world.svc, activate_second)
    other = freeze_context(MODEL).model_dump(mode="json")
    assert (await world.client.post(f"/v1/models/{activate_second}/freeze", headers=job, json=other)).status_code == 409
    assert world.state(activate_second) == "activo"
    assert (await world.client.post(f"/v1/models/{activate_second}/freeze", headers=job, json={"model_version_id": "x"})).status_code == 422
