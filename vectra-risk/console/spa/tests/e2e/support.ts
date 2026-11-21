// NFR-U10-63: el extremo a extremo con dobles (Playwright; con Keycloak y los servicios reales es de U12 Paso 18).
// Soporte de las pruebas con navegador de la SPA real (U10-T04; solo pruebas; no es una especificacion). El servidor es el BUILD servido con
// `vite preview` y las cabeceras del perfil `spa` de U2 (`vite.e2e.config.ts`); el BFF es el real sobre los dobles (`bff_e2e_server.py`
// con `VECTRA_E2E_DEMO=1`). Sin `waitForTimeout`: se espera por estado.
import { type BrowserContext, type Page, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const read = (...parts: string[]): unknown => JSON.parse(readFileSync(resolve(HERE, "..", "..", "src", "i18n", ...parts), "utf-8"));
type Messages = { ui: Record<string, string>; notice: Record<string, string>; code: Record<string, string>; reason: Record<string, string> };
type Labels = Record<string, Record<string, string>>;

export type Lang = "es" | "en";

/** Los textos de un idioma, como los muestra la SPA. */
export interface Texts {
  readonly lang: Lang;
  readonly ui: (key: string, params?: Record<string, string>) => string;
  readonly notice: (key: string) => string;
  readonly label: (group: string, value: string) => string;
  readonly problemCode: (code: string) => string;
  /** Todas las cadenas del catalogo (mensajes y etiquetas). */
  readonly all: readonly string[];
}

/** Los textos salen del catalogo (los mismos que muestra la SPA): Playwright no importa JSON, asi que se lee el archivo. */
export function texts(lang: Lang): Texts {
  const messages = read(`messages.${lang}.json`) as Messages;
  const labels = read(`labels.${lang}.json`) as Labels;
  return {
    lang,
    ui: (key, params = {}) => {
      const text = messages.ui[key];
      if (text === undefined) throw new Error(`ui.${key} no existe`);
      return text.replace(/\{(\w+)\}/g, (_, name: string) => params[name] ?? "");
    },
    notice: (key) => messages.notice[key] ?? key,
    label: (group, value) => labels[group]?.[value] ?? value,
    problemCode: (code) => messages.code[code] ?? code,
    all: [...Object.values(messages.ui), ...Object.values(messages.notice), ...Object.values(messages.code), ...Object.values(messages.reason), ...Object.values(labels).flatMap((group) => Object.values(group))],
  };
}

/** El espanol es el idioma por omision de la SPA y de las pruebas: `ui`, `label`... sin mas son los textos en espanol. */
export const ES = texts("es");
export const EN = texts("en");
export const { ui, notice, label, problemCode } = ES;

/** Las claves de las preferencias en el almacenamiento local (`src/preferences/storage.ts`). */
export const PREFERENCE_KEYS = { language: "vectra.console.language", theme: "vectra.console.theme" } as const;

/**
 * Deja guardadas las preferencias ANTES de cargar cualquier pagina del contexto, como si la persona las hubiera elegido en una visita anterior
 * (el login es una redireccion completa: cada carga las vuelve a leer del almacenamiento local).
 */
export async function seedPreferences(context: BrowserContext, preferences: { language?: Lang; theme?: "system" | "light" | "dark" }): Promise<void> {
  await context.addInitScript(
    ({ keys, values }) => {
      if (values.language !== undefined) window.localStorage.setItem(keys.language, values.language);
      if (values.theme !== undefined) window.localStorage.setItem(keys.theme, values.theme);
    },
    { keys: PREFERENCE_KEYS, values: preferences },
  );
}

/**
 * El tema del SISTEMA en las pruebas (`prefers-color-scheme`). `test.use({ colorScheme })` basta en Chromium; en el Firefox de Playwright la
 * emulacion se pierde en la primera navegacion a una pagina con `Cross-Origin-Opener-Policy` (el perfil `spa` de U2 la pone: el navegador
 * cambia de grupo de contextos) y hay que repetirla ya dentro del origen; despues se conserva en las navegaciones y recargas siguientes
 * (medido con Firefox 157). Por eso se entra primero a un recurso del origen que no es la SPA y se emula ahi, antes de cargar la SPA.
 */
export async function emulateSystemScheme(page: Page, scheme: "light" | "dark"): Promise<void> {
  await page.goto(`${ORIGIN}/theme-boot.js`);
  await page.emulateMedia({ colorScheme: scheme });
}

/** El boton de un selector de preferencias: su nombre accesible es el valor elegido y el nombre del control. */
export const languageButton = (page: Page, t: Texts = ES) => page.getByRole("button", { name: `${t.ui(`language_name_${t.lang}`)} ${t.ui("language_label")}`, exact: true });
export const themeButton = (page: Page, value: "system" | "light" | "dark" = "system", t: Texts = ES) =>
  page.getByRole("button", { name: `${t.ui(`theme_${value}`)} ${t.ui("theme_label")}`, exact: true });

/** Elige un idioma en el selector (desde el idioma `from`) y espera a que la pagina este en el nuevo. */
export async function chooseLanguage(page: Page, from: Texts, to: Texts): Promise<void> {
  await languageButton(page, from).click();
  await page.getByRole("listbox").getByRole("option", { name: to.ui(`language_name_${to.lang}`) }).click();
  await expect(languageButton(page, to)).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", to.lang);
}

/** Elige un tema en el selector. */
export async function chooseTheme(page: Page, from: "system" | "light" | "dark", to: "system" | "light" | "dark", t: Texts = ES): Promise<void> {
  await themeButton(page, from, t).click();
  await page.getByRole("listbox").getByRole("option", { name: t.ui(`theme_${to}`) }).click();
  await expect(themeButton(page, to, t)).toBeVisible();
}

/**
 * Los textos del catalogo en ESPANOL que siguen a la vista con la pagina en ingles (texto, `aria-label`, `data-label`, `title`, `alt`,
 * `placeholder`): debe ser una lista vacia. No cuentan los textos que se escriben igual en los dos idiomas ni los que llevan marcadores
 * (`{nombre}`); los textos que entrega el servidor (narrativas, nombres, identificadores) no estan en el catalogo y no se miran.
 */
export async function spanishLeft(page: Page): Promise<string[]> {
  const english = new Set(EN.all);
  const spanish = ES.all.filter((text) => !english.has(text) && !text.includes("{"));
  return page.evaluate((candidates) => {
    const shown = new Set<string>();
    for (const node of document.body.querySelectorAll("*")) {
      for (const child of node.childNodes) if (child.nodeType === Node.TEXT_NODE && child.textContent !== null) shown.add(child.textContent.trim());
      for (const attribute of ["aria-label", "data-label", "title", "alt", "placeholder"]) {
        const value = node.getAttribute(attribute);
        if (value !== null) shown.add(value);
      }
    }
    return candidates.filter((text) => shown.has(text));
  }, spanish);
}

export const ORIGIN = process.env["VECTRA_E2E_APP_ORIGIN"] ?? "http://127.0.0.1:47174";
const DOUBLES = `http://127.0.0.1:${process.env["VECTRA_E2E_APP_DOUBLES_PORT"] ?? "47181"}`;

export type Role = "analista" | "ingeniero_riesgo" | "cro" | "cumplimiento";

// Los identificadores del mundo de `bff_e2e_world.py`.
export const CASES = {
  listo: "00000000-0000-0000-0000-000000000001",
  noDisponible: "00000000-0000-0000-0000-000000000002",
  decidido: "00000000-0000-0000-0000-000000000003",
  anonimizado: "00000000-0000-0000-0000-000000000004",
  sincronizacion: "00000000-0000-0000-0000-000000000005",
  congelado: "00000000-0000-0000-0000-000000000006",
  revision: "00000000-0000-0000-0000-000000000007",
  vencido: "00000000-0000-0000-0000-000000000008",
  bajaConfianza: "00000000-0000-0000-0000-000000000009",
  inexistente: "00000000-0000-0000-0000-0000000000ff",
} as const;
export const FREEZE_ID = "freeze-mv-congelado";

/** El control de pruebas del servidor de dobles (`/__e2e/**`): no pasa por el proxy de la SPA, se le habla al puerto de los dobles. */
export const control = {
  async reset(page: Page): Promise<void> {
    await page.request.post(`${DOUBLES}/__e2e/reset`);
    await page.request.post(`${ORIGIN}/auth/__e2e/reset`);
  },
  async down(page: Page, double: string, down = true): Promise<void> {
    await page.request.post(`${DOUBLES}/__e2e/down`, { data: { double, down } });
  },
  async forceMfaRequired(page: Page, times = 1): Promise<void> {
    await page.request.post(`${DOUBLES}/__e2e/force-mfa-required`, { data: { times } });
  },
  async count(page: Page, double: string, method: string, template: string): Promise<number> {
    const response = await page.request.get(`${DOUBLES}/__e2e/count`, { params: { double, method, template } });
    return ((await response.json()) as { count: number }).count;
  },
};

/** Inicio de sesion interactivo como `role`: la SPA redirige al emisor de prueba, que deja elegir al usuario (los cuatro roles). */
export async function loginAs(page: Page, role: Role, path = "/", t: Texts = ES): Promise<void> {
  await page.goto(path);
  await page.getByRole("button", { name: t.ui("login_button") }).click();
  await page.waitForURL(/\/protocol\/openid-connect\/auth\?/);
  await page.selectOption("#username", role);
  await page.click("#kc-login");
  await expect(page.getByRole("button", { name: t.ui("logout_button") })).toBeVisible();
}

/** Navega dentro de la SPA sin recargar (el enrutador responde al historial): los tokens viven en memoria y una recarga los perderia. */
export async function goTo(page: Page, path: string): Promise<void> {
  await page.evaluate((target) => {
    window.history.pushState(null, "", target);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, path);
}

/** Un evento `securitypolicyviolation` visto en cualquier pagina del contexto (la principal, la ventana del step-up, las pestanas). */
export interface CspViolation {
  readonly page: string;
  readonly directive: string;
  readonly blocked: string;
  readonly sample: string;
}

/**
 * Instala, **antes de cargar cualquier pagina del contexto**, un oyente de `securitypolicyviolation` en el documento (en captura). Cada evento
 * pasa a Node por un enlace del contexto, que sobrevive a las navegaciones (el login es una redireccion completa). Devuelve la lista viva.
 */
export async function watchCsp(context: BrowserContext): Promise<CspViolation[]> {
  const found: CspViolation[] = [];
  await context.exposeBinding("__reportCspViolation", (source, violation: Omit<CspViolation, "page">) => {
    found.push({ ...violation, page: source.page.url() });
  });
  await context.addInitScript(() => {
    document.addEventListener(
      "securitypolicyviolation",
      (event) => {
        void (window as never as { __reportCspViolation: (v: unknown) => Promise<void> }).__reportCspViolation({
          directive: event.effectiveDirective,
          blocked: event.blockedURI,
          sample: event.sample,
        });
      },
      true,
    );
  });
  return found;
}
