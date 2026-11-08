"""Consultas en la replica (Paso 8 del plan de U3; BR-U3-15, 17; domain-entities §3; US-403).

Las entradas se siembran con `seed` (cadena valida con `recorded_at` elegido) o por la API; las tablas derivadas, por SQL de
superusuario. Cada lectura va por `GET /v1/entries` o `POST /v1/monitoring/daily:query` de la app, contra el standby real.
"""

import asyncio
import json
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any

import psycopg
import pytest
from conftest import Env
from entries import CASE, NOW, iso, payload_for
from seed import seed, spec
from service_harness import READ_EXPLANATION, READ_METRICS, READ_MONITORING, service_token
from vectra_contracts.models.monitoring import MonitoringWindow
from vectra_registry.health import MONITORING_LAG, Gauges

pytestmark = pytest.mark.integration

OTHER_CASE = uuid.UUID("00000000-0000-4000-8000-0000000000c2")


async def get(env: Env, scope: str, **params: Any) -> Any:
    response = await env.client.get("/v1/entries", params={k: v for k, v in params.items() if v is not None}, headers=service_token(scope))
    return response


def recommendation(at: datetime, case: uuid.UUID = CASE, **payload: Any) -> tuple[dict[str, Any], datetime]:
    return spec("recommendation", at, case_id=case, payload=payload_for("recommendation", at, **payload))


def decision(at: datetime, reference: int, case: uuid.UUID = CASE, **payload: Any) -> tuple[dict[str, Any], datetime]:
    return spec("human_decision", at, case_id=case, payload=payload_for("human_decision", at, recommendation_entry_id=str(reference), **payload))


# --- GET /v1/entries: proyecciones y filtros ---------------------------------------------------------------------------------


async def test_br_u3_15_la_proyeccion_explanation_exige_case_id_y_seq(env: Env) -> None:
    (seq,) = seed(env.cdb, [recommendation(NOW)])
    missing = await get(env, READ_EXPLANATION, case_id=str(CASE))
    assert missing.status_code == 422
    assert {p["name"] for p in missing.json()["invalid_params"]} == {"seq"}
    ok = await get(env, READ_EXPLANATION, case_id=str(CASE), seq=seq)
    assert ok.status_code == 200
    body = ok.json()
    assert body["next_seq_after"] is None and len(body["items"]) == 1
    assert set(body["items"][0]) == {"seq", "case_id", "model_version_id", "payload"}
    assert set(body["items"][0]["payload"]) == {"explanation"}


async def test_br_u3_15_explanation_con_un_seq_de_otro_caso_es_una_pagina_vacia(env: Env) -> None:
    (seq,) = seed(env.cdb, [recommendation(NOW, OTHER_CASE)])
    response = await get(env, READ_EXPLANATION, case_id=str(CASE), seq=seq)
    assert response.status_code == 200 and response.json() == {"items": [], "next_seq_after": None}


async def test_br_u3_15_explanation_de_un_seq_que_no_es_una_recomendacion_es_una_pagina_vacia(env: Env) -> None:
    (seq,) = seed(env.cdb, [spec("explanation_view", NOW)])
    response = await get(env, READ_EXPLANATION, case_id=str(CASE), seq=seq)
    assert response.json()["items"] == []


async def test_br_u3_15_un_consumidor_solo_recibe_su_proyeccion_y_lo_demas_es_403_sin_datos(env: Env) -> None:
    seed(env.cdb, [recommendation(NOW)])
    for scope, projection in [
        (READ_METRICS, "explanation"),
        (READ_METRICS, "full"),
        (READ_EXPLANATION, "metrics"),
        (READ_EXPLANATION, "monitoring_freezes"),
        (READ_MONITORING, "metrics"),
        (READ_MONITORING, "full"),
    ]:
        response = await get(env, scope, projection=projection, case_id=str(CASE), seq=1)
        assert response.status_code == 403, (scope, projection)
        assert set(response.json()) == {"type", "title", "status", "code", "correlation_id"}  # el Problem, sin datos parciales


