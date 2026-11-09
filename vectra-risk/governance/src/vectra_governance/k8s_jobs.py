"""Jobs de `vectra-staging` por K01 (P-U4-03, NFR-U4-25): lectura del Job para el barrido y lanzador del Paso 10.

- **Lanzador** (`job_manifest`, `KubernetesJobs.create`): el `model-validation-job` en `vectra-staging` con
  `ttlSecondsAfterFinished: 86400`, `activeDeadlineSeconds: 7200` y `backoffLimit: 0` (BR-U4-05). `mode` es un parametro
  del manifiesto: `validacion` desde `POST /v1/models/{id}/validations` y `source_comparison` solo desde
  `POST /v1/data-sources/{id}/comparisons` (BR-U4-13). El Job lo puntua el Paso 13; aqui solo se crea.
- **Lectura** (`KubernetesJobs.get`): sin watch, una consulta por vencimiento; el barrido (`background.py`) solo la usa
  para registrar el motivo del `validacion_fallida`.
- **`inference_service_exists`**: la comprobacion de INF-U4-05 (`start_source_comparison` exige los dos `InferenceService`
  de staging).

El cliente habla con la API REST de Kubernetes con `httpx` y timeouts de 5 s por llamada (NFR-U4-25), con el token del
ServiceAccount de K01. Se eligio `httpx` (ya es dependencia) y no el cliente oficial de Kubernetes para no sumar al
`uv.lock` del workspace un paquete que solo usan tres llamadas (decision registrada en la bitacora de U04-T04).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Literal, Protocol

import httpx
from vectra_common.errors import DependencyUnavailable

JobReason = Literal["failed", "deadline", "sin informe"]
REASONS: Final = ("failed", "deadline", "sin informe")

NAMESPACE: Final = "vectra-staging"
JOB_TTL_SECONDS: Final = 86400  # P-U4-03
ACTIVE_DEADLINE_SECONDS: Final = 7200  # BR-U4-05: 2 h
BACKOFF_LIMIT: Final = 0
K8S_TIMEOUT: Final = 5.0  # NFR-U4-25
JOB_SERVICE_ACCOUNT: Final = "model-validation-job"
Mode = Literal["validacion", "source_comparison"]


@dataclass(frozen=True)
class JobInfo:
    """Lo que el barrido necesita del Job: si fallo y si lo cancelo el `activeDeadlineSeconds`."""

    failed: bool = False
    deadline_exceeded: bool = False


class JobReader(Protocol):
    def get(self, job_name: str) -> JobInfo | None:
        """El Job, o `None` si ya no existe (el TTL lo borro)."""
        ...


class JobLauncher(JobReader, Protocol):
    def create(self, manifest: dict[str, Any]) -> None:
        """Crea el Job (K01 `create`). `DependencyUnavailable` si la API de Kubernetes no lo acepta."""
        ...

    def inference_service_exists(self, name: str) -> bool:
        """Si el `InferenceService` existe en `vectra-staging` (INF-U4-05)."""
        ...


def reason_of(info: JobInfo | None) -> JobReason:
    """`deadline` si el Job vencio por su plazo; `failed` si fallo; si no, o si ya no existe, `sin informe` (BR-U4-05)."""
    if info is not None and info.deadline_exceeded:
        return "deadline"
    if info is not None and info.failed:
        return "failed"
    return "sin informe"


# --- Manifiesto --------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class JobSpec:
    """Lo que recibe el `model-validation-job` (BR-U4-05): version, URIs del paquete, dataset y, en `source_comparison`, la
    fuente y la version `activo` contra la que se compara (la candidata es `model_version_id`)."""

    job_name: str
    mode: Mode
    run_id: str
    model_version_id: str
    image: str
    manifest_uri: str
    artifact_uri: str
    explainer_uri: str
    dataset_ref: str
    callback_url: str
    source_id: str | None = None
    baseline_version_id: str | None = None


def job_manifest(spec: JobSpec) -> dict[str, Any]:
    """El `batch/v1 Job` en `vectra-staging`: TTL, plazo de 2 h y `backoffLimit: 0` (BR-U4-05, P-U4-03)."""
    if (spec.mode == "source_comparison") != (spec.source_id is not None and spec.baseline_version_id is not None):
        raise ValueError("mode_fields_incoherent")  # mismo CHECK que `validation_runs` (domain-entities §2.1)
    env = {
        "VECTRA_JOB_MODE": spec.mode,
        "VECTRA_RUN_ID": spec.run_id,
        "VECTRA_MODEL_VERSION_ID": spec.model_version_id,
        "VECTRA_MANIFEST_URI": spec.manifest_uri,
        "VECTRA_ARTIFACT_URI": spec.artifact_uri,
        "VECTRA_EXPLAINER_URI": spec.explainer_uri,
        "VECTRA_DATASET_REF": spec.dataset_ref,
        "VECTRA_GOVERNANCE_URL": spec.callback_url,
    }
    if spec.source_id is not None and spec.baseline_version_id is not None:
        env["VECTRA_SOURCE_ID"] = spec.source_id
        env["VECTRA_BASELINE_VERSION_ID"] = spec.baseline_version_id
    labels = {
        "app.kubernetes.io/name": "model-validation-job",
        "app.kubernetes.io/managed-by": "governance-service",
        "vectra.io/run-id": spec.run_id,
        "vectra.io/mode": spec.mode.replace("_", "-"),
    }
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": spec.job_name, "namespace": NAMESPACE, "labels": labels},
        "spec": {
            "ttlSecondsAfterFinished": JOB_TTL_SECONDS,
            "activeDeadlineSeconds": ACTIVE_DEADLINE_SECONDS,
            "backoffLimit": BACKOFF_LIMIT,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "Never",
                    "serviceAccountName": JOB_SERVICE_ACCOUNT,
                    "priorityClassName": "vectra-low",
                    "securityContext": {"runAsNonRoot": True},
                    "containers": [
                        {
                            "name": "model-validation-job",
                            "image": spec.image,
                            "env": [{"name": name, "value": value} for name, value in env.items()],
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "resources": {
                                "requests": {"cpu": "250m", "memory": "512Mi"},
                                "limits": {"cpu": "1", "memory": "1Gi"},
                            },
                        }
                    ],
                },
            },
        },
    }


# --- Cliente de la API de Kubernetes ------------------------------------------------------------------------------------------


class KubernetesJobs:
    """K01 (`create` y `get` de `batch/jobs`) y `get` de `inferenceservices` en `vectra-staging`, con timeouts de 5 s."""

    def __init__(
        self,
        base_url: str,
        token: Callable[[], str],
        *,
        verify: bool | str = True,
        timeout: float = K8S_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._token = token
        self._client = httpx.Client(
            base_url=base_url, timeout=httpx.Timeout(timeout), verify=verify, transport=transport
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._client.request(method, path, headers={"Authorization": f"Bearer {self._token()}"}, **kwargs)
        except httpx.HTTPError as error:
            raise DependencyUnavailable() from error

    def create(self, manifest: dict[str, Any]) -> None:
        response = self._request("POST", f"/apis/batch/v1/namespaces/{NAMESPACE}/jobs", json=manifest)
        if response.status_code not in (200, 201, 409):  # 409: el Job ya existe (reintento del mismo `run_id`)
            raise DependencyUnavailable()

    def get(self, job_name: str) -> JobInfo | None:
        response = self._request("GET", f"/apis/batch/v1/namespaces/{NAMESPACE}/jobs/{job_name}")
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise DependencyUnavailable()
        conditions = response.json().get("status", {}).get("conditions") or []
        failed = [c for c in conditions if c.get("type") == "Failed" and c.get("status") == "True"]
        return JobInfo(
            failed=bool(failed), deadline_exceeded=any(c.get("reason") == "DeadlineExceeded" for c in failed)
        )

    def inference_service_exists(self, name: str) -> bool:
        response = self._request(
            "GET", f"/apis/serving.kserve.io/v1beta1/namespaces/{NAMESPACE}/inferenceservices/{name}"
        )
        if response.status_code == 404:
            return False
        if response.status_code != 200:
            raise DependencyUnavailable()
        return True

    def close(self) -> None:
        self._client.close()
