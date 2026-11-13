// U10-T04 (Paso 15): las lineas «de esta tarea» de la aceptacion que necesitan un navegador real.
//  - NFR-U10-41: el cierre por inactividad llega a la otra pestana por `BroadcastChannel` (logout en dos pestanas);
//  - NFR-U10-52: al cerrarse la ventana del step-up sin terminar, el foco vuelve al control que la abrio en < 1 s;
//  - NFR-U10-32 (E1 y E3 de P-U10-05 §5): con el doble de bias caido, la bandeja, el detalle y la decision funcionan y `Freezes` dice
//    `dependency_unavailable`; con el de case caido, la bandeja lo dice y `Models` sigue.
// El tiempo del foco es el unico tiempo real que se mide; `uptime` va en la bitacora junto a cada medida.
import { expect, test } from "@playwright/test";
import { CASES, control, FREEZE_ID, goTo, label, loginAs, ORIGIN, problemCode, ui } from "./support";
import { openCase } from "./tour";

test.use({ baseURL: ORIGIN });

test.beforeEach(async ({ page }) => {
  await control.reset(page);
});

test("logout por inactividad en una pestana: la otra pestana tambien cierra la sesion (BroadcastChannel)", async ({ page, context }) => {
  await loginAs(page, "analista");
  const other = await context.newPage();
  await other.goto("/"); // misma sesion del emisor: `prompt=none` entra sin interaccion
  await expect(other.getByRole("button", { name: ui("logout_button") })).toBeVisible();

  await page.clock.install();
  await page.keyboard.press("Shift"); // reprograma el contador con el reloj falso
  await page.clock.fastForward("25:30");
  await expect(page.getByRole("alertdialog", { name: ui("idle_title") })).toBeVisible();
  await page.clock.fastForward("05:00"); // a los 30 minutos: logout, y el mensaje `logout` (sin datos) por el canal
  await expect(page.getByRole("button", { name: ui("login_button") })).toBeVisible();
  await expect(other.getByRole("button", { name: ui("login_button") })).toBeVisible(); // la otra pestana, sin tocarla
  await expect(other.getByRole("button", { name: ui("logout_button") })).toHaveCount(0);
});

test("el foco vuelve al control que abrio la ventana del step-up en menos de 1 s tras cerrarla", async ({ page, context }, info) => {
  await loginAs(page, "cumplimiento");
  await goTo(page, `/congelamientos/${FREEZE_ID}`);
  await page.getByRole("button", { name: ui("resolve_open") }).click();
  await page.getByLabel(ui("resolve_justification")).fill("Justificacion del foco");
  const confirm = page.getByRole("button", { name: ui("verify_and_confirm") });
  const opened = context.waitForEvent("page");
  await confirm.click();
  const popup = await opened;
  await popup.waitForURL(/\/protocol\/openid-connect\/auth\?/);
  await expect(confirm).not.toBeFocused();
  await page.bringToFront();
  const started = Date.now();
  await popup.close();
  await expect(page.getByText(ui("stepup_incomplete"))).toBeVisible();
  await expect(confirm).toBeFocused({ timeout: 1000 });
  const elapsed = Date.now() - started;
  info.annotations.push({ type: "foco", description: `${elapsed} ms (${info.project.name})` });
  console.log(`foco de vuelta en ${elapsed} ms (${info.project.name})`);
  expect(elapsed).toBeLessThan(1000);
});

test("con el doble de bias caido: bandeja, detalle y decision funcionan; Freezes dice dependency_unavailable", async ({ page }) => {
  await control.down(page, "bias");
  await loginAs(page, "analista");
  await expect(page.getByRole("table")).toBeVisible();
  await openCase(page, CASES.listo);
  await page.getByRole("radio", { name: label("DECISIONS", "sigue") }).check();
  await page.getByRole("checkbox", { name: ui("decision_field_none") }).check();
  await page.getByRole("button", { name: ui("decision_submit") }).click();
  await page.getByRole("button", { name: ui("decision_confirm_button") }).click();
  await expect(page.getByText(ui("decision_saved"))).toBeVisible();
  await page.getByRole("button", { name: ui("logout_button") }).click();
  await control.reset(page);
  await control.down(page, "bias");
  await loginAs(page, "cro");
  await goTo(page, "/congelamientos");
  await expect(page.getByRole("alert")).toContainText(problemCode("dependency_unavailable"));
});

test("con el doble de case caido: la bandeja muestra el mensaje y Models sigue", async ({ page }) => {
  await control.down(page, "case");
  await loginAs(page, "cro");
  await expect(page.getByRole("alert")).toContainText(problemCode("dependency_unavailable"));
  await goTo(page, "/modelos");
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("link", { name: "mv-activo" })).toBeVisible();
});