async def test_br_u3_15_un_token_sin_scope_de_lectura_es_403_y_la_proyeccion_por_omision_es_la_del_scope(env: Env) -> None:
    seed(env.cdb, [recommendation(NOW), spec("freeze", NOW)])
    assert (await get(env, "registry:append:scoring")).status_code == 403
    metrics = (await get(env, READ_METRICS)).json()["items"]
    assert [i["entry_type"] for i in metrics] == ["recommendation"]
    freezes = (await get(env, READ_MONITORING)).json()["items"]
    assert [set(i) for i in freezes] == [{"seq", "freeze_id", "model_version_id", "frozen_at", "recorded_at", "context_package"}]


async def test_br_u3_15_metrics_no_lleva_feature_vector_justification_ni_actor_id(env: Env) -> None:
    seed(env.cdb, [recommendation(NOW), decision(NOW, 1), spec("explanation_view", NOW)])
    text = json.dumps((await get(env, READ_METRICS)).json())
    for forbidden in ("feature_vector", "justification", "actor_id", "narrative"):
        assert forbidden not in text


async def test_us_403_los_filtros_de_metrics_case_id_tipo_seq_y_rango_de_recorded_at(env: Env) -> None:
    seqs = seed(
        env.cdb,
        [
            recommendation(NOW - timedelta(days=3)),
            recommendation(NOW - timedelta(days=2), OTHER_CASE),
            decision(NOW - timedelta(days=1), 1),
            spec("explanation_view", NOW),
        ],
    )

    async def ask(**params: Any) -> list[int]:
        response = await get(env, READ_METRICS, **params)
        assert response.status_code == 200, response.text
        return [i["seq"] for i in response.json()["items"]]

    assert await ask() == seqs
    assert await ask(case_id=str(OTHER_CASE)) == [seqs[1]]
    assert await ask(entry_type="human_decision,explanation_view") == [seqs[2], seqs[3]]
    assert await ask(entry_type="freeze") == []  # un tipo que no es de la proyeccion
    assert await ask(seq=seqs[2]) == [seqs[2]]
    assert await ask(recorded_from=iso(NOW - timedelta(days=2, hours=1)), recorded_to=iso(NOW - timedelta(hours=1))) == [seqs[1], seqs[2]]
    assert await ask(seq_after=seqs[1]) == seqs[2:]


# --- Paginacion por clave (P-U11-01) ---------------------------------------------------------------------------------------


async def test_p_u11_01_limit_1001_es_422(env: Env) -> None:
    assert (await get(env, READ_METRICS, limit=1001)).status_code == 422
    assert (await get(env, READ_METRICS, limit=0)).status_code == 422
    assert (await get(env, READ_METRICS, limit=1000)).status_code == 200


async def test_p_u11_01_2500_entradas_con_limit_1000_son_tres_paginas_sin_huecos_ni_repetidos(env: Env) -> None:
    seqs = seed(env.cdb, [spec("explanation_view", NOW - timedelta(seconds=2500 - i)) for i in range(2500)])
    pages, after = [], None
    while True:
        response = await get(env, READ_METRICS, limit=1000, seq_after=after)
        assert response.status_code == 200
        body = response.json()
        pages.append(body)
        after = body["next_seq_after"]
        if after is None:
            break
    assert [len(p["items"]) for p in pages] == [1000, 1000, 500]
    assert [p["next_seq_after"] is not None for p in pages] == [True, True, False] and pages[-1]["next_seq_after"] is None
    assert [i["seq"] for p in pages for i in p["items"]] == seqs  # ni huecos ni repetidos
    assert pages[0]["next_seq_after"] == seqs[999] and pages[1]["next_seq_after"] == seqs[1999]


async def test_p_u11_01_una_pagina_exacta_no_anuncia_otra(env: Env) -> None:
    seqs = seed(env.cdb, [spec("explanation_view", NOW) for _ in range(3)])
    body = (await get(env, READ_METRICS, limit=3)).json()
    assert len(body["items"]) == 3 and body["next_seq_after"] is None and seqs


