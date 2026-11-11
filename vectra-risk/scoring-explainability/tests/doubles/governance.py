"""Doble de U4 (governance): `GET /v1/serving-config` con `If-None-Match` y `GET /v1/models/{id}/feature-dictionary`."""

from collections.abc import Mapping

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from vectra_contracts.models.features import FeatureDictionary
from vectra_contracts.models.governance import ServingConfig

from doubles import Faults, Recorder
from doubles.samples import MODEL, dictionary, serving_config


class GovernanceDouble:
    def __init__(
        self,
        config: ServingConfig | None = None,
        dictionaries: Mapping[str, FeatureDictionary] | None = None,
    ) -> None:
        self.config = config or serving_config()
        self.dictionaries = dict(dictionaries if dictionaries is not None else {MODEL: dictionary()})
        self.recorder = Recorder()
        self.config_faults = Faults()
        self.dictionary_faults = Faults()
        self.app = Starlette(
            routes=[
                Route("/v1/serving-config", self._serving_config),
                Route("/v1/models/{model_id}/feature-dictionary", self._dictionary),
            ]
        )

    @property
    def calls(self) -> list:  # type: ignore[type-arg]
        return self.recorder.calls

    def freeze(self) -> None:
        """U4 BR-U4-14: el congelamiento cambia el contenido y, con el, el `etag`."""
        self.config = self.config.model_copy(update={"state": "congelado", "etag": self.config.etag + "-f"})

    async def _serving_config(self, request: Request) -> Response:
        await self.recorder.record(request)
        forced = await self.config_faults.gate()
        if forced is not None:
            return Response(status_code=forced)
        header = request.headers.get("if-none-match")
        etag = f'"{self.config.etag}"'
        if header is not None and header.strip('"') == self.config.etag:
            return Response(status_code=304, headers={"ETag": etag})
        return Response(
            self.config.model_dump_json(exclude_none=True),
            media_type="application/json",
            headers={"ETag": etag},
        )

    async def _dictionary(self, request: Request) -> Response:
        await self.recorder.record(request)
        forced = await self.dictionary_faults.gate()
        if forced is not None:
            return Response(status_code=forced)
        found = self.dictionaries.get(request.path_params["model_id"])
        if found is None:
            return Response(status_code=404)
        return Response(found.model_dump_json(exclude_none=True), media_type="application/json")
