// La validacion pura de la decision (BR-U10-09; frontend-components §3). Cuenta y decide **igual que el servidor** (PBT-U10-04: el cliente
// acepta <=> acepta `validate_decision` de U8, el oraculo de PBT-U8-03):
//  - BR-U0-36 (`check_justification`): en `se_aparta` y `resuelve_revision`, de 20 a 2000 caracteres tras quitar espacios en los bordes.
//    Python cuenta PUNTOS DE CODIGO (un emoji es 1; en JavaScript `.length` cuenta 2) y su `str.strip()` quita otros caracteres que
//    `String.prototype.trim` (p. ej. U+001C..U+001F y U+0085 si, U+FEFF no): se cuenta con `[...texto].length` y `pyStrip`.
//  - `DecisionIn` rechaza una justificacion de mas de 2000 caracteres ANTES de recortar, tambien en `sigue`.
//  - BR-U0-36/BR-U8-16 (`check_used_factors`, `validate_decision`): `ninguno` solo, de 1 a 20 factores, sin repetidos y dentro del `shap_vector`.
//  - BR-U0-35 (`decision_is_coherent`): la decision es coherente con la recomendacion y el resultado final elegido, o es un 409.
import type { UiKey } from "../../i18n";

export type Decision = "sigue" | "se_aparta" | "resuelve_revision";
export type FinalOutcome = "favorable" | "desfavorable";
export type Outcome = FinalOutcome | "revision_requerida";

export const NO_FACTORS = "ninguno";
export const JUSTIFICATION_MIN = 20;
export const JUSTIFICATION_MAX = 2000;
export const FACTORS_MAX = 20;

export interface DecisionDraft {
  readonly decision: Decision;
  readonly finalOutcome: FinalOutcome;
  readonly usedFactors: readonly string[];
  readonly justification: string;
}

export interface DecisionTarget {
  readonly outcome: Outcome;
  /** Los `feature_id` del `shap_vector` de la recomendacion. */
  readonly shapFeatureIds: readonly string[];
}

export type DecisionField = "justification" | "used_factors";

export interface FieldError {
  readonly field: DecisionField;
  readonly message: UiKey;
}

/** `422`: el cuerpo no cumple las reglas (con el campo y su texto); `409`: coherencia con el estado del caso (BR-U0-35). */
export type DecisionCheck =
  | { readonly status: "ok" }
  | { readonly status: 422; readonly errors: readonly FieldError[] }
  | { readonly status: 409 };

// `str.isspace()` de Python 3: los separadores Unicode de categoria Zs y los de tipo bidireccional WS, B o S.
const PY_SPACE = "\\t-\\r\\x1c-\\x20\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const PY_STRIP = new RegExp(`^[${PY_SPACE}]+|[${PY_SPACE}]+$`, "gu");

/** `str.strip()` de Python (no `trim()`: ver arriba). */
export function pyStrip(text: string): string {
  return text.replace(PY_STRIP, "");
}

/** `len(str)` de Python: puntos de codigo. */
export function pyLength(text: string): number {
  return [...text].length;
}

/** La longitud que cuenta el contador de la justificacion: sin espacios en los bordes. */
export function justificationLength(text: string): number {
  return pyLength(pyStrip(text));
}

export function isCoherent(decision: Decision, finalOutcome: FinalOutcome, outcome: Outcome): boolean {
  if (outcome === "revision_requerida") return decision === "resuelve_revision";
  if (decision === "sigue") return finalOutcome === outcome;
  if (decision === "se_aparta") return finalOutcome !== outcome;
  return false;
}

function factorErrors(used: readonly string[], known: readonly string[]): FieldError[] {
  if (used.length === 1 && used[0] === NO_FACTORS) return [];
  const errors: FieldError[] = [];
  const fail = (message: UiKey): void => {
    errors.push({ field: "used_factors", message });
  };
  if (used.includes(NO_FACTORS)) fail("decision_error_factors_none_alone");
  else if (used.length < 1 || used.length > FACTORS_MAX) fail("decision_error_factors_size");
  else if (new Set(used).size !== used.length) fail("decision_error_factors_repeated");
  if (used.some((factor) => factor !== NO_FACTORS && !known.includes(factor))) fail("decision_error_factors_unknown");
  return errors;
}

export function validateDecision(draft: DecisionDraft, target: DecisionTarget): DecisionCheck {
  const errors: FieldError[] = [];
  if (pyLength(draft.justification) > JUSTIFICATION_MAX) {
    errors.push({ field: "justification", message: "decision_error_justification_too_long" });
  } else if (draft.decision !== "sigue") {
    const length = justificationLength(draft.justification);
    if (length < JUSTIFICATION_MIN || length > JUSTIFICATION_MAX) {
      errors.push({ field: "justification", message: "decision_error_justification_length" });
    }
  }
  errors.push(...factorErrors(draft.usedFactors, target.shapFeatureIds));
  if (errors.length > 0) return { status: 422, errors };
  return isCoherent(draft.decision, draft.finalOutcome, target.outcome) ? { status: "ok" } : { status: 409 };
}