async def test_p_u11_01_seq_after_igual_a_la_cabeza_es_una_pagina_vacia_con_next_nulo(env: Env) -> None:
    seqs = seed(env.cdb, [spec("explanation_view", NOW) for _ in range(3)])
    response = await get(env, READ_METRICS, seq_after=seqs[-1])
    assert response.status_code == 200 and response.json() == {"items": [], "next_seq_after": None}


# --- metrics: referencia resuelta en el servidor, first_evaluation, received_at, delivery_status --------------------------------


async def test_p_u11_01_una_decision_que_referencia_una_recomendacion_de_60_dias_trae_sus_campos_con_35_dias_de_consulta(
    env: Env,
) -> None:
    old = NOW - timedelta(days=60)
    seqs = seed(env.cdb, [recommendation(old, channel="oficina"), decision(NOW - timedelta(days=1), 1)])
    response = await get(env, READ_METRICS, recorded_from=iso(NOW - timedelta(days=35)))
    items = response.json()["items"]
    assert [i["seq"] for i in items] == [seqs[1]]  # la recomendacion de 60 dias queda fuera del rango, la decision no
    ref = items[0]["recommendation"]
    assert ref["seq"] == seqs[0] and ref["channel"] == "oficina" and ref["model_version_id"] == "mv-1"
    assert set(ref) == {"seq", "outcome", "model_version_id", "evaluated_at", "received_at", "channel", "attempt", "first_evaluation"}


async def test_p_u11_01_una_decision_que_referencia_un_freeze_tiene_recommendation_null(env: Env) -> None:
    seqs = seed(env.cdb, [spec("freeze", NOW), decision(NOW, 1)])
    items = (await get(env, READ_METRICS)).json()["items"]
    assert [i["seq"] for i in items] == [seqs[1]] and items[0]["recommendation"] is None
    assert "recommendation" in items[0]  # el campo es `null`, no se omite


async def test_p_u11_01_una_decision_que_referencia_un_seq_inexistente_tiene_recommendation_null(env: Env) -> None:
    seed(env.cdb, [decision(NOW, 9999)])
    assert (await get(env, READ_METRICS)).json()["items"][0]["recommendation"] is None


async def test_p_u11_01_first_evaluation_y_received_at_salen_como_los_guardo_u8(env: Env) -> None:
    received = NOW - timedelta(days=2)
    seqs = seed(
        env.cdb,
        [
            recommendation(NOW - timedelta(minutes=30), attempt=1, first_evaluation=True, received_at=iso(received)),
            recommendation(NOW - timedelta(minutes=20), attempt=2, first_evaluation=False, received_at=iso(received)),
            recommendation(NOW - timedelta(minutes=10), attempt=3, first_evaluation=False, received_at=iso(received)),
        ],
    )
    items = (await get(env, READ_METRICS, case_id=str(CASE))).json()["items"]
    assert [(i["seq"], i["attempt"], i["first_evaluation"]) for i in items] == [(seqs[0], 1, True), (seqs[1], 2, False), (seqs[2], 3, False)]
    assert {i["received_at"] for i in items} == {iso(received)}


async def test_br_u3_14_metrics_lleva_delivery_status_de_cada_recomendacion(env: Env) -> None:
    """Candidata 4 de U03-T02: `delivery_status` esta en `MetricsProjection` de U0 y sale solo en la `recommendation`."""
    seqs = seed(
        env.cdb,
        [
            recommendation(NOW - timedelta(minutes=30)),
            recommendation(NOW - timedelta(minutes=20)),
            decision(NOW - timedelta(minutes=10), 2),
            recommendation(NOW - timedelta(minutes=5), OTHER_CASE),
        ],
    )
    items = {i["seq"]: i for i in (await get(env, READ_METRICS)).json()["items"]}
    assert items[seqs[0]]["delivery_status"] == "no_entregada"  # el caso decidio sobre la segunda
    assert items[seqs[1]]["delivery_status"] == "entregada"
    assert items[seqs[3]]["delivery_status"] == "pendiente_de_decision"
    assert "delivery_status" not in items[seqs[2]]


