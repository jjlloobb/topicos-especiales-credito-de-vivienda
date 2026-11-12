// U10-T03, ronda 2 (F-03; decision del usuario, 2026-11-12): el login por REDIRECCION con la SPA REAL (`index.html`, `src/main.tsx`, el
// `UserManager` de `oidc-client-ts`) en Chromium y Firefox, contra el emisor OIDC de prueba y el BFF con dobles. En cada paso se lee el
// almacenamiento: `localStorage` vacio, ninguna cookie de la SPA (la del emisor es `VECTRA_SSO`, de la ruta `/auth`), `IndexedDB` sin
// bases y, en `sessionStorage`, como mucho la clave del flujo en curso (`oidc.<state>`), sin ningun token, y que desaparece tras el
// callback. Pasos: login interactivo -> sesion; recarga -> `prompt=none` -> sesion sin interaccion; recarga con la sesion del emisor
// cerrada -> login interactivo, sin bucle de redirecciones. Sin `waitForTimeout`: se espera por estado.
import { type BrowserContext, type Page, expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// Los textos salen del catalogo; Playwright no importa JSON, asi que se lee el archivo (los mismos textos que muestra la SPA).
const MESSAGES = JSON.parse(
  readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "src", "i18n", "messages.es.json"), "utf-8"),
) as { ui: Record<string, string> };
const ui = (key: string, params: Record<string, string> = {}): string =>
  (MESSAGES.ui[key] ?? key).replace(/\{(\w+)\}/g, (_, name: string) => params[name] ?? "");

const ORIGIN = process.env["VECTRA_E2E_APP_ORIGIN"] ?? "http://127.0.0.1:47174";
const ISSUER_COOKIE = "VECTRA_SSO";
const AUTHORIZE = "/protocol/openid-connect/auth";

test.use({ baseURL: ORIGIN });

interface Stats {
  authorize: number;
  token: number;
  end_session: number;
}

interface Snapshot {
  local: number;
  sessionKeys: string[];
  sessionDump: string;
  cookie: string;
  databases: number;
  url: string;
}

const stats = async (page: Page): Promise<Stats> => (await (await page.request.get("/auth/__e2e/stats")).json()) as Stats;

/** El almacenamiento del origen, leido en la pagina actual (la SPA, el formulario del emisor o `/callback`: son el mismo origen). */
const snapshot = (page: Page): Promise<Snapshot> =>
  page.evaluate(async () => ({
    local: localStorage.length,
    sessionKeys: Object.keys(sessionStorage),
    sessionDump: JSON.stringify(Object.entries(sessionStorage)),
    cookie: document.cookie,
    databases: (await indexedDB.databases()).length,
    url: location.pathname + location.search,
  }));

/** Ninguna cookie salvo la del emisor (`httpOnly`, ruta `/auth`): la SPA no pone cookies. */
async function expectNoSpaCookies(context: BrowserContext): Promise<void> {
  const names = (await context.cookies()).map((cookie) => cookie.name);
  expect(names.filter((name) => name !== ISSUER_COOKIE)).toEqual([]);
}

/** `localStorage` vacio, sin cookies de la SPA, sin IndexedDB; `sessionStorage` solo con la clave del flujo y sin tokens. */
async function expectStorage(page: Page, context: BrowserContext, flowKeys: number): Promise<Snapshot> {
  const state = await snapshot(page);
  expect(state.local).toBe(0);
  expect(state.cookie).toBe("");
  expect(state.databases).toBe(0);
  expect(state.sessionKeys).toHaveLength(flowKeys);
  for (const key of state.sessionKeys) expect(key).toMatch(/^oidc\.[\w-]+$/);
  expect(state.sessionDump).not.toMatch(/access_token|refresh_token|id_token|"profile"/);
  await expectNoSpaCookies(context);
  return state;
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/auth/__e2e/reset");
});

