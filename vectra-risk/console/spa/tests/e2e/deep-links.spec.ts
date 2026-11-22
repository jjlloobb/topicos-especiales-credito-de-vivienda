// H-12 («los enlaces directos no se conservan»), en un navegador real sobre el BUILD con la CSP de U2 y el emisor de prueba: una carga
// completa de una ruta de la SPA (ruta + query) pasa por el login por redireccion y termina en ESA ruta, con el login silencioso
// (`prompt=none`, con sesion en el emisor) y con el interactivo (sin sesion). Los tokens viven en memoria, asi que cada `goto` y cada
// recarga repiten el login. El destino viaja en la clave transitoria del flujo: al terminar no queda nada en el almacenamiento.
import { type Page, expect, test } from "@playwright/test";
import { CASES, control, FREEZE_ID, label, loginAs, ORIGIN, ui } from "./support";

test.use({ baseURL: ORIGIN });

const AUTHORIZE = "/protocol/openid-connect/auth";
const location = (page: Page): string => {
  const url = new URL(page.url());
  return `${url.pathname}${url.search}`;
};
// La URL se espera con `expect.poll`: el boton de la sesion aparece un instante antes de que el enrutador navegue de `/` al destino.
const logoutButton = (page: Page) => page.getByRole("button", { name: ui("logout_button") });
const sessionKeys = (page: Page): Promise<string[]> => page.evaluate(() => Object.keys(sessionStorage));

/** Las solicitudes de la bandeja al BFF desde este punto (para ver con que filtro se pidio). */
function watchInbox(page: Page): URL[] {
  const calls: URL[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/console/cases") calls.push(url);
  });
  return calls;
}

/** Carga completa de `path` SIN sesion en el emisor: `prompt=none` falla, queda el login interactivo y se entra como `role`. */
async function openWithoutSession(page: Page, path: string, role: string): Promise<void> {
  await page.goto(path);
  await page.getByRole("button", { name: ui("login_button") }).click();
  await page.waitForURL(new RegExp(AUTHORIZE.replaceAll("/", "\\/")));
  await page.selectOption("#username", role);
  await page.click("#kc-login");
  await expect(logoutButton(page)).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await control.reset(page);
});

test("sin sesion: el enlace a la bandeja con filtro y pagina sobrevive al login interactivo", async ({ page }) => {
  const calls = watchInbox(page);
  await openWithoutSession(page, "/casos?state=no_disponible", "analista");
  await expect(page.getByRole("heading", { name: ui("view_cases") })).toBeVisible();
  await expect.poll(() => location(page)).toBe("/casos?state=no_disponible");
  await expect(page.getByRole("table")).toBeVisible();
  // la bandeja se pidio CON el filtro (antes se pedian los estados por omision) y solo muestra ese estado
  expect(calls.at(-1)?.searchParams.getAll("state")).toEqual(["no_disponible"]);
  const rows = page.getByRole("row").filter({ has: page.getByRole("cell") });
  await expect(rows).toHaveCount(2);
  await expect(rows.filter({ hasText: label("CASE_STATES", "no_disponible") })).toHaveCount(2);
  await expect(page.getByRole("button", { name: label("CASE_STATES", "no_disponible"), exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(await sessionKeys(page)).toEqual([]); // el destino viajo en la clave del flujo, que ya no existe
});

test("con sesion en el emisor: el enlace directo y la recarga conservan ruta y query (prompt=none)", async ({ page }) => {
  await loginAs(page, "analista");
  const calls = watchInbox(page);
  await page.goto("/casos?state=listo&page=2"); // carga completa: tokens perdidos, login silencioso
  await expect(logoutButton(page)).toBeVisible();
  await expect(page.getByRole("heading", { name: ui("view_cases") })).toBeVisible();
  await expect.poll(() => location(page)).toBe("/casos?state=listo&page=2");
  await expect.poll(() => calls.at(-1)?.searchParams.get("page")).toBe("2");
  expect(calls.at(-1)?.searchParams.getAll("state")).toEqual(["listo"]);
  await page.reload();
  await expect(logoutButton(page)).toBeVisible();
  await expect.poll(() => location(page)).toBe("/casos?state=listo&page=2");
  expect(await sessionKeys(page)).toEqual([]);
});

test("el detalle de un caso: enlace directo sin sesion, y recarga (F5) dentro del detalle", async ({ page }) => {
  const path = `/casos/${CASES.decidido}`;
  await openWithoutSession(page, path, "analista");
  await expect(page.getByRole("heading", { name: ui("decision_recorded_title") })).toBeVisible();
  await expect.poll(() => location(page)).toBe(path);
  await page.reload();
  await expect(logoutButton(page)).toBeVisible();
  await expect(page.getByRole("heading", { name: ui("decision_recorded_title") })).toBeVisible();
  await expect.poll(() => location(page)).toBe(path);
});

test("el paquete de un congelamiento y el detalle de un modelo: enlace directo y recarga", async ({ page }) => {
  const freeze = `/congelamientos/${FREEZE_ID}`;
  await openWithoutSession(page, freeze, "cumplimiento");
  await expect(page.getByRole("heading", { name: ui("freeze_context_title") })).toBeVisible();
  await expect.poll(() => location(page)).toBe(freeze);
  await page.reload();
  await expect(page.getByRole("heading", { name: ui("freeze_context_title") })).toBeVisible();
  await expect.poll(() => location(page)).toBe(freeze);
  await page.goto("/modelos/mv-activo");
  await expect(page.getByRole("heading", { name: ui("validation_title") })).toBeVisible();
  await expect.poll(() => location(page)).toBe("/modelos/mv-activo");
});

test("no se restaura lo que no es una ruta de la SPA ni una ruta de otro rol: inicio del rol", async ({ page }) => {
  await loginAs(page, "ingeniero_riesgo");
  await expect.poll(() => location(page)).toBe("/modelos");
  for (const path of ["/casos?state=listo", `/congelamientos/${FREEZE_ID}`, "/no/existe", "/callback"]) {
    await page.goto(path);
    await expect(logoutButton(page)).toBeVisible();
    await expect(page.getByRole("heading", { name: ui("view_models") })).toBeVisible();
    await expect.poll(() => location(page), path).toBe("/modelos");
    expect(new URL(page.url()).origin).toBe(ORIGIN);
  }
});

test("`/` sigue llevando al inicio del rol, y el destino no se repite en la carga siguiente", async ({ page }) => {
  await loginAs(page, "analista");
  await page.goto("/casos?state=no_disponible");
  await expect(logoutButton(page)).toBeVisible();
  await expect.poll(() => location(page)).toBe("/casos?state=no_disponible");
  await page.goto("/");
  await expect(logoutButton(page)).toBeVisible();
  await expect.poll(() => location(page)).toBe("/casos");
});
