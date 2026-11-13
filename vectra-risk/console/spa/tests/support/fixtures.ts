// Cuerpos de la API del BFF para las pruebas de las vistas (U10-T04): la forma de `contracts/ts` (`console-bff.d.ts`), con valores de ejemplo.
import type { CaseDetail, CaseSummary, FreezeRecord, FreezeSummary, ModelVersion, ModelVersionDetail } from "../../src/api/endpoints";

export const CASE_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
export const OTHER_CASE_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7";
export const FEATURES = ["installment_to_income", "loan_to_value"] as const;
const TS = "2026-11-12T15:00:00Z";

export function summary(over: Partial<CaseSummary> = {}): CaseSummary {
  return { case_id: CASE_ID, state: "listo", channel: "web", created_at: TS, applicant_display: "A. G.", outcome: null, score: null, ...over };
}

type Recommendation = NonNullable<CaseDetail["recommendation"]>;

export function recommendation(over: Partial<Recommendation> = {}): Recommendation {
  return {
    kind: "recommendation",
    case_id: CASE_ID,
    outcome: "favorable",
    score: "0.7312",
    confidence: "0.8800",
    reasons: ["score_sobre_corte"],
    model_version_id: "mv-activo",
    policy_version_id: "pv-1",
    feature_vector_hash: "a".repeat(64),
    evaluated_at: TS,
    registry_entry_id: "7",
    explanation: {
      model_version_id: "mv-activo",
      method: "shap",
      base_value: "0.0500",
      narrative: "La relación cuota/ingreso aumenta el riesgo.",
      narrative_generator: "template:v1",
      feature_dictionary_version: "d1",
      posthoc_notice: "Aproximación posterior.",
      factuality_check: "passed",
      shap_vector: FEATURES.map((feature_id) => ({ feature_id, value: { type: "decimal" as const, value: "0.3000" }, contribution: "0.1200" })),
    },
    ...over,
  } as Recommendation;
}

export function detail(over: Partial<CaseDetail> = {}): CaseDetail {
  return {
    ...summary(),
    application: {
      broker_id: null,
      channel: "web",
      department_code: "11",
      employment_months: 36,
      employment_type: "asalariado",
      free_text: null,
      max_days_past_due_12m: 0,
      monthly_income: 8_000_000,
      monthly_obligations: 1_200_000,
      other_income: 0,
      property_condition: "nueva",
      property_value: 320_000_000,
      proposed_rate_ea: "0.1150",
      requested_amount: 200_000_000,
      term_months: 240,
    },
    attempts: 0,
    anonymized: false,
    credit_status: null,
    decision: null,
    identifiers: null,
    last_cause: null,
    model_frozen_after_recommendation: false,
    outcome: "favorable",
    recommendation: recommendation(),
    recommendation_entry_id: "7",
    score: "0.7312",
    ...over,
  } as CaseDetail;
}

export function page<T>(items: T[]): { items: T[]; page: number; total: number; next_seq_after: null } {
  return { items, page: 1, total: items.length, next_seq_after: null };
}

export function model(id = "mv-activo", state: ModelVersion["state"] = "activo"): ModelVersion {
  return {
    model_version_id: id,
    state,
    artifact_uri: "s3://m/a.onnx",
    artifact_format: "onnx",
    artifact_sha256: "a".repeat(64),
    explainer_uri: "s3://m/e.bin",
    explainer_sha256: "a".repeat(64),
    inference_service: "isvc-1",
    manifest_uri: "s3://m/m.json",
    manifest_sha256: "a".repeat(64),
    feature_dictionary_version: "fd-1",
    data_sources: [],
    registered_by: "user-2",
    investigation: false,
    created_at: TS,
    updated_at: TS,
    approved_by: null,
    archived_at: null,
    archived_uri: null,
    source_candidate_for: null,
  };
}

export function modelDetail(over: Partial<ModelVersionDetail> = {}): ModelVersionDetail {
  return { ...model(), validation_report: null, ...over };
}

export const CELL_OK = { group: "andina", band: "20_30", n: 120, rate: "0.6200", status: "suficiente" } as const;
export const CELL_LOW = { group: "caribe", band: "20_30", n: 4, rate: null, status: "muestra_insuficiente" } as const;

export function disparity(version = "mv-congelado") {
  return {
    population: "modelo" as const,
    model_version_id: version,
    window_from: "2026-10-13",
    window_to: "2026-11-11",
    attributes: [
      {
        attribute: "region" as const,
        cells: [CELL_OK, CELL_LOW],
        bands: [{ band: "20_30" as const, difference: "0.0800", extreme_pair: ["andina", "caribe"], ci_95: null, n_band: 124 }],
        aggregate: "0.6000",
        aggregate_ci_95: null,
        population_difference: null,
        population_difference_partial: false,
      },
    ],
    model_aggregate: null,
    trigger_attribute: null,
    departure_rates: null,
  };
}

export function freezeSummary(over: Partial<FreezeSummary> = {}): FreezeSummary {
  return { freeze_id: "freeze-mv-congelado", model_version_id: "mv-congelado", frozen_at: TS, trigger_attribute: "region", model_aggregate: "0.6000", resolution: null, ...over };
}

export function freezeRecord(over: { before?: "sin_datos" | ReturnType<typeof disparity>; last7?: "sin_datos" | ReturnType<typeof disparity>; resolutions?: FreezeRecord["resolutions"] } = {}): FreezeRecord {
  return {
    freeze_id: "freeze-mv-congelado",
    model_version_id: "mv-congelado",
    frozen_at: TS,
    resolutions: over.resolutions ?? [],
    context_package: {
      model_version_id: "mv-congelado",
      computed_at: TS,
      threshold_pp: "5.0000",
      n_min: 30,
      window_days: 30,
      schedule: "2,17,32,47 * * * *",
      stale_after_s: 3600,
      library_version: "1.0.0",
      window_start: "2026-10-13",
      before: over.before ?? disparity(),
      after: disparity(),
      last_7_days: over.last7 ?? disparity(),
      trigger_attribute: "region",
      implicated: [{ attribute: "region", freeze_lower_limit: "0.0500", bands: [{ band: "20_30", difference: "0.0800", extreme_pair: ["andina", "caribe"] }] }, { raro: true }],
      affected_volume: { total: 124, favorable: 80 },
      truncated: false,
      data_sources: [{ ds_id: "ds-1", name: "Buró alterno" }, "otra cosa"],
      initial_disparity: { attributes: disparity().attributes, model_aggregate: null, n_min: null, rule_met: null, threshold_pp: null, trigger_attribute: null },
    },
  } as FreezeRecord;
}
