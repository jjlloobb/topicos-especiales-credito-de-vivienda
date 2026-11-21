// @vitest-environment jsdom
// El idioma de la interfaz (enmienda del 2026-11-21 a NFR-U10-53): como se resuelve el inicial (preferencia guardada > `locale` de `get_me` >
// navegador > espanol), el cambio (inmediato, con aviso a quien escucha, `<html lang>` y titulo), la persistencia (solo la eleccion explicita,
// una clave en el almacenamiento local, validada al leer) y los formatos de fechas y numeros de cada idioma.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { channelText, formatCount, formatDate, formatDay, formatDecimal, formatMoney, label, labelOrRaw, notice, problemText, safeDecimal, ui } from "../../../src/i18n";
import {
  adoptSessionLocale,
  browserLanguageEnv,
  chooseLanguage,
  DEFAULT_LANGUAGE,
  getLanguage,
  initLanguage,
  type Language,
  type LanguageEnv,
  languageOf,
  LOCALES,
  resolveLanguage,
  subscribeLanguage,
} from "../../../src/i18n/language";
import { createLanguageStorage, LANGUAGE_KEY } from "../../../src/preferences/storage";

/** Un entorno de prueba: un almacenamiento en memoria, los idiomas del navegador dados y un documento falso. */
function fakeEnv(browser: readonly string[] = [], stored: Language | null = null) {
  const state = { stored, writes: [] as Language[] };
  const doc = { documentElement: { lang: "es" }, title: "Vectra Risk" };
  const env: LanguageEnv = {
    storage: {
      read: () => state.stored,
      write: (language) => {
        state.stored = language;
        state.writes.push(language);
      },
    },
    browserLanguages: () => browser,
    document: doc as unknown as Document,
  };
  return { env, state, doc };
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});
afterEach(() => {
  initLanguage(); // vuelve al estado de fabrica: espanol, sin entorno
});

describe("languageOf", () => {
  it.each([
    ["es", "es"],
    ["es-CO", "es"],
    ["es_419", "es"],
    ["ES-co", "es"],
    ["en", "en"],
    ["en-US", "en"],
    ["en-GB", "en"],
    [" en-AU ", "en"],
  ])("%s -> %s", (tag, expected) => {
    expect(languageOf(tag)).toBe(expected);
  });

  it.each(["fr", "pt-BR", "", "e", "english", "esp", "eng-US", "x-es", null, undefined, 7, {}])("%s no es ninguno de los dos", (tag) => {
    expect(languageOf(tag)).toBeNull();
  });
});

describe("resolveLanguage: preferencia guardada > locale de get_me > navegador > espanol", () => {
  it("la preferencia guardada manda sobre todo lo demas", () => {
    expect(resolveLanguage({ stored: "en", sessionLocale: "es-CO", browser: ["es-CO"] })).toBe("en");
    expect(resolveLanguage({ stored: "es", sessionLocale: "en-US", browser: ["en-US"] })).toBe("es");
  });
  it("sin preferencia, el locale de get_me si es uno de los dos", () => {
    expect(resolveLanguage({ stored: null, sessionLocale: "es-CO", browser: ["en-US"] })).toBe("es");
    expect(resolveLanguage({ sessionLocale: "en-GB", browser: ["es-CO"] })).toBe("en");
  });
  it("si el locale de get_me no es ninguno de los dos (o no hay sesion), el navegador: el primero que sea espanol o ingles", () => {
    expect(resolveLanguage({ sessionLocale: "fr-FR", browser: ["en-US", "es"] })).toBe("en");
    expect(resolveLanguage({ sessionLocale: null, browser: ["pt-BR", "fr", "en-GB", "es-CO"] })).toBe("en");
    expect(resolveLanguage({ browser: ["es-MX", "en"] })).toBe("es");
  });
  it("si nada sirve, espanol", () => {
    expect(resolveLanguage({ sessionLocale: "fr", browser: ["pt-BR", "de"] })).toBe("es");
    expect(resolveLanguage({})).toBe("es");
    expect(DEFAULT_LANGUAGE).toBe("es");
  });
});

