// U10-T04 (Paso 15): las vistas de la demo en un navegador real (Chromium y Firefox), sobre el BUILD con la CSP de U2 y el BFF real con dobles.
// Lo que las pruebas de vitest (jsdom) no pueden mostrar: el enrutador con el historial, el cliente de la API contra el BFF de verdad, las
// llamadas que de verdad salen al destino (se cuentan en el doble) y las ventanas del step-up.
import { expect, test } from "@playwright/test";
import { CASES, control, FREEZE_ID, goTo, label, loginAs, ORIGIN, ui } from "./support";
import { completeStepUp, openCase } from "./tour";

const EXPLANATION_VIEWS = "/v1/cases/{id}/explanation-views";
const DECISION = "/v1/cases/{id}/decision";
const RESOLUTION = "/v1/models/{id}/frozen-resolution";

test.use({ baseURL: ORIGIN });

test.beforeEach(async ({ page }) => {
  await control.reset(page);
});

test("bandeja: por omision sin vencido; con el filtro aparecen; la URL no lleva datos del solicitante", async ({ page }) => {
  await loginAs(page, "analista");
  await expect(page.getByRole("table")).toBeVisible();
  const vencido = page.getByRole("row").filter({ hasText: label("CASE_STATES", "vencido") });
  await expect(vencido).toHaveCount(0);
  await page.getByRole("checkbox", { name: label("CASE_STATES", "vencido") }).click();
  await expect(page.getByRole("checkbox", { name: label("CASE_STATES", "vencido") })).toBeChecked(); // el enrutador actualiza en una transicion
  await expect(vencido).toHaveCount(1);
  const url = new URL(page.url());
  expect(url.pathname).toBe("/casos");
  expect(url.searchParams.getAll("state")).toContain("vencido");
  expect(decodeURIComponent(url.search)).not.toContain("A. G.");
  expect(decodeURIComponent(url.search)).not.toContain("B. P.");
});

test("bandeja: «Ir al caso» abre el detalle por identificador", async ({ page }) => {
  await loginAs(page, "analista");
  await page.getByLabel(ui("go_to_case_label")).fill("no-es-un-uuid");
  await page.getByRole("button", { name: ui("go_to_case_button") }).click();
  await expect(page.getByRole("alert")).toHaveText(ui("go_to_case_invalid"));
  await page.getByLabel(ui("go_to_case_label")).fill(CASES.decidido);
  await page.getByRole("button", { name: ui("go_to_case_button") }).click();
  await expect(page.getByRole("heading", { name: ui("decision_recorded_title") })).toBeVisible();
});

test("detalle: free_text con <script> se muestra como texto y no ejecuta nada; no_integrado y las marcas", async ({ page }) => {
  const dialogs: string[] = [];
  page.on("dialog", (dialog) => {
    dialogs.push(dialog.message());
    void dialog.dismiss();
  });
  await loginAs(page, "analista");
  await openCase(page, CASES.listo);
  await expect(page.locator(".free-text")).toHaveText("<script>alert(1)</script>");
  expect(await page.locator("#root script").count()).toBe(0);
  expect(dialogs).toEqual([]);
  await expect(page.getByText(ui("credit_title"))).toBeVisible();
  await expect(page.getByText("Estado de crédito no integrado")).toBeVisible();
  await openCase(page, CASES.bajaConfianza);
  await expect(page.locator(".mark-low")).toContainText("Confianza baja");
  await openCase(page, CASES.revision);
  await expect(page.locator(".mark-review")).toContainText("requiere una revisión humana");
  await openCase(page, CASES.congelado);
  await expect(page.getByText("El modelo se congeló después de esta recomendación")).toBeVisible();
  await openCase(page, CASES.sincronizacion);
  await expect(page.getByText(ui("case_refreshing"))).toBeVisible();
});

test("panel de explicacion: analista, una sola llamada por vista y ninguna sin abrirlo", async ({ page }) => {
  await loginAs(page, "analista");
  await openCase(page, CASES.listo);
  await expect(page.getByRole("button", { name: ui("explanation_button") })).toBeVisible();
  expect(await control.count(page, "case", "POST", EXPLANATION_VIEWS)).toBe(0); // abrir el detalle no es una consulta
  const toggle = page.getByRole("button", { name: ui("explanation_button") });
  await toggle.click();
  await expect(page.getByText(ui("explanation_narrative"))).toBeVisible();
  await expect.poll(() => control.count(page, "case", "POST", EXPLANATION_VIEWS)).toBe(1);
  await toggle.click();
  await toggle.click();
  await expect(page.getByText(ui("explanation_narrative"))).toBeVisible();
  expect(await control.count(page, "case", "POST", EXPLANATION_VIEWS)).toBe(1);
});

test("panel de explicacion: el CRO lo abre y no sale ninguna llamada", async ({ page }) => {
  await loginAs(page, "cro");
  await openCase(page, CASES.listo);
  await page.getByRole("button", { name: ui("explanation_button") }).click();
  await expect(page.getByText(ui("explanation_narrative"))).toBeVisible();
  expect(await control.count(page, "case", "POST", EXPLANATION_VIEWS)).toBe(0);
  await expect(page.getByRole("heading", { name: ui("decision_form_title") })).toHaveCount(0);
});

