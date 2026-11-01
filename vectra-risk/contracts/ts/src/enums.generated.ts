// Generado por contracts/tools/codegen.py. No editar.

export const CASE_STATES = ["en_evaluacion", "listo", "en_sincronizacion", "no_disponible", "modelo_congelado", "decidido", "vencido"] as const;
export const CREDIT_STATUSES = ["en_estudio", "aprobado", "desembolsado", "rechazado", "cancelado", "sin_credito", "no_disponible", "no_integrado"] as const;
export const DECISIONS = ["sigue", "se_aparta", "resuelve_revision"] as const;
export const ENTRY_TYPES = ["recommendation", "fail_closed", "human_decision", "explanation_view", "model_event", "policy_event", "data_source_event", "freeze", "frozen_resolution", "genesis", "checkpoint"] as const;
export const EXPLAINER_ERRORS = ["timeout", "unavailable", "error", "version_mismatch", "factuality_failed", "feature_dictionary_incomplete"] as const;
export const FAIL_CLOSED_CAUSES = ["model_frozen", "serving_config_unavailable", "model_output_invalid", "timeout", "explainer_unavailable", "explainer_error", "version_mismatch", "feature_dictionary_incomplete", "factuality_failed", "registry_unavailable"] as const;
export const FINAL_OUTCOMES = ["favorable", "desfavorable"] as const;
export const LOCAL_CAUSES = ["serving_config_unavailable", "scoring_unreachable", "scoring_rejected"] as const;
export const LOG_EVENTS = ["authz.denied", "recommendation.fail_closed", "applicant_summary.generated", "case.viewed", "case.retry_requested", "evaluation.result_discarded", "disparity.viewed", "freeze_context.viewed", "console.client_error", "registry.idempotency_conflict"] as const;
export const OUTCOMES = ["favorable", "desfavorable", "revision_requerida"] as const;
export const PROBLEM_CODES = ["malformed_request", "unsupported_media_type", "validation_error", "unauthenticated", "forbidden", "mfa_required", "not_found", "conflict_state", "payload_too_large", "rate_limited", "dependency_unavailable", "internal_error", "unprocessable_explanation", "deadline_exceeded"] as const;
export const PROBLEM_REASONS = ["decision_already_recorded", "transition_pending", "version_mismatch", "feature_dictionary_incomplete", "factuality_failed", "no_active_version", "active_version_frozen"] as const;
export const REASON_CODES = ["score_bajo_corte", "score_sobre_corte", "baja_confianza", "vis", "no_vis", "tasa_sobre_usura", "parametro_normativo_no_vigente"] as const;
export const REGISTRY_ERRORS = ["unavailable"] as const;
export const ROLES = ["analista", "ingeniero_riesgo", "cro", "cumplimiento"] as const;
export const SCOPES = ["case:recommend", "scoring:explain", "governance:read-serving", "governance:freeze", "governance:validation-report", "governance:promotion", "bias:compare", "governance:read-dictionary", "governance:read-feature-spec", "registry:append:case", "registry:append:scoring", "registry:append:governance", "registry:read:explanation", "registry:read:monitoring", "registry:read:metrics", "intake:submit", "core:read-credit", "core:write-credit"] as const;
export const SERVING_STATES = ["activo", "congelado", "no_disponible"] as const;
