"""`POST /v1/models/{modelo}:predict` (protocolo v1 de KServe): una instancia -> `{score, confidence, model_version_id}`."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import Field
from vectra_contracts.models.base import StrictModel
from vectra_contracts.models.features import FeatureVector
from vectra_serving_common.concurrency import ConcurrencyLimiter, predictor_limiter
from vectra_serving_common.model import FeatureMissing
from vectra_serving_common.service import error_body, guarded, not_ready

from vectra_predictor.core import Predictor


class PredictRequest(StrictModel):
    instances: list[FeatureVector] = Field(min_length=1, max_length=1)


class PredictionOut(StrictModel):
    score: float
    confidence: str
    model_version_id: str


class PredictResponse(StrictModel):
    predictions: list[PredictionOut]


def create_app(predictor: Predictor | None, limiter: ConcurrencyLimiter | None = None) -> FastAPI:
    """`predictor=None`: el paquete no paso la verificacion; el componente no esta listo y responde 503."""
    app = FastAPI(title="vectra-model-predictor", docs_url=None, redoc_url=None, openapi_url=None)
    gate = limiter or predictor_limiter()

    @app.post("/v1/models/{model_name}:predict", response_model=None)
    def predict(model_name: str, request: PredictRequest) -> PredictResponse | JSONResponse:  # noqa: ARG001
        if predictor is None:
            return not_ready()

        def call() -> PredictResponse | JSONResponse:
            try:
                result = predictor.predict(request.instances[0])
            except FeatureMissing as missing:
                return JSONResponse(error_body("feature_missing", feature_id=str(missing)), status_code=422)
            return PredictResponse(
                predictions=[
                    PredictionOut(
                        score=result.score,
                        confidence=result.confidence,
                        model_version_id=result.model_version_id,
                    )
                ]
            )

        return guarded(gate, call)

    return app
