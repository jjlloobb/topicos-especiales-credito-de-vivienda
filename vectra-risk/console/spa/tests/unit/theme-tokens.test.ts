// @vitest-environment node
// El tema de la consola (NFR-U10-51; WCAG 2.1 AA): los tokens de color de `src/styles.css`, en claro y en oscuro, cumplen el contraste de cada par
// texto/fondo que la hoja usa (>= 4.5:1; >= 3:1 en bordes de controles y en el foco), con la formula de luminancia relativa de WCAG. Y la hoja
// no trae nada que la CSP de U2 (`style-src 'self'`, sin otros origenes) no deje cargar: ni `@import`, ni `url(`, ni fuentes.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const CSS = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "src", "styles.css"), "utf-8");

/** Los tokens `--nombre: #RRGGBB;` del primer bloque `:root { ... }` a partir de `from`. */
function rootTokens(from: number): Record<string, string> {
  const start = CSS.indexOf(":root {", from);
  const end = CSS.indexOf("}", start);
  expect(start).toBeGreaterThanOrEqual(0);
  const tokens: Record<string, string> = {};
  for (const match of CSS.slice(start, end).matchAll(/--([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;/g)) tokens[match[1] as string] = match[2] as string;
  return tokens;
}

const LIGHT = rootTokens(0);
const DARK_OVERRIDES = rootTokens(CSS.indexOf("@media (prefers-color-scheme: dark)"));
const THEMES: [string, Record<string, string>][] = [
  ["claro", LIGHT],
  ["oscuro", { ...LIGHT, ...DARK_OVERRIDES }],
];

function channel(value: number): number {
  const s = value / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16)) as [number, number, number];
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a: string, b: string): number {
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (high + 0.05) / (low + 0.05);
}

// [texto, fondo]: los pares que `styles.css` usa.
const TEXT_PAIRS: [string, string][] = [
  ["text", "bg"],
  ["text", "surface"],
  ["text", "surface-alt"],
  ["text", "surface-hover"],
  ["text", "surface-raised"],
  ["text", "warn-bg"], // la fila del atributo disparador
  ["text-muted", "bg"],
  ["text-muted", "surface"],
  ["text-muted", "surface-alt"],
  ["text-muted", "surface-hover"],
  ["text-muted", "surface-muted"],
  ["text-muted", "surface-raised"],
  ["text-muted", "warn-bg"],
  ["link", "bg"],
  ["link", "surface"],
  ["link", "surface-alt"],
  ["link", "surface-hover"],
  ["link", "surface-raised"],
  ["link", "warn-bg"],
  ["header-text", "header-bg"],
  ["header-text-muted", "header-bg"],
  ["nav-text", "nav-bg"],
  ["nav-active-text", "nav-active-bg"],
  ["primary-text", "primary-bg"],
  ["primary-text", "primary-bg-hover"],
  ["danger-strong-text", "danger-strong"],
  ["thead-text", "thead-bg"],
  ["ok-text", "ok-bg"],
  ["warn-text", "warn-bg"],
  ["danger-text", "danger-bg"],
  ["danger-text", "bg"],
  ["danger-text", "surface"],
  ["danger-text", "surface-raised"],
  ["info-text", "info-bg"],
  ["neutral-text", "neutral-bg"],
  ["disabled-text", "disabled-bg"],
];

// [color, fondo]: lo que no es texto (bordes de controles, foco, borde de aviso) necesita 3:1 (WCAG 1.4.11).
const UI_PAIRS: [string, string][] = [
  ["border-strong", "surface"],
  ["border-strong", "bg"],
  ["focus", "bg"],
  ["focus", "surface"],
  ["focus", "surface-raised"],
  ["focus-on-brand", "header-bg"],
  ["focus-on-brand", "nav-bg"],
  ["warn-border", "surface"],
  ["primary-bg", "surface"],
];

describe.each(THEMES)("tema %s", (_name, tokens) => {
  const color = (token: string): string => {
    const value = tokens[token];
    expect(value, `falta el token --${token}`).toBeTypeOf("string");
    return value as string;
  };

  it.each(TEXT_PAIRS)("texto --%s sobre --%s: contraste >= 4.5:1", (text, background) => {
    expect(contrast(color(text), color(background))).toBeGreaterThanOrEqual(4.5);
  });

  it.each(UI_PAIRS)("borde o foco --%s sobre --%s: contraste >= 3:1", (edge, background) => {
    expect(contrast(color(edge), color(background))).toBeGreaterThanOrEqual(3);
  });
});

describe("la hoja de estilos", () => {
  it("el tema oscuro redefine todos los tokens de color del claro (ninguno se queda con el valor claro)", () => {
    expect(Object.keys(LIGHT).length).toBeGreaterThan(30);
    expect(Object.keys(DARK_OVERRIDES).sort()).toEqual(Object.keys(LIGHT).sort());
  });

  it("la formula de contraste es la de WCAG: negro sobre blanco 21:1 y un amarillo sobre blanco no llega", () => {
    expect(contrast("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
    expect(contrast("#FFFF00", "#FFFFFF")).toBeLessThan(4.5);
  });

  it("no carga nada de otro origen ni en linea: sin @import, sin url(), sin @font-face", () => {
    expect(CSS).not.toMatch(/@import/i);
    expect(CSS).not.toMatch(/url\s*\(/i);
    expect(CSS).not.toMatch(/@font-face/i);
    expect(CSS).not.toMatch(/https?:/i);
  });

  it("se adapta a las preferencias de la persona y a los cuatro anchos de corte", () => {
    for (const query of ["prefers-color-scheme: dark", "prefers-reduced-motion: reduce", "prefers-contrast: more", "min-width: 48rem", "min-width: 64rem", "min-width: 90rem", "max-width: 22.49rem"]) {
      expect(CSS, query).toContain(`(${query})`);
    }
    expect(CSS).toMatch(/--target:\s*2\.75rem/); // objetivo tactil de 44 px
  });
});
