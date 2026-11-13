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
import { ORIGIN, type Role, ui, watchCsp } from "../e2e/support";

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
