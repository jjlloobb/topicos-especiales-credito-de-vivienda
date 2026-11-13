// El recorrido de «Precisiones» del Paso 15 (U10-T04): cada vista y cada dialogo que entra, con los cuatro roles. No es una especificacion:
// `tests/csp` (cero eventos `securitypolicyviolation`) y `tests/a11y` (cero hallazgos `serious` o `critical` de axe) lo recorren con su propia
// parada (`stop`), de modo que las dos pruebas ven exactamente las mismas pantallas.
import { type BrowserContext, type Page, expect } from "@playwright/test";
import { CASES, control, FREEZE_ID, goTo, label, loginAs, problemCode, type Role, ui } from "./support";

export type Stop = (name: string) => Promise<void>;

/** Abre la ventana del step-up desde `trigger`, elige al usuario en el emisor de prueba y espera a que la ventana se cierre sola. */
export async function completeStepUp(context: BrowserContext, trigger: () => Promise<void>, role: Role): Promise<void> {
  const opened = context.waitForEvent("page");
  await trigger();
  const popup = await opened;
  await popup.waitForURL(/\/protocol\/openid-connect\/auth\?/);
  await popup.selectOption("#username", role);
  await Promise.all([popup.waitForEvent("close"), popup.click("#kc-login", { noWaitAfter: true })]);
}

export async function openCase(page: Page, id: string): Promise<void> {
  await goTo(page, `/casos/${id}`);
  await expect(page.getByRole("heading", { name: ui("view_case_detail") })).toBeVisible();
  await expect(page.getByRole("heading", { name: ui("application_title") })).toBeVisible();
}

