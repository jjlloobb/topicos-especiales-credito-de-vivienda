// El tema de la consola (enmienda del 2026-11-21 a NFR-U10-51), en un navegador real sobre el BUILD con la CSP de U2:
//  - «Sistema» (por omision) sigue a `prefers-color-scheme`; «Claro» y «Oscuro» ganan al sistema en los dos sentidos, con los mismos colores;
//  - el cambio es inmediato (sin recargar), queda en UNA clave del almacenamiento local y sobrevive a la recarga y al login;
//  - la primera pintura ya sale con el tema elegido (lo aplica `theme-boot.js`, un guion del mismo origen en el <head>: la CSP no admite
//    guiones en linea), y los controles nativos siguen el tema (`color-scheme`).
import { type BrowserContext, type Page, expect, test } from "@playwright/test";
import { chooseTheme, control, emulateSystemScheme, EN, ES, loginAs, ORIGIN, PREFERENCE_KEYS, seedPreferences, themeButton, watchCsp } from "./support";

test.use({ baseURL: ORIGIN });

// `--bg`, `--text` y `--header-bg` de `styles.css`, en claro y en oscuro.
const LIGHT = { bg: "rgb(250, 248, 244)", text: "rgb(31, 42, 36)", header: "rgb(11, 59, 44)" };
const DARK = { bg: "rgb(16, 26, 21)", text: "rgb(232, 239, 234)", header: "rgb(11, 35, 24)" };

const colors = (page: Page) =>
  page.evaluate(() => ({
    bg: getComputedStyle(document.body).backgroundColor,
    text: getComputedStyle(document.body).color,
    header: getComputedStyle(document.querySelector(".app-header, .auth-screen") as Element).backgroundColor,
    scheme: getComputedStyle(document.documentElement).colorScheme,
    attribute: document.documentElement.getAttribute("data-theme"),
  }));

interface Paint {
  readonly when: string;
  readonly path: string;
  readonly attribute: string | null;
  readonly background: string;
}

/**
 * Registra, en cada documento de la SPA que carga el contexto, el tema en los primeros momentos en que el navegador puede pintar: cuando
 * aparece `<body>` (antes no hay nada que pintar), en el primer cuadro de animacion (el navegador solo da cuadros cuando ya puede pintar: la
 * hoja de estilos del <head> bloquea la pintura hasta que carga) y en `DOMContentLoaded`. El oyente se instala antes de cualquier guion de la
 * pagina y solo mira: no toca el almacenamiento ni el atributo. Cuando aparece `<body>` la hoja puede no haber cargado aun (Firefox): el fondo
 * calculado es entonces transparente, que es «todavia sin pintar», no un tema.
 */
const UNSTYLED = "rgba(0, 0, 0, 0)";

/** En todos los momentos registrados el atributo es `theme`; el fondo, cuando ya hay estilos, es `background`, y en cada cuadro lo es siempre. */
function expectPaintedAs(paints: readonly Paint[], theme: "light" | "dark", background: string): void {
  for (const paint of paints) {
    expect(paint.attribute, `data-theme en «${paint.when}» de ${paint.path}`).toBe(theme);
    if (paint.when === "frame") expect(paint.background, `fondo en el primer cuadro de ${paint.path}`).toBe(background);
    else if (paint.background !== "") expect([background, UNSTYLED], `fondo en «${paint.when}» de ${paint.path}`).toContain(paint.background);
  }
}

/** Instala el registro de la primera pintura (ver arriba) y devuelve la lista viva de lo registrado. */
async function watchFirstPaint(context: BrowserContext): Promise<Paint[]> {
  const paints: Paint[] = [];
  await context.exposeBinding("__reportPaint", (_source, paint: Paint) => {
    paints.push(paint);
  });
  await context.addInitScript(() => {
    if (location.pathname.startsWith("/auth/") || location.pathname.includes(".")) return; // ni el formulario del emisor de prueba ni un archivo suelto son la SPA
    const report = (when: string): void => {
      void (window as never as { __reportPaint: (paint: unknown) => Promise<void> }).__reportPaint({
        when,
        path: location.pathname,
        attribute: document.documentElement.getAttribute("data-theme"),
        background: document.body === null ? "" : getComputedStyle(document.body).backgroundColor,
      });
    };
    const observer = new MutationObserver(() => {
      if (document.body === null) return;
      observer.disconnect();
      report("body");
    });
    observer.observe(document, { childList: true, subtree: true }); // al instalarse el oyente aun no existe ni <html>
    requestAnimationFrame(() => {
      report("frame");
    });
    document.addEventListener("DOMContentLoaded", () => {
      report("ready");
    });
  });
  return paints;
}

