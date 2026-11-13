"""Autenticacion del mock y conteo de intentos de escritura (Paso 17; BR-U8-22; INF-U8-02, 03; NFR-U8-26, 45).

- El mock valida la firma con el JWKS de Keycloak, `aud = core-banking-mock` y el scope, todo con `vectra_common` (U0): el
  `Authenticator` sale de `authenticator_from_env`, que se evalua en el primer uso para que `build_app()` no lea el entorno.
- `WriteAttemptMiddleware` (P-4 (a) de U08-T04): el `WriteAttempt` es el registro `authz.denied` que U0 ya emite en el 403 de
  `POST /v1/credits/{id}/status` (con la identidad del token y la plantilla de la ruta), mas el incremento de
  `vectra_core_write_attempts_total`. Se cuenta en la **denegacion** de la ruta (un 403 de `POST /v1/credits/{id}/status`), no en el
  handler: el 403 lo emite la autorizacion antes de que corra el handler. Un 401 (sin token o con firma invalida) no cuenta: no hay
  identidad que registrar y queda en `vectra_authz_denied_total`.
"""

import re
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send
from vectra_common.authn import Authenticator, authenticator_from_env
from vectra_contracts.models.api import Principal

from core_banking_mock.metrics import WRITE_ATTEMPTS

SERVICE: Final = "core-banking-mock"
FORBIDDEN: Final = 403
_WRITE_PATH: Final = re.compile(r"^/v1/credits/[^/]+/status$")


class LazyEnvAuthenticator:
    """Sin autenticador inyectado, `build_app()` no lee el entorno; el primer uso si (y sin variables, ninguna solicitud autentica)."""

    def __init__(self) -> None:
        self._real: Authenticator | None = None

    async def authenticate(self, authorization: str | None) -> Principal:
        if self._real is None:
            self._real = authenticator_from_env(SERVICE)
        return await self._real.authenticate(authorization)


class WriteAttemptMiddleware:
    """ASGI, el mas externo: cuenta un `POST /v1/credits/{id}/status` que termina en 403."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or not _WRITE_PATH.match(scope["path"]):
            await self.app(scope, receive, send)
            return

        async def count(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] == FORBIDDEN:
                WRITE_ATTEMPTS.inc()
            await send(message)

        await self.app(scope, receive, count)
