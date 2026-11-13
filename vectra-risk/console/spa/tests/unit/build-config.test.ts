// @vitest-environment node
// NFR-U10-50 (navegadores), NFR-U10-03 (presupuesto del paquete inicial), NFR-U10-42 y P-U10-08 (CSP: sin codigo en linea, sin polyfill de
// `modulepreload`): lo que se puede comprobar sin construir. El build, el tamano real y la CSP en un navegador son de `console check` y de `tests/csp`.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import config, { BUILD_TARGET } from "../../vite.config";

const SPA = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const read = (name: string): string => readFileSync(resolve(SPA, name), "utf-8");
const pkg = JSON.parse(read("package.json")) as { browserslist: string[]; scripts: Record<string, string> };

describe("NFR-U10-50: browserslist y build.target", () => {
  it("package.json declara las dos ultimas versiones de Chrome y de Edge y Firefox ESR", () => {
    expect(pkg.browserslist).toEqual(["last 2 Chrome versions", "last 2 Edge versions", "Firefox ESR"]);
  });

  it("build.target tiene un objetivo por cada familia de browserslist, con version", () => {
    const families = pkg.browserslist.map((query) => (/Chrome/.test(query) ? "chrome" : /Edge/.test(query) ? "edge" : "firefox"));
    expect([...BUILD_TARGET].map((target) => /^[a-z]+/.exec(target)?.[0]).sort()).toEqual([...families].sort());
    for (const target of BUILD_TARGET) expect(target).toMatch(/^(chrome|edge|firefox)\d+$/);
    expect(config.build?.target).toEqual(BUILD_TARGET);
  });
});

describe("P-U10-08, NFR-U10-42: el build no escribe codigo en linea", () => {
  it("sin el polyfill de modulepreload (que seria un <script> en linea)", () => {
    expect(config.build?.modulePreload).toEqual({ polyfill: false });
  });

  it("`index.html` no tiene <style> ni <script> con cuerpo, y el unico script es el modulo de entrada", () => {
    const html = read("index.html");
    expect(html).not.toMatch(/<style/i);
    const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
    expect(scripts).toHaveLength(1);
    expect(scripts[0]?.[1]).toContain('type="module"');
    expect(scripts[0]?.[1]).toContain("src=");
    expect(scripts[0]?.[2]).toBe("");
    expect(html).not.toMatch(/\son\w+\s*=/i); // ni manejadores en linea
    expect(html).not.toMatch(/style\s*=/i);
  });

  it("react-aria no inyecta su <style> (CSP): el id esta ocupado en `index.html` y la regla vive en `styles.css`", () => {
    expect(read("index.html")).toContain('id="react-aria-pressable-style"');
    expect(read("src/styles.css")).toMatch(/\[data-react-aria-pressable\]\s*{\s*touch-action:\s*pan-x pan-y pinch-zoom;/);
  });
});

describe("NFR-U10-03: el presupuesto del paquete inicial", () => {
  it("`size-limit` mide el cierre del index.html con gzip y 250 KiB, y el build escribe el manifiesto que lee", () => {
    const sizeLimit = read(".size-limit.mjs");
    expect(sizeLimit).toContain("gzip: true");
    expect(sizeLimit).toContain('limit: "250 KiB"');
    expect(sizeLimit).toContain("src/views/");
    expect(config.build?.manifest).toBe(true);
    expect(pkg.scripts["build"]).toBe("vite build");
  });
});