test.beforeEach(async ({ page }) => {
  await control.reset(page);
});

test.describe("con el sistema en claro", () => {
  test.use({ colorScheme: "light" });

  test("por omision «Sistema»: claro, sin atributo y sin nada guardado; elegir «Oscuro» cambia ya, sin recargar, y queda guardado", async ({ page }) => {
    await loginAs(page, "analista");
    await expect(page.getByRole("table")).toBeVisible();
    expect(await colors(page)).toEqual({ ...LIGHT, scheme: "light dark", attribute: null });
    expect(await page.evaluate(() => localStorage.length)).toBe(0);
    await page.evaluate(() => {
      (window as never as { __sameDocument: boolean }).__sameDocument = true;
    });
    await chooseTheme(page, "system", "dark");
    expect(await colors(page)).toEqual({ ...DARK, scheme: "dark", attribute: "dark" });
    expect(await page.evaluate(() => (window as never as { __sameDocument?: boolean }).__sameDocument)).toBe(true);
    await expect(page.getByRole("table")).toBeVisible(); // la pantalla y la sesion siguen
    expect(await page.evaluate(() => [Object.entries(localStorage), Object.keys(sessionStorage), document.cookie])).toEqual([[[PREFERENCE_KEYS.theme, "dark"]], [], ""]);
    // «Claro» explicito y de vuelta a «Sistema»
    await chooseTheme(page, "dark", "light");
    expect(await colors(page)).toEqual({ ...LIGHT, scheme: "light", attribute: "light" });
    await chooseTheme(page, "light", "system");
    expect(await colors(page)).toEqual({ ...LIGHT, scheme: "light dark", attribute: null });
  });

  test("el selector se opera con el teclado, anuncia el tema elegido y sus textos siguen al idioma", async ({ page, context }) => {
    await seedPreferences(context, { language: "en" });
    await loginAs(page, "analista", "/", EN);
    const button = themeButton(page, "system", EN);
    await button.focus();
    await page.keyboard.press("Enter");
    const options = page.getByRole("listbox").getByRole("option");
    await expect(options).toHaveText(["System", "Light", "Dark"]);
    await expect(options.nth(0)).toHaveAttribute("aria-selected", "true");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await expect(themeButton(page, "dark", EN)).toBeFocused();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await themeButton(page, "dark", EN).press("Enter");
    await expect(page.getByRole("listbox").getByRole("option").nth(2)).toHaveAttribute("aria-selected", "true");
  });

  test("con «Oscuro» guardado, la primera pintura ya es oscura: en la carga, tras el login por redireccion y en la recarga; sin violar la CSP", async ({ page, context }) => {
    const violations = await watchCsp(context);
    const paints = await watchFirstPaint(context);
    // una visita anterior: la persona elige «Oscuro» en la pantalla de inicio de sesion
    await page.goto("/");
    await expect(page.getByRole("button", { name: ES.ui("login_button") })).toBeVisible();
    await chooseTheme(page, "system", "dark");
    expect(paints.length).toBeGreaterThan(0);
    expect(paints.every((paint) => paint.attribute === null)).toBe(true); // hasta aqui, sin preferencia: el tema del sistema
    paints.length = 0;

    // carga completa con la preferencia guardada (pasa por `prompt=none` y vuelve por /callback: varios documentos)
    await page.goto("/casos");
    await expect(page.getByRole("button", { name: ES.ui("login_button") })).toBeVisible();
    expect(await colors(page)).toMatchObject({ bg: DARK.bg, scheme: "dark", attribute: "dark" });
    // el login interactivo (otra redireccion completa) y, ya dentro, una recarga
    await loginAs(page, "analista", "/casos");
    await expect(page.getByRole("table")).toBeVisible();
    await page.reload();
    await expect(page.getByRole("table")).toBeVisible();
    expect(await colors(page)).toEqual({ ...DARK, scheme: "dark", attribute: "dark" });

    // En TODOS los documentos de la SPA y en los tres momentos, el tema ya era el oscuro: nunca hubo un instante en claro.
    expect(new Set(paints.map((paint) => paint.when))).toEqual(new Set(["body", "frame", "ready"]));
    expect(paints.filter((paint) => paint.when === "body").length).toBeGreaterThanOrEqual(4); // /casos, /callback (x2 o mas) y la recarga
    expect(paints.filter((paint) => paint.when === "frame").length).toBeGreaterThanOrEqual(3);
    expectPaintedAs(paints, "dark", DARK.bg);
    expect(violations).toEqual([]);
  });

  test("los controles nativos siguen el tema elegido: `color-scheme` llega al campo de fecha y a la lista del filtro", async ({ page, context }) => {
    await seedPreferences(context, { theme: "dark" });
    await loginAs(page, "analista");
    await page.getByText(ES.ui("filters_more")).click();
    for (const control of [page.getByLabel(ES.ui("filter_created_from")), page.getByLabel(ES.ui("filter_channel"))]) {
      await expect(control).toBeVisible();
      expect(await control.evaluate((element) => getComputedStyle(element).colorScheme)).toBe("dark");
    }
  });
});