test("login por redireccion, recarga con prompt=none y recarga con la sesion del emisor cerrada (sin bucle)", async ({ page, context }) => {
  const authorizeRequests: URL[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.endsWith(AUTHORIZE) && request.resourceType() === "document") authorizeRequests.push(url);
  });
  const loginButton = page.getByRole("button", { name: ui("login_button") });
  const logoutButton = page.getByRole("button", { name: ui("logout_button") });

  // 1. carga inicial sin sesion: UNA redireccion prompt=none, el emisor responde login_required y queda el login interactivo
  await page.goto("/");
  await expect(loginButton).toBeVisible();
  expect(authorizeRequests.map((url) => url.searchParams.get("prompt"))).toEqual(["none"]);
  expect((await stats(page)).authorize).toBe(1);
  expect(await expectStorage(page, context, 0)).toMatchObject({ url: "/" }); // la URL no conserva `error` ni `state`
  await expect(page.getByRole("alert")).toHaveCount(0); // login_required no es un fallo

  // 2. clic en «Iniciar sesion»: redireccion completa al formulario del emisor; ahi (mismo origen) vive la clave del flujo
  await loginButton.click();
  await page.waitForURL(/\/protocol\/openid-connect\/auth\?/);
  const form = await expectStorage(page, context, 1);
  expect(form.sessionDump).toContain("code_verifier"); // el estado transitorio que sobrevive a la redireccion
  expect(authorizeRequests.at(-1)?.searchParams.get("prompt")).toBeNull();
  expect(authorizeRequests.at(-1)?.searchParams.get("code_challenge_method")).toBe("S256");
  expect(authorizeRequests.at(-1)?.searchParams.get("nonce")).toMatch(/^[0-9a-f-]{36}$/);
  await page.click("#kc-login");

  // 3. de vuelta: la SPA canjea en memoria, pide get_me y muestra el rol; la URL queda limpia y la clave del flujo desaparece
  await expect(logoutButton).toBeVisible();
  expect(await page.getByText(ui("session_role", { role: "Analista" })).count()).toBe(1);
  expect(await expectStorage(page, context, 0)).toMatchObject({ url: "/" });
  expect((await stats(page)).token).toBe(1);

  // 4. recarga: los tokens estaban en memoria y se perdieron; prompt=none con la sesion del emisor entra sin interaccion
  const before = authorizeRequests.length;
  await page.reload();
  await expect(logoutButton).toBeVisible();
  expect(authorizeRequests.slice(before).map((url) => url.searchParams.get("prompt"))).toEqual(["none"]);
  expect(await expectStorage(page, context, 0)).toMatchObject({ url: "/" });
  expect((await stats(page)).token).toBe(2);

  // 5. se cierra la sesion del emisor y se recarga: login_required -> login interactivo, UNA sola redireccion, sin bucle
  await context.clearCookies({ name: ISSUER_COOKIE });
  const beforeClosed = authorizeRequests.length;
  await page.reload();
  await expect(loginButton).toBeVisible();
  await page.waitForLoadState("networkidle");
  expect(authorizeRequests.slice(beforeClosed).map((url) => url.searchParams.get("prompt"))).toEqual(["none"]);
  expect((await stats(page)).authorize).toBe(authorizeRequests.length);
  expect(await expectStorage(page, context, 0)).toMatchObject({ url: "/" });
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("logout: end_session, sin sesion en el emisor y de vuelta al login", async ({ page, context }) => {
  await page.goto("/");
  await page.getByRole("button", { name: ui("login_button") }).click();
  await page.click("#kc-login");
  const logoutButton = page.getByRole("button", { name: ui("logout_button") });
  await expect(logoutButton).toBeVisible();
  await logoutButton.click();
  await expect(page.getByRole("button", { name: ui("login_button") })).toBeVisible();
  expect((await stats(page)).end_session).toBe(1);
  expect(await expectStorage(page, context, 0)).toMatchObject({ url: "/" });
  expect((await context.cookies()).map((cookie) => cookie.name)).not.toContain(ISSUER_COOKIE);
});
