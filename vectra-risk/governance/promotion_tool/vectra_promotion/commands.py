"""Las operaciones de `promotion-tool` (US-204, US-208). `retire_inference_service` no existe: esta diferido por la demo."""

from vectra_contracts.models.governance import ModelVersion

from vectra_promotion import values
from vectra_promotion.api import GovernanceApi
from vectra_promotion.errors import PromotionError
from vectra_promotion.gitops import PromotionRepo


def list_promotable(api: GovernanceApi) -> list[ModelVersion]:
    return api.list_promotable()


def create_promotion_pr(api: GovernanceApi, repo: PromotionRepo, model_version_id: str) -> str:
    """PR 1: agrega la version `aprobado` con los minimos de produccion; no toca al activo (BR-U4-09)."""
    candidate = next((m for m in api.list_promotable() if m.model_version_id == model_version_id), None)
    if candidate is None:
        raise PromotionError("model_not_promotable")
    entries = values.promote(repo.current(), model_version_id, values.storage_uri(candidate.manifest_uri))
    return repo.open_pr("promocion", model_version_id, entries, "feat(model-serving): promover")


def post_activation_pr(repo: PromotionRepo, previous_version_id: str) -> str:
    """PR 2, despues de `mark_active`: la version anterior baja a 1 replica por componente (`prod` -> `inactive`)."""
    entries = values.demote(repo.current(), previous_version_id)
    return repo.open_pr("post-activacion", previous_version_id, entries, "chore(model-serving): bajar a inactivo")


def rollback_pr(repo: PromotionRepo, model_version_id: str) -> str:
    """PR de rollback, antes de `mark_active`: la version `inactivo` recupera los minimos de produccion (`inactive` -> `prod`)."""
    entries = values.restore(repo.current(), model_version_id)
    return repo.open_pr("rollback", model_version_id, entries, "fix(model-serving): restaurar minimos de produccion de")


def mark_active(api: GovernanceApi, repo: PromotionRepo, model_version_id: str, evidence: str) -> str:
    """`POST /v1/models/{id}/activation`. Exige que la version ya este declarada en `prod` en los values del entorno.

    Governance fija `inference_service` en `serving-config` en la misma transaccion (BR-U4-08); aqui se deja en la evidencia el
    `isvc-<8 hex>` que la herramienta espera.
    """
    if not values.has_entry(repo.current(), model_version_id, "prod"):
        raise PromotionError("not_promoted_in_values")
    isvc = values.isvc_name(model_version_id)
    api.mark_active(model_version_id, f"{evidence} [inference_service={isvc}]"[:500])
    return isvc
