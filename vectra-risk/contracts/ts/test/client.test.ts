import Decimal from "decimal.js";
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { fromDecimal, parseDecimal4, toDecimal } from "../src/decimal";
import { CASE_STATES, CREDIT_STATUSES, OUTCOMES, PROBLEM_CODES, PROBLEM_REASONS } from "../src/enums.generated";
import type { paths as consolePaths } from "../src/generated/console-bff";
import { parseRecommendResult, type FeatureValueWire, type RecommendResultWire } from "../src/wire";

const seed = Date.now() % 2147483647;
const options = { seed, numRuns: 500, verbose: 1 } as const;
console.log(`fast-check seed: ${seed}`);

const decimal4 = fc
  .bigInt({ min: -(10n ** 16n), max: 10n ** 16n })
  .map((n) => {
    const sign = n < 0n ? "-" : "";
    const digits = (n < 0n ? -n : n).toString().padStart(5, "0");
    return `${sign}${digits.slice(0, -4)}.${digits.slice(-4)}`;
  });

describe("Decimal4 (BR-U0-15, NFR-U0-45)", () => {
  it("round-trip como cadena sin perdida", () => {
    fc.assert(
      fc.property(decimal4, (text) => {
        const parsed = parseDecimal4(text);
        expect(JSON.parse(JSON.stringify({ v: parsed })).v).toBe(text);
        expect(new Decimal(fromDecimal(toDecimal(parsed))).equals(new Decimal(text))).toBe(true);
      }),
      options,
    );
  });

  it("rechaza otra escala", () => {
    for (const bad of ["0.5", "0.12345", "abc", ""]) {
      expect(() => parseDecimal4(bad)).toThrow();
    }
  });
});

describe("RecommendResult por kind", () => {
  const failClosed = fc.record({
    kind: fc.constant("fail_closed" as const),
    case_id: fc.uuid(),
    status: fc.constantFrom("en_sincronizacion" as const, "modelo_congelado" as const),
    cause: fc.string(),
    retryable: fc.boolean(),
    occurred_at: fc.constant("2026-10-31T12:00:00Z"),
  });
  const recommendation = fc.record({
    kind: fc.constant("recommendation" as const),
    case_id: fc.uuid(),
    score: decimal4,
    confidence: decimal4,
  });

  it("round-trip", () => {
    fc.assert(
      fc.property(fc.oneof(failClosed, recommendation), (value: RecommendResultWire) => {
        const back = parseRecommendResult(JSON.stringify(value));
        expect(back).toEqual(value);
        expect(back.kind).toBe(value.kind);
      }),
      options,
    );
  });

  it("rechaza un kind desconocido", () => {
    expect(() => parseRecommendResult('{"kind":"otro"}')).toThrow();
  });
});

describe("FeatureValue", () => {
  it("round-trip del objeto discriminado", () => {
    const value: fc.Arbitrary<FeatureValueWire> = fc.oneof(
      fc.record({ type: fc.constant("decimal" as const), value: decimal4 }),
      fc.record({ type: fc.constant("int" as const), value: fc.integer() }),
      fc.record({ type: fc.constant("category" as const), value: fc.string({ maxLength: 60 }) }),
    );
    fc.assert(
      fc.property(value, (v) => {
        expect(JSON.parse(JSON.stringify(v))).toEqual(v);
      }),
      options,
    );
  });
});

describe("catalogos generados", () => {
  it("exporta los valores de U0", () => {
    expect(PROBLEM_REASONS).toHaveLength(7);
    expect(CREDIT_STATUSES).toContain("no_integrado");
    expect(PROBLEM_CODES).toContain("deadline_exceeded");
  });
});

describe("Filtros del cliente generado (U10)", () => {
  it("los filtros de consulta tienen tipo", () => {
    const filter: NonNullable<consolePaths["/api/console/cases"]["get"]["parameters"]["query"]> = {
      state: ["listo"],
      page: 1,
    };
    expect(filter.page).toBe(1);
  });
  it("los enumerados del catalogo llegan a TypeScript", () => {
    expect(CASE_STATES.length).toBeGreaterThan(0);
    expect(OUTCOMES).toContain("favorable");
  });
});
