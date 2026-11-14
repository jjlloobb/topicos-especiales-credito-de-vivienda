"""El BFF **real** encadenado a la app **real** de governance (U12-T03, CA-16; P-6 (a)): la app de `create_governance_app` sobre PostgreSQL de Testcontainers (el `ApiWorld` de U4), con el BFF real por delante.

El BFF reenvia el `Authorization` del usuario tal cual; governance usa el autenticador del BFF (el emisor de prueba de U0, `aud = console-bff`) y su reloj es el real (el `auth_time` de los tokens es de ahora). Los otros cuatro
destinos del BFF son los dobles de U10. El model-store, el informe del Job de validacion y Kubernetes son los dobles de U4 (`FakeModelStore`, `receive_report`, `FakeKubernetes`): no son de U12.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from external_paths import use_governance_doubles, use_u10_doubles
from sync_asgi import BackgroundLoop, SyncASGITransport

use_governance_doubles()
use_u10_doubles()
import bff_tokens  # noqa: E402
from api_support import ApiWorld  # noqa: E402
from bff_doubles import Doubles  # noqa: E402
from evidence_support import VALIDATION_JOB, report, with_active_policy  # noqa: E402
from governance_pg import Db  # noqa: E402
from vectra_common import process  # noqa: E402
from vectra_governance.api import create_governance_app  # noqa: E402

from console_bff.app import build  # noqa: E402


class RealChain:
    def __init__(self, db: Db) -> None:
        process.ensure_service()
        self.api = ApiWorld(db)
        self.api.clock.current = datetime.now(
            UTC
        )  # el reloj de governance es el real: los tokens del BFF llevan `auth_time` de ahora
        with_active_policy(
            self.api.svc
        )  # el lanzador de validacion pasa la politica activa al Job (BR-U7-04/05)
        self.background = BackgroundLoop()
        self.governance = create_governance_app(self.api.deps, authenticator=bff_tokens.authenticator())
        self.doubles = Doubles()
        transports: dict[str, Any] = dict(self.doubles.transports())
        transports["governance"] = httpx.ASGITransport(app=self.governance, raise_app_exceptions=False)
        self.app = build(self.doubles.urls(), authenticator=bff_tokens.authenticator(), transports=transports)
        self.transport = SyncASGITransport(self.app, self.background)

    def add_package(self, prefix: str, directory: Path) -> None:
        """Sube un paquete al model-store de prueba bajo `s3://model-store/<prefix>/` (el prefijo es un solo segmento)."""
        self.api.store.add(prefix, directory)

    def state(self, model_id: str) -> str | None:
        return self.api.state(model_id)

    def deliver_validation_report(self, model_id: str, *, passed: bool = True) -> None:
        """Lo que hace el Job de validacion al terminar (no es de U12): el informe llega a governance."""
        run_id = str(
            self.api.sql("SELECT run_id FROM validation_runs WHERE model_version_id = %s", model_id)[0][
                "run_id"
            ]
        )
        self.api.svc.receive_report(VALIDATION_JOB, model_id, run_id, report(passed))

    def close(self) -> None:
        self.transport.close()
        self.background.run(self.app.state.upstreams.aclose())
        self.background.close()
        self.api.close()
