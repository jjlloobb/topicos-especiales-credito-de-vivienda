"""Doble de U6 (KServe, protocolo v1): `:predict` y `:explain`, con la forma de `model-serving/*/app.py`."""

import json
import zlib
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from doubles import Faults, Recorder
from doubles.samples import MODEL


def _seed(features: dict[str, Any]) -> int:
    return zlib.crc32(json.dumps(features, sort_keys=True).encode())


class KServeDouble:
    """Predictor y explicador de un `InferenceService`. `score`/`contributions` por omision salen del vector, sin azar:
    el mismo vector da la misma salida (RT-1)."""

    def __init__(self, model_version_id: str = MODEL) -> None:
        self.model_version_id = model_version_id
        self.predict_version: str | None = None  # si no es None, el predictor responde esa version
        self.explain_version: str | None = None  # si no es None, el explicador responde esa version
        self.score: float | None = None
        self.confidence: str = "0.9000"
        self.contributions: dict[str, float] | None = None
        self.predict_body: Any = None  # si no es None, el cuerpo JSON de `:predict` (una respuesta ilegible)
        self.explain_body: Any = None  # idem para `:explain`
        self.predict_faults = Faults()
        self.explain_faults = Faults()
        self.recorder = Recorder()
        self.app = Starlette(
            routes=[
                Route("/v1/models/{name}:predict", self._predict, methods=["POST"]),
                Route("/v1/models/{name}:explain", self._explain, methods=["POST"]),
            ]
        )

    def _features(self, body: bytes) -> dict[str, Any]:
        instances = json.loads(body)["instances"]
        assert len(instances) == 1  # protocolo v1 de U6: una instancia
        features: dict[str, Any] = instances[0]["features"]
        return features

    async def _predict(self, request: Request) -> Response:
        call = await self.recorder.record(request)
        forced = await self.predict_faults.gate()
        if forced is not None:
            return Response(status_code=forced)
        if self.predict_body is not None:
            return JSONResponse(self.predict_body)
        features = self._features(call.body)
        score = self.score if self.score is not None else (_seed(features) % 10_000) / 10_000
        return JSONResponse(
            {
                "predictions": [
                    {
                        "score": score,
                        "confidence": self.confidence,
                        "model_version_id": self.predict_version or self.model_version_id,
                    }
                ]
            }
        )

    async def _explain(self, request: Request) -> Response:
        call = await self.recorder.record(request)
        forced = await self.explain_faults.gate()
        if forced is not None:
            return Response(status_code=forced)
        if self.explain_body is not None:
            return JSONResponse(self.explain_body)
        features = self._features(call.body)
        contributions = self.contributions or {
            feature_id: ((_seed({feature_id: value}) % 2001) - 1000) / 10_000
            for feature_id, value in features.items()
        }
        return JSONResponse(
            {
                "explanations": [
                    {
                        "contributions": [
                            {"feature_id": feature_id, "contribution": value}
                            for feature_id, value in contributions.items()
                        ],
                        "base_value": 0.08,
                        "model_version_id": self.explain_version or self.model_version_id,
                    }
                ]
            }
        )
