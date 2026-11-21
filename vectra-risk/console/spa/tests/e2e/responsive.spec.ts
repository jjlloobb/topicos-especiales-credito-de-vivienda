// El tema responsivo (NFR-U10-51; WCAG 1.4.10 «reflow»): en los cuatro anchos de corte (360, 768, 1024 y 1440 px) las vistas de las demos no
// provocan scroll horizontal, ni de la PAGINA ni de una region interna: por debajo de 768 px cada tabla pasa a tarjetas apiladas (cada celda
// con el titulo de su columna) sin dejar de ser una tabla; y los controles llegan al objetivo tactil de 44 px. Sobre el BUILD con la CSP de
// U2, como el resto de `tests/e2e`.
//
// Enmienda del 2026-11-21 (selectores de idioma y de tema): las mismas comprobaciones corren en dos variantes, porque el ingles y el espanol
// tienen longitudes distintas y el tema oscuro no debe cambiar ninguna medida: (1) espanol con el tema del sistema (claro), la de siempre, y
// (2) ingles con el tema oscuro forzado. En las dos, los selectores estan en la cabecera, llegan a 44 px y su lista cabe en la ventana.
import { type Page, expect, test } from "@playwright/test";
import { CASES, control, EN, ES, FREEZE_ID, goTo, languageButton, loginAs, ORIGIN, seedPreferences, type Texts, themeButton } from "./support";
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

/**
 * Las marcas de agua (pedido del dueno del proyecto, 2026-11-21): desde 768 px, la del pie de la pagina se ve, es decorativa, no captura clics y
 * no pisa ninguna tabla, tarjeta, formulario ni control; por debajo (tarjetas apiladas), no esta. Nunca provoca scroll horizontal.
 */
async function expectWatermark(page: Page, where: string, width: number, motif: string): Promise<void> {
  const mark = page.locator(`main svg.watermark-page.watermark-${motif}`);
  await expect(mark, `marca de agua en ${where}`).toHaveCount(1);
  if (width < 768) {
    await expect(mark, `marca de agua oculta en movil en ${where}`).toBeHidden();
    return;
  }
  await expect(mark, `marca de agua en ${where}`).toBeVisible();
  const state = await mark.evaluate((svg) => {
    svg.scrollIntoView({ block: "center" });
    const box = svg.getBoundingClientRect();
    const style = getComputedStyle(svg);
    const overlaps = (other: Element): boolean => {
      const rect = other.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0 && rect.left < box.right && rect.right > box.left && rect.top < box.bottom && rect.bottom > box.top;
    };
    const busy = [...document.querySelectorAll("main table, main section, main form, main a, main button, main input, main select, main textarea, main p, main h2, main [role=region]")];
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    const state = {
      hidden: svg.getAttribute("aria-hidden"),
      pointer: style.pointerEvents,
      opacity: Number.parseFloat(style.opacity),
      animation: style.animationName,
      overlapping: busy.filter(overlaps).map((element) => element.tagName.toLowerCase()),
      hitIsMark: hit !== null && svg.contains(hit),
      insideViewport: box.left >= 0 && box.right <= document.documentElement.clientWidth,
      height: Math.round(box.height),
    };
    window.scrollTo(0, 0);
    return state;
  });
  expect(state, `marca de agua en ${where}`).toMatchObject({ hidden: "true", pointer: "none", opacity: 0.1, animation: "none", overlapping: [], hitIsMark: false, insideViewport: true });
  expect(state.height).toBeGreaterThan(40);
  await expectNoPageOverflow(page, `${where} con la marca de agua`);
}

interface Variant {
  /** Prefijo del titulo de la prueba (vacio en la variante de siempre). */
  readonly name: string;
  readonly t: Texts;
  readonly theme: "system" | "dark";
}

const VARIANTS: readonly Variant[] = [
  { name: "", t: ES, theme: "system" },
  { name: "en ingles y oscuro, ", t: EN, theme: "dark" },
];

// El fondo de la pagina de cada tema (`--bg` de `styles.css`).
const PAGE_BACKGROUND = { system: "rgb(250, 248, 244)", dark: "rgb(16, 26, 21)" } as const;

/** Los dos selectores de la cabecera: 44 px de alto, y su lista desplegada cabe en la ventana sin desbordar la pagina. */
async function expectSelectorsFit(page: Page, variant: Variant, width: number, height: number): Promise<void> {
  for (const button of [languageButton(page, variant.t), themeButton(page, variant.theme, variant.t)]) {
    const name = (await button.textContent()) ?? "";
    const box = await button.boundingBox();
    expect(box?.height ?? 0, `alto del selector «${name}»`).toBeGreaterThanOrEqual(43.9);
    expect((box?.x ?? -1) >= 0 && (box?.x ?? 0) + (box?.width ?? 0) <= width, `el selector «${name}» dentro de la ventana`).toBe(true);
    await button.click();
    const list = page.getByRole("listbox");
    await expect(list).toBeVisible();
    const listBox = await list.boundingBox();
    expect(listBox?.x ?? -1, `lista de «${name}»: borde izquierdo`).toBeGreaterThanOrEqual(0);
    expect((listBox?.x ?? 0) + (listBox?.width ?? 0), `lista de «${name}»: borde derecho`).toBeLessThanOrEqual(width);
    expect((listBox?.y ?? 0) + (listBox?.height ?? 0), `lista de «${name}»: borde inferior`).toBeLessThanOrEqual(height);
    for (const option of await list.getByRole("option").all()) {
      expect((await option.boundingBox())?.height ?? 0, `alto de una opcion de «${name}»`).toBeGreaterThanOrEqual(43.9);
    }
    await expectNoPageOverflow(page, `la lista de «${name}» abierta`);
    await page.keyboard.press("Escape");
    await expect(list).toHaveCount(0);
  }
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe(PAGE_BACKGROUND[variant.theme]);
}

