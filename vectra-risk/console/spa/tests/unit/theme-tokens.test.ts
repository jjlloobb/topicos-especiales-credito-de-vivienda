// @vitest-environment node
// El tema de la consola (NFR-U10-51; WCAG 2.1 AA): los tokens de color de `src/styles.css`, en claro y en oscuro, cumplen el contraste de cada par
// texto/fondo que la hoja usa (>= 4.5:1; >= 3:1 en bordes de controles y en el foco), con la formula de luminancia relativa de WCAG. Y la hoja
// no trae nada que la CSP de U2 (`style-src 'self'`, sin otros origenes) no deje cargar: ni `@import`, ni `url(`, ni fuentes.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const CSS = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "src", "styles.css"), "utf-8");

// Enmienda del 2026-11-21 (selector de tema): la paleta es UNA y cada token de color lleva sus dos valores, `light-dark(#claro, #oscuro)`, en el
// unico bloque `:root { ... }` de tokens; el tema lo decide `color-scheme` (el sistema, o `data-theme` en <html>). Los valores son los de antes.
const ROOT = CSS.slice(CSS.indexOf(":root {"), CSS.indexOf("\n}", CSS.indexOf(":root {")));

/** Los tokens `--nombre: light-dark(#RRGGBB, #RRGGBB);` del bloque `:root`: [claro, oscuro]. */
function rootTokens(): { light: Record<string, string>; dark: Record<string, string> } {
  const light: Record<string, string> = {};
  const dark: Record<string, string> = {};
  for (const match of ROOT.matchAll(/--([\w-]+):\s*light-dark\(\s*(#[0-9A-Fa-f]{6})\s*,\s*(#[0-9A-Fa-f]{6})\s*\)\s*;/g)) {
    light[match[1] as string] = match[2] as string;
    dark[match[1] as string] = match[3] as string;
  }
  return { light, dark };
}

const { light: LIGHT, dark: DARK } = rootTokens();
const THEMES: [string, Record<string, string>][] = [
  ["claro", LIGHT],
  ["oscuro", DARK],
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
  // los selectores de idioma y de tema: el boton sobre la cabecera y en la tarjeta del login, y la lista desplegable con su opcion senalada
  ["link", "surface-hover"],
  ["text", "surface-raised"],
  ["text", "surface-hover"],
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
  // los selectores de idioma y de tema: el borde del boton en la cabecera y en la tarjeta, el borde y el foco de la lista, la marca de la opcion elegida
  ["header-text-muted", "header-bg"],
  ["border-strong", "surface-raised"],
  ["focus", "surface-hover"],
  ["primary-bg", "surface-raised"],
  ["primary-bg", "surface-hover"],
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

// Las marcas de agua (pedido del dueno del proyecto, 2026-11-21): un trazo de color `--watermark` con la opacidad `--watermark-opacity` sobre el
// fondo. Van en zonas sin texto, pero el peor caso se calcula igual: si un texto quedara encima de un trazo, seguiria cumpliendo AA con margen.
describe.each(THEMES)("marcas de agua, tema %s", (_name, tokens) => {
  const opacity = Number.parseFloat(/--watermark-opacity:\s*([\d.]+);/.exec(ROOT)?.[1] ?? "NaN");
  /** El color que se pinta donde pasa un trazo: `stroke` con la opacidad dada sobre `background`. */
  const blend = (stroke: string, background: string): string =>
    `#${[1, 3, 5]
      .map((at) => Math.round(parseInt(stroke.slice(at, at + 2), 16) * opacity + parseInt(background.slice(at, at + 2), 16) * (1 - opacity)))
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("")}`;

  it("el token existe y la opacidad es baja", () => {
    expect(tokens["watermark"]).toMatch(/^#[0-9A-Fa-f]{6}$/);
    expect(opacity).toBeGreaterThan(0);
    expect(opacity).toBeLessThanOrEqual(0.12);
  });

  it.each([
    ["text", "bg", "watermark"],
    ["text-muted", "bg", "watermark"],
    ["link", "bg", "watermark"],
    ["danger-text", "bg", "watermark"],
    ["text-muted", "surface", "watermark"],
    ["header-text", "header-bg", "header-text-muted"], // la del inicio de sesion, sobre el verde de la cabecera
    ["header-text-muted", "header-bg", "header-text-muted"],
  ])("peor caso: texto --%s sobre --%s con un trazo de --%s debajo cumple AA con margen (>= 5:1)", (text, background, stroke) => {
    const worst = contrast(tokens[text] as string, blend(tokens[stroke] as string, tokens[background] as string));
    expect(worst).toBeGreaterThanOrEqual(5);
    expect(worst).toBeLessThan(contrast(tokens[text] as string, tokens[background] as string)); // el calculo de verdad mezcla el trazo
  });

  it("el trazo se distingue del fondo sin llegar a ser un elemento de la interfaz (contraste entre 1.05 y 1.6)", () => {
    for (const [stroke, background] of [["watermark", "bg"], ["watermark", "surface"], ["header-text-muted", "header-bg"]] as const) {
      const visible = contrast(blend(tokens[stroke] as string, tokens[background] as string), tokens[background] as string);
      expect(visible, `${stroke} sobre ${background}`).toBeGreaterThan(1.05);
      expect(visible, `${stroke} sobre ${background}`).toBeLessThan(1.6);
    }
  });
});

describe("la hoja de estilos", () => {
  it("las marcas de agua no capturan clics, usan los tokens y se quitan con mas contraste, con colores forzados, al imprimir y (la de las vistas) en movil", () => {
    expect(CSS).toMatch(/\.watermark\s*{[^}]*color:\s*var\(--watermark\);[^}]*opacity:\s*var\(--watermark-opacity\);[^}]*pointer-events:\s*none;/);
    expect(CSS).toMatch(/@media \(prefers-contrast: more\), \(forced-colors: active\), print\s*{\s*\.watermark\s*{\s*display:\s*none;/);
    expect(CSS).toMatch(/@media \(max-width: 47\.99rem\)\s*{[^@]*\.watermark-page\s*{\s*display:\s*none;/);
    const rules = [...CSS.matchAll(/\.watermark[\w-]*[^{]*{([^}]*)}/g)].map((match) => match[1] as string).join(" ");
    expect(rules).not.toMatch(/animation|transition|url\(|#[0-9A-Fa-f]{3,8}\b/);
  });

  it("todo token de color tiene sus dos valores, claro y oscuro, y son distintos (ninguno se queda con el valor claro)", () => {
    expect(Object.keys(LIGHT).length).toBeGreaterThan(30);
    expect(Object.keys(DARK).sort()).toEqual(Object.keys(LIGHT).sort());
    // ningun color suelto en el bloque de tokens: todo `#RRGGBB` y todo `rgba()` esta dentro de un `light-dark()`
    const outside = ROOT.replace(/light-dark\([^;]*\)\s*;/g, ";");
    expect(outside).not.toMatch(/#[0-9A-Fa-f]{3,8}\b/);
    expect(outside).not.toMatch(/rgba?\(/);
    const same = Object.keys(LIGHT).filter((token) => LIGHT[token] === DARK[token]);
    expect(same).toEqual(["focus-on-brand"]); // el ambar del foco sobre la cabecera verde sirve en los dos temas
  });

  it("los valores oscuros estan escritos UNA sola vez: no hay un bloque `prefers-color-scheme` ni otro bloque de tokens por tema", () => {
    expect(CSS).not.toMatch(/@media[^{]*prefers-color-scheme/);
    for (const hex of new Set(Object.values(DARK))) {
      const outsideRoot = CSS.replace(ROOT, "");
      expect(outsideRoot.includes(hex), `${hex} fuera del bloque de tokens`).toBe(false);
    }
  });

  it("el tema: el del sistema por omision (`color-scheme: light dark`) y `data-theme` lo fija en los dos sentidos, tambien para los controles nativos", () => {
    expect(ROOT).toMatch(/color-scheme:\s*light dark;/);
    expect(CSS).toMatch(/:root\[data-theme="light"\]\s*{\s*color-scheme:\s*light;\s*}/);
    expect(CSS).toMatch(/:root\[data-theme="dark"\]\s*{\s*color-scheme:\s*dark;\s*}/);
    // las reglas del atributo van DESPUES del bloque de tokens (misma especificidad de `:root` mas el atributo: ganan siempre)
    expect(CSS.indexOf(':root[data-theme="dark"]')).toBeGreaterThan(CSS.indexOf(":root {"));
    // y ninguna regla de color depende de una consulta del sistema que el atributo no pueda vencer
    expect(CSS.match(/color-scheme:/g)?.length).toBe(3);
  });

  it("los colores son los de siempre: una muestra de la paleta verde, en claro y en oscuro", () => {
    expect([LIGHT["bg"], DARK["bg"]]).toEqual(["#FAF8F4", "#101A15"]);
    expect([LIGHT["header-bg"], DARK["header-bg"]]).toEqual(["#0B3B2C", "#0B2318"]);
    expect([LIGHT["primary-bg"], DARK["primary-bg"]]).toEqual(["#14633F", "#6FCF97"]);
    expect([LIGHT["warn-bg"], DARK["warn-bg"]]).toEqual(["#FCEFCB", "#3D2E0A"]);
    expect([LIGHT["danger-text"], DARK["danger-text"]]).toEqual(["#8B1A1A", "#F7B4AE"]);
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
    for (const query of ["prefers-reduced-motion: reduce", "prefers-contrast: more", "min-width: 48rem", "min-width: 64rem", "min-width: 90rem", "max-width: 22.49rem"]) {
      expect(CSS, query).toContain(`(${query})`);
    }
    expect(CSS).toContain("(forced-colors: active)");
    expect(CSS).toMatch(/color-scheme:\s*light dark;/); // el tema del sistema (`prefers-color-scheme`) lo aplica `light-dark()` con `color-scheme`
    expect(CSS).toMatch(/--target:\s*2\.75rem/); // objetivo tactil de 44 px
  });
});
