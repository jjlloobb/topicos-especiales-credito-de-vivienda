// @vitest-environment jsdom
// BR-U10-09; US-108, US-502: `DecisionForm` dentro de `CaseDetail`: validacion igual que el servidor, dialogo de confirmacion, boton deshabilitado en
// curso (dos clics -> una solicitud), y los errores del servidor (422 en su campo, 409 `decision_already_recorded` y `conflict_state`, 503).
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { label, problemText, ui } from "../../../../src/i18n";
import { CASE_ID, detail, recommendation } from "../../../support/fixtures";
import { problem, renderApp, type Reply } from "../../../support/views-world";

afterEach(cleanup);

const GET_CASE = "GET /api/console/cases/{id}";
const DECISION = "POST /api/console/cases/{id}/decision";
const PATH = `/casos/${CASE_ID}`;
const DECISION_REF = { case_id: CASE_ID, registry_entry_id: "9", recorded_at: "2026-11-12T15:00:00Z" };

async function open(post: () => Reply | Promise<Reply> = () => ({ status: 200, body: DECISION_REF }), over = {}) {
  const view = renderApp({ role: "analista", path: PATH, routes: { [GET_CASE]: detail(over), [DECISION]: post } });
  await screen.findByRole("heading", { name: ui("decision_form_title") });
  return view;
}

const pick = (name: string) => fireEvent.click(screen.getByRole("radio", { name }));
const check = (name: string) => fireEvent.click(screen.getByRole("checkbox", { name }));
const submit = () => fireEvent.click(screen.getByRole("button", { name: ui("decision_submit") }));
const justify = (text: string) => fireEvent.change(screen.getByLabelText(ui("decision_field_justification")), { target: { value: text } });

describe("DecisionForm: quien la ve y que ofrece", () => {
  it("solo `analista` con el caso `listo`; el CRO y un caso decidido no la ven", async () => {
    renderApp({ role: "cro", path: PATH, routes: { [GET_CASE]: detail() } });
    await screen.findByRole("heading", { name: ui("recommendation_title") });
    expect(screen.queryByRole("heading", { name: ui("decision_form_title") })).toBeNull();
    cleanup();
    renderApp({ role: "analista", path: PATH, routes: { [GET_CASE]: detail({ state: "decidido" }) } });
    await screen.findByRole("heading", { name: ui("recommendation_title") });
    expect(screen.queryByRole("heading", { name: ui("decision_form_title") })).toBeNull();
  });

  it("con favorable o desfavorable: `sigue` y `se_aparta`; con `revision_requerida`: solo `resuelve_revision` (BR-U0-35)", async () => {
    await open();
    expect(screen.getByRole("radio", { name: label("DECISIONS", "sigue") })).toBeTruthy();
    expect(screen.getByRole("radio", { name: label("DECISIONS", "se_aparta") })).toBeTruthy();
    expect(screen.queryByRole("radio", { name: label("DECISIONS", "resuelve_revision") })).toBeNull();
    cleanup();
    await open(undefined, { outcome: "revision_requerida", recommendation: recommendation({ outcome: "revision_requerida" }) });
    expect(screen.getByRole("radio", { name: label("DECISIONS", "resuelve_revision") })).toBeTruthy();
    expect(screen.queryByRole("radio", { name: label("DECISIONS", "sigue") })).toBeNull();
  });

  it("elegir una decision propone el resultado final: el mismo en `sigue`, el otro en `se_aparta`; los factores son los del shap_vector y «Ninguno» es exclusivo", async () => {
    await open();
    pick(label("DECISIONS", "sigue"));
    expect((screen.getByRole("radio", { name: label("FINAL_OUTCOMES", "favorable") }) as HTMLInputElement).checked).toBe(true);
    pick(label("DECISIONS", "se_aparta"));
    expect((screen.getByRole("radio", { name: label("FINAL_OUTCOMES", "desfavorable") }) as HTMLInputElement).checked).toBe(true);
    const none = screen.getByRole("checkbox", { name: ui("decision_field_none") }) as HTMLInputElement;
    const first = screen.getByRole("checkbox", { name: "installment_to_income" }) as HTMLInputElement;
    const second = screen.getByRole("checkbox", { name: "loan_to_value" }) as HTMLInputElement;
    check("installment_to_income");
    check("loan_to_value");
    expect([first.checked, second.checked, none.checked]).toEqual([true, true, false]);
    check(ui("decision_field_none")); // «Ninguno» desmarca los demas
    expect([first.checked, second.checked, none.checked]).toEqual([false, false, true]);
    check("loan_to_value"); // y un factor desmarca «Ninguno»
    expect([first.checked, second.checked, none.checked]).toEqual([false, true, false]);
    check("loan_to_value");
    expect(second.checked).toBe(false);
    check(ui("decision_field_none"));
    check(ui("decision_field_none"));
    expect(none.checked).toBe(false);
  });

  it("el contador cuenta como el servidor: sin espacios en los bordes y por puntos de codigo", async () => {
    await open();
    justify(`   ${"😀".repeat(7)}  `);
    expect(screen.getByText(ui("decision_counter", { count: "7" }))).toBeTruthy();
  });
});