async def test_br_u3_15_metrics_valida_contra_metrics_projection_de_u0(env: Env) -> None:
    from vectra_contracts.models.registry import MetricsProjection

    seed(env.cdb, [recommendation(NOW), decision(NOW, 1), spec("explanation_view", NOW)])
    for item in (await get(env, READ_METRICS)).json()["items"]:
        MetricsProjection.model_validate_json(json.dumps(item))


# --- monitoring_freezes ----------------------------------------------------------------------------------------------------


def resolution(at: datetime, action: str, version: str = "mv-1") -> tuple[dict[str, Any], datetime]:
    return spec("frozen_resolution", at, payload=payload_for("frozen_resolution", at, action=action), model_version_id=version)


async def test_br_u3_17_freeze_en_entries_lleva_recorded_at_y_el_context_package_completo(env: Env) -> None:
    (seq,) = seed(env.cdb, [spec("freeze", NOW - timedelta(hours=1))])
    (item,) = (await get(env, READ_MONITORING, projection="monitoring_freezes")).json()["items"]
    assert item["seq"] == seq and item["recorded_at"] == iso(NOW - timedelta(hours=1))
    from vectra_contracts.models.monitoring import FreezeContextPackage

    def package(data: Any) -> FreezeContextPackage:
        return FreezeContextPackage.model_validate_json(json.dumps(data))

    assert package(item["context_package"]) == package(payload_for("freeze", NOW)["context_package"])  # completo, tal como se guardo
    assert set(item["context_package"]) >= {"data_sources", "initial_disparity", "affected_volume", "before", "after"}


async def test_br_u3_17_freezes_un_reactivar_deja_resolutions_con_su_recorded_at(env: Env) -> None:
    seed(env.cdb, [spec("freeze", NOW - timedelta(hours=3)), resolution(NOW - timedelta(hours=1), "reactivar")])
    response = await env.client.get("/v1/monitoring/freezes", headers=service_token(READ_MONITORING))
    assert response.status_code == 200
    (record,) = response.json()
    assert record["resolutions"][-1] == {"action": "reactivar", "recorded_at": iso(NOW - timedelta(hours=1))}
    from vectra_contracts.models.monitoring import FreezeRecord

    FreezeRecord.model_validate_json(json.dumps(record))


async def test_br_u3_17_freezes_investigar_y_luego_reactivar_son_dos_elementos_en_ese_orden(env: Env) -> None:
    seed(
        env.cdb,
        [
            spec("freeze", NOW - timedelta(hours=5)),
            resolution(NOW - timedelta(hours=3), "investigar"),
            resolution(NOW - timedelta(hours=1), "reactivar"),
        ],
    )
    (record,) = (await env.client.get("/v1/monitoring/freezes", headers=service_token(READ_MONITORING))).json()
    assert [r["action"] for r in record["resolutions"]] == ["investigar", "reactivar"]


async def test_br_u3_17_freezes_cada_resolucion_va_con_el_freeze_de_su_version(env: Env) -> None:
    seed(
        env.cdb,
        [
            spec("freeze", NOW - timedelta(hours=5), model_version_id="mv-1"),
            spec("freeze", NOW - timedelta(hours=4), model_version_id="mv-2"),
            resolution(NOW - timedelta(hours=3), "descartar", "mv-2"),
        ],
    )
    records = (await env.client.get("/v1/monitoring/freezes", headers=service_token(READ_MONITORING))).json()
    assert [(r["model_version_id"], len(r["resolutions"])) for r in records] == [("mv-1", 0), ("mv-2", 1)]


async def test_br_u3_17_freezes_exige_el_scope_de_monitoreo(env: Env) -> None:
    assert (await env.client.get("/v1/monitoring/freezes", headers=service_token(READ_METRICS))).status_code == 403


