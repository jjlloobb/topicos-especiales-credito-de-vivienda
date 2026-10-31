// Generado por contracts/tools/codegen.py. No editar.

export const PROBLEM_CODES = ["malformed_request", "unsupported_media_type", "validation_error", "unauthenticated", "forbidden", "mfa_required", "not_found", "conflict_state", "payload_too_large", "rate_limited", "dependency_unavailable", "internal_error", "unprocessable_explanation", "deadline_exceeded"] as const;
export const PROBLEM_REASONS = ["decision_already_recorded", "transition_pending", "version_mismatch", "feature_dictionary_incomplete", "factuality_failed", "no_active_version", "active_version_frozen"] as const;
export const CREDIT_STATUSES = ["en_estudio", "aprobado", "desembolsado", "rechazado", "cancelado", "sin_credito", "no_disponible", "no_integrado"] as const;
export const FAIL_CLOSED_CAUSES = ["model_frozen", "serving_config_unavailable", "model_output_invalid", "timeout", "explainer_unavailable", "explainer_error", "version_mismatch", "feature_dictionary_incomplete", "factuality_failed", "registry_unavailable"] as const;
export const REASON_CODES = ["score_bajo_corte", "score_sobre_corte", "baja_confianza", "vis", "no_vis", "tasa_sobre_usura", "parametro_normativo_no_vigente"] as const;
export const ROLES = ["analista", "ingeniero_riesgo", "cro", "cumplimiento"] as const;
export const SCOPES = ["case:recommend", "scoring:explain", "governance:read-serving", "governance:freeze", "governance:validation-report", "governance:promotion", "bias:compare", "governance:read-dictionary", "governance:read-feature-spec", "registry:append:case", "registry:append:scoring", "registry:append:governance", "registry:read:explanation", "registry:read:monitoring", "registry:read:metrics", "intake:submit", "core:read-credit", "core:write-credit"] as const;
