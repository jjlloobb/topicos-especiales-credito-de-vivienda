// El idioma de la interfaz (enmienda del 2026-11-21 a NFR-U10-53): espanol (por omision), ingles o portugues de Brasil. Un solo estado para toda la SPA, fuera de
// React, porque `ui`, `label` y los formatos de `index.ts` se llaman tambien fuera de los componentes; `useLanguage` lo conecta con React.
//
// El idioma inicial, en este orden: (1) la preferencia que la persona eligio y quedo guardada en el navegador (`preferences/storage.ts`);
// (2) el `locale` de `get_me`, si es uno de los tres idiomas; (3) el primer idioma del navegador que sea espanol, ingles o portugues
// (cualquier `pt-*`); (4) espanol.
// Solo la eleccion explicita (`chooseLanguage`) se guarda: sin ella no se escribe nada en el navegador. El idioma no viaja al servidor.
import messagesEn from "./messages.en.json";
import messagesEs from "./messages.es.json";
import messagesPt from "./messages.pt.json";

export const LANGUAGES = ["es", "en", "pt"] as const;
export type Language = (typeof LANGUAGES)[number];
export const DEFAULT_LANGUAGE: Language = "es";

/**
 * El `locale` de `Intl` de cada idioma. En ingles, `en-GB`: el dia va antes del mes, como en Colombia, y el mes va con letras
 * («12 Nov 2026, 15:30»), asi que una fecha no se puede leer al reves; los decimales llevan punto y los pesos se escriben «COP 1,500,000»
 * (un «$» solo se leeria como dolares). La zona horaria es siempre la de Bogota (`index.ts`).
 */
export const LOCALES: Readonly<Record<Language, string>> = { es: "es-CO", en: "en-GB", pt: "pt-BR" };

/**
 * El estilo de fecha de `Intl` de cada idioma. En portugues, el corto: `pt-BR` escribe el medio como «12 de nov. de 2026», que no cabe en una
 * columna de tabla sin partirse; el corto («12/11/2026», dia/mes/anio, la forma habitual en Brasil y la misma que en espanol) si.
 */
export const DATE_STYLES: Readonly<Record<Language, "medium" | "short">> = { es: "medium", en: "medium", pt: "short" };

/**
 * La etiqueta de idioma de cada uno hacia fuera de la consola: el `lang` de `<html>` y de cada opcion del selector, y el `ui_locales` de las
 * peticiones de autorizacion (el login de Keycloak nombra el portugues de Brasil `pt-BR`). Un conjunto cerrado: nunca texto libre.
 */
export const LANGUAGE_TAGS = { es: "es", en: "en", pt: "pt-BR" } as const satisfies Readonly<Record<Language, string>>;
export type LanguageTag = (typeof LANGUAGE_TAGS)[Language];

/** El `ui_locales` del idioma en curso (`es`, `en` o `pt-BR`). */
export function uiLocales(): LanguageTag {
  return LANGUAGE_TAGS[current];
}

const TITLES: Readonly<Record<Language, string>> = { es: messagesEs.ui.document_title, en: messagesEn.ui.document_title, pt: messagesPt.ui.document_title };

/** El idioma de una etiqueta BCP 47 (`es-CO`, `en_US`, `EN`): solo cuenta el idioma primario (`pt-BR`, `pt-PT` y `pt` son portugues); `null` si no es ninguno de los tres. */
export function languageOf(tag: unknown): Language | null {
  if (typeof tag !== "string") return null;
  const primary = tag.trim().toLowerCase().split(/[-_]/)[0];
  return LANGUAGES.find((language) => language === primary) ?? null;
}

export interface LanguageSources {
  /** La preferencia guardada (ya validada), si la hay. */
  readonly stored?: Language | null | undefined;
  /** El `locale` de `get_me`, si hay sesion. */
  readonly sessionLocale?: string | null | undefined;
  /** `navigator.languages`, en el orden de preferencia de la persona. */
  readonly browser?: readonly string[] | undefined;
}

export function resolveLanguage({ stored, sessionLocale, browser = [] }: LanguageSources): Language {
  const fromBrowser = browser.map(languageOf).find((language) => language !== null);
  return stored ?? languageOf(sessionLocale) ?? fromBrowser ?? DEFAULT_LANGUAGE;
}

export interface LanguageStorage {
  read(): Language | null;
  write(language: Language): void;
}

/** De donde sale y donde se refleja el idioma en un navegador. Sin entorno (las pruebas de las vistas), la SPA queda en espanol. */
export interface LanguageEnv {
  readonly storage: LanguageStorage | null;
  readonly browserLanguages: () => readonly string[];
  /** El documento cuyo `<html lang>` y cuyo titulo siguen al idioma. */
  readonly document: Pick<Document, "documentElement" | "title"> | null;
}

const NO_ENV: LanguageEnv = { storage: null, browserLanguages: () => [], document: null };

let env: LanguageEnv = NO_ENV;
let current: Language = DEFAULT_LANGUAGE;
// La eleccion de esta carga de pagina: vale aunque el navegador no deje guardar (modo privado, almacenamiento bloqueado).
let chosen: Language | null = null;
let sessionLocale: string | null = null;
const listeners = new Set<() => void>();

function apply(next: Language): void {
  const changed = next !== current;
  current = next;
  if (env.document !== null) {
    env.document.documentElement.lang = LANGUAGE_TAGS[next];
    env.document.title = TITLES[next];
  }
  if (changed) for (const listener of [...listeners]) listener();
}

function resolved(): Language {
  return resolveLanguage({ stored: chosen ?? env.storage?.read() ?? null, sessionLocale, browser: env.browserLanguages() });
}

export function getLanguage(): Language {
  return current;
}

export function subscribeLanguage(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Al arrancar la pagina (`main.tsx`), antes de pintar: fija el entorno y el idioma inicial. Sin argumento vuelve al estado de fabrica. */
export function initLanguage(next: LanguageEnv = NO_ENV): void {
  env = next;
  chosen = null;
  sessionLocale = null;
  apply(resolved());
}

/** La persona elige el idioma en el selector: cambia ya, sin recargar, y queda guardado. */
export function chooseLanguage(language: Language): void {
  chosen = language;
  env.storage?.write(language);
  apply(language);
}

/** La sesion cambio (`get_me` respondio, o se cerro): su `locale` cuenta solo si la persona no ha elegido un idioma. */
export function adoptSessionLocale(locale: string | null): void {
  sessionLocale = locale;
  apply(resolved());
}

export function browserLanguageEnv(win: Window, storage: LanguageStorage | null): LanguageEnv {
  return {
    storage,
    browserLanguages: () => (win.navigator.languages.length > 0 ? win.navigator.languages : [win.navigator.language]),
    document: win.document,
  };
}