# --- POST /v1/monitoring/daily:query ----------------------------------------------------------------------------------------


GROUPS = {"sexo": ("F", "M", "no_informado")}


def seed_daily(env: Env, *, days: int = 90, version: str = "mv-1", population: str = "modelo", count: int = 2) -> int:
    """`monitoring_daily` con 27 filas por dia (3 grupos x 3 bandas x 3 resultados); devuelve cuantas inserto."""
    rows = []
    for offset in range(days):
        day = date(2026, 8, 1) + timedelta(days=offset)
        for group in GROUPS["sexo"]:
            for band in ("lt_20", "20_30", "gt_30"):
                for result in ("favorable", "desfavorable", "revision_requerida"):
                    rows.append((population, version, day, "sexo", group, band, result, "-", count))
    with env.cdb.db.connect() as conn, conn.cursor() as cursor:
        cursor.executemany(
            'INSERT INTO monitoring_daily (population, model_version_id, day, attribute, "group", band, result, decision, count) '
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )
    env.cdb.sync()
    return len(rows)


def query(ranges: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"ranges": ranges, "include_versions": extra.pop("include_versions", True), **extra}


def day_range(range_id: str, first: str = "2026-08-01", last: str = "2026-10-29", **extra: Any) -> dict[str, Any]:
    return {"range_id": range_id, "population": "modelo", "from_day": first, "to_day": last, **extra}


async def daily(env: Env, body: dict[str, Any], scope: str = READ_MONITORING) -> Any:
    return await env.client.post("/v1/monitoring/daily:query", content=json.dumps(body), headers={**service_token(scope), "content-type": "application/json"})


async def test_br_u3_17_12_rangos_de_90_dias_con_miles_de_filas_responden_en_el_limite_del_pool_y_suman_en_el_servidor(
    env: Env,
) -> None:
    inserted = seed_daily(env)
    assert inserted == 2430
    body = query([day_range(f"r{i}") for i in range(12)])
    started = time.monotonic()
    response = await daily(env, body)
    elapsed = time.monotonic() - started
    assert response.status_code == 200, response.text
    assert elapsed < 2.0, elapsed
    window = MonitoringWindow.model_validate_json(response.text)
    # Suma en el servidor: una fila por celda y rango (27 celdas x 12 rangos), no una por dia.
    assert len(window.counts) == 27 * 12
    assert {c.count for c in window.counts} == {2 * 90}
    assert len(window.totals) == 12 and {t.range_id for t in window.totals} == {f"r{i}" for i in range(12)}


async def test_br_u3_17_una_consulta_explanation_concurrente_no_supera_su_limite(env: Env) -> None:
    seed_daily(env)
    (seq,) = seed(env.cdb, [recommendation(NOW)])
    body = query([day_range(f"r{i}") for i in range(12)])

    async def explanation() -> tuple[int, float]:
        started = time.monotonic()
        response = await get(env, READ_EXPLANATION, case_id=str(CASE), seq=seq)
        return response.status_code, time.monotonic() - started

    results = await asyncio.gather(daily(env, body), explanation(), explanation())
    assert results[0].status_code == 200
    for status, elapsed in results[1:]:
        assert status == 200 and elapsed < 2.0, (status, elapsed)  # el pool `projections` espera hasta 2 s


