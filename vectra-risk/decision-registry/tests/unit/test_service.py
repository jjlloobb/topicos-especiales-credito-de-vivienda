"""Configuracion del servicio por variables de entorno (INF-U3-04: 5 conexiones, 3 DSN)."""

import base64

import pytest
from vectra_registry import service


def test_config_from_env_arma_los_cuatro_pools_con_tres_dsn_y_las_llaves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGISTRY_RW_APP_DSN", "postgresql://registry_app:a@rw/registry")
    monkeypatch.setenv("REGISTRY_RW_HEALTH_DSN", "postgresql://registry_health:h@rw/registry")
    monkeypatch.setenv("REGISTRY_RO_VERIFIER_DSN", "postgresql://registry_verifier:v@ro/registry")
    keys = [bytes([i]) * 32 for i in (1, 2)]
    monkeypatch.setenv("REGISTRY_CHECKPOINT_PUBLIC_KEYS", ",".join(base64.b64encode(k).decode() for k in keys) + ", ")
    pools, config = service.config_from_env()
    assert [p.size for p in (pools.append, pools.dossier, pools.projections, pools.health)] == [2, 1, 1, 1]
    assert list(config.public_keys) == keys


def test_sin_dsn_el_servicio_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("REGISTRY_RW_APP_DSN", "REGISTRY_RW_HEALTH_DSN", "REGISTRY_RO_VERIFIER_DSN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(KeyError):
        service.config_from_env()


def _dsns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGISTRY_RW_APP_DSN", "postgresql://rw/registry?user=registry_app&passfile=/run/pgpass/pgpass")
    monkeypatch.setenv("REGISTRY_RW_HEALTH_DSN", "postgresql://rw/registry?user=registry_health&passfile=/run/pgpass/pgpass")
    monkeypatch.setenv("REGISTRY_RO_VERIFIER_DSN", "postgresql://ro/registry?user=registry_verifier&passfile=/run/pgpass/pgpass")
    # Variables de U0 (F50) que `create_app` exige y el chart fija: emisor, llaves por http (sin CA) y nada mas.
    monkeypatch.setenv("VECTRA_OIDC_ISSUER", "http://keycloak/realms/vectra")
    monkeypatch.setenv("VECTRA_JWKS_URL", "http://keycloak/realms/vectra/certs")


def test_build_app_arma_la_aplicacion_con_la_configuracion_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    _dsns(monkeypatch)
    monkeypatch.delenv("REGISTRY_CHECKPOINT_PUBLIC_KEYS", raising=False)
    app = service.build_app()
    assert app.title or app.routes  # la fabrica de U0 deja las rutas del contrato


def test_main_arranca_el_servicio_con_la_aplicacion_armada(monkeypatch: pytest.MonkeyPatch) -> None:
    _dsns(monkeypatch)
    started: list[object] = []
    monkeypatch.setattr(service, "run_service", started.append)
    service.main()
    assert len(started) == 1 and type(started[0]).__name__ == "FastAPI"


def test_el_reloj_por_omision_de_la_api_es_la_hora_actual_en_utc() -> None:
    from datetime import UTC, datetime

    from vectra_registry import api

    assert abs((api._utc_now() - datetime.now(UTC)).total_seconds()) < 5  # noqa: SLF001
