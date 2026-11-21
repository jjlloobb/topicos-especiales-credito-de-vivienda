// Pasada de usabilidad del 2026-11-21, en un navegador real (Chromium y Firefox) sobre el BUILD con la CSP de U2: lo que jsdom no puede mostrar.
// El portapapeles de verdad dentro del clic (sin relajar ninguna politica), el titulo del documento por pantalla, el foco al cambiar de ruta,
// «Saltar al contenido» como primera parada del teclado, la direccion del caso pegada en «Ir al caso» y la bandeja vacia que propone quitar el filtro.
import { expect, test } from "@playwright/test";
import { CASES, control, EN, ES, FREEZE_ID, chooseLanguage, goTo, label, loginAs, ORIGIN, ui, watchCsp } from "./support";
import { openCase } from "./tour";

test.use({ baseURL: ORIGIN });

test.beforeEach(async ({ page }) => {
  await control.reset(page);
});

const titled = (view: string, t = ES): string => t.ui("document_title_view", { view: t.ui(view) });

test("el identificador del caso se ve en la bandeja (abreviado) y en el detalle (completo), y «Copiar» lo deja en el portapapeles sin violar la CSP", async ({ page, context }, info) => {
  const violations = await watchCsp(context);
  // Leer el portapapeles pide permiso (solo Chromium lo deja conceder); al conceder una lista, lo que no este en ella queda negado: van los dos.
  if (info.project.name === "chromium") await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await loginAs(page, "analista");
  const row = page.getByRole("row").filter({ hasText: "B. P." });
  const short = row.locator("code");
  await expect(short).toHaveText(`${CASES.decidido.slice(0, 8)}…`);
  await expect(short).toHaveAttribute("title", CASES.decidido);
  await row.getByRole("button", { name: ui("case_id_copy_of", { applicant: "B. P." }) }).click();
  await expect(row.getByRole("status")).toHaveText(ui("copy_done"));
  if (info.project.name === "chromium") expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(CASES.decidido);

  await openCase(page, CASES.listo);
  const line = page.locator(".case-id");
  await expect(line.locator("code")).toHaveText(CASES.listo);
  await line.getByRole("button", { name: ui("case_id_copy") }).click();
  await expect(line.getByRole("status")).toHaveText(ui("copy_done"));
  if (info.project.name === "chromium") expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(CASES.listo);
  expect(violations).toEqual([]);
});

test("si el navegador niega el portapapeles, «Copiar» no falla en silencio: muestra el identificador completo, seleccionado", async ({ page, context }, info) => {
  test.skip(info.project.name !== "chromium", "solo Chromium deja negar el permiso del portapapeles desde la prueba");
  await context.grantPermissions(["geolocation"]); // una lista sin `clipboard-write`: queda negado
  await loginAs(page, "analista");
  await openCase(page, CASES.listo);
  const line = page.locator(".case-id");
  await line.getByRole("button", { name: ui("case_id_copy") }).click();
  await expect(line.getByRole("status")).toHaveText(ui("copy_manual"));
  await expect(line.locator(".copy-fallback")).toHaveText(CASES.listo);
  expect(await page.evaluate(() => window.getSelection()?.toString())).toBe(CASES.listo);
});

test("el codigo de soporte de un error se puede copiar", async ({ page }) => {
  await loginAs(page, "analista");
  await goTo(page, `/casos/${CASES.inexistente}`);
  const alert = page.getByRole("alert");
  await expect(alert).toContainText(/[0-9a-f]{32}/);
  await alert.getByRole("button", { name: ui("support_code_copy") }).click();
  await expect(alert.getByRole("status")).toHaveText(ui("copy_done"));
});

test("«Ir al caso» acepta la direccion completa del caso pegada, con espacios, y solo usa el identificador", async ({ page }) => {
  await loginAs(page, "analista");
  await page.getByLabel(ui("go_to_case_label")).fill(`  ${ORIGIN}/casos/${CASES.decidido.toUpperCase()}?state=listo  `);
  await page.getByRole("button", { name: ui("go_to_case_button") }).click();
  await expect(page.getByRole("heading", { name: ui("decision_recorded_title") })).toBeVisible();
  const url = new URL(page.url());
  expect(`${url.pathname}${url.search}`).toBe(`/casos/${CASES.decidido}`);
});

test("el titulo del documento dice la pantalla (y sigue al idioma); al cambiar de pantalla el foco pasa al contenido y la pagina vuelve arriba", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 500 });
  await loginAs(page, "analista");
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page).toHaveTitle(titled("view_cases"));
  const open = page.getByRole("link", { name: ui("open_case", { applicant: "E. S." }) });
  await open.scrollIntoViewIfNeeded();
  await open.click();
  await expect(page.getByRole("heading", { name: ui("view_case_detail") })).toBeVisible();
  await expect(page).toHaveTitle(titled("view_case_detail"));
  await expect(page.getByRole("main")).toBeFocused();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await expect(page.locator("p[aria-live='polite'].visually-hidden")).toHaveText(ui("route_announcement", { view: ui("view_case_detail") }));
  await chooseLanguage(page, ES, EN);
  await expect(page).toHaveTitle(titled("view_case_detail", EN));
  await goTo(page, "/modelos");
  await expect(page).toHaveTitle(titled("no_access_title", EN));
  await page.getByRole("button", { name: EN.ui("logout_button") }).click();
  await expect(page.getByRole("button", { name: EN.ui("login_button") })).toBeVisible();
  await expect(page).toHaveTitle(EN.ui("document_title")); // sin sesion, el titulo general
});

test("«Saltar al contenido» es la primera parada del teclado, se ve al recibir el foco y lleva al contenido", async ({ page }) => {
  await loginAs(page, "cumplimiento");
  await expect(page.getByRole("table")).toBeVisible();
  const skip = page.getByRole("link", { name: ui("skip_to_content") });
  expect((await skip.boundingBox())?.y ?? 0).toBeLessThan(0); // fuera de la vista mientras no tiene el foco
  await page.keyboard.press("Tab");
  await expect(skip).toBeFocused();
  const box = await skip.boundingBox();
  expect(box?.y ?? -1).toBeGreaterThanOrEqual(0);
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(43.9);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  expect(new URL(page.url()).hash).toBe("");
  await goTo(page, `/congelamientos/${FREEZE_ID}`);
  await expect(page).toHaveTitle(titled("view_freeze_context"));
});

test("la bandeja vacia con un filtro propone quitarlo; «Mas filtros» cuenta los avanzados activos", async ({ page }) => {
  await loginAs(page, "analista", "/casos?state=en_evaluacion&channel=manual");
  await expect(page.getByText(ui("inbox_empty"))).toBeVisible();
  await expect(page.locator("details.more-filters > summary")).toContainText(ui("filters_active_one")); // el canal; el estado unico es un chip y no cuenta
  await page.getByRole("button", { name: ui("inbox_empty_clear") }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: label("CASE_STATES", "listo") }).first()).toBeVisible();
  expect(new URL(page.url()).search).toBe("");
  await expect(page.locator("details.more-filters > summary .badge")).toHaveCount(0);
});