describe("DecisionForm: la validacion del cliente", () => {
  it("sin elegir nada: pide la decision y el resultado final y no abre el dialogo", async () => {
    const { world } = await open();
    submit();
    expect(screen.getByText(ui("decision_error_choose_decision"))).toBeTruthy();
    expect(screen.getByText(ui("decision_error_choose_final"))).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(world.count(DECISION)).toBe(0);
  });

  it("se_aparta con una justificacion corta, sin factores: errores en su campo; con una decision incoherente: error general", async () => {
    await open();
    pick(label("DECISIONS", "se_aparta"));
    justify("corta");
    submit();
    expect(screen.getByText(ui("decision_error_justification_length"))).toBeTruthy();
    expect(screen.getByText(ui("decision_error_factors_size"))).toBeTruthy();
    check(ui("decision_field_none"));
    justify("x".repeat(25));
    pick(label("FINAL_OUTCOMES", "favorable")); // se_aparta con el mismo resultado: incoherente (BR-U0-35)
    submit();
    expect(screen.getByText(ui("decision_error_incoherent"))).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("DecisionForm: confirmar y enviar", () => {
  async function toConfirm() {
    const view = await open();
    pick(label("DECISIONS", "sigue"));
    check("installment_to_income");
    justify("Sin objeciones");
    submit();
    expect(await screen.findByRole("dialog", { name: ui("decision_confirm_title") })).toBeTruthy();
    return view;
  }

  it("el dialogo resume la decision; «Volver al formulario» no envia nada", async () => {
    const { world } = await toConfirm();
    expect(screen.getByText(ui("decision_confirm_summary", { decision: label("DECISIONS", "sigue"), final: label("FINAL_OUTCOMES", "favorable") }))).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: ui("decision_confirm_cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(world.count(DECISION)).toBe(0);
  });

  it("dos clics seguidos en «Confirmar y enviar» salen como UNA solicitud, con el cuerpo del formulario; el boton queda deshabilitado en curso", async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const { world } = await open(async () => {
      await gate;
      return { status: 200, body: DECISION_REF };
    });
    pick(label("DECISIONS", "sigue"));
    check("installment_to_income");
    justify("Sin objeciones");
    submit();
    const confirm = await screen.findByRole("button", { name: ui("decision_confirm_button") });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    await waitFor(() => expect(screen.getByRole("button", { name: ui("decision_sending") }).hasAttribute("disabled")).toBe(true));
    release();
    expect(await screen.findByText(ui("decision_saved"))).toBeTruthy();
    expect(world.count(DECISION)).toBe(1);
    expect(world.calls.find((c) => c.method === "POST")?.body).toEqual({
      decision: "sigue",
      final_outcome: "favorable",
      used_factors: ["installment_to_income"],
      justification: "Sin objeciones",
    });
    await waitFor(() => expect(world.count(GET_CASE)).toBe(2)); // y recarga el caso
  });

  it("409 decision_already_recorded: el aviso del catalogo y la recarga del caso", async () => {
    const view = await open(() => problem(409, "conflict_state", "decision_already_recorded"));
    pick(label("DECISIONS", "sigue"));
    check("installment_to_income");
    submit();
    fireEvent.click(await screen.findByRole("button", { name: ui("decision_confirm_button") }));
    expect((await screen.findByText(problemText({ code: "conflict_state", reason: "decision_already_recorded" }))).textContent).toContain("Otra persona ya registró");
    await waitFor(() => expect(view.world.count(GET_CASE)).toBe(2));
  });

  it("409 conflict_state: error general y recarga; 503: «el registro no responde; la decision quedo pendiente»", async () => {
    const conflict = await open(() => problem(409, "conflict_state"));
    pick(label("DECISIONS", "sigue"));
    check("installment_to_income");
    submit();
    fireEvent.click(await screen.findByRole("button", { name: ui("decision_confirm_button") }));
    expect(await screen.findByText(problemText({ code: "conflict_state" }))).toBeTruthy();
    await waitFor(() => expect(conflict.world.count(GET_CASE)).toBe(2));
    cleanup();
    await open(() => problem(503, "dependency_unavailable"));
    pick(label("DECISIONS", "sigue"));
    check("installment_to_income");
    submit();
    fireEvent.click(await screen.findByRole("button", { name: ui("decision_confirm_button") }));
    expect(await screen.findByText(ui("decision_pending_registry"))).toBeTruthy();
  });

  it("422 con invalid_params: el error queda en su campo", async () => {
    await open(() => problem(422, "validation_error", undefined, { invalid_params: [{ name: "justification", reason_code: "justification_length" }, { name: "otro_campo", reason_code: "x" }] }));
    pick(label("DECISIONS", "sigue"));
    check("installment_to_income");
    submit();
    fireEvent.click(await screen.findByRole("button", { name: ui("decision_confirm_button") }));
    expect(await screen.findByText(ui("decision_error_general"))).toBeTruthy();
    expect(screen.getByText(problemText({ code: "validation_error" }))).toBeTruthy();
  });

  it("otro error (500) se muestra con el catalogo y un fallo de red tambien; el formulario queda como estaba", async () => {
    await open(() => problem(500, "internal_error"));
    pick(label("DECISIONS", "sigue"));
    check("installment_to_income");
    justify("Sin objeciones");
    submit();
    fireEvent.click(await screen.findByRole("button", { name: ui("decision_confirm_button") }));
    expect(await screen.findByText(problemText({ code: "internal_error" }))).toBeTruthy();
    expect((screen.getByLabelText(ui("decision_field_justification")) as HTMLTextAreaElement).value).toBe("Sin objeciones");
    cleanup();
    await open(() => {
      throw new TypeError("Failed to fetch");
    });
    pick(label("DECISIONS", "sigue"));
    check("installment_to_income");
    submit();
    fireEvent.click(await screen.findByRole("button", { name: ui("decision_confirm_button") }));
    expect(await screen.findByText(ui("api_network"))).toBeTruthy();
  });
});

