"""Cache del diccionario de features (P-U7-05, NFR-U7-21): por version, sin expiracion, LRU de 4 versiones.

El diccionario de una version es inmutable (BR-U4-18), asi que solo se descarta por espacio. Si governance no responde,
la solicitud falla con `DependencyUnavailable` (BR-U7-09); nunca se usa un diccionario de otra version.
"""

from collections import OrderedDict
from datetime import datetime
from urllib.parse import quote

from vectra_common import deps
from vectra_common.deps import DependencyClient
from vectra_common.errors import DependencyUnavailable
from vectra_contracts.models.features import FeatureDictionary
from vectra_contracts.models.governance import ServingConfig

from explainability.config import DICTIONARY_LRU_VERSIONS, DICTIONARY_TIMEOUT_MS
from explainability.metrics import timed

OK = 200
SERVER_ERROR = 500


class DictionaryCache:
    """`client` es el de governance (F103, pool de 5); lo comparten el diccionario y la precarga de la version activa."""

    def __init__(self, client: DependencyClient, capacity: int = DICTIONARY_LRU_VERSIONS) -> None:
        self._client = client
        self._capacity = capacity
        self._entries: OrderedDict[str, FeatureDictionary] = OrderedDict()

    @property
    def versions(self) -> list[str]:
        """De la menos a la mas reciente usada."""
        return list(self._entries)

    def cached(self, model_version_id: str) -> FeatureDictionary | None:
        found = self._entries.get(model_version_id)
        if found is not None:
            self._entries.move_to_end(model_version_id)
        return found

    def _store(self, model_version_id: str, dictionary: FeatureDictionary) -> None:
        self._entries[model_version_id] = dictionary
        self._entries.move_to_end(model_version_id)
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)

    async def get(self, model_version_id: str, deadline: datetime | None = None) -> FeatureDictionary:
        """Del cache o de F103; un `DependencyTimeout`/`DependencyUnavailable` de `deps.call` se propaga tal cual."""
        found = self.cached(model_version_id)
        if found is not None:
            return found
        path = f"/v1/models/{quote(model_version_id, safe='')}/feature-dictionary"
        async with timed("dictionary"):
            response = await deps.call(
                self._client, "GET", path, timeout=DICTIONARY_TIMEOUT_MS / 1000, deadline=deadline
            )
        if response.status_code != OK:
            raise DependencyUnavailable()  # 404, 4xx o 5xx: no se pudo obtener (BR-U7-09)
        dictionary = FeatureDictionary.model_validate_json(response.content)
        self._store(model_version_id, dictionary)
        return dictionary

    async def preload(self) -> str | None:
        """NFR-U7-21: la version activa, al arrancar. Si governance no responde devuelve `None`; nunca bloquea el arranque."""
        try:
            response = await deps.call(
                self._client, "GET", "/v1/serving-config", timeout=DICTIONARY_TIMEOUT_MS / 1000
            )
            if response.status_code != OK:
                return None
            config = ServingConfig.model_validate_json(response.content)
            await self.get(config.model_version_id)
        except Exception:  # noqa: BLE001 - la precarga es oportunista: la primera solicitud pedira el diccionario
            return None
        return config.model_version_id