async function walkAnalista(page: Page, stop: Stop): Promise<void> {
  await expect(page.getByRole("table")).toBeVisible();
  await stop("bandeja");
  await openCase(page, CASES.listo);
  await stop("detalle listo (credito no integrado, free_text con script)");
  await page.getByRole("button", { name: ui("explanation_button") }).click();
  await expect(page.getByText(ui("explanation_narrative"))).toBeVisible();
  await stop("panel de explicacion");
  await page.getByRole("radio", { name: label("DECISIONS", "sigue") }).check();
  await page.getByRole("checkbox", { name: ui("decision_field_none") }).check();
  await page.getByRole("button", { name: ui("decision_submit") }).click();
  await expect(page.getByRole("dialog", { name: ui("decision_confirm_title") })).toBeVisible();
  await stop("dialogo de confirmacion de la decision");
  await page.getByRole("button", { name: ui("decision_confirm_cancel") }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await stop("formulario de decision");
  for (const [id, name] of [
    [CASES.sincronizacion, "detalle en sincronizacion"],
    [CASES.decidido, "detalle decidido"],
    [CASES.congelado, "detalle modelo congelado"],
    [CASES.revision, "detalle revision requerida"],
    [CASES.bajaConfianza, "detalle con baja confianza"],
  ] as const) {
    await openCase(page, id);
    await stop(name);
  }
  await goTo(page, "/politicas");
  await expect(page.getByText(ui("not_available_body"))).toBeVisible();
  await stop("marcador de una vista diferida");
  await goTo(page, "/modelos");
  await expect(page.getByRole("heading", { name: ui("no_access_title") })).toBeVisible();
  await stop("sin acceso (modelos)");
  await goTo(page, `/casos/${CASES.inexistente}`);
  await expect(page.getByRole("alert")).toContainText(problemCode("not_found"));
  await stop("ProblemMessage (caso inexistente)");
}

async function walkIngeniero(page: Page, stop: Stop): Promise<void> {
  await expect(page.getByRole("table")).toBeVisible();
  await stop("modelos");
  await page.getByRole("link", { name: "mv-activo" }).click();
  await expect(page.getByRole("heading", { name: ui("validation_title") })).toBeVisible();
  await stop("detalle de modelo con informe de validacion");
  await goTo(page, "/casos");
  await expect(page.getByRole("heading", { name: ui("no_access_title") })).toBeVisible();
  await stop("sin acceso (bandeja)");
}

async function walkCro(page: Page, stop: Stop): Promise<void> {
  await expect(page.getByRole("table")).toBeVisible();
  await stop("bandeja del CRO");
  await openCase(page, CASES.listo);
  await page.getByRole("button", { name: ui("explanation_button") }).click();
  await expect(page.getByText(ui("explanation_narrative"))).toBeVisible();
  await expect(page.getByRole("heading", { name: ui("decision_form_title") })).toHaveCount(0); // `cro` no decide
  await stop("detalle y explicacion del CRO (sin formulario)");
  await goTo(page, "/congelamientos");
  await expect(page.getByRole("table")).toBeVisible();
  await stop("congelamientos (lista, sin el paquete)");
  await goTo(page, `/congelamientos/${FREEZE_ID}`);
  await expect(page.getByRole("heading", { name: ui("no_access_title") })).toBeVisible();
  await stop("sin acceso (paquete de contexto)");
  await goTo(page, "/modelos");
  await expect(page.getByRole("table")).toBeVisible();
  await stop("modelos del CRO");
  await goTo(page, "/sesgo");
  await expect(page.getByText(ui("not_available_body"))).toBeVisible();
  await stop("marcador (sesgo)");
}

async function walkCumplimiento(page: Page, context: BrowserContext, stop: Stop): Promise<void> {
  await expect(page.getByRole("table")).toBeVisible();
  await stop("congelamientos de cumplimiento");
  await page.getByRole("link", { name: ui("freeze_open_context", { id: FREEZE_ID }) }).click();
  await expect(page.getByText(ui("bias_disclaimer"))).toBeVisible();
  await expect(page.getByText(ui("cell_insufficient")).first()).toBeVisible();
  await stop("paquete de contexto del congelamiento");
  const open = page.getByRole("button", { name: ui("resolve_open") });
  await open.click();
  await expect(page.getByRole("dialog", { name: ui("resolve_title") })).toBeVisible();
  await expect(page.getByText(ui("resolve_reactivate_warning"))).toBeVisible();
  await stop("ResolveFrozenDialog (aviso de reactivar)");
  await page.getByLabel(ui("resolve_justification")).fill("Revisado por cumplimiento");
  // Sin MFA reciente: «Verificar y confirmar» abre la ventana en el clic; al terminar, el reintento envia la resolucion.
  await completeStepUp(context, () => page.getByRole("button", { name: ui("verify_and_confirm") }).click(), "cumplimiento");
  await expect(page.getByText(ui("freeze_resolution_done"))).toBeVisible();
  await stop("resolucion hecha");
  // Con MFA reciente en la SPA pero un 403 mfa_required inesperado: sale StepUpDialog.
  await control.forceMfaRequired(page, 1);
  await open.click();
  await page.getByLabel(ui("resolve_justification")).fill("Otra vez");
  await page.getByRole("button", { name: ui("resolve_submit") }).click();
  await expect(page.getByRole("dialog", { name: ui("stepup_dialog_title") })).toBeVisible();
  await stop("StepUpDialog");
  await completeStepUp(context, () => page.getByRole("button", { name: ui("verify_identity") }).click(), "cumplimiento");
  await expect(page.getByText(ui("freeze_resolution_done"))).toBeVisible();
  await goTo(page, "/casos");
  await expect(page.getByRole("heading", { name: ui("no_access_title") })).toBeVisible();
  await stop("sin acceso (bandeja de casos)");
}

/** El aviso de inactividad: con el reloj de Playwright, 25 minutos sin actividad (BR-U10-20). */
export async function openInactivityDialog(page: Page): Promise<void> {
  await page.clock.install();
  await page.keyboard.press("Shift"); // una actividad con el reloj falso ya instalado: el contador se reprograma con sus temporizadores
  await page.clock.fastForward("25:30");
  await expect(page.getByRole("alertdialog", { name: ui("idle_title") })).toBeVisible();
}

/** Recorre todas las vistas y dialogos que entran con `role`. `stop` se llama en cada parada. */
export async function walk(page: Page, context: BrowserContext, role: Role, stop: Stop): Promise<void> {
  await control.reset(page);
  await loginAs(page, role);
  if (role === "analista") await walkAnalista(page, stop);
  else if (role === "ingeniero_riesgo") await walkIngeniero(page, stop);
  else if (role === "cro") await walkCro(page, stop);
  else await walkCumplimiento(page, context, stop);
  await openInactivityDialog(page);
  await stop("InactivityDialog");
  await page.getByRole("button", { name: ui("idle_continue") }).click();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
}
