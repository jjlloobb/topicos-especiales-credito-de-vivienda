// CA-3 (Paso 1): los fixtures que deben fallar fallan en ESLint, y `tsconfig.json` es estricto.
// U10-T03 (CA-7): los casos de las candidatas de U10-T01 (F-01 `jsx-no-literals` con atributos; F-03 `parseFloat`, `Number.parseFloat`,
// `sessionStorage` global, `globalThis.localStorage`) y el caso lento de U10-T02 (ESLint en frio pasaba de los 5 s de vitest).
// NFR-U10-43 (sin `dangerouslySetInnerHTML`), NFR-U10-53 (todo texto visible sale del catalogo i18n) y NFR-U10-64 (sin `Number(` ni
// `parseFloat` sobre decimales): las tres reglas de `eslint.config.mjs`, que los `.mjs` no dejan trazar.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const SPA_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const FIXTURES = resolve(SPA_ROOT, "tests", "unit", "eslint-fixtures");

// Una sola instancia: el costo de ESLint es el primer uso (carga de plugins y del parser).
const ESLINT = new ESLint({ cwd: SPA_ROOT });

async function ruleIdsOf(file: string): Promise<string[]> {
  const eslint = ESLINT;
  const [result] = await eslint.lintFiles([resolve(FIXTURES, file)]);
  return (result?.messages ?? []).map((message) => message.ruleId ?? "parse-error");
}

// El timeout es de este archivo (no el global): con la maquina cargada ESLint en frio llego a 5137 ms (candidata de U10-T02).
describe("ESLint de la SPA", { timeout: 30_000 }, () => {
  it.each([
    ["dangerously-set-inner-html.tsx", "react/no-danger"],
    ["local-storage.ts", "no-restricted-globals"],
    ["window-session-storage.ts", "no-restricted-properties"],
    ["text-literal.tsx", "react/jsx-no-literals"],
    ["number-on-decimal.ts", "no-restricted-syntax"],
    ["parse-float.ts", "no-restricted-globals"],
    ["number-parse-float.ts", "no-restricted-syntax"],
    ["session-storage-global.ts", "no-restricted-globals"],
    ["global-this-local-storage.ts", "no-restricted-properties"],
    ["visible-attribute.tsx", "no-restricted-syntax"],
    ["visible-title.tsx", "no-restricted-syntax"],
  ])("%s falla con %s", async (file, rule) => {
    expect(await ruleIdsOf(file)).toContain(rule);
  });

  it("un componente que muestra una variable pasa limpio", async () => {
    expect(await ruleIdsOf("clean.tsx")).toEqual([]);
  });

  it("role, id, htmlFor y href literales pasan limpios (candidata F-01 de U10-T01)", async () => {
    expect(await ruleIdsOf("literal-attributes.tsx")).toEqual([]);
  });

  it("jsx-a11y esta activo: una imagen sin alt falla", async () => {
    const [result] = await ESLINT.lintText("export const Img = ({ src }: { src: string }) => <img src={src} />;", {
      filePath: resolve(SPA_ROOT, "src", "probe.tsx"),
    });
    expect((result?.messages ?? []).map((message) => message.ruleId)).toContain("jsx-a11y/alt-text");
  });

  it("tsconfig.json tiene strict y noUncheckedIndexedAccess", () => {
    const tsconfig = JSON.parse(readFileSync(resolve(SPA_ROOT, "tsconfig.json"), "utf-8")) as {
      compilerOptions: Record<string, unknown>;
    };
    expect(tsconfig.compilerOptions["strict"]).toBe(true);
    expect(tsconfig.compilerOptions["noUncheckedIndexedAccess"]).toBe(true);
  });
});
