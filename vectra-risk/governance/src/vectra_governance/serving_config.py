"""Composicion y etag de serving-config (BR-U4-11, 14). Pura, sin E/S (Bloque C, Paso 5).

`compose` arma el `ServingConfig` de U0 (domain-entities §5) a partir de la version servible, la politica `activa`, el
momento de la ultima transicion confirmada y el instante de hoy (parametro: el modulo no lee el reloj). El `etag` es el
SHA-256 en hex del JSON canonico (JCS, `vectra_contracts.canonical`) de **todos** los campos salvo el propio `etag`,
incluido `inference_service` (`bias_monitoring_age_s` se quito, U9 FD 2026-10-08).

U04-T09: copia `cutoff`, `low_confidence_threshold` y `channel_rules` de la politica `activa`.

P-U4-07: la salida tiene solo los campos del tipo de U0 (`ServingConfig`); este modulo no agrega ninguno.

Eleccion: el tipo de U0 exige una version servible (`activo` o `congelado`) y una politica `activa`. Si falta alguna,
`compose` devuelve `None` y no inventa un `ServingConfig`. Que responde la API en ese caso es de los Pasos 9 y 10.
"""

from datetime import datetime

from vectra_contracts.canonical import sha256_hex
from vectra_contracts.models.governance import ModelVersion, PolicyVersion, ServingConfig

from vectra_governance.policy import normative_current

_SERVABLE = ("activo", "congelado")


def compute_etag(config: ServingConfig) -> str:
    """SHA-256 hex del contenido canonico (JCS) de todos los campos de `config` menos `etag`."""
    return sha256_hex(config.model_dump(mode="json", exclude={"etag"}))


def compose(
    model: ModelVersion | None, policy: PolicyVersion | None, effective_from: datetime, now: datetime
) -> ServingConfig | None:
    """El `serving-config` vigente, o `None` si no hay version servible o politica `activa`."""
    if model is None or model.state not in _SERVABLE or policy is None or policy.state != "activa":
        return None
    draft = ServingConfig(
        model_version_id=model.model_version_id,
        state=model.state,  # type: ignore[arg-type]
        policy_version_id=policy.policy_version_id,
        cutoff=policy.cutoff,
        low_confidence_threshold=policy.low_confidence_threshold,
        channel_rules=policy.channel_rules,
        feature_dictionary_version=model.feature_dictionary_version,
        effective_from=effective_from,
        inference_service=model.inference_service,
        etag="",
        normative_current=normative_current(policy, now),
    )
    return draft.model_copy(update={"etag": compute_etag(draft)})
