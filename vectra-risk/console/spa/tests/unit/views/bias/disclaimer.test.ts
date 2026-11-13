// @vitest-environment node
// P-4 (a): el `disclaimer` de `FreezeContextView` es un texto propio del catalogo, igual a `DISCLAIMER` de U9 (`bias-monitoring/src/vectra_bias/dashboard.py`):
// la prueba lee ese archivo como texto y los compara. (`FreezeRecord` no trae el campo: candidata de U0, ver `CANDIDATAS.md`.)
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { ui } from "../../../../src/i18n";

const VECTRA_RISK = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..", "..", "..");

describe("el disclaimer propio de la consola", () => {
  it("es el de U9, caracter por caracter", () => {
    const source = readFileSync(resolve(VECTRA_RISK, "bias-monitoring", "src", "vectra_bias", "dashboard.py"), "utf-8");
    const upstream = /^DISCLAIMER: Final = "([^"]+)"$/m.exec(source)?.[1];
    expect(upstream).toBe("mide y alerta, no certifica");
    expect(ui("bias_disclaimer")).toBe(upstream);
  });
});
