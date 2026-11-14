"""Apoyo comun de los escenarios `rt3`, `rt2-setup`, `rt2` y `sim-normal` (U12-T03; no esta en §1 del plan: P-4). Toda la E/S pasa por `clients/` y `simulator`.

- `Sessions`: las sesiones del BFF por usuario. Las escrituras con MFA (`register_model`, `start_validation`, `approve_model`, `resolve_frozen`) piden MFA reciente (`MFA_MAX_AGE = 900` s): si el `auth_time` de la sesion tiene mas
  de `MFA_FRESH` (800 s), se hace un step-up nuevo **antes** de escribir; un 401 o un 403 `mfa_required` no se reintenta a ciegas: un step-up y **una** repeticion.
- `registration_body`: el `ModelRegistration` de un paquete de U5 con la convencion de `governance/docs/kind/registro-cuerpo.sh` (`s3://model-store/<prefijo>/<archivo>`; el prefijo por omision es el `model_version_id`).
- `list_all_models`: todas las paginas de `GET /api/console/models`.
"""

from __future__ import annotations

import hashlib
import json
import ssl
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Protocol, TypeVar

from vectra_contracts.models.governance import ModelRegistration, ModelVersion

from vectra_verification import guard
from vectra_verification.clients._api import ApiError, RunTag
from vectra_verification.clients.bff import BffClient, Session
from vectra_verification.clients.k8s_read import K8sError
from vectra_verification.clients.oidc import OidcError
from vectra_verification.clock import Clock
from vectra_verification.guard import Environment

MFA_FRESH: Final = 800.0  # el BFF acepta 900 s: se renueva antes de que venza
PAGE_SIZE: Final = 50
MAX_PAGES: Final = 100
T = TypeVar("T")


class ScenarioError(Exception):
    """Un escenario se niega a seguir o no puede empezar: el mensaje empieza por un codigo estable y no lleva credenciales ni datos del solicitante."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}:{detail}" if detail else code)
        self.code = code


class UserSession(Session, Protocol):
    auth_time: datetime | None


class Oidc(Protocol):
    def login(self, user: str) -> UserSession: ...

    def step_up(self, user: str) -> UserSession: ...


class Sessions:
    def __init__(
        self,
        environment: Environment,
        oidc: Oidc,
        clock: Clock,
        tag: RunTag,
        *,
        transport: Any = None,  # un `httpx.BaseTransport`: `scenarios` no importa `httpx` (contrato de import-linter)
        verify: ssl.SSLContext
        | bool = True,  # la CA del entorno (`OidcClient.ca_file`) o `False` en las pruebas
    ) -> None:
        self._environment, self._oidc, self._clock, self._tag = environment, oidc, clock, tag
        self._transport, self._verify = transport, verify
        self._readers: dict[str, BffClient] = {}
        self._writers: dict[str, tuple[BffClient, UserSession]] = {}
        self.step_ups: dict[str, int] = {}

    def _client(self, session: UserSession) -> BffClient:
        return BffClient(
            self._environment, session, self._tag, transport=self._transport, verify=self._verify
        )

    def reader(self, user: str) -> BffClient:
        if user not in self._readers:
            self._readers[user] = self._client(self._oidc.login(user))
        return self._readers[user]

    def _fresh(self, session: UserSession) -> bool:
        return (
            session.auth_time is not None
            and (self._clock.now() - session.auth_time).total_seconds() <= MFA_FRESH
        )

    def writer(self, user: str, *, force: bool = False) -> BffClient:
        """Un cliente con una sesion de step-up vigente (renovada si el `auth_time` pasa de 800 s). Una sesion sin step-up es un error **antes** de enviar."""
        known = self._writers.get(user)
        if known is not None and not force and self._fresh(known[1]):
            return known[0]
        session = self._oidc.step_up(user)
        self.step_ups[user] = self.step_ups.get(user, 0) + 1
        if not session.step_up:
            raise ScenarioError("step_up_required", user)
        client = self._client(session)
        self._writers[user] = (client, session)
        return client

    def write(self, user: str, call: Callable[[BffClient], T]) -> T:
        """Una escritura con MFA: si el BFF dice que el MFA vencio (401 o 403 `mfa_required`), un step-up y una repeticion."""
        try:
            return call(self.writer(user))
        except ApiError as error:
            if error.status == 401 or (error.status == 403 and error.code == "mfa_required"):
                return call(self.writer(user, force=True))
            raise


def registration_body(package_dir: Path, prefix: str | None = None) -> ModelRegistration:
    """El cuerpo del registro de un paquete (como `registro-cuerpo.sh`): los SHA-256 salen del `manifest.json` y de sus bytes. `prefix` es la carpeta del model-store (por omision, el `model_version_id`)."""
    manifest_file = package_dir / "manifest.json"
    document = json.loads(manifest_file.read_text(encoding="utf-8"))
    base = f"s3://model-store/{prefix if prefix is not None else document['model_version_id']}/"
    sha = {entry["name"]: entry["sha256"] for entry in document["files"]}
    return ModelRegistration(
        artifact_uri=base + "predictor.json",
        artifact_format="xgboost_json",
        artifact_sha256=sha["predictor.json"],
        explainer_uri=base + "explainer.json",
        explainer_sha256=sha["explainer.json"],
        manifest_uri=base + "manifest.json",
        manifest_sha256=hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
    )


def package_version(package_dir: Path) -> str:
    return str(json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))["model_version_id"])


def list_all_models(bff: BffClient) -> list[ModelVersion]:
    models: list[ModelVersion] = []
    for page in range(1, MAX_PAGES + 1):
        batch = bff.list_models(page=page, page_size=PAGE_SIZE).items
        models.extend(batch)
        if len(batch) < PAGE_SIZE:
            return models
    raise ScenarioError("models_pagination_unbounded")


def snapshot(models: list[ModelVersion]) -> dict[str, str]:
    """`model_version_id -> state`: lo que RT-3 compara antes y despues de los registros (P-3: sustituto de `serving-config`)."""
    return {m.model_version_id: m.state for m in models}


def check_section(environment: Environment, section: str) -> None:
    guard.check_section(environment, section)


INFRA_ERRORS: Final = (K8sError, OidcError)


def infra_failure(error: Exception, prefix: str) -> tuple[str, str]:
    """El codigo estable y el detalle de un fallo de infraestructura que **no** es un incumplimiento del sistema (F-05, ronda 2): un `port-forward` caido o un `kubectl` que no responde (`K8sError`) y un login que no se pudo
    hacer o renovar (`OidcError`). El resultado es `no ejecutado`; el detalle trae el codigo del error, que nunca lleva credenciales."""
    if isinstance(error, K8sError):
        forward = str(error).startswith("port_forward")
        return f"{prefix}_{'port_forward_caido' if forward else 'kubectl_no_responde'}", str(error)[:200]
    code = str(error)[:80] or type(error).__name__  # `OidcError` lleva un codigo estable como mensaje
    return f"{prefix}_sesion_oidc_no_disponible", f"oidc:{code}"