async def test_br_u3_17_versions_devuelve_first_day_y_last_day_por_version_y_poblacion_y_totals_una_fila_por_range_id(
    env: Env,
) -> None:
    seed_daily(env, days=10, version="mv-1")
    seed_daily(env, days=5, version="mv-2")
    with env.cdb.db.connect() as conn:
        conn.execute(
            "INSERT INTO monitoring_entry_totals (population, model_version_id, day, total, invalid) VALUES "
            "('modelo', 'mv-1', '2026-08-01', 10, 2), ('modelo', 'mv-1', '2026-08-02', 5, 1), ('modelo', 'mv-2', '2026-08-01', 7, 0)"
        )
    env.cdb.sync()
    body = query([day_range("a", "2026-08-01", "2026-08-01"), day_range("b", "2026-08-01", "2026-08-31", model_version_id="mv-1")])
    window = MonitoringWindow.model_validate_json((await daily(env, body)).text)
    assert [(v.model_version_id, v.population, v.first_day.isoformat(), v.last_day.isoformat()) for v in window.versions] == [
        ("mv-1", "modelo", "2026-08-01", "2026-08-10"),
        ("mv-2", "modelo", "2026-08-01", "2026-08-05"),
    ]
    assert {t.range_id: (t.total_entries, t.invalid_entries) for t in window.totals} == {"a": (17, 2), "b": (15, 3)}
    no_versions = MonitoringWindow.model_validate_json((await daily(env, query([day_range("a")], include_versions=False))).text)
    assert no_versions.versions == []


async def test_br_u3_17_13_rangos_es_422(env: Env) -> None:
    response = await daily(env, query([day_range(f"r{i}") for i in range(13)]))
    assert response.status_code == 422


async def test_br_u3_17_un_rango_o_un_unattributable_range_con_from_day_mayor_que_to_day_es_422(env: Env) -> None:
    assert (await daily(env, query([day_range("a", "2026-09-02", "2026-09-01")]))).status_code == 422
    inverted = query([day_range("a")], unattributable_range={"from_day": "2026-09-02", "to_day": "2026-09-01"})
    assert (await daily(env, inverted)).status_code == 422


async def test_br_u3_17_unattributable_invalid_es_un_solo_valor_0_sin_el_rango_y_no_aparece_en_totals(env: Env) -> None:
    with env.cdb.db.connect() as conn:
        conn.execute(
            "INSERT INTO monitoring_entry_totals (population, model_version_id, day, total, invalid) VALUES "
            "('humana', '-', '2026-08-01', 4, 3), ('humana', '-', '2026-08-02', 2, 2), ('humana', '-', '2026-09-10', 9, 9), "
            "('humana', 'mv-1', '2026-08-01', 5, 1)"
        )
    env.cdb.sync()
    wide = query([day_range("a", "2026-08-01", "2026-08-31")], unattributable_range={"from_day": "2026-08-01", "to_day": "2026-08-31"})
    window = MonitoringWindow.model_validate_json((await daily(env, wide)).text)
    assert window.unattributable_invalid == 5  # 3 + 2: un solo valor sobre el rango pedido
    assert [t.total_entries for t in window.totals] == [0]  # las filas `-` no suman en `totals`
    without = MonitoringWindow.model_validate_json((await daily(env, query([day_range("a", "2026-08-01", "2026-08-31")]))).text)
    assert without.unattributable_invalid == 0


async def test_br_u3_17_invalid_seqs_son_hasta_100_los_menores_de_los_dias_pedidos(env: Env) -> None:
    with env.cdb.db.connect() as conn, conn.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO monitoring_invalid (seq, population, model_version_id, day, reason) VALUES (%s, 'modelo', 'mv-1', '2026-08-01', 'x')",
            [(1000 - i,) for i in range(150)],
        )
        cursor.execute("INSERT INTO monitoring_invalid VALUES (5, 'modelo', 'mv-1', '2027-01-01', 'fuera de los dias pedidos')")
    env.cdb.sync()
    window = MonitoringWindow.model_validate_json((await daily(env, query([day_range("a", "2026-08-01", "2026-08-02")]))).text)
    assert window.invalid_seqs == list(range(851, 951))


async def test_br_u3_17_daily_query_exige_el_scope_de_monitoreo(env: Env) -> None:
    assert (await daily(env, query([day_range("a")]), READ_METRICS)).status_code == 403


async def test_br_u3_17_daily_query_no_escribe_y_es_solo_lectura(env: Env) -> None:
    with env.cdb.db.connect() as conn:
        before = conn.execute("SELECT count(*) FROM monitoring_daily").fetchone()
    await daily(env, query([day_range("a")]))
    with env.cdb.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM monitoring_daily").fetchone() == before


