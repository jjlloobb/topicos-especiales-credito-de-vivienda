"""Paso 2 (P-U6-05, NFR-U6-41): la solicitud N+1 con N en curso recibe 503 de inmediato y sube `vectra_serving_rejected_total`."""

import asyncio
import threading
import time
from typing import Any

import httpx
import pytest
from vectra_common.metrics import REGISTRY
from vectra_serving_common.concurrency import (
    EXPLAINER_LIMIT,
    PREDICTOR_LIMIT,
    ConcurrencyLimiter,
    Saturated,
    explainer_limiter,
    predictor_limiter,
)
from vectra_predictor.app import create_app
from vectra_predictor.core import Prediction


def _rejected(component: str) -> float:
    return REGISTRY.get_sample_value("vectra_serving_rejected_total", {"component": component}) or 0.0


def test_the_limits_are_16_for_the_predictor_and_8_for_the_explainer() -> None:
    assert (PREDICTOR_LIMIT, EXPLAINER_LIMIT) == (16, 8)
    assert (predictor_limiter().limit, predictor_limiter().component) == (16, "predictor")
    assert (explainer_limiter().limit, explainer_limiter().component) == (8, "explainer")


def test_request_n_plus_one_is_rejected_without_waiting() -> None:
    limiter = ConcurrencyLimiter("predictor", 3)
    before = _rejected("predictor")
    held = [limiter.try_acquire() for _ in range(3)]
    start = time.perf_counter()
    assert limiter.try_acquire() is False
    assert time.perf_counter() - start < 0.05
    assert held == [True, True, True]
    assert _rejected("predictor") == before + 1
    limiter.release()
    assert limiter.try_acquire() is True  # liberar devuelve el lugar


def test_slot_raises_saturated_and_releases_on_exit_even_on_error() -> None:
    limiter = ConcurrencyLimiter("explainer", 1)
    with pytest.raises(RuntimeError), limiter.slot():
        raise RuntimeError("falla dentro")
    assert limiter.in_flight == 0
    with limiter.slot(), pytest.raises(Saturated):
        with limiter.slot():
            pass
    assert limiter.in_flight == 0


def test_the_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="limit_must_be_positive"):
        ConcurrencyLimiter("predictor", 0)


class _BlockingPredictor:
    """Doble del predictor: `predict` espera a que la prueba lo libere, para tener N solicitudes en curso."""

    model_version_id = "mv-2026-01-01-aaaaaaaa"

    def __init__(self) -> None:
        self.release = threading.Event()

    def predict(self, _: Any) -> Prediction:
        self.release.wait(10)
        return Prediction(0.1, 0.0, "0.9000", self.model_version_id)


async def test_the_http_request_n_plus_one_gets_503_immediately_while_n_are_in_flight() -> None:
    limit = 4
    limiter = ConcurrencyLimiter("predictor", limit)
    predictor = _BlockingPredictor()
    app = create_app(predictor, limiter)  # type: ignore[arg-type]
    before = _rejected("predictor")
    body = {"instances": [{"features": {}}]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        # El doble no arma vectores: `predict` recibe un FeatureVector vacio y el limite se prueba en la admision.
        in_flight = [
            asyncio.create_task(client.post("/v1/models/m:predict", json=body)) for _ in range(limit)
        ]
        for _ in range(200):
            if limiter.in_flight == limit:
                break
            await asyncio.sleep(0.01)
        assert limiter.in_flight == limit
        start = time.perf_counter()
        rejected = await client.post("/v1/models/m:predict", json=body)
        elapsed = time.perf_counter() - start
        assert rejected.status_code == 503
        assert rejected.json() == {"error": "saturated"}
        assert elapsed < 0.5  # sin cola ni espera: los N en curso siguen bloqueados
        assert _rejected("predictor") == before + 1
        predictor.release.set()
        done = await asyncio.gather(*in_flight)
    assert [r.status_code for r in done] == [200] * limit
    assert limiter.in_flight == 0
