"""Doble de explainability (F20) para las pruebas de `scoring`: `POST /v1/explanations` con la forma de `Explanation` o un `Problem`."""

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from vectra_contracts.models.api import ExplainRequest
from vectra_contracts.models.explanation import Explanation
from vectra_contracts.models.features import FeatureContribution

from doubles import Faults, Recorder, problem
from doubles.samples import dictionary


class ExplainabilityDouble:
    def __init__(self) -> None:
        self.recorder = Recorder()
        self.faults = Faults()
        self.version: str | None = None  # responde otra version (RT-3)
        self.error: tuple[int, str, str | None] | None = None  # (status, code, reason)
        self.app = Starlette(routes=[Route("/v1/explanations", self._explain, methods=["POST"])])

    @property
    def calls(self) -> list:  # type: ignore[type-arg]
        return self.recorder.calls

    async def _explain(self, request: Request) -> Response:
        call = await self.recorder.record(request)
        forced = await self.faults.gate()
        if forced is not None:
            return Response(status_code=forced)
        if self.error is not None:
            status, code, reason = self.error
            return JSONResponse(problem(status, code, reason), status_code=status)
        wanted = ExplainRequest.model_validate_json(call.body)
        shap = [
            FeatureContribution(feature_id=feature_id, value=value, contribution="0.0100")
            for feature_id, value in wanted.features.features.items()
        ]
        explanation = Explanation(
            model_version_id=self.version or wanted.model_version_id,
            method="shap",
            shap_vector=shap,
            base_value="0.0800",
            narrative="narrativa del doble",
            narrative_generator="template:v1",
            feature_dictionary_version=dictionary().dictionary_version,
            posthoc_notice="aviso",
            factuality_check="passed",
        )
        return Response(explanation.model_dump_json(), media_type="application/json")
