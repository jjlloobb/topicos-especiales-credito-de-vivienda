"""Paso 9 (U04-T03): `serving-config` en memoria y convergencia entre 2 replicas (P-U4-01, P-U4-05; NFR-U4-04, 05, 06).

Dos replicas son dos instancias del servicio (`Evidence` + `ServingConfigCache`, cada una con sus pools) en el mismo proceso,
contra el mismo PostgreSQL de Testcontainers. «Cortar la conexion `LISTEN`» es `pg_terminate_backend` sobre esa conexion;
«pausar la base» es `docker pause` del contenedor desde la prueba.
"""

import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime

import psycopg
import pytest
from evidence_support import (
    BIAS,
    ING,
    FakeRegistry,
    SimClock,
    freeze_context,
    make_service,
    normative,
    policy_draft,
    service_dsn,
    to_activo,
    to_aprobado,
    wait_for,
    with_active_policy,
)
from governance_pg import Db, admin_url
from vectra_common.errors import DependencyUnavailable
from vectra_common.metrics import REGISTRY
from vectra_governance.convergence import ServingConfigCache, ServingConfigUnavailable
from vectra_governance.evidence import Evidence
from vectra_governance.pools import Pools

pytestmark = pytest.mark.integration

AGE_GAUGE = "vectra_serving_config_age_seconds"


@dataclass
class Replicas:
    db: Db
    clock: SimClock
    registry: FakeRegistry
    a: Evidence
    b: Evidence
    cache_a: ServingConfigCache
    cache_b: ServingConfigCache

    def terminate_listener(self, replica: str) -> int:
        with psycopg.connect(admin_url(self.db.pg, self.db.name), autocommit=True) as conn:
            rows = conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = %s",
                (f"governance:{replica}:listen",),
            ).fetchall()
        return len(rows)


def build(db: Db, *, normative_to: date | None = None, **cache_args: object) -> Iterator[Replicas]:
    clock = SimClock()
    registry = FakeRegistry(clock)
    a = make_service(db, registry, clock, "a")
    b = make_service(db, registry, clock, "b")
    with_active_policy(a, draft=policy_draft(normative=[normative(date(2026, 1, 1), normative_to)]))
    to_activo(a, "mv-1")
    cache_a = ServingConfigCache(a.pools, clock=clock, **cache_args)  # type: ignore[arg-type]
    cache_b = ServingConfigCache(b.pools, clock=clock, **cache_args)  # type: ignore[arg-type]
    replicas = Replicas(db, clock, registry, a, b, cache_a, cache_b)
    yield replicas
    cache_a.stop()
    cache_b.stop()
    a.pools.close()
    b.pools.close()


@pytest.fixture
def replicas(db: Db) -> Iterator[Replicas]:
    yield from build(db)


def start_both(r: Replicas) -> None:
    r.cache_a.start()
    r.cache_b.start()
    assert r.cache_a.wait_ready(10) and r.cache_b.wait_ready(10)
    assert wait_for(lambda: r.cache_a.listening and r.cache_b.listening, 5) is not None


# --- freeze en A -> B sirve el etag nuevo en <= 1 s ------------------------------------------------------------------------------


def test_freeze_en_a_llega_a_b_en_menos_de_1_s_por_listen(replicas: Replicas) -> None:
    start_both(replicas)
    before = replicas.cache_b.current()
    assert before.state == "activo"
    started = time.monotonic()
    replicas.a.freeze(BIAS, "mv-1", freeze_context("mv-1"))
    took = wait_for(lambda: replicas.cache_b.current().etag != before.etag, 1.0)
    assert took is not None, "B no sirvio el etag nuevo en 1 s"
    assert time.monotonic() - started <= 1.0
    after = replicas.cache_b.current()
    assert after.state == "congelado"
    # Lectura de vuelta: el etag que sirve B es el que quedo en la base.
    assert replicas.a.pools is not replicas.b.pools
    with replicas.b.pools.read() as conn:
        row = conn.execute("SELECT etag, state FROM serving_config").fetchone()
        conn.rollback()
    assert row is not None and row["state"] == "congelado" and row["etag"] == after.etag == replicas.cache_a.current().etag


def test_freeze_en_a_llega_a_b_en_menos_de_1_s_con_la_conexion_listen_de_b_cortada(
    replicas: Replicas, monkeypatch: pytest.MonkeyPatch
) -> None:
    start_both(replicas)
    before = replicas.cache_b.current()

    def refuse() -> None:
        raise DependencyUnavailable()

    monkeypatch.setattr(replicas.b.pools, "listen_connection", refuse)  # B no puede volver a escuchar
    assert replicas.terminate_listener("b") == 1
    assert wait_for(lambda: not replicas.cache_b.listening, 2) is not None

    started = time.monotonic()
    replicas.a.freeze(BIAS, "mv-1", freeze_context("mv-1"))
    took = wait_for(lambda: replicas.cache_b.current().etag != before.etag, 1.0)
    assert took is not None, "sin LISTEN, el sondeo no llevo el etag nuevo a B en 1 s"
    assert time.monotonic() - started <= 1.0
    assert replicas.cache_b.current().state == "congelado" and not replicas.cache_b.listening


def test_mark_active_tambien_converge_con_el_etag_nuevo(replicas: Replicas) -> None:
    to_aprobado(replicas.a, "mv-2")
    start_both(replicas)
    before = replicas.cache_b.current()
    replicas.a.mark_active(ING, "mv-2")
    assert wait_for(lambda: replicas.cache_b.current().etag != before.etag, 1.0) is not None
    now = replicas.cache_b.current()
    assert now.model_version_id == "mv-2" and now.inference_service != before.inference_service