describe("el estado del idioma", () => {
  it("sin entorno (las pruebas de las vistas) es espanol y no toca el documento ni el almacenamiento", () => {
    expect(getLanguage()).toBe("es");
    chooseLanguage("en");
    expect(getLanguage()).toBe("en");
    expect(localStorage.length).toBe(0);
    expect(document.documentElement.lang).toBe("");
  });

  it("al arrancar: la preferencia guardada, y si no hay, el navegador; el documento queda con su `lang` y su titulo", () => {
    const stored = fakeEnv(["es-CO"], "en");
    initLanguage(stored.env);
    expect(getLanguage()).toBe("en");
    expect(stored.doc.documentElement.lang).toBe("en");
    expect(stored.doc.title).toBe("Vectra Risk · Home loans");

    const english = fakeEnv(["en-US", "es"]);
    initLanguage(english.env);
    expect(getLanguage()).toBe("en");

    const spanish = fakeEnv(["es-CO", "en"]);
    initLanguage(spanish.env);
    expect(getLanguage()).toBe("es");
    expect(spanish.doc.documentElement.lang).toBe("es");
    expect(spanish.doc.title).toBe("Vectra Risk · Crédito de vivienda");

    initLanguage(fakeEnv(["fr-FR"]).env);
    expect(getLanguage()).toBe("es");
  });

  it("arrancar no guarda nada: solo la eleccion explicita se guarda", () => {
    const world = fakeEnv(["en-US"]);
    initLanguage(world.env);
    adoptSessionLocale("es-CO");
    adoptSessionLocale(null);
    expect(world.state.writes).toEqual([]);
    chooseLanguage("en");
    expect(world.state.writes).toEqual(["en"]);
  });

  it("elegir cambia ya: avisa a quien escucha (una vez por cambio), actualiza `lang` y titulo, y guarda", () => {
    const world = fakeEnv(["es-CO"]);
    initLanguage(world.env);
    const listener = vi.fn();
    const unsubscribe = subscribeLanguage(listener);
    chooseLanguage("en");
    expect(getLanguage()).toBe("en");
    expect(ui("login_button")).toBe("Sign in");
    expect(listener).toHaveBeenCalledTimes(1);
    expect(world.doc.documentElement.lang).toBe("en");
    expect(world.doc.title).toBe("Vectra Risk · Home loans");
    expect(world.state.stored).toBe("en");
    chooseLanguage("en"); // el mismo: no avisa otra vez
    expect(listener).toHaveBeenCalledTimes(1);
    chooseLanguage("es");
    expect(ui("login_button")).toBe("Iniciar sesión");
    expect(listener).toHaveBeenCalledTimes(2);
    expect(world.doc.documentElement.lang).toBe("es");
    unsubscribe();
    chooseLanguage("en");
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it("el locale de get_me cuenta solo si no hay preferencia: con navegador en ingles, la sesion es-CO pasa a espanol; al cerrarla, vuelve el navegador", () => {
    const world = fakeEnv(["en-US"]);
    initLanguage(world.env);
    expect(getLanguage()).toBe("en"); // pantalla de inicio de sesion: el navegador
    adoptSessionLocale("es-CO");
    expect(getLanguage()).toBe("es");
    expect(world.doc.documentElement.lang).toBe("es");
    adoptSessionLocale(null);
    expect(getLanguage()).toBe("en");
  });

  it("con una preferencia guardada, el locale de get_me no la cambia", () => {
    initLanguage(fakeEnv(["es-CO"], "en").env);
    adoptSessionLocale("es-CO");
    expect(getLanguage()).toBe("en");
  });

  it("la eleccion vale aunque el navegador no deje guardar: get_me no la deshace en esta carga de pagina", () => {
    const env: LanguageEnv = { storage: { read: () => null, write: () => undefined }, browserLanguages: () => ["es-CO"], document: null };
    initLanguage(env);
    chooseLanguage("en");
    adoptSessionLocale("es-CO");
    expect(getLanguage()).toBe("en");
  });

  it("un locale de sesion que no es ninguno de los dos deja el del navegador", () => {
    initLanguage(fakeEnv(["en-GB"]).env);
    adoptSessionLocale("fr-FR");
    expect(getLanguage()).toBe("en");
  });
});

describe("la preferencia en el navegador (languageStorage)", () => {
  it("guarda UNA clave en el almacenamiento local, con «es» o «en», y nada en el de sesion ni en cookies", () => {
    const storage = createLanguageStorage(window);
    expect(storage.read()).toBeNull();
    storage.write("en");
    expect(Object.entries(localStorage)).toEqual([[LANGUAGE_KEY, "en"]]);
    expect(storage.read()).toBe("en");
    storage.write("es");
    expect(Object.entries(localStorage)).toEqual([[LANGUAGE_KEY, "es"]]);
    expect(sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  it.each(["fr", "EN", "en-US", "", "<script>", "null", '"en"'])("un valor guardado que no es «es» ni «en» (%s) es como si no hubiera", (value) => {
    localStorage.setItem(LANGUAGE_KEY, value);
    expect(createLanguageStorage(window).read()).toBeNull();
  });

  it("si el navegador no deja leer ni escribir, no rompe", () => {
    const broken = {
      get localStorage(): Storage {
        throw new DOMException("denegado", "SecurityError");
      },
    } as unknown as Window;
    const storage = createLanguageStorage(broken);
    expect(storage.read()).toBeNull();
    expect(() => {
      storage.write("en");
    }).not.toThrow();
  });

  it("sobrevive a una recarga: otra carga de pagina (estado nuevo) lee la preferencia que dejo la anterior", () => {
    initLanguage(browserLanguageEnv(window, createLanguageStorage(window)));
    chooseLanguage("en");
    expect(document.documentElement.lang).toBe("en");
    expect(document.title).toBe("Vectra Risk · Home loans");
    initLanguage(); // la memoria de la pagina se pierde
    expect(getLanguage()).toBe("es");
    initLanguage(browserLanguageEnv(window, createLanguageStorage(window)));
    expect(getLanguage()).toBe("en");
  });

  it("el entorno del navegador lee `navigator.languages` (y `navigator.language` si la lista viene vacia)", () => {
    const win = (languages: string[], language: string) => ({ navigator: { languages, language }, document }) as unknown as Window;
    expect(browserLanguageEnv(win(["en-US", "es"], "en-US"), null).browserLanguages()).toEqual(["en-US", "es"]);
    expect(browserLanguageEnv(win([], "es-CO"), null).browserLanguages()).toEqual(["es-CO"]);
  });
});

describe("textos por idioma", () => {
  it("ui, notice, label, labelOrRaw, channelText y problemText siguen al idioma en curso", () => {
    chooseLanguage("en");
    expect(ui("session_role", { role: label("ROLES", "cro") })).toBe("Role: Chief Risk Officer (CRO)");
    expect(notice("credit_not_integrated")).toBe("Loan status not integrated");
    expect(label("CASE_STATES", "modelo_congelado")).toBe("Model frozen");
    expect(label("CELL_STATUSES", "muestra_insuficiente")).toBe("Insufficient sample");
    expect(label("ROLES", "inexistente" as never)).toBe("Value without a label");
    expect(labelOrRaw("ATTRIBUTES", "sexo")).toBe("Sex");
    expect(labelOrRaw("ATTRIBUTES", "otro")).toBe("otro");
    expect(channelText("manual")).toBe("Manual");
    expect(channelText("b2b")).toBe("b2b");
    expect(problemText({ code: "mfa_required" })).toBe("This action requires two-step verification.");
    expect(problemText({ code: "conflict_state", reason: "active_version_frozen" })).toBe("The active model version is frozen.");
    expect(problemText({ code: "algo_nuevo", correlation_id: "abc" })).toBe("Something unexpected went wrong. If it keeps happening, give this code to support: abc.");
    chooseLanguage("es");
    expect(label("CASE_STATES", "modelo_congelado")).toBe("Modelo congelado");
    expect(problemText({ code: "mfa_required" })).toBe("Esta acción requiere verificar tu identidad con un segundo factor.");
  });
});

describe("fechas y numeros por idioma (Intl; zona de Bogota)", () => {
  it("los locales: es-CO y en-GB", () => {
    expect(LOCALES).toEqual({ es: "es-CO", en: "en-GB" });
  });

  it("espanol: coma decimal, punto de miles, dia/mes/anio, pesos con $", () => {
    expect(safeDecimal("0.2438")).toBe("0,2438");
    expect(formatDecimal("1234.5", 2)).toBe("1.234,50");
    expect(formatCount(12345)).toBe("12.345");
    expect(formatMoney(1500000).replace(/\s/g, " ")).toBe("$ 1.500.000");
    expect(formatDate("2026-11-12T20:30:00Z")).toMatch(/^12\/11\/2026, 3:30/);
    expect(formatDay("2026-11-01")).toBe("1/11/2026");
  });

  it("ingles: punto decimal, coma de miles, fecha con el mes en letras (no ambigua) y hora de 24 h, pesos como COP", () => {
    chooseLanguage("en");
    expect(safeDecimal("0.2438")).toBe("0.2438");
    expect(safeDecimal("-0.0001")).toBe("-0.0001");
    expect(formatDecimal("1234.5", 2)).toBe("1,234.50");
    expect(formatCount(12345)).toBe("12,345");
    expect(formatMoney(1500000).replace(/\s/g, " ")).toBe("COP 1,500,000");
    expect(formatDate("2026-11-12T20:30:00Z")).toBe("12 Nov 2026, 15:30"); // 20:30 UTC = 15:30 en Bogota
    expect(formatDate("2026-11-13T02:00:00Z")).toBe("12 Nov 2026, 21:00"); // el dia es el de Bogota, no el de UTC
    expect(formatDay("2026-11-01")).toBe("1 Nov 2026"); // un dia sin hora no se corre al anterior
  });

  it("el decimal del servidor no se recalcula: los mismos digitos en los dos idiomas, solo cambian los separadores", () => {
    const value = "12345678901234567.1234"; // un number de doble precision perderia digitos
    expect(formatDecimal(value)).toBe("12.345.678.901.234.567,1234");
    chooseLanguage("en");
    expect(formatDecimal(value)).toBe("12,345,678,901,234,567.1234");
    for (const digits of ["0.2438", "0.0500", "1.0000", "-0.1250"]) {
      chooseLanguage("es");
      const spanish = safeDecimal(digits);
      chooseLanguage("en");
      expect(safeDecimal(digits)).toBe(digits);
      expect(spanish).toBe(digits.replace(".", ","));
    }
  });

  it("lo que no es un decimal se muestra tal cual en los dos idiomas, y formatDecimal lo rechaza", () => {
    chooseLanguage("en");
    expect(safeDecimal("n/d")).toBe("n/d");
    expect(safeDecimal("0,2438")).toBe("0,2438");
    expect(() => formatDecimal("1e5")).toThrow(RangeError);
  });
});
