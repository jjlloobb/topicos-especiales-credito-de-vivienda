// PBT-U10-04 (BR-U10-09; BR-U0-35, 36; BR-U8-16; US-108, US-502): la validacion del cliente acepta <=> acepta `validate_decision` de U8.
// P-2 (a): el oraculo de PBT-U8-03 (`case-management/tests/property/test_decision.py`: la tabla `COHERENT` y `oracle`) esta transcrito AQUI,
// aparte de la implementacion (`decision-validation.ts`), con los mismos generadores (largos 0, 1, 19, 20, 21, 1999, 2000 y 2001 con espacios en los
// bordes; subconjuntos, ajenos, `ninguno` solo, combinado y repetidos) y con los casos que Python y JavaScript cuentan distinto (un emoji, los
// espacios que `strip()` quita y `trim()` no, y los que `trim()` quita y `strip()` no). Una prueba lee el archivo de Python como texto y exige que las
// 18 filas de `COHERENT` sean las mismas. Perfil y semilla: tests/support/pbt.ts (`VECTRA_PBT_PROFILE`, `VECTRA_PBT_SEED`).
import fc from "fast-check";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { type Decision, type DecisionDraft, type FinalOutcome, type Outcome, pyLength, pyStrip, validateDecision } from "../../../../src/views/cases/decision-validation";
import { pbtOptions } from "../../../support/pbt";

const VECTRA_RISK = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..", "..", "..");
const PYTHON_ORACLE = resolve(VECTRA_RISK, "case-management", "tests", "property", "test_decision.py");

// BR-U0-35 como tabla (decision, final_outcome, outcome de la recomendacion) -> coherente: transcrita de PBT-U8-03.
const COHERENT: Record<string, boolean> = {
  "sigue|favorable|favorable": true,
  "sigue|favorable|desfavorable": false,
  "sigue|favorable|revision_requerida": false,
  "sigue|desfavorable|favorable": false,
  "sigue|desfavorable|desfavorable": true,
  "sigue|desfavorable|revision_requerida": false,
  "se_aparta|favorable|favorable": false,
  "se_aparta|favorable|desfavorable": true,
  "se_aparta|favorable|revision_requerida": false,
  "se_aparta|desfavorable|favorable": true,
  "se_aparta|desfavorable|desfavorable": false,
  "se_aparta|desfavorable|revision_requerida": false,
  "resuelve_revision|favorable|favorable": false,
  "resuelve_revision|favorable|desfavorable": false,
  "resuelve_revision|favorable|revision_requerida": true,
  "resuelve_revision|desfavorable|favorable": false,
  "resuelve_revision|desfavorable|desfavorable": false,
  "resuelve_revision|desfavorable|revision_requerida": true,
};

// `str.isspace()` de Python 3, calculado con Python (los 29 puntos de codigo). Es el dato de `strip()`; el oraculo lo usa sin expresiones regulares.
const PY_SPACE = new Set([
  0x9, 0xa, 0xb, 0xc, 0xd, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85, 0xa0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009,
  0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
]);

const SHAP_IDS = ["installment_to_income", "loan_to_value"];
const OUTSIDE = "zona_ajena";

/** `len(str.strip())` de Python, por puntos de codigo y sin `trim()`. */
function strippedLength(text: string): number {
  const points = Array.from(text, (char) => char.codePointAt(0) as number);
  let from = 0;
  let to = points.length;
  while (from < to && PY_SPACE.has(points[from] as number)) from += 1;
  while (to > from && PY_SPACE.has(points[to - 1] as number)) to -= 1;
  return to - from;
}

/** 422, 409 o `null` (acepta), sin usar nada de la implementacion (el `oracle` de PBT-U8-03). */
function oracle(raw: { decision: Decision; finalOutcome: FinalOutcome; usedFactors: readonly string[]; justification: string }, outcome: Outcome): 422 | 409 | null {
  const length = Array.from(raw.justification).length;
  if (length > 2000) return 422;
  const stripped = strippedLength(raw.justification);
  if (raw.decision !== "sigue" && !(stripped >= 20 && stripped <= 2000)) return 422;
  const used = raw.usedFactors;
  if (!(used.length === 1 && used[0] === "ninguno")) {
    if (used.includes("ninguno") || used.length < 1 || used.length > 20 || new Set(used).size !== used.length) return 422;
    if (used.some((factor) => !SHAP_IDS.includes(factor))) return 422;
  }
  return COHERENT[`${raw.decision}|${raw.finalOutcome}|${outcome}`] === true ? null : 409;
}

const clientStatus = (draft: DecisionDraft, outcome: Outcome): 422 | 409 | null => {
  const check = validateDecision(draft, { outcome, shapFeatureIds: SHAP_IDS });
  return check.status === "ok" ? null : check.status;
};