def test_if_none_match_con_el_etag_vigente_es_sin_cambios(replicas: Replicas) -> None:
    start_both(replicas)
    config = replicas.cache_a.current()
    assert replicas.cache_a.lookup(f'"{config.etag}"') == (config, True)  # 304 en U04-T04
    assert replicas.cache_a.lookup(f'W/"{config.etag}"')[1] is True
    assert replicas.cache_a.lookup(f'"otro", "{config.etag}"')[1] is True
    assert replicas.cache_a.lookup("*")[1] is True
    assert replicas.cache_a.lookup('"otro"')[1] is False
    assert replicas.cache_a.lookup(None)[1] is False
    replicas.a.freeze(BIAS, "mv-1", freeze_context("mv-1"))
    assert wait_for(lambda: replicas.cache_a.current().etag != config.etag, 1.0) is not None
    assert replicas.cache_a.lookup(f'"{config.etag}"')[1] is False  # el etag viejo ya no es el vigente


# --- readiness -----------------------------------------------------------------------------------------------------------------


def test_una_replica_recien_arrancada_no_esta_lista_hasta_cargar_la_copia(replicas: Replicas) -> None:
    cache = replicas.cache_b
    assert cache.ready is False
    with pytest.raises(ServingConfigUnavailable):
        cache.current()
    cache.start()
    assert cache.wait_ready(10) and cache.ready
    assert cache.current().model_version_id == "mv-1"


def test_sin_poder_cargar_la_copia_la_replica_no_esta_lista(db: Db) -> None:
    """La base no responde (la plantilla ni siquiera existe para ese usuario): sigue sin estar lista y responde 503."""
    clock = SimClock()
    pools = Pools(service_dsn(db).replace("gov_app:gov_app", "gov_app:mala"), "z")
    cache = ServingConfigCache(pools, clock=clock)
    cache.start()
    try:
        assert cache.wait_ready(1.5) is False
        with pytest.raises(ServingConfigUnavailable) as error:
            cache.current()
        assert error.value.detail == "not_loaded"
    finally:
        cache.stop()


def test_sin_version_servible_la_replica_esta_lista_pero_responde_503(db: Db) -> None:
    clock = SimClock()
    svc = make_service(db, FakeRegistry(clock), clock, "z")
    cache = ServingConfigCache(svc.pools, clock=clock)
    cache.start()
    try:
        assert cache.wait_ready(10)
        with pytest.raises(ServingConfigUnavailable) as error:
            cache.current()
        assert error.value.detail == "no_serving_config"
    finally:
        cache.stop()
        svc.pools.close()


# --- medianoche de Bogota (P-U4-05), con reloj simulado ---------------------------------------------------------------------------


def test_la_copia_cambia_al_pasar_las_00_00_de_bogota_y_no_a_las_19_00(db: Db) -> None:
    for r in build(db, normative_to=date(2026, 11, 10), poll_interval=60.0, midnight_check=0.05):
        # 00:00 UTC es las 19:00 del 9 de noviembre en Bogota: la vigencia sigue; el sondeo (60 s) no interviene.
        r.clock.current = datetime(2026, 11, 10, 0, 0, 0, tzinfo=UTC)
        r.cache_a.start()
        assert r.cache_a.wait_ready(10)
        first = r.cache_a.current()
        assert first.normative_current is not None and first.normative_current.effective_to == date(2026, 11, 10)

        r.clock.current = datetime(2026, 11, 10, 4, 59, 59, tzinfo=UTC)  # 23:59:59 en Bogota
        time.sleep(0.4)
        assert r.cache_a.current().etag == first.etag and r.cache_a.current().normative_current is not None

        r.clock.current = datetime(2026, 11, 10, 5, 0, 0, tzinfo=UTC)  # 00:00:00 del 10 en Bogota
        assert wait_for(lambda: r.cache_a.current().normative_current is None, 2.0) is not None
        assert r.cache_a.current().etag != first.etag  # un cambio de `normative_current` cambia el `etag`
        # La base no cambio: el cambio es local, por el temporizador (no por una recarga).
        with r.a.pools.read() as conn:
            assert conn.execute("SELECT normative_current FROM serving_config").fetchone() is not None
            conn.rollback()


# --- base pausada: edad de la copia (NFR-U4-04) ------------------------------------------------------------------------------------


def gauge_age() -> float:
    value = REGISTRY.get_sample_value(AGE_GAUGE)
    assert value is not None
    return value


def test_con_la_base_pausada_sirve_la_ultima_copia_29_s_y_responde_503_a_los_31_s(replicas: Replicas) -> None:
    cache = replicas.cache_a
    cache.start()
    assert cache.wait_ready(10)
    last = cache.current()
    time.sleep(1.2)
    assert gauge_age() < 1.0  # sondeando: la edad se mantiene cerca de 0
    container = replicas.db.pg.get_wrapped_container()
    container.pause()  # `docker pause` del contenedor de PostgreSQL
    paused_at = time.monotonic()
    try:
        time.sleep(29.0 - (time.monotonic() - paused_at))
        assert cache.current() == last  # a los 29 s sigue sirviendo la ultima copia
        age_29 = gauge_age()
        assert 27.0 < age_29 < 30.0  # el gauge crece
        time.sleep(31.0 - (time.monotonic() - paused_at))
        with pytest.raises(ServingConfigUnavailable) as error:
            cache.current()  # a los 31 s: 503
        assert error.value.detail == "serving_config_stale"
        assert gauge_age() >= 30.0
    finally:
        container.unpause()
    assert wait_for(lambda: gauge_age() < 1.0, 10) is not None  # al reanudar, la edad vuelve a ~0
    assert cache.current().etag == last.etag
