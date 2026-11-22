// CA-3 de U10-T04 (Paso 15; NFR-U10-51; US-611): `@axe-core/playwright` en cada parada del recorrido de las vistas y dialogos que entran, con los
// cuatro roles, en Chromium y Firefox: cero hallazgos `serious` o `critical`. (La lista de chequeo manual y NVDA son del Paso 22, diferidos.)
import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";
import { walk } from "../e2e/tour";
import { chooseLanguage, chooseTheme, emulateSystemScheme, EN, ES, languageButton, loginAs, ORIGIN, type Role, seedPreferences, type Texts, themeButton } from "../e2e/support";

test.use({ baseURL: ORIGIN });

const ROLES: Role[] = ["analista", "ingeniero_riesgo", "cro", "cumplimiento"];

/** Los hallazgos `serious` o `critical` de axe en la pagina tal como esta. */
async function seriousFindings(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).analyze();
  return results.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => `${violation.id} (${violation.impact}): ${violation.nodes.map((node) => node.target.join(" ")).join(" | ")}`);
}

for (const role of ROLES) {
  test(`recorrido de ${role}: axe sin hallazgos serious ni critical en cada parada`, async ({ page, context }) => {
    const names: string[] = [];
    await walk(page, context, role, async (name) => {
      expect(await seriousFindings(page), `axe en «${name}»`).toEqual([]);
      names.push(name);
    });
    expect(names.length).toBeGreaterThan(2);
  });
}

// Enmienda del 2026-11-21 (selectores de idioma y de tema): el mismo recorrido, con las mismas paradas, en ingles y con el tema FORZADO en
// contra del sistema, en los dos sentidos: (a) ingles y «Oscuro» con el sistema en claro; (b) espanol y «Claro» con el sistema en oscuro.
// axe mide el contraste con los colores que de verdad se pintan, asi que un par texto/fondo que no llegue a AA en un tema falla aqui.
const FORCED: { name: string; system: "light" | "dark"; theme: "light" | "dark"; t: Texts; background: string }[] = [
  { name: "en ingles, con el tema oscuro forzado y el sistema en claro", system: "light", theme: "dark", t: EN, background: "rgb(16, 26, 21)" },
  { name: "con el tema claro forzado y el sistema en oscuro", system: "dark", theme: "light", t: ES, background: "rgb(250, 248, 244)" },
];

for (const variant of FORCED) {
  test.describe(variant.name, () => {
    test.use({ colorScheme: variant.system });

    for (const role of ROLES) {
      test(`recorrido de ${role}, ${variant.name}: axe sin hallazgos serious ni critical en cada parada`, async ({ page, context }) => {
        await seedPreferences(context, { language: variant.t.lang, theme: variant.theme });
        await emulateSystemScheme(page, variant.system);
        expect(await page.evaluate(() => matchMedia("(prefers-color-scheme: dark)").matches)).toBe(variant.system === "dark"); // el sistema va en contra
        const names: string[] = [];
        await walk(
          page,
          context,
          role,
          async (name) => {
            expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), `tema en «${name}»`).toBe(variant.background);
            expect(await seriousFindings(page), `axe en «${name}»`).toEqual([]);
            names.push(name);
          },
          variant.t,
        );
        expect(names.length).toBeGreaterThan(2);
      });
    }

    test(`los selectores de idioma y de tema, ${variant.name}: axe con cada lista abierta, en la cabecera y en el inicio de sesion`, async ({ page, context }) => {
      await seedPreferences(context, { language: variant.t.lang, theme: variant.theme });
      await emulateSystemScheme(page, variant.system);
      await page.goto("/");
      await expect(page.getByRole("button", { name: variant.t.ui("login_button") })).toBeVisible();
      expect(await seriousFindings(page), "axe en el inicio de sesion").toEqual([]);
      for (const button of [languageButton(page, variant.t), themeButton(page, variant.theme, variant.t)]) {
        await button.click();
        await expect(page.getByRole("listbox")).toBeVisible();
        expect(await seriousFindings(page), "axe con una lista abierta en el inicio de sesion").toEqual([]);
        await page.keyboard.press("Escape");
      }
      await loginAs(page, "analista", "/", variant.t);
      await expect(page.getByRole("table")).toBeVisible();
      for (const button of [languageButton(page, variant.t), themeButton(page, variant.theme, variant.t)]) {
        await button.click();
        await expect(page.getByRole("listbox")).toBeVisible();
        expect(await seriousFindings(page), "axe con una lista abierta en la cabecera").toEqual([]);
        await page.keyboard.press("Escape");
      }
    });
  });
}

test("los selectores en espanol con el tema del sistema: axe con cada lista abierta, y tras cambiar de idioma y de tema sin recargar", async ({ page }) => {
  await loginAs(page, "analista");
  await expect(page.getByRole("table")).toBeVisible();
  for (const button of [languageButton(page, ES), themeButton(page, "system", ES)]) {
    await button.click();
    await expect(page.getByRole("listbox")).toBeVisible();
    expect(await seriousFindings(page), "axe con una lista abierta").toEqual([]);
    await page.keyboard.press("Escape");
  }
  await chooseLanguage(page, ES, EN);
  await chooseTheme(page, "system", "dark", EN);
  expect(await seriousFindings(page), "axe tras cambiar a ingles y a oscuro").toEqual([]);
});
