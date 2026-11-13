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
const MESSAGES = read("messages.es.json") as { ui: Record<string, string>; notice: Record<string, string>; code: Record<string, string> };
const LABELS = read("labels.es.json") as Record<string, Record<string, string>>;

/** Los textos salen del catalogo (los mismos que muestra la SPA): Playwright no importa JSON, asi que se lee el archivo. */
export const ui = (key: string, params: Record<string, string> = {}): string => {
  const text = MESSAGES.ui[key];
  if (text === undefined) throw new Error(`ui.${key} no existe`);
  return text.replace(/\{(\w+)\}/g, (_, name: string) => params[name] ?? "");
};
export const notice = (key: string): string => MESSAGES.notice[key] ?? key;
export const label = (group: string, value: string): string => LABELS[group]?.[value] ?? value;
export const problemCode = (code: string): string => MESSAGES.code[code] ?? code;

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
export async function loginAs(page: Page, role: Role, path = "/"): Promise<void> {
  await page.goto(path);
  await page.getByRole("button", { name: ui("login_button") }).click();
  await page.waitForURL(/\/protocol\/openid-connect\/auth\?/);
  await page.selectOption("#username", role);
  await page.click("#kc-login");
  await expect(page.getByRole("button", { name: ui("logout_button") })).toBeVisible();
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
