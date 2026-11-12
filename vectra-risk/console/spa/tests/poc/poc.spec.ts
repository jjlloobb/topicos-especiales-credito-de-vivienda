// CA-1 de U10-T03, la puerta del Paso 10: el step-up en una ventana emergente (P-U10-07; BR-U10-06), en Chromium y Firefox,
// contra el emisor OIDC de prueba. Las cuatro lineas de la aceptacion del plan:
//   1. el token nuevo trae `acr = mfa`;
//   2. `sessionStorage` y `localStorage` quedan vacios (ventana principal y emergente);
//   3. un `window.open` llamado fuera del clic queda bloqueado (P-2);
//   4. un `postMessage` de otro origen se ignora.
// Sin `waitForTimeout`: se espera por estado.
import { type BrowserContext, type Page, expect, test } from "@playwright/test";

const POC = "/tests/poc/index.html";
const OTHER_ORIGIN_HOST = "localhost";

interface PocState {
  opens: { inClick: boolean }[];
  result: { acr: unknown; auth_time: unknown } | null;
  sent: { justification: string }[];
  messages: { origin: string; fromPopup: boolean }[];
}

const poc = (page: Page): Promise<PocState> => page.evaluate(() => (window as never as { __poc: PocState }).__poc);
const storage = (page: Page): Promise<{ session: number; local: number }> =>
  page.evaluate(() => ({ session: sessionStorage.length, local: localStorage.length }));
const tokenCalls = async (page: Page): Promise<number> =>
  ((await (await page.request.get("/auth/__e2e/stats")).json()) as { token: number }).token;

/** Hace clic en el boton y devuelve la ventana emergente, ya en el formulario del emisor. */
async function openStepUp(page: Page, context: BrowserContext): Promise<Page> {
  const [popup] = await Promise.all([context.waitForEvent("page"), page.click("#verify")]);
  await popup.waitForURL(/\/protocol\/openid-connect\/auth\?/);
  return popup;
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/auth/__e2e/reset");
  await page.goto(POC);
});

test("el token nuevo trae acr = mfa y el estado queda en memoria", async ({ page, context }) => {
  const before = Math.floor(Date.now() / 1000);
  const popup = await openStepUp(page, context);
  const url = new URL(popup.url());
  expect(url.searchParams.get("prompt")).toBe("login");
  expect(url.searchParams.get("max_age")).toBe("0");
  expect(url.searchParams.get("acr_values")).toBe("mfa");
  expect(url.searchParams.get("redirect_uri")).toBe(`${new URL(page.url()).origin}/stepup-callback`);
  expect(url.searchParams.get("code_challenge_method")).toBe("S256");
  expect(url.searchParams.get("nonce")).toMatch(/^[0-9a-f-]{36}$/);
  expect(await storage(popup)).toEqual({ session: 0, local: 0 });

  await popup.click("#kc-login", { noWaitAfter: true });
  await expect(page.locator("#status")).toHaveText("done");
  const state = await poc(page);
  expect(state.result?.acr).toBe("mfa");
  expect(Number(state.result?.auth_time)).toBeGreaterThanOrEqual(before);
  expect(state.sent).toEqual([{ justification: "justificacion de la PoC" }]); // un solo reenvio, con el mismo cuerpo
  expect(await storage(page)).toEqual({ session: 0, local: 0 });
  expect(page.url()).toBe(new URL(POC, page.url()).toString()); // la ventana principal no se recargo ni cambio de URL
  expect(await tokenCalls(page)).toBe(1);
});

test("el callback no guarda nada ni canjea: suelto, sin ventana de origen, no hace nada", async ({ context }) => {
  const loose = await context.newPage();
  await loose.goto("/stepup-callback?code=abc&state=xyz");
  expect(await storage(loose)).toEqual({ session: 0, local: 0 });
  expect(loose.url()).toContain("/stepup-callback?code=abc&state=xyz");
  expect(await tokenCalls(loose)).toBe(0);
});

test("window.open se llama de forma sincrona dentro del clic", async ({ page, context }) => {
  const popup = await openStepUp(page, context);
  expect((await poc(page)).opens).toEqual([{ inClick: true }]);
  await popup.close();
  await expect(page.locator("#status")).toHaveText("failed:closed"); // cerrada sin terminar: sin reenvio
  expect((await poc(page)).sent).toEqual([]);
});

test("un window.open fuera del clic queda bloqueado (P-2)", async ({ page, context }) => {
  // La pagina llama a `window.open` al cargarse (`?probe=open-outside-click`): no hay clic ni activacion de usuario detras.
  // El bloqueador de ventanas emergentes, encendido en `playwright.config.ts`, lo bloquea (devuelve `null`) y no nace ninguna pagina.
  await page.goto(`${POC}?probe=open-outside-click`);
  const state = await page.evaluate(() => (window as never as { __poc: PocState & { outsideClickBlocked: boolean } }).__poc);
  expect(state.opens).toEqual([{ inClick: false }]);
  expect(state.outsideClickBlocked).toBe(true);
  expect(context.pages()).toHaveLength(1);
});

test("un postMessage de otro origen se ignora aunque traiga el state vigente", async ({ page, context }) => {
  const popup = await openStepUp(page, context);
  const state = new URL(popup.url()).searchParams.get("state") ?? "";
  const other = `http://${OTHER_ORIGIN_HOST}:${new URL(page.url()).port}`;
  // Navegacion iniciada por la propia ventana (no por el navegador): asi conserva `window.opener` al cambiar de origen.
  await popup.evaluate((target) => {
    window.location.href = target;
  }, `${other}/tests/poc/attacker.html?code=robado&state=${state}`);
  // el mensaje llega a la ventana principal (de la ventana emergente y con el state vigente) pero con otro origen
  await expect.poll(async () => (await poc(page)).messages).toEqual([{ origin: other, fromPopup: true }]);
  await expect(page.locator("#status")).toHaveText("waiting");
  expect(await tokenCalls(page)).toBe(0);
  expect((await poc(page)).sent).toEqual([]);
  await popup.close();
  await expect(page.locator("#status")).toHaveText("failed:closed");
  expect(await tokenCalls(page)).toBe(0);
});