test("decision: dos clics en «Confirmar y enviar» salen como una solicitud y el caso queda decidido", async ({ page }) => {
  await loginAs(page, "analista");
  await openCase(page, CASES.listo);
  await page.getByRole("radio", { name: label("DECISIONS", "sigue") }).check();
  await page.getByRole("checkbox", { name: ui("decision_field_none") }).check();
  await page.getByRole("button", { name: ui("decision_submit") }).click();
  const confirm = page.getByRole("button", { name: ui("decision_confirm_button") });
  await confirm.dblclick();
  await expect(page.getByText(ui("decision_saved"))).toBeVisible();
  expect(await control.count(page, "case", "POST", DECISION)).toBe(1);
  await expect(page.getByRole("heading", { name: ui("decision_recorded_title") })).toBeVisible(); // la recarga ve la decision registrada
  await expect(page.getByRole("heading", { name: ui("decision_form_title") })).toHaveCount(0);
});

test("decision: la validacion del cliente se ve en su campo y no envia nada", async ({ page }) => {
  await loginAs(page, "analista");
  await openCase(page, CASES.listo);
  await page.getByRole("radio", { name: label("DECISIONS", "se_aparta") }).check();
  await page.getByRole("checkbox", { name: ui("decision_field_none") }).check();
  await page.getByLabel(ui("decision_field_justification")).fill("corta");
  await page.getByRole("button", { name: ui("decision_submit") }).click();
  await expect(page.getByRole("alert").filter({ hasText: ui("decision_error_justification_length") })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await control.count(page, "case", "POST", DECISION)).toBe(0);
});

test("modelos y congelamientos: de lectura, con el informe y el paquete; el CRO no abre el paquete", async ({ page }) => {
  await loginAs(page, "cumplimiento");
  await goTo(page, "/modelos");
  await page.getByRole("link", { name: "mv-activo" }).click();
  await expect(page.getByText("AUC-ROC")).toBeVisible();
  await expect(page.getByRole("button")).toHaveCount(1); // solo «Cerrar sesion»: sin registro, aprobacion ni retiro
  await goTo(page, "/congelamientos");
  await page.getByRole("link", { name: ui("freeze_open_context", { id: FREEZE_ID }) }).click();
  await expect(page.getByText(ui("bias_disclaimer"))).toBeVisible();
  await expect(page.getByText(ui("freeze_no_data")).first()).toBeVisible(); // `before` y `last_7_days` en sin_datos
  await expect(page.getByText(ui("cell_insufficient")).first()).toBeVisible();
});

test("resolver un congelamiento sin MFA reciente: ventana, reintento unico con la misma justificacion y una sola escritura", async ({ page, context }) => {
  await loginAs(page, "cumplimiento");
  await goTo(page, `/congelamientos/${FREEZE_ID}`);
  await page.getByRole("button", { name: ui("resolve_open") }).click();
  await page.getByRole("radio", { name: label("RESOLUTION_ACTIONS", "descartar") }).check();
  await page.getByLabel(ui("resolve_justification")).fill("Falso positivo");
  await expect(page.getByRole("button", { name: ui("verify_and_confirm") })).toBeEnabled();
  await completeStepUp(context, () => page.getByRole("button", { name: ui("verify_and_confirm") }).click(), "cumplimiento");
  await expect(page.getByText(ui("freeze_resolution_done"))).toBeVisible();
  expect(await control.count(page, "governance", "POST", RESOLUTION)).toBe(1);
});

test("resolver con un 403 mfa_required inesperado: StepUpDialog y el reintento llega al destino una vez", async ({ page, context }) => {
  await loginAs(page, "cumplimiento");
  await goTo(page, `/congelamientos/${FREEZE_ID}`);
  await page.getByRole("button", { name: ui("resolve_open") }).click();
  await page.getByLabel(ui("resolve_justification")).fill("Primera");
  await completeStepUp(context, () => page.getByRole("button", { name: ui("verify_and_confirm") }).click(), "cumplimiento");
  await expect(page.getByText(ui("freeze_resolution_done"))).toBeVisible();
  await control.forceMfaRequired(page, 1);
  await page.getByRole("button", { name: ui("resolve_open") }).click();
  await page.getByLabel(ui("resolve_justification")).fill("Segunda justificacion");
  await page.getByRole("button", { name: ui("resolve_submit") }).click();
  await expect(page.getByRole("dialog", { name: ui("stepup_dialog_title") })).toBeVisible();
  expect(await control.count(page, "governance", "POST", RESOLUTION)).toBe(1); // el 403 forzado no llego al destino
  await completeStepUp(context, () => page.getByRole("button", { name: ui("verify_identity") }).click(), "cumplimiento");
  await expect(page.getByText(ui("freeze_resolution_done"))).toBeVisible();
  await expect.poll(() => control.count(page, "governance", "POST", RESOLUTION)).toBe(2);
});

test("sin acceso: la ruta de otro rol no llama al BFF", async ({ page }) => {
  await loginAs(page, "ingeniero_riesgo");
  await expect(page.getByRole("table")).toBeVisible(); // su inicio (modelos) ya cargo: lo que sigue se cuenta aparte
  const calls: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) calls.push(request.url());
  });
  await goTo(page, "/casos");
  await expect(page.getByRole("heading", { name: ui("no_access_title") })).toBeVisible();
  await goTo(page, `/congelamientos/${FREEZE_ID}`);
  await expect(page.getByRole("heading", { name: ui("no_access_title") })).toBeVisible();
  expect(calls).toEqual([]);
});
