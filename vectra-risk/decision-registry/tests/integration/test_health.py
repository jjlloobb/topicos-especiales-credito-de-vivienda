"""Readiness `/readyz` (puerto 8081) con `registry_health` (Paso 9 del plan de U3; P-U3-01; NFR-U3-11).

Con el standby sincrono detenido, `/readyz` da 503 en <= 5 s: el pod sale del balanceo y los llamadores tratan el error de
conexion como `registry_unavailable` (fail-closed, BR-U0-02). `/healthz` (liveness) depende solo del proceso.
"""

import asyncio
import time

import httpx
import pytest
from conftest import Env
from strategies import auth as u0_auth
from vectra_registry import health as health_module
from vectra_registry.api import create_service_app
from vectra_registry.health import CACHE_SECONDS, Health

pytestmark = pytest.mark.integration


def ops_client(env: Env) -> tuple[httpx.AsyncClient, Health]:
    app = create_service_app(env.pools, env.config, authenticator=u0_auth.authenticator())
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app.state.ops_app), base_url="http://ops")
    return client, app.state.health


async def test_p_u3_01_con_el_standby_sincrono_presente_readyz_es_200(env: Env) -> None:
    client, health = ops_client(env)
    await health.start()
    try:
        assert (await client.get("/readyz")).status_code == 200
        assert (await client.get("/healthz")).status_code == 200
    finally:
        await health.stop()
        await client.aclose()


async def test_p_u3_01_con_el_standby_detenido_readyz_da_503_en_menos_de_5_s_y_vuelve_a_200(env: Env) -> None:
    cluster = env.cdb.cluster
    client, health = ops_client(env)
    await health.start()
    try:
        assert (await client.get("/readyz")).status_code == 200
        cluster.stop_standby()
        try:
            started = time.monotonic()
            status = 200
            while status == 200 and time.monotonic() - started < 10:
                await asyncio.sleep(0.25)
                status = (await client.get("/readyz")).status_code
            elapsed = time.monotonic() - started
            assert status == 503, "readyz siguio en 200 con el standby detenido"
            assert elapsed <= 5.0, elapsed
            assert (await client.get("/healthz")).status_code == 200  # liveness: solo el proceso
        finally:
            cluster.start_standby()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and (await client.get("/readyz")).status_code != 200:
            await asyncio.sleep(0.25)
        assert (await client.get("/readyz")).status_code == 200  # el standby volvio: el pod vuelve al balanceo
    finally:
        await health.stop()
        await client.aclose()


async def test_p_u3_01_la_sonda_usa_el_rol_registry_health_que_no_lee_registry_entries(env: Env) -> None:
    import psycopg

    with psycopg.connect(env.cdb.dsn("health")) as conn:
        assert conn.execute("SELECT current_user").fetchone() == ("registry_health",)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT count(*) FROM registry_entries")
        conn.rollback()
        assert conn.execute(health_module.SYNC_STANDBYS).fetchone() == (1,)


async def test_p_u3_01_sin_la_primaria_la_sonda_da_falso(env: Env) -> None:
    from vectra_registry.pools import Pool

    broken = Pool("health", "postgresql://registry_health:x@127.0.0.1:1/nada", 1, 1.0)
    assert await health_module.probe(broken) is False


# --- La cache de 5 s (sin base) ----------------------------------------------------------------------------------------------


class FakePool:
    """Solo para contar cuantas veces se consulta."""


async def test_p_u3_01_el_resultado_se_cachea_5_s_y_uno_mas_viejo_cuenta_como_no_listo(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []
    answers = iter([True, False])

    async def fake_probe(pool: object) -> bool:
        calls.append(True)
        return next(answers)

    monkeypatch.setattr(health_module, "probe", fake_probe)
    now = [100.0]
    health = Health(FakePool(), monotonic=lambda: now[0])  # type: ignore[arg-type]
    assert health.is_ready() is False  # sin ninguna comprobacion todavia
    await health.refresh()
    assert health.is_ready() is True and len(calls) == 1
    now[0] += CACHE_SECONDS - 0.1
    assert health.is_ready() is True and len(calls) == 1  # dentro de los 5 s: el mismo resultado, sin consultar
    now[0] += 0.2
    assert health.is_ready() is False  # el resultado caduco y nadie lo refresco: no listo
    await health.refresh()
    assert health.is_ready() is False and len(calls) == 2  # el nuevo resultado es "sin standby"


def test_p_u3_01_el_refresco_es_mas_corto_que_la_vigencia() -> None:
    assert CACHE_SECONDS == 5.0 and health_module.REFRESH_SECONDS < CACHE_SECONDS


async def test_br_u3_17_el_ciclo_de_vida_arranca_la_sonda_y_los_gauges_y_cierra_los_pools(env: Env) -> None:
    """Al arrancar la app: primera comprobacion de readiness y primera lectura del atraso; al cerrar, las tareas y los pools."""
    app = create_service_app(env.pools, env.config, authenticator=u0_auth.authenticator())
    health_module.MONITORING_LAG.set(-1)
    async with app.router.lifespan_context(app):
        assert app.state.health.is_ready() is True  # la sonda ya corrio antes de aceptar trafico
        for _ in range(40):  # los gauges corren en su tarea: la primera lectura no espera 60 s
            if health_module.MONITORING_LAG._value.get() >= 0:  # type: ignore[attr-defined]
                break
            await asyncio.sleep(0.1)
        assert health_module.MONITORING_LAG._value.get() >= 0  # type: ignore[attr-defined]
        assert app.state.health._task is not None and app.state.gauges._task is not None
    assert app.state.health._task.cancelled() and app.state.gauges._task.cancelled()
    assert env.pools.append._idle.empty()  # los pools se vaciaron y sus conexiones se cerraron


def test_br_u3_17_los_gauges_corren_cada_60_s() -> None:
    assert health_module.GAUGE_SECONDS == 60.0
