/** Lectura del `RecommendResult` por su discriminador `kind` (BR-U0-06). */
export interface RecommendationWire {
  kind: "recommendation";
  case_id: string;
  score: string;
  confidence: string;
  [key: string]: unknown;
}

export interface FailClosedWire {
  kind: "fail_closed";
  case_id: string;
  status: "en_sincronizacion" | "modelo_congelado";
  cause: string;
  retryable: boolean;
  occurred_at: string;
}

export type RecommendResultWire = RecommendationWire | FailClosedWire;

export function parseRecommendResult(text: string): RecommendResultWire {
  const value = JSON.parse(text) as { kind?: unknown };
  if (value.kind !== "recommendation" && value.kind !== "fail_closed") {
    throw new Error("kind desconocido");
  }
  return value as RecommendResultWire;
}

export type FeatureValueWire =
  | { type: "decimal"; value: string }
  | { type: "int"; value: number }
  | { type: "category"; value: string };
