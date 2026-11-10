"""Un proceso de `scoring-service` real (uvicorn por `ops_server.serve`) contra dobles servidos por sockets. Solo para `test_shutdown.py`.

Variables: `GOV_URL`, `EXPLAIN_URL`, `REGISTRY_URL`, `KSERVE_URL`, `PORT`, `OPS_PORT`, `JWKS_JSON` (el JWKS de la llave de prueba de U0).
"""

import asyncio
import json
import os
from typing import Any

from scoring.app import Settings, build_deps, create_scoring_app
from vectra_common.ops_server import serve

from strategies import auth as u0
from vectra_common.authn import Authenticator
from vectra_common.jwks_cache import JwksCache


def main() -> None:
    env = os.environ
    jwks = json.loads(env["JWKS_JSON"])  # la llave de firma es del proceso de la prueba: aqui solo se valida

    async def fetch() -> Any:
        return jwks

    authenticator = Authenticator(issuer=u0.ISSUER, audience="scoring-service", jwks=JwksCache(fetch))
    settings = Settings(env["GOV_URL"], env["EXPLAIN_URL"], env["REGISTRY_URL"], env["KSERVE_URL"])
    app = create_scoring_app(build_deps(settings), authenticator=authenticator)
    asyncio.run(serve(app, host="127.0.0.1", port=int(env["PORT"]), ops_port=int(env["OPS_PORT"])))


if __name__ == "__main__":
    main()
