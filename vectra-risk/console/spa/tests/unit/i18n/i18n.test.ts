// BR-U10-17: textos y formatos. Los enumerados que NO estan en los arreglos de `contracts/ts` (P-4 (a) de U10-T03) tienen su texto:
// una prueba de ejemplo lee sus valores de `contracts/openapi/console-bff.yaml`.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";
import { fill, formatDate, formatDecimal, label, notice, problemText, ui } from "../../../src/i18n";
import labels from "../../../src/i18n/labels.es.json";
import messages from "../../../src/i18n/messages.es.json";

const VECTRA_RISK = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..", "..");
type Schemas = Record<string, { properties?: Record<string, { enum?: string[] }> }>;
const schemas = (parse(readFileSync(resolve(VECTRA_RISK, "contracts", "openapi", "console-bff.yaml"), "utf-8")) as { components: { schemas: Schemas } })
  .components.schemas;
const enumOf = (schema: string, property: string): string[] => schemas[schema]?.properties?.[property]?.enum ?? [];

describe("los enumerados de P-4 tienen su texto (leidos de console-bff.yaml)", () => {
  it.each([
    ["MODEL_STATES", enumOf("ModelVersion", "state")],
    ["RESOLUTION_ACTIONS", enumOf("Resolution", "action")],
    ["CELL_STATUSES", enumOf("CellResult", "status")],
    ["ATTRIBUTES", enumOf("AttributeResult", "attribute")],
    ["BANDS", enumOf("CellResult", "band")],
  ])("%s", (group, values) => {
    expect(values.length).toBeGreaterThan(0);
    expect(Object.keys((labels as Record<string, object>)[group] as object).sort()).toEqual([...values].sort());
  });
});

describe("problemText", () => {
  it("un code conocido da su mensaje", () => {
    expect(problemText({ code: "forbidden" })).toBe(messages.code.forbidden);
  });

  it("un reason conocido manda sobre el code", () => {
    expect(problemText({ code: "conflict_state", reason: "decision_already_recorded" })).toBe(
      "Otra persona ya registró la decisión de este caso. Se muestra la decisión registrada.",
    );
  });

  it("un reason desconocido cae al mensaje del code", () => {
    expect(problemText({ code: "not_found", reason: "otro" })).toBe(messages.code.not_found);
    expect(problemText({ code: "not_found", reason: null })).toBe(messages.code.not_found);
  });

  it("un code desconocido da el mensaje generico con el correlation_id", () => {
    const text = problemText({ code: "algo_nuevo", correlation_id: "f".repeat(32) });
    expect(text).toContain("f".repeat(32));
    expect(text).toBe(fill(messages.generic, { correlation_id: "f".repeat(32) }));
    expect(problemText({ code: "algo_nuevo" })).not.toContain("{");
  });

  it("nunca muestra el detail del servidor", () => {
    const problem = { code: "internal_error", detail: "Traceback (most recent call last)" } as { code: string };
    expect(problemText(problem)).not.toContain("Traceback");
  });
});

describe("textos y avisos", () => {
  it("fill sustituye {nombre} y deja vacio el que falta", () => {
    expect(fill("a {x} b {y}", { x: "1" })).toBe("a 1 b ");
    expect(fill("sin parametros")).toBe("sin parametros");
  });
  it("ui, notice y label", () => {
    expect(ui("verify_and_confirm")).toBe("Verificar y confirmar");
    expect(ui("session_role", { role: "Analista" })).toBe("Rol: Analista");
    expect(notice("credit_not_integrated")).toBe("Estado de crédito no integrado");
    expect(notice("credit_unavailable")).toBe("Estado de crédito no disponible por ahora");
    expect(label("ROLES", "cro")).toBe("Director de riesgo (CRO)");
  });
  it("los avisos de negocio de BR-U10-17 existen", () => {
    expect(Object.keys(messages.notice).sort()).toEqual(
      ["case_anonymized", "credit_not_integrated", "credit_unavailable", "low_confidence", "model_frozen_after_recommendation", "revision_requerida"].sort(),
    );
  });
  it("label de un valor sin texto no rompe", () => {
    expect(label("ROLES", "inexistente" as never)).toBe(messages.ui.unknown_value);
  });
});

describe("formatos es-CO con Intl", () => {
  it("un Decimal4 como cadena se formatea sin pasar por Number: coma decimal y 4 decimales", () => {
    expect(formatDecimal("0.1234")).toBe("0,1234");
    expect(formatDecimal("1234.5", 2)).toBe("1.234,50");
    expect(formatDecimal("-0.0001")).toBe("-0,0001");
  });
  it("conserva los digitos que un number de doble precision perderia", () => {
    expect(formatDecimal("12345678901234567.1234")).toBe("12.345.678.901.234.567,1234");
  });
  it("rechaza lo que no es un decimal", () => {
    for (const bad of ["", "abc", "1e5", "1,5", "--1", "1."]) expect(() => formatDecimal(bad)).toThrow(RangeError);
  });
  it("la fecha sale en la zona de Bogota", () => {
    // 20:30 UTC = 15:30 en Bogota (UTC-5, sin horario de verano); dia/mes/anio de es-CO
    expect(formatDate("2026-11-12T20:30:00Z")).toMatch(/12\/11\/2026.*3:30/);
  });
});
