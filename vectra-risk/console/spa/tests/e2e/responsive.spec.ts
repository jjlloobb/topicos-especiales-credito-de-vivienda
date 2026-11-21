// El tema responsivo (NFR-U10-51; WCAG 1.4.10 «reflow»): en los cuatro anchos de corte (360, 768, 1024 y 1440 px) las vistas de las demos no
// provocan scroll horizontal, ni de la PAGINA ni de una region interna: por debajo de 768 px cada tabla pasa a tarjetas apiladas (cada celda
// con el titulo de su columna) sin dejar de ser una tabla; y los controles llegan al objetivo tactil de 44 px. Sobre el BUILD con la CSP de
// U2, como el resto de `tests/e2e`.
import { type Page, expect, test } from "@playwright/test";
import { CASES, control, FREEZE_ID, goTo, label, loginAs, ORIGIN, ui } from "./support";
import { openCase } from "./tour";

test.use({ baseURL: ORIGIN });

const VIEWPORTS = [
  { name: "movil (360)", width: 360, height: 740 },
  { name: "tableta (768)", width: 768, height: 1024 },
  { name: "portatil (1024)", width: 1024, height: 768 },
  { name: "escritorio ancho (1440)", width: 1440, height: 900 },
] as const;

/** La pagina no se desplaza en horizontal: el documento no es mas ancho que la ventana. */
async function expectNoPageOverflow(page: Page, where: string): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, `scroll horizontal de la pagina en ${where}`).toBeLessThanOrEqual(0);
}

/** Ninguna region de tabla se desplaza en horizontal, y por debajo de 768 px cada celda muestra el titulo de su columna. */
async function expectNoRegionOverflow(page: Page, where: string, width: number): Promise<void> {
  const regions = await page.evaluate(() =>
    [...document.querySelectorAll(".table-scroll")].map((region) => ({
      overflow: region.scrollWidth - region.clientWidth,
      table: (region.querySelector("table")?.getBoundingClientRect().right ?? 0) - document.documentElement.clientWidth,
      label: getComputedStyle(region.querySelector("tbody td[data-label]") ?? region, "::before").content,
      expected: region.querySelector("tbody td[data-label]")?.getAttribute("data-label") ?? null,
      display: getComputedStyle(region.querySelector("tbody tr") ?? region).display,
    })),
  );
  expect(regions.length, `tablas en ${where}`).toBeGreaterThan(0);
  for (const region of regions) {
    expect(region.overflow, `scroll horizontal de una tabla en ${where}`).toBeLessThanOrEqual(0);
    expect(region.table, `tabla fuera de la ventana en ${where}`).toBeLessThanOrEqual(0);
    if (width < 768) {
      expect(region.display, `fila como tarjeta en ${where}`).toBe("block");
      if (region.expected !== null) expect(region.label, `etiqueta de columna en ${where}`).toContain(region.expected);
    } else {
      expect(region.display, `fila de tabla en ${where}`).toBe("table-row");
    }
  }
}

test.beforeEach(async ({ page }) => {
  await control.reset(page);
});

for (const viewport of VIEWPORTS) {
  test(`${viewport.name}: bandeja y detalle del caso sin scroll horizontal de la pagina`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await loginAs(page, "analista");
    const region = page.getByRole("region", { name: ui("table_scroll_label", { name: ui("view_cases") }) });
    await expect(region).toBeVisible();
    await expect(region.getByRole("table")).toBeVisible();
    await expectNoPageOverflow(page, "la bandeja");
    await expectNoRegionOverflow(page, "la bandeja", viewport.width);
    await expect(region.getByRole("row")).toHaveCount(9); // la cabecera y las 8 filas siguen siendo filas de una tabla, tambien como tarjetas
    await expect(region.getByRole("link", { name: ui("open_case", { applicant: "B. P." }) })).toBeVisible();
    await region.focus(); // la region recibe el foco del teclado
    await expect(region).toBeFocused();
    // «Mas filtros» esta cerrado: los chips a la vista y las casillas ocultas; al abrirlo, sin desbordes
    const vencido = page.getByRole("checkbox", { name: label("CASE_STATES", "vencido") });
    await expect(vencido).toBeHidden();
    await page.getByText(ui("filters_more")).click();
    await expect(vencido).toBeVisible();
    await expectNoPageOverflow(page, "la bandeja con «Mas filtros» abierto");
    await page.getByText(ui("filters_more")).click();
    await expect(vencido).toBeHidden();
    await expect(page.getByRole("navigation", { name: ui("nav_label") }).getByRole("link").first()).toBeVisible(); // el menu sigue a la vista (hace wrap)
    for (const name of [ui("page_first"), ui("page_previous"), ui("page_next"), ui("page_last"), ui("go_to_case_button"), ui("logout_button")]) {
      const box = await page.getByRole("button", { name, exact: true }).boundingBox();
      expect(box?.height ?? 0, `alto de «${name}»`).toBeGreaterThanOrEqual(43.9); // 44 px; Firefox devuelve 43,99999 por el redondeo de subpixel
    }
    await openCase(page, CASES.listo);
    await expectNoPageOverflow(page, "el detalle del caso");
    await page.getByText(ui("application_toggle")).click();
    await expect(page.locator(".free-text")).toBeVisible();
    await expectNoPageOverflow(page, "el detalle con la solicitud desplegada");
    await page.getByRole("button", { name: ui("explanation_button") }).click();
    await expect(page.getByText(ui("explanation_narrative"))).toBeVisible();
    await expectNoPageOverflow(page, "el detalle con la explicacion");
  });

  test(`${viewport.name}: congelamientos, paquete de contexto y dialogo dentro de la pantalla`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await loginAs(page, "cumplimiento");
    await expect(page.getByRole("table")).toBeVisible();
    await expectNoPageOverflow(page, "la lista de congelamientos");
    await expectNoRegionOverflow(page, "la lista de congelamientos", viewport.width);
    await goTo(page, "/modelos");
    await expect(page.getByRole("link", { name: "mv-activo" })).toBeVisible();
    await expectNoPageOverflow(page, "modelos");
    await expectNoRegionOverflow(page, "modelos", viewport.width);
    await goTo(page, `/congelamientos/${FREEZE_ID}`);
    const comparison = page.getByRole("table", { name: ui("freeze_compare_caption") });
    await expect(comparison).toBeVisible();
    await expect(comparison.getByText(ui("col_trigger"))).toBeVisible(); // el disparador, dicho con texto
    await expectNoPageOverflow(page, "el paquete de contexto");
    await expectNoRegionOverflow(page, "el paquete de contexto", viewport.width);
    for (const toggle of await page.getByText(ui("disparity_detail_toggle")).all()) {
      if (!(await toggle.evaluate((summary) => (summary.closest("details") as HTMLDetailsElement).open))) await toggle.click();
    }
    await expectNoPageOverflow(page, "el paquete con todo el detalle desplegado");
    await expectNoRegionOverflow(page, "el paquete con todo el detalle desplegado", viewport.width);
    await page.getByRole("button", { name: ui("resolve_open") }).click();
    const dialog = page.getByRole("dialog", { name: ui("resolve_title") });
    await expect(dialog).toBeVisible();
    const box = await dialog.boundingBox();
    expect(box).not.toBeNull();
    expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
    expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(viewport.width);
    expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(viewport.height);
    await expectNoPageOverflow(page, "el dialogo de resolucion");
  });
}
