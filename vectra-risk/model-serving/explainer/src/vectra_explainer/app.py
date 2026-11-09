"""`POST /v1/models/{modelo}:explain`: una instancia -> contribuciones en el orden del `feature_spec`, `base_value` y version."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import Field
from vectra_contracts.models.base import StrictModel
from vectra_contracts.models.features import FeatureVector
from vectra_serving_common.concurrency import ConcurrencyLimiter, explainer_limiter
from vectra_serving_common.model import FeatureMissing
from vectra_serving_common.service import error_body, guarded, not_ready

from vectra_explainer.core import Explainer


class ExplainRequest(StrictModel):
    instances: list[FeatureVector] = Field(min_length=1, max_length=1)


class ContributionOut(StrictModel):
    feature_id: str
    contribution: float


class ExplanationOut(StrictModel):
    contributions: list[ContributionOut]
    base_value: float
    model_version_id: str


class ExplainResponse(StrictModel):
    explanations: list[ExplanationOut]


def create_app(explainer: Explainer | None, limiter: ConcurrencyLimiter | None = None) -> FastAPI:
    """`explainer=None`: el paquete no paso la verificacion; el componente no esta listo y responde 503."""
    app = FastAPI(title="vectra-model-explainer", docs_url=None, redoc_url=None, openapi_url=None)
    gate = limiter or explainer_limiter()

    @app.post("/v1/models/{model_name}:explain", response_model=None)
    def explain(model_name: str, request: ExplainRequest) -> ExplainResponse | JSONResponse:  # noqa: ARG001
        if explainer is None:
            return not_ready()

        def call() -> ExplainResponse | JSONResponse:
            try:
                result = explainer.explain(request.instances[0])
            except FeatureMissing as missing:
                return JSONResponse(error_body("feature_missing", feature_id=str(missing)), status_code=422)
            return ExplainResponse(
                explanations=[
                    ExplanationOut(
                        contributions=[
                            ContributionOut(feature_id=f, contribution=c)
                            for f, c in zip(result.feature_ids, result.contributions, strict=True)
                        ],
                        base_value=result.base_value,
                        model_version_id=result.model_version_id,
                    )
                ]
            )

        return guarded(gate, call)

    return app