# --- Permisos de registry_verifier y el gauge del atraso ---------------------------------------------------------------------


def test_br_u3_17_registry_verifier_no_puede_leer_monitoring_case_index(env: Env) -> None:
    with psycopg.connect(env.cdb.dsn("projections")) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM monitoring_case_index")
        conn.rollback()
        for table in ("monitoring_daily", "monitoring_entry_totals", "monitoring_invalid", "monitoring_watermark", "integrity_checks"):
            conn.execute(f"SELECT count(*) FROM {table}")  # noqa: S608


def set_watermark(env: Env, last_seq: int) -> None:
    with env.cdb.db.connect() as conn:
        conn.execute("UPDATE monitoring_watermark SET last_seq = %s WHERE id = 1", (last_seq,))
    env.cdb.sync()


async def test_br_u3_17_el_gauge_de_atraso_es_0_con_la_marca_igual_a_la_cabeza_y_2_h_sin_trafico(env: Env) -> None:
    seqs = seed(env.cdb, [spec("explanation_view", NOW - timedelta(hours=2, minutes=i)) for i in (2, 1, 0)])
    set_watermark(env, seqs[-1])  # el agregador llego a la cabeza; el registro lleva 2 h sin trafico
    await Gauges(env.pools, env.clock).refresh()
    assert MONITORING_LAG._value.get() == 0  # type: ignore[attr-defined]
    window = MonitoringWindow.model_validate_json((await daily(env, query([day_range("a")]))).text)
    assert (window.watermark_seq, window.lag_seconds) == (seqs[-1], 0)


async def test_br_u3_17_el_gauge_de_atraso_con_una_entrada_pendiente_de_hace_31_min_supera_1800(env: Env) -> None:
    seqs = seed(
        env.cdb,
        [spec("explanation_view", NOW - timedelta(hours=1)), spec("explanation_view", NOW - timedelta(minutes=31))],
    )
    set_watermark(env, seqs[0])  # la entrada `last_seq + 1` es la de hace 31 min
    await Gauges(env.pools, env.clock).refresh()
    assert MONITORING_LAG._value.get() == 31 * 60  # type: ignore[attr-defined]
    assert MONITORING_LAG._value.get() > 1800  # type: ignore[attr-defined]
    window = MonitoringWindow.model_validate_json((await daily(env, query([day_range("a")]))).text)
    assert window.lag_seconds == 31 * 60


async def test_br_u3_13b_los_gauges_de_la_verificacion_bajo_demanda(env: Env) -> None:
    from vectra_registry.health import CHECKS_FAILED, FULL_AGE, PENDING_AGE

    with env.cdb.db.connect() as conn:
        conn.execute(
            "INSERT INTO integrity_checks (check_id, mode, from_seq, to_seq, requested_by, requested_at, status) "
            "VALUES (gen_random_uuid(), 'range', 0, 1, 'x', %s, 'pendiente')",
            (NOW - timedelta(minutes=12),),
        )
        conn.execute(
            "INSERT INTO integrity_checks (check_id, mode, requested_by, requested_at, finished_at, status, report) "
            "VALUES (gen_random_uuid(), 'full', 'cron', %s, %s, 'terminada', '{\"result\": \"integra\"}')",
            (NOW - timedelta(days=41), NOW - timedelta(days=40)),
        )
        conn.execute(
            "INSERT INTO integrity_checks (check_id, mode, requested_by, requested_at, status, reason) "
            "VALUES (gen_random_uuid(), 'full', 'cron', %s, 'fallida', 'interrumpida')",
            (NOW - timedelta(days=50),),
        )
    env.cdb.sync()
    await Gauges(env.pools, env.clock).refresh()
    assert PENDING_AGE._value.get() == 12 * 60  # type: ignore[attr-defined]
    assert CHECKS_FAILED._value.get() == 1  # type: ignore[attr-defined]
    assert FULL_AGE._value.get() == 40 * 86400  # type: ignore[attr-defined]
