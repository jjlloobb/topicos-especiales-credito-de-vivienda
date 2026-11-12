// CA-3 (Paso 1): los fixtures que deben fallar fallan en ESLint, y `tsconfig.json` es estricto.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const SPA_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const FIXTURES = resolve(SPA_ROOT, "tests", "unit", "eslint-fixtures");

async function ruleIdsOf(file: string): Promise<string[]> {
  const eslint = new ESLint({ cwd: SPA_ROOT });
  const [result] = await eslint.lintFiles([resolve(FIXTURES, file)]);
  return (result?.messages ?? []).map((message) => message.ruleId ?? "parse-error");
}

describe("ESLint de la SPA", () => {
  it.each([
    ["dangerously-set-inner-html.tsx", "react/no-danger"],
    ["local-storage.ts", "no-restricted-globals"],
    ["window-session-storage.ts", "no-restricted-properties"],
    ["text-literal.tsx", "react/jsx-no-literals"],
    ["number-on-decimal.ts", "no-restricted-syntax"],
  ])("%s falla con %s", async (file, rule) => {
    expect(await ruleIdsOf(file)).toContain(rule);
  });

  it("un componente que muestra una variable pasa limpio", async () => {
    expect(await ruleIdsOf("clean.tsx")).toEqual([]);
  });

  it("jsx-a11y esta activo: una imagen sin alt falla", async () => {
    const eslint = new ESLint({ cwd: SPA_ROOT });
    const [result] = await eslint.lintText("export const Img = ({ src }: { src: string }) => <img src={src} />;", {
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
