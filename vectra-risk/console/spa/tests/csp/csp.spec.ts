// CA-3 de U10-T04 (Paso 15; P-U10-08; NFR-U10-42; US-611): la CSP de U2 sobre el BUILD de la SPA, con Trusted Types, en Chromium y Firefox.
//  - la cabecera `Content-Security-Policy` (y las demas del perfil `spa`) que recibe el navegador es, caracter por caracter, la de
//    `identity-edge/gateway/routes.yaml` (se lee aqui, aparte del servidor de pruebas);
//  - el oyente de `securitypolicyviolation` se instala ANTES de cargar la pagina (en el contexto, tambien para la ventana del step-up) y el
//    recorrido de las vistas y dialogos que entran, con los cuatro roles, termina con **cero** eventos;
//  - el oyente funciona (una violacion de verdad se ve): sin esa prueba, «cero eventos» no demostraria nada.
import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";
import { walk } from "../e2e/tour";
import { chooseLanguage, chooseTheme, EN, ES, loginAs, ORIGIN, type Role, seedPreferences, ui, watchCsp } from "../e2e/support";

const ROUTES_YAML = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..", "identity-edge", "gateway", "routes.yaml");
const profiles = (parse(readFileSync(ROUTES_YAML, "utf-8")) as { profiles: Record<string, { set: Record<string, string> }> }).profiles;
const EXPECTED = { ...profiles["common"]?.set, ...profiles["spa"]?.set } as Record<string, string>;
test.use({ baseURL: ORIGIN });

const ROLES: Role[] = ["analista", "ingeniero_riesgo", "cro", "cumplimiento"];

test("la cabecera de la pagina y de /stepup-callback es la del perfil spa de U2, caracter por caracter", async ({ page }) => {
  expect(Object.keys(EXPECTED)).toContain("Content-Security-Policy");
  expect(EXPECTED["Content-Security-Policy"]).toContain("require-trusted-types-for 'script'");
  expect(EXPECTED["Content-Security-Policy"]).not.toContain("unsafe-inline");
  for (const path of ["/", "/stepup-callback", "/casos"]) {
    const response = await page.goto(path);
    const received = response?.headers() ?? {};
    for (const [name, value] of Object.entries(EXPECTED)) expect(received[name.toLowerCase()], `${name} en ${path}`).toBe(value);
  }
});

test("el oyente ve una violacion de verdad: un estilo en linea escrito con setAttribute", async ({ page, context }) => {
  const violations = await watchCsp(context);
  await page.goto("/");
  await expect(page.getByRole("button", { name: ui("login_button") })).toBeVisible();
  await page.evaluate(() => {
    document.body.setAttribute("style", "color: red"); // `style-src-attr`: el atributo en linea no esta permitido
  });
  await expect.poll(() => violations.map((violation) => violation.directive)).toContainEqual(expect.stringMatching(/^style-src/));
});

// Enmienda del 2026-11-21: los selectores de idioma y de tema (una lista desplegable de React Aria, `theme-boot.js` en el <head>, el
// almacenamiento local) no provocan ninguna violacion, ni al abrirlos, ni al cambiar, ni al cargar con las preferencias ya guardadas.
test("los selectores de idioma y de tema: cero eventos securitypolicyviolation al elegir y al cargar con las preferencias guardadas", async ({ page, context }) => {
  const violations = await watchCsp(context);
  const response = await page.goto("/theme-boot.js"); // el guion del tema es del mismo origen y llega con las cabeceras del perfil `spa`
  expect(response?.status()).toBe(200);
  expect(response?.headers()["content-type"]).toMatch(/javascript/);
  await loginAs(page, "analista");
  await expect(page.getByRole("table")).toBeVisible();
  await chooseLanguage(page, ES, EN);
  await chooseTheme(page, "system", "dark", EN);
  await chooseTheme(page, "dark", "light", EN);
  await page.reload(); // con las dos preferencias guardadas: `theme-boot.js` las lee antes de pintar
  await expect(page.getByRole("button", { name: EN.ui("logout_button") })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(violations).toEqual([]);
});

test("recorrido de cumplimiento en ingles y oscuro: cero eventos securitypolicyviolation", async ({ page, context }) => {
  const violations = await watchCsp(context);
  await seedPreferences(context, { language: "en", theme: "dark" });
  let stops = 0;
  await walk(
    page,
    context,
    "cumplimiento",
    async () => {
      stops += 1;
    },
    EN,
  );
  expect(stops).toBeGreaterThan(2);
  expect(violations).toEqual([]);
});

for (const role of ROLES) {
  test(`recorrido de ${role}: cero eventos securitypolicyviolation`, async ({ page, context }) => {
    const violations = await watchCsp(context);
    let stops = 0;
    await walk(page, context, role, async () => {
      stops += 1;
    });
    expect(stops).toBeGreaterThan(2);
    expect(violations).toEqual([]);
  });
}
