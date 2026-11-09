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