test.describe("la marca de agua del inicio de sesion", () => {
  for (const [theme, stroke] of [
    ["light", "rgb(207, 230, 216)"],
    ["dark", "rgb(181, 205, 191)"],
  ] as const) {
    test(`tema ${theme}: decorativa, con el color del tema, detras de la tarjeta, sin capturar clics ni provocar scroll (1440 y 360 px)`, async ({ page, context }) => {
      await seedPreferences(context, { theme });
      for (const width of [1440, 360]) {
        await page.setViewportSize({ width, height: width === 360 ? 740 : 900 });
        await page.goto("/");
        await expect(page.getByRole("button", { name: ES.ui("login_button") })).toBeVisible();
        const mark = page.locator("main.auth-screen > svg.watermark-auth.watermark-skyline");
        await expect(mark).toBeVisible();
        const state = await mark.evaluate((svg) => {
          const style = getComputedStyle(svg);
          const card = (document.querySelector(".auth-card") as Element).getBoundingClientRect();
          return {
            hidden: svg.getAttribute("aria-hidden"),
            pointer: style.pointerEvents,
            color: style.color,
            opacity: Number.parseFloat(style.opacity),
            overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            // en el centro de la tarjeta lo que recibe el clic es la tarjeta, no el dibujo
            top: (document.elementFromPoint(card.left + card.width / 2, card.top + card.height / 2) as Element).closest(".auth-card") !== null,
          };
        });
        expect(state).toEqual({ hidden: "true", pointer: "none", color: stroke, opacity: 0.1, overflow: 0, top: true });
        await themeButton(page, theme).click(); // un control de la pantalla sigue respondiendo
        await expect(page.getByRole("listbox")).toBeVisible();
        await page.keyboard.press("Escape");
      }
    });
  }
});

test.describe("con el sistema en oscuro", () => {
  test.use({ colorScheme: "dark" });

  test("«Sistema» sigue al sistema (oscuro) y «Claro» le gana; con «Claro» guardado la primera pintura ya es clara", async ({ page, context }) => {
    const paints = await watchFirstPaint(context);
    await emulateSystemScheme(page, "dark");
    await loginAs(page, "cumplimiento");
    await expect(page.getByRole("table")).toBeVisible();
    expect(await colors(page)).toEqual({ ...DARK, scheme: "light dark", attribute: null }); // los mismos colores que el oscuro elegido
    expect(paints.filter((paint) => paint.when === "frame").length).toBeGreaterThan(0);
    expect(paints.filter((paint) => paint.when === "frame").every((paint) => paint.background === DARK.bg && paint.attribute === null)).toBe(true);
    await chooseTheme(page, "system", "light");
    expect(await colors(page)).toEqual({ ...LIGHT, scheme: "light", attribute: "light" });
    paints.length = 0;
    await page.reload();
    await expect(page.getByRole("table")).toBeVisible();
    expect(await colors(page)).toEqual({ ...LIGHT, scheme: "light", attribute: "light" });
    expect(paints.filter((paint) => paint.when === "frame").length).toBeGreaterThan(0);
    expectPaintedAs(paints, "light", LIGHT.bg);
  });
});