// Los generadores de PBT-U8-03 y los de Python-vs-JavaScript.
const PY_ONLY_BORDERS = ["\u001c", "\u001f", "\u0085", "　", " ", " ", " "]; // Python los quita; `trim()` no los quita todos
const JS_ONLY_BORDERS = ["﻿", "​", "᠎"]; // `trim()` quita U+FEFF; ni Python ni `trim()` quitan U+200B ni U+180E (en Python 3)
const PADDING = fc.array(fc.constantFrom(" ", " ", "\t", "\n", ...PY_ONLY_BORDERS, ...JS_ONLY_BORDERS), { maxLength: 4 }).map((chars) => chars.join(""));
const CORE_CHAR = fc.constantFrom("x", "x", "x", "é", "😀"); // el emoji: 1 en Python, 2 en `.length`
const justifications = fc
  .tuple(fc.oneof(fc.constantFrom(0, 1, 19, 20, 21, 1999, 2000), fc.integer({ min: 0, max: 2001 })), CORE_CHAR, PADDING, PADDING)
  .map(([length, char, left, right]) => left + char.repeat(length) + right);
const shapSubsets = fc.uniqueArray(fc.constantFrom(...SHAP_IDS), { maxLength: 3 });
const factors = fc.oneof(
  shapSubsets,
  shapSubsets.map((xs) => [...xs, OUTSIDE]),
  fc.constant([OUTSIDE]),
  fc.constant(["ninguno"]),
  shapSubsets.map((xs) => ["ninguno", ...xs.slice(0, 1)]),
  fc.constant([]),
  fc.array(fc.constantFrom(...SHAP_IDS), { minLength: 2, maxLength: 3 }).map((xs) => [xs[0] as string, ...xs]),
  fc.uniqueArray(fc.string({ minLength: 1, maxLength: 6 }), { minLength: 21, maxLength: 22 }), // mas de 20 factores
);

describe("PBT-U10-04: la validacion de la decision del cliente coincide con el oraculo de PBT-U8-03", () => {
  it("acepta <=> el oraculo acepta; y los codigos 422 y 409 coinciden", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<Decision>("sigue", "se_aparta", "resuelve_revision"),
        fc.constantFrom<FinalOutcome>("favorable", "desfavorable"),
        fc.constantFrom<Outcome>("favorable", "desfavorable", "revision_requerida"),
        factors,
        justifications,
        (decision, finalOutcome, outcome, usedFactors, justification) => {
          const raw = { decision, finalOutcome, usedFactors, justification };
          expect(clientStatus(raw, outcome)).toBe(oracle(raw, outcome));
        },
      ),
      pbtOptions("PBT-U10-04"),
    );
  });

  it("la tabla COHERENT transcrita tiene las 18 filas de PBT-U8-03, y son las mismas que las del archivo de Python", () => {
    expect(Object.keys(COHERENT)).toHaveLength(18);
    const text = readFileSync(PYTHON_ORACLE, "utf-8");
    const rows = [...text.matchAll(/\("(\w+)", "(\w+)", "(\w+)"\): (True|False)/g)].map((m) => [`${m[1]}|${m[2]}|${m[3]}`, m[4] === "True"] as const);
    expect(rows).toHaveLength(18);
    expect(Object.fromEntries(rows)).toEqual(COHERENT);
    expect(text).toContain("20 <= len(just.strip()) <= 2000"); // el oraculo de Python sigue siendo el que se transcribio
    expect(text).toContain("len(just) > 2000");
  });

  it("`pyStrip` quita exactamente los caracteres de `str.isspace()` de Python (los 29), y `trim()` no es lo mismo", () => {
    for (let point = 0; point < 0x10000; point += 1) {
      if (point >= 0xd800 && point <= 0xdfff) continue; // sustitutos sueltos: no son texto
      const char = String.fromCodePoint(point);
      expect(pyStrip(`a${char}`) === "a", `U+${point.toString(16)}`).toBe(PY_SPACE.has(point));
    }
    expect("\u001f ".trim()).toBe("\u001f"); // `trim()` no quita U+001F: por eso no se usa
    expect(pyStrip("\u001f ")).toBe("");
    expect("﻿a".trim()).toBe("a"); // y quita U+FEFF, que `strip()` no quita
    expect(pyStrip("﻿a")).toBe("﻿a");
  });

  it("`pyLength` cuenta puntos de codigo, no unidades UTF-16", () => {
    expect(pyLength("😀")).toBe(1);
    expect("😀".length).toBe(2);
    expect(pyLength("a😀b")).toBe(3);
  });
});
