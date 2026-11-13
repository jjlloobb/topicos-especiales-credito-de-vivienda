// BR-U10-09; BR-U0-35, 36; BR-U8-16: ejemplos de la validacion pura de la decision (la propiedad es `tests/property/views/cases/decision.test.ts`).
import { describe, expect, it } from "vitest";
import {
  type DecisionDraft,
  isCoherent,
  justificationLength,
  validateDecision,
} from "../../../../src/views/cases/decision-validation";

const TARGET = { outcome: "favorable", shapFeatureIds: ["installment_to_income", "loan_to_value"] } as const;
const GOOD: DecisionDraft = { decision: "sigue", finalOutcome: "favorable", usedFactors: ["ninguno"], justification: "" };
const LONG = "x".repeat(20);
const check = (over: Partial<DecisionDraft>, target: Parameters<typeof validateDecision>[1] = TARGET) => validateDecision({ ...GOOD, ...over }, target);
const messages = (over: Partial<DecisionDraft>): string[] => {
  const result = check(over);
  return result.status === 422 ? result.errors.map((error) => error.message) : [];
};

describe("validateDecision", () => {
  it("una decision `sigue` coherente, con «Ninguno» y sin justificacion, se acepta", () => {
    expect(check({})).toEqual({ status: "ok" });
  });

  it("la justificacion de `se_aparta` y `resuelve_revision` pide de 20 a 2000 caracteres sin espacios en los bordes", () => {
    const apart = { decision: "se_aparta", finalOutcome: "desfavorable" } as const;
    expect(messages({ ...apart, justification: "x".repeat(19) })).toEqual(["decision_error_justification_length"]);
    expect(messages({ ...apart, justification: `   ${"x".repeat(19)}   ` })).toEqual(["decision_error_justification_length"]); // los bordes no cuentan
    expect(check({ ...apart, justification: LONG })).toEqual({ status: "ok" });
    expect(check({ ...apart, justification: `  ${"x".repeat(2000)}  ` }).status).toBe(422); // 2004 > 2000 antes de recortar
    expect(check({ ...apart, justification: "x".repeat(2000) })).toEqual({ status: "ok" });
    expect(check({ decision: "resuelve_revision", finalOutcome: "favorable", justification: "corta" }, { ...TARGET, outcome: "revision_requerida" }).status).toBe(422);
  });

  it("mas de 2000 caracteres se rechaza aunque la decision sea `sigue` (el servidor lo rechaza antes de recortar)", () => {
    expect(messages({ justification: "x".repeat(2001) })).toEqual(["decision_error_justification_too_long"]);
    expect(check({ justification: "x".repeat(2000) })).toEqual({ status: "ok" });
  });

  it("cuenta como el servidor: puntos de codigo, y los espacios que quita `str.strip()`", () => {
    expect(justificationLength("😀".repeat(20))).toBe(20); // `.length` diria 40
    expect(check({ decision: "se_aparta", finalOutcome: "desfavorable", justification: "😀".repeat(20) })).toEqual({ status: "ok" });
    expect(justificationLength(`　\u0085${LONG}\u001f`)).toBe(20);
    expect(justificationLength(`﻿${LONG}`)).toBe(21); // U+FEFF no es espacio para Python
  });

  it("los factores: `ninguno` solo, de 1 a 20, sin repetidos y dentro del `shap_vector`", () => {
    expect(messages({ usedFactors: [] })).toEqual(["decision_error_factors_size"]);
    expect(messages({ usedFactors: ["ninguno", "loan_to_value"] })).toEqual(["decision_error_factors_none_alone"]);
    expect(messages({ usedFactors: ["loan_to_value", "loan_to_value"] })).toEqual(["decision_error_factors_repeated"]);
    expect(messages({ usedFactors: ["otro"] })).toEqual(["decision_error_factors_unknown"]);
    expect(messages({ usedFactors: Array.from({ length: 21 }, (_, i) => `f${i}`) })).toContain("decision_error_factors_size");
    expect(check({ usedFactors: ["loan_to_value"] })).toEqual({ status: "ok" });
  });

  it("la coherencia con la recomendacion (BR-U0-35) es un 409 y gana la 422 si hay ambas", () => {
    expect(check({ decision: "sigue", finalOutcome: "desfavorable" })).toEqual({ status: 409 });
    expect(check({ decision: "se_aparta", finalOutcome: "favorable", justification: LONG })).toEqual({ status: 409 });
    expect(check({ decision: "sigue", finalOutcome: "desfavorable", usedFactors: [] }).status).toBe(422);
  });

  it("isCoherent: `revision_requerida` solo se resuelve con `resuelve_revision`, con cualquier resultado final", () => {
    expect(isCoherent("resuelve_revision", "favorable", "revision_requerida")).toBe(true);
    expect(isCoherent("resuelve_revision", "desfavorable", "revision_requerida")).toBe(true);
    expect(isCoherent("sigue", "favorable", "revision_requerida")).toBe(false);
    expect(isCoherent("resuelve_revision", "favorable", "favorable")).toBe(false);
  });
});
