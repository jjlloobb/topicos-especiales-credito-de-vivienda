"""Configuracion del Job desde variables de entorno. Las `VECTRA_*` de `job_manifest` (K01) y las de las credenciales del chart."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from vectra_validation.errors import ValidationJobError

DEFAULT_AUC_TARGET: Final = "0.8500"  # domain-entities §2.2: 0,85 [INTERNO]
DEFAULT_CUTOFF: Final = "0.0800"  # `cutoff` de la politica de referencia de U5; el lanzador lo fija con la politica activa
DEFAULT_N_MIN: Final = 30  # BR-U9-13
DEFAULT_THRESHOLD_PP: Final = "5.0000"  # BR-U9-13


@dataclass(frozen=True)
class JobConfig:
    mode: str
    run_id: str
    model_version_id: str
    manifest_uri: str
    artifact_uri: str
    explainer_uri: str
    dataset_ref: str
    governance_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    token_url: str
    client_id: str
    key_path: str
    key_id: str | None
    audience: str
    evaluated_on: str | None
    auc_target: str = DEFAULT_AUC_TARGET
    cutoff: str = DEFAULT_CUTOFF
    n_min: int = DEFAULT_N_MIN
    threshold_pp: str = DEFAULT_THRESHOLD_PP
    scope: str = "governance:validation-report"


def _need(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise ValidationJobError(f"missing_env:{name}")
    return value


def from_env(env: Mapping[str, str]) -> JobConfig:
    """`missing_env:<NOMBRE>` si falta una obligatoria (nunca imprime su valor)."""
    return JobConfig(
        mode=_need(env, "VECTRA_JOB_MODE"),
        run_id=_need(env, "VECTRA_RUN_ID"),
        model_version_id=_need(env, "VECTRA_MODEL_VERSION_ID"),
        manifest_uri=_need(env, "VECTRA_MANIFEST_URI"),
        artifact_uri=_need(env, "VECTRA_ARTIFACT_URI"),
        explainer_uri=_need(env, "VECTRA_EXPLAINER_URI"),
        dataset_ref=_need(env, "VECTRA_DATASET_REF"),
        governance_url=_need(env, "VECTRA_GOVERNANCE_URL"),
        s3_endpoint=_need(env, "VECTRA_S3_ENDPOINT"),
        s3_access_key=_need(env, "VECTRA_S3_ACCESS_KEY"),
        s3_secret_key=_need(env, "VECTRA_S3_SECRET_KEY"),
        token_url=_need(env, "VECTRA_TOKEN_URL"),
        client_id=env.get("VECTRA_CLIENT_ID", "model-validation-job"),
        key_path=_need(env, "VECTRA_CLIENT_KEY_PATH"),
        key_id=env.get("VECTRA_CLIENT_KEY_ID") or None,
        audience=env.get("VECTRA_TOKEN_AUDIENCE", "governance-service"),
        evaluated_on=env.get("VECTRA_EVALUATED_ON") or None,  # sin valor, `main` usa el reloj (solo el punto de entrada lo lee)
        auc_target=env.get("VECTRA_AUC_TARGET", DEFAULT_AUC_TARGET),
        cutoff=env.get("VECTRA_CUTOFF", DEFAULT_CUTOFF),
        n_min=int(env.get("VECTRA_N_MIN", str(DEFAULT_N_MIN))),
        threshold_pp=env.get("VECTRA_THRESHOLD_PP", DEFAULT_THRESHOLD_PP),
    )
