// @vitest-environment jsdom
// El tema (enmienda del 2026-11-21 a NFR-U10-51): «Sistema» por omision (sin atributo), «Claro» y «Oscuro» ponen `data-theme` en <html>; solo la
// eleccion explicita se guarda (una clave del almacenamiento local, validada contra el conjunto cerrado); y `public/theme-boot.js`, el guion
// que lo aplica antes de la primera pintura, usa la misma clave y los mismos valores.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createThemeStorage, LANGUAGE_KEY, THEME_KEY } from "../../../src/preferences/storage";
import { browserThemeEnv, chooseTheme, DEFAULT_THEME, getTheme, initTheme, subscribeTheme, themeOf, THEMES } from "../../../src/theme/theme";

const SPA = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const BOOT = readFileSync(resolve(SPA, "public", "theme-boot.js"), "utf-8");
const root = document.documentElement;
const start = (): void => {
  initTheme(browserThemeEnv(window, createThemeStorage(window)));
};

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  root.removeAttribute("data-theme");
});
afterEach(() => {
  initTheme();
  root.removeAttribute("data-theme");
});

describe("el estado del tema", () => {
  it("el conjunto es cerrado: system, light y dark; por omision, system", () => {
    expect([...THEMES]).toEqual(["system", "light", "dark"]);
    expect(DEFAULT_THEME).toBe("system");
    expect(themeOf("dark")).toBe("dark");
    for (const bad of ["Dark", "auto", "", "light dark", null, undefined, 1]) expect(themeOf(bad)).toBeNull();
  });

  it("sin entorno (las pruebas de las vistas) no toca el documento ni el almacenamiento", () => {
    chooseTheme("dark");
    expect(getTheme()).toBe("dark");
    expect(root.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.length).toBe(0);
  });

  it("al arrancar sin preferencia: «Sistema», sin atributo y sin escribir nada", () => {
    start();
    expect(getTheme()).toBe("system");
    expect(root.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.length).toBe(0);
  });

  it("elegir cambia ya: `data-theme` en <html>, aviso a quien escucha (una vez por cambio) y una sola clave guardada", () => {
    start();
    const listener = vi.fn();
    const unsubscribe = subscribeTheme(listener);
    chooseTheme("dark");
    expect(root.getAttribute("data-theme")).toBe("dark");
    expect(Object.entries(localStorage)).toEqual([[THEME_KEY, "dark"]]);
    expect(listener).toHaveBeenCalledTimes(1);
    chooseTheme("dark");
    expect(listener).toHaveBeenCalledTimes(1);
    chooseTheme("light");
    expect(root.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    chooseTheme("system");
    expect(root.hasAttribute("data-theme")).toBe(false); // «Sistema» quita el atributo: decide `prefers-color-scheme`
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
    expect(listener).toHaveBeenCalledTimes(3);
    unsubscribe();
    chooseTheme("dark");
    expect(listener).toHaveBeenCalledTimes(3);
    expect(sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  it("sobrevive a una recarga: otra carga de pagina lee el tema que dejo la anterior", () => {
    start();
    chooseTheme("dark");
    initTheme();
    root.removeAttribute("data-theme");
    expect(getTheme()).toBe("system");
    start();
    expect(getTheme()).toBe("dark");
    expect(root.getAttribute("data-theme")).toBe("dark");
  });

  it.each(["Dark", "auto", "", "<script>", "es", '"dark"'])("un valor guardado fuera del conjunto (%s) es como si no hubiera", (value) => {
    localStorage.setItem(THEME_KEY, value);
    expect(createThemeStorage(window).read()).toBeNull();
    start();
    expect(getTheme()).toBe("system");
    expect(root.hasAttribute("data-theme")).toBe(false);
  });

  it("si el navegador no deja leer ni escribir, no rompe", () => {
    const broken = {
      get localStorage(): Storage {
        throw new DOMException("denegado", "SecurityError");
      },
      document,
    } as unknown as Window;
    const storage = createThemeStorage(broken);
    expect(storage.read()).toBeNull();
    initTheme(browserThemeEnv(broken, storage));
    chooseTheme("dark");
    expect(root.getAttribute("data-theme")).toBe("dark"); // vale para esta carga de pagina
  });

  it("la clave del tema y la del idioma son distintas y no se pisan", () => {
    expect(THEME_KEY).not.toBe(LANGUAGE_KEY);
    localStorage.setItem(LANGUAGE_KEY, "en");
    start();
    chooseTheme("light");
    expect(Object.fromEntries(Object.entries(localStorage))).toEqual({ [LANGUAGE_KEY]: "en", [THEME_KEY]: "light" });
  });
});

describe("public/theme-boot.js: el tema antes de la primera pintura", () => {
  const run = (): void => {
    new Function(BOOT)(); // el archivo es un guion clasico: se ejecuta tal cual contra el documento de jsdom
  };

  it("usa la misma clave que `preferences/storage.ts` y solo los valores `light` y `dark`", () => {
    expect(BOOT).toContain(`getItem("${THEME_KEY}")`);
    expect([...BOOT.matchAll(/theme === "(\w+)"/g)].map((match) => match[1])).toEqual(["light", "dark"]);
  });

  it.each([
    ["dark", "dark"],
    ["light", "light"],
    ["system", null],
    [null, null],
    ["Dark", null],
    ["javascript:alert(1)", null],
  ])("con %s guardado deja data-theme = %s", (stored, expected) => {
    if (stored !== null) localStorage.setItem(THEME_KEY, stored);
    run();
    expect(root.getAttribute("data-theme")).toBe(expected);
  });

  it("no escribe nada, y lo que deja coincide con lo que despues aplica la aplicacion", () => {
    for (const theme of THEMES) {
      localStorage.clear();
      root.removeAttribute("data-theme");
      localStorage.setItem(THEME_KEY, theme);
      const before = JSON.stringify(Object.entries(localStorage));
      run();
      const early = root.getAttribute("data-theme");
      expect(JSON.stringify(Object.entries(localStorage))).toBe(before);
      start();
      expect(root.getAttribute("data-theme")).toBe(early);
    }
  });

  it("si el almacenamiento falla, no rompe la pagina y queda el tema del sistema", () => {
    const original = Object.getOwnPropertyDescriptor(window, "localStorage") as PropertyDescriptor;
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get: () => {
        throw new DOMException("denegado", "SecurityError");
      },
    });
    try {
      expect(run).not.toThrow();
      expect(root.hasAttribute("data-theme")).toBe(false);
    } finally {
      Object.defineProperty(window, "localStorage", original);
    }
  });

  it("es un guion sin nada que la CSP o Trusted Types bloqueen: ni eval, ni HTML, ni otro origen", () => {
    const code = BOOT.replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toMatch(/eval|Function\(|innerHTML|document\.write|import\(|https?:|setItem|cookie/);
  });
});