test.beforeEach(async ({ page }) => {
  await control.reset(page);
});

for (const variant of VARIANTS) {
  const { t } = variant;
  const prepare = async (page: Page): Promise<void> => {
    if (variant.t.lang !== "es" || variant.theme !== "system") await seedPreferences(page.context(), { language: variant.t.lang, theme: variant.theme });
  };
  for (const viewport of VIEWPORTS) {
    test(`${variant.name}${viewport.name}: bandeja y detalle del caso sin scroll horizontal de la pagina`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await prepare(page);
      await loginAs(page, "analista", "/", t);
      const region = page.getByRole("region", { name: t.ui("table_scroll_label", { name: t.ui("view_cases") }) });
      await expect(region).toBeVisible();
      await expect(region.getByRole("table")).toBeVisible();
      await expectNoPageOverflow(page, "la bandeja");
      await expectNoRegionOverflow(page, "la bandeja", viewport.width);
      await expect(region.getByRole("row")).toHaveCount(9); // la cabecera y las 8 filas siguen siendo filas de una tabla, tambien como tarjetas
      await expect(region.getByRole("link", { name: t.ui("open_case", { applicant: "B. P." }) })).toBeVisible();
      await expectSelectorsFit(page, variant, viewport.width, viewport.height);
      await expectWatermark(page, "la bandeja", viewport.width, "skyline");
      await region.focus(); // la region recibe el foco del teclado
      await expect(region).toBeFocused();
      // «Mas filtros» esta cerrado: los chips a la vista y las casillas ocultas; al abrirlo, sin desbordes
      const vencido = page.getByRole("checkbox", { name: t.label("CASE_STATES", "vencido") });
      await expect(vencido).toBeHidden();
      await page.getByText(t.ui("filters_more")).click();
      await expect(vencido).toBeVisible();
      await expectNoPageOverflow(page, "la bandeja con «Mas filtros» abierto");
      await page.getByText(t.ui("filters_more")).click();
      await expect(vencido).toBeHidden();
      await expect(page.getByRole("navigation", { name: t.ui("nav_label") }).getByRole("link").first()).toBeVisible(); // el menu sigue a la vista (hace wrap)
      for (const name of [t.ui("page_first"), t.ui("page_previous"), t.ui("page_next"), t.ui("page_last"), t.ui("go_to_case_button"), t.ui("logout_button")]) {
        const box = await page.getByRole("button", { name, exact: true }).boundingBox();
        expect(box?.height ?? 0, `alto de «${name}»`).toBeGreaterThanOrEqual(43.9); // 44 px; Firefox devuelve 43,99999 por el redondeo de subpixel
      }
      await openCase(page, CASES.listo, t);
      await expectNoPageOverflow(page, "el detalle del caso");
      await page.getByText(t.ui("application_toggle")).click();
      await expect(page.locator(".free-text")).toBeVisible();
      await expectNoPageOverflow(page, "el detalle con la solicitud desplegada");
      await page.getByRole("button", { name: t.ui("explanation_button") }).click();
      await expect(page.getByText(t.ui("explanation_narrative"))).toBeVisible();
      await expectNoPageOverflow(page, "el detalle con la explicacion");
    });

    test(`${variant.name}${viewport.name}: congelamientos, paquete de contexto y dialogo dentro de la pantalla`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await prepare(page);
      await loginAs(page, "cumplimiento", "/", t);
      await expect(page.getByRole("table")).toBeVisible();
      await expectSelectorsFit(page, variant, viewport.width, viewport.height);
      await expectNoPageOverflow(page, "la lista de congelamientos");
      await expectNoRegionOverflow(page, "la lista de congelamientos", viewport.width);
      await goTo(page, "/modelos");
      await expect(page.getByRole("link", { name: "mv-activo" })).toBeVisible();
      await expectNoPageOverflow(page, "modelos");
      await expectWatermark(page, "modelos", viewport.width, "skyline");
      await expectNoRegionOverflow(page, "modelos", viewport.width);
      await goTo(page, `/congelamientos/${FREEZE_ID}`);
      const comparison = page.getByRole("table", { name: t.ui("freeze_compare_caption") });
      await expect(comparison).toBeVisible();
      await expect(comparison.getByText(t.ui("col_trigger"))).toBeVisible(); // el disparador, dicho con texto
      await expectNoPageOverflow(page, "el paquete de contexto");
      await expectWatermark(page, "el paquete de contexto", viewport.width, "skyline");
      await expectNoRegionOverflow(page, "el paquete de contexto", viewport.width);
      for (const toggle of await page.getByText(t.ui("disparity_detail_toggle")).all()) {
        if (!(await toggle.evaluate((summary) => (summary.closest("details") as HTMLDetailsElement).open))) await toggle.click();
      }
      await expectNoPageOverflow(page, "el paquete con todo el detalle desplegado");
      await expectNoRegionOverflow(page, "el paquete con todo el detalle desplegado", viewport.width);
      await page.getByRole("button", { name: t.ui("resolve_open") }).click();
      const dialog = page.getByRole("dialog", { name: t.ui("resolve_title") });
      await expect(dialog).toBeVisible();
      const box = await dialog.boundingBox();
      expect(box).not.toBeNull();
      expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
      expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(viewport.width);
      expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(viewport.height);
      await expectNoPageOverflow(page, "el dialogo de resolucion");
    });
  }
}
