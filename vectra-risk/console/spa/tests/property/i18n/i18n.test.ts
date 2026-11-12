// PBT-U10-06 (BR-U10-17, 18; NFR-U10-53): para todo `code`, `reason` y valor de enumerado de U0 existe un texto, y ningun texto de los
// catalogos contiene una frase de la lista prohibida. Los arreglos se importan como MODULO de `@vectra/contracts` (no una lista escrita a
// mano): un arreglo nuevo en U0 rompe la prueba hasta que tenga textos. Perfil y semilla: tests/support/pbt.ts.
import * as contracts from "@vectra/contracts";
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import labels from "../../../src/i18n/labels.es.json";
import messages from "../../../src/i18n/messages.es.json";
import { allStrings, forbiddenPatterns, violations } from "../../support/phrases";
import { pbtOptions } from "../../support/pbt";

const arrays = Object.entries(contracts).filter(([, value]) => Array.isArray(value)) as unknown as [string, readonly string[]][];

/** Donde vive el texto de cada arreglo: `PROBLEM_CODES` y `PROBLEM_REASONS` en messages; los demas en labels. */
function catalogOf(name: string): Record<string, string> | undefined {
  if (name === "PROBLEM_CODES") return messages.code;
  if (name === "PROBLEM_REASONS") return messages.reason;
  return (labels as Record<string, Record<string, string>>)[name];
}

const pairs: [string, string][] = arrays.flatMap(([name, values]) => values.map((value): [string, string] => [name, value]));

describe("PBT-U10-06: i18n", () => {
  it("U0 exporta los 17 arreglos de enumerados (o mas)", () => {
    expect(arrays.length).toBeGreaterThanOrEqual(17);
    expect(arrays.map(([name]) => name)).toEqual(expect.arrayContaining(["PROBLEM_CODES", "PROBLEM_REASONS", "ROLES", "CASE_STATES", "SCOPES"]));
  });

  it("para todo valor de todo arreglo de U0 existe un texto no vacio", () => {
    fc.assert(
      fc.property(fc.constantFrom(...pairs), ([name, value]) => {
        const text = catalogOf(name)?.[value];
        expect(text, `${name}: ${value} no tiene texto`).toBeTypeOf("string");
        expect((text as string).trim().length, `${name}: ${value} tiene el texto vacio`).toBeGreaterThan(0);
      }),
      { ...pbtOptions("PBT-U10-06 (cobertura)"), numRuns: Math.max(pairs.length * 3, 300) },
    );
  });

  it("y los catalogos no tienen textos de mas: cada clave de un arreglo de U0 es un valor de ese arreglo", () => {
    const covered = new Set(arrays.map(([name]) => name));
    for (const [name, catalog] of Object.entries(labels)) {
      if (!covered.has(name)) continue; // los de P-4 (abajo) no estan en `contracts/ts`
      const values = (contracts as unknown as Record<string, readonly string[]>)[name] as readonly string[];
      expect(Object.keys(catalog).sort()).toEqual([...values].sort());
    }
    expect(Object.keys(messages.code).sort()).toEqual([...contracts.PROBLEM_CODES].sort());
    expect(Object.keys(messages.reason).sort()).toEqual([...contracts.PROBLEM_REASONS].sort());
  });

  it("ningun texto de los catalogos contiene una frase prohibida", () => {
    const patterns = forbiddenPatterns();
    const texts = [...allStrings(messages), ...allStrings(labels)];
    expect(texts.length).toBeGreaterThan(100);
    fc.assert(
      fc.property(fc.constantFrom(...texts), ([path, text]) => {
        expect(violations(text, patterns), `${path} contiene una frase prohibida`).toEqual([]);
      }),
      { ...pbtOptions("PBT-U10-06 (frases prohibidas)"), numRuns: Math.max(texts.length * 2, 300) },
    );
  });

  it("el detector de frases funciona: una frase de la lista, con tildes o mayusculas, se encuentra", () => {
    expect(violations("Este modelo es SIN SESGO.")).toEqual(["sin sesgo"]);
    expect(violations("Decisión Imparcial garantizada")).toEqual(["decisión imparcial"]);
    expect(violations("Muestra insuficiente")).toEqual([]);
  });
});
