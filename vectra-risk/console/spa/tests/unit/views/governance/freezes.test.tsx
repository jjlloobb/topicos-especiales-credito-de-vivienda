// @vitest-environment jsdom
// BR-U10-12, 13, 15; US-304, US-305, US-602: `Freezes`, `FreezeContextView` (el paquete completo, el `disclaimer` siempre) y `ResolveFrozenDialog`
// (justificacion obligatoria en las tres acciones, el aviso de `reactivar`, y el MFA: «Verificar y confirmar», el 403 `mfa_required` inesperado
// con `StepUpDialog` y el reintento unico con la misma justificacion).
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { label, ui } from "../../../../src/i18n";
import { freezeRecord, freezeSummary, disparity } from "../../../support/fixtures";
import { problem, renderApp, stepUpWorld } from "../../../support/views-world";
import { readImplicated } from "../../../../src/views/governance/FreezeContextView";
import { justificationOk } from "../../../../src/views/governance/resolution";

afterEach(cleanup);

const LIST = "GET /api/console/freezes";
const GET = "GET /api/console/freezes/{id}";
const RESOLVE = "POST /api/console/models/{id}/frozen-resolution";
const PATH = "/congelamientos/freeze-mv-congelado";

describe("Freezes", () => {
  it("cumplimiento abre el paquete de cada congelamiento; el CRO ve la lista SIN enlace al paquete", async () => {
    renderApp({ role: "cumplimiento", path: "/congelamientos", routes: { [LIST]: [freezeSummary(), freezeSummary({ freeze_id: "freeze-2", resolution: { action: "descartar", recorded_at: "2026-11-12T15:00:00Z" }, model_aggregate: null })] } });
    const table = await screen.findByRole("table");
    expect(within(table).getByRole("link", { name: ui("freeze_open_context", { id: "freeze-mv-congelado" }) }).getAttribute("href")).toBe("/congelamientos/freeze-mv-congelado");
    expect(within(table).getByText(label("RESOLUTION_ACTIONS", "descartar"))).toBeTruthy();
    expect(within(table).getByText(ui("no_resolution"))).toBeTruthy();
    expect(within(table).getByText(ui("no_value"))).toBeTruthy(); // sin disparidad agregada
    expect(screen.queryByText(ui("freeze_context_hidden"))).toBeNull();
    cleanup();
    renderApp({ role: "cro", path: "/congelamientos", routes: { [LIST]: [freezeSummary()] } });
    const croTable = await screen.findByRole("table");
    expect(within(croTable).queryAllByRole("link")).toHaveLength(0);
    expect(screen.getByText(ui("freeze_context_hidden"))).toBeTruthy();
  });

  it("vacia y con el doble de bias caido: el mensaje de dependency_unavailable", async () => {
    renderApp({ role: "cro", path: "/congelamientos", routes: { [LIST]: [] } });
    expect(await screen.findByText(ui("freezes_empty"))).toBeTruthy();
    cleanup();
    renderApp({ role: "cro", path: "/congelamientos", routes: { [LIST]: () => problem(503, "dependency_unavailable") } });
    expect((await screen.findByRole("alert")).textContent).toContain("Un servicio necesario no está disponible");
  });
});

describe("FreezeContextView: el paquete completo y el disclaimer", () => {
  it("antes, despues, ultimos 7 dias, disparador, grupos y bandas, fuentes, disparidad de validacion e historial; las celdas insuficientes dicen asi", async () => {
    const record = freezeRecord({ before: "sin_datos", last7: disparity(), resolutions: [{ action: "investigar", recorded_at: "2026-11-12T15:00:00Z" }] });
    renderApp({ role: "cumplimiento", path: PATH, routes: { [GET]: record } });
    expect(await screen.findByText(ui("freeze_summary_model", { id: "mv-congelado" }))).toBeTruthy();
    expect(screen.getByText(ui("freeze_summary_trigger", { attribute: label("ATTRIBUTES", "region") }))).toBeTruthy();
    expect(screen.getByText(ui("freeze_summary_volume", { total: "124", favorable: "80" }))).toBeTruthy();
    for (const title of ["freeze_section_before", "freeze_section_after", "freeze_section_last7", "freeze_section_implicated", "freeze_section_sources", "freeze_section_initial", "freeze_section_history"] as const) {
      expect(screen.getByRole("heading", { name: ui(title) })).toBeTruthy();
    }
    expect(screen.getAllByText(ui("freeze_no_data"))).toHaveLength(1); // solo `before` en sin_datos
    expect(screen.getAllByText(ui("cell_insufficient")).length).toBeGreaterThanOrEqual(3); // after, ultimos 7 dias y disparidad de validacion
    expect(screen.queryAllByRole("cell", { name: "0" })).toEqual([]); // nunca 0 donde falta la muestra
    expect(screen.getByText(ui("freeze_implicated_item", { attribute: label("ATTRIBUTES", "region"), limit: "0,0500" }))).toBeTruthy();
    expect(screen.getByText(ui("freeze_implicated_band", { band: label("BANDS", "20_30"), difference: "0,0800" }))).toBeTruthy();
    expect(screen.getByText(ui("freeze_source_item", { id: "ds-1", name: "Buró alterno" }))).toBeTruthy();
    expect(screen.getByText('{"raro":true}')).toBeTruthy(); // un elemento sin la forma esperada no se pierde: sale como JSON
    expect(screen.getByText('"otra cosa"')).toBeTruthy();
    expect(screen.getByText(ui("freeze_history_item", { action: label("RESOLUTION_ACTIONS", "investigar"), at: "12/11/2026, 10:00 a. m." }))).toBeTruthy();
  });

  it("el disclaimer «mide y alerta, no certifica» esta en TODOS los estados: cargando, con error, con `sin_datos` y con datos", async () => {
    // cargando
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    renderApp({ role: "cumplimiento", path: PATH, routes: { [GET]: async () => { await gate; return { status: 200, body: freezeRecord() }; } } });
    expect((await screen.findByText(ui("bias_disclaimer"))).textContent).toBe("mide y alerta, no certifica");
    expect(screen.getByText(ui("loading"))).toBeTruthy();
    release();
    await screen.findByText(ui("freeze_summary_model", { id: "mv-congelado" }));
    expect(screen.getByText(ui("bias_disclaimer"))).toBeTruthy();
    cleanup();
    // error
    renderApp({ role: "cumplimiento", path: PATH, routes: { [GET]: () => problem(503, "dependency_unavailable") } });
    await screen.findByRole("alert");
    expect(screen.getByText(ui("bias_disclaimer"))).toBeTruthy();
    cleanup();
    // before y last_7_days en sin_datos
    renderApp({ role: "cumplimiento", path: PATH, routes: { [GET]: freezeRecord({ before: "sin_datos", last7: "sin_datos" }) } });
    await screen.findByText(ui("freeze_summary_model", { id: "mv-congelado" }));
    expect(screen.getAllByText(ui("freeze_no_data"))).toHaveLength(2);
    expect(screen.getByText(ui("bias_disclaimer"))).toBeTruthy();
  });

  it("listas vacias: sin implicados, sin fuentes, sin disparidad de validacion y sin historial; paquete truncado", async () => {
    const record = freezeRecord();
    const empty = { ...record, context_package: { ...record.context_package, implicated: [], data_sources: [], truncated: true, initial_disparity: { attributes: [] } } };
    renderApp({ role: "cumplimiento", path: PATH, routes: { [GET]: empty } });
    await screen.findByText(ui("freeze_truncated"));
    expect(screen.getAllByText(ui("freeze_list_empty"))).toHaveLength(2);
    expect(screen.getAllByText(ui("freeze_no_data")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(ui("freeze_no_history"))).toBeTruthy();
  });

  it("el CRO no llega al paquete: «sin acceso» y ninguna solicitud", async () => {
    const { world } = renderApp({ role: "cro", path: PATH, routes: { [GET]: freezeRecord() } });
    expect(await screen.findByRole("heading", { name: ui("no_access_title") })).toBeTruthy();
    expect(world.calls).toEqual([]);
  });
});

describe("readImplicated", () => {
  it("lee la forma de BR-U9-15 y rechaza lo demas", () => {
    expect(readImplicated({ attribute: "region", freeze_lower_limit: "0.05", bands: [{ band: "gt_30", difference: "0.1", extreme_pair: null }] })).toEqual({ attribute: "region", limit: "0.05", bands: [{ band: "gt_30", difference: "0.1" }] });
    expect(readImplicated(null)).toBeNull();
    expect(readImplicated([])).toBeNull();
    expect(readImplicated({ attribute: "region" })).toBeNull();
    expect(readImplicated({ attribute: "region", freeze_lower_limit: "0.05", bands: [{ band: 1 }] })).toBeNull();
    expect(readImplicated({ attribute: "region", freeze_lower_limit: "0.05", bands: [null] })).toBeNull();
  });
});

describe("justificacion de la resolucion", () => {
  it("1 a 2000 caracteres (puntos de codigo) y no solo espacios", () => {
    expect(justificationOk("")).toBe(false);
    expect(justificationOk("   ")).toBe(false);
    expect(justificationOk("a")).toBe(true);
    expect(justificationOk("😀".repeat(2000))).toBe(true); // 4000 unidades UTF-16, 2000 puntos de codigo
    expect(justificationOk("x".repeat(2001))).toBe(false);
  });
});

function openDialog() {
  fireEvent.click(screen.getByRole("button", { name: ui("resolve_open") }));
}
const write = (text: string) => fireEvent.change(screen.getByLabelText(ui("resolve_justification")), { target: { value: text } });

describe("ResolveFrozenDialog", () => {
  it("las tres acciones exigen justificacion; `reactivar` avisa de la ventana de monitoreo y las otras no", async () => {
    renderApp({ role: "cumplimiento", mfa: true, path: PATH, routes: { [GET]: freezeRecord() } });
    await screen.findByText(ui("freeze_summary_model", { id: "mv-congelado" }));
    openDialog();
    expect(await screen.findByRole("dialog", { name: ui("resolve_title") })).toBeTruthy();
    for (const action of ["reactivar", "descartar", "investigar"] as const) {
      fireEvent.click(screen.getByRole("radio", { name: label("RESOLUTION_ACTIONS", action) }));
      expect(screen.queryByText(ui("resolve_reactivate_warning")) !== null).toBe(action === "reactivar");
      write("");
      expect(screen.getByRole("button", { name: ui("resolve_submit") }).hasAttribute("disabled"), `${action} sin justificacion`).toBe(true);
      expect(screen.getByText(ui("resolve_error_required"))).toBeTruthy();
      write("   ");
      expect(screen.getByRole("button", { name: ui("resolve_submit") }).hasAttribute("disabled")).toBe(true);
      write("Porque sí");
      expect(screen.getByRole("button", { name: ui("resolve_submit") }).hasAttribute("disabled"), `${action} con justificacion`).toBe(false);
    }
    write("x".repeat(2001));
    expect(screen.getByText(ui("resolve_error_too_long"))).toBeTruthy();
    expect(screen.getByRole("button", { name: ui("resolve_submit") }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: ui("resolve_close") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("con MFA reciente: «Confirmar resolucion» envia ya, con la accion y la justificacion, una sola vez, y el congelamiento se recarga", async () => {
    const { world } = renderApp({ role: "cumplimiento", mfa: true, path: PATH, routes: { [GET]: freezeRecord(), [RESOLVE]: { status: 204 } } });
    await screen.findByText(ui("freeze_summary_model", { id: "mv-congelado" }));
    openDialog();
    fireEvent.click(await screen.findByRole("radio", { name: label("RESOLUTION_ACTIONS", "descartar") }));
    write("Falso positivo");
    fireEvent.click(screen.getByRole("button", { name: ui("resolve_submit") }));
    expect(await screen.findByText(ui("freeze_resolution_done"))).toBeTruthy();
    expect(world.count(RESOLVE)).toBe(1);
    expect(world.calls.find((c) => c.method === "POST")?.body).toEqual({ action: "descartar", justification: "Falso positivo" });
    expect(world.calls.find((c) => c.method === "POST")?.path).toBe("/api/console/models/mv-congelado/frozen-resolution");
    await waitFor(() => expect(world.count(GET)).toBe(2));
  });

  it("el aviso de la resolucion anterior no vale para la nueva: al reabrir el dialogo se limpia", async () => {
    renderApp({ role: "cumplimiento", mfa: true, path: PATH, routes: { [GET]: freezeRecord(), [RESOLVE]: { status: 204 } } });
    await screen.findByText(ui("freeze_summary_model", { id: "mv-congelado" }));
    openDialog();
    write("Primera");
    fireEvent.click(await screen.findByRole("button", { name: ui("resolve_submit") }));
    expect(await screen.findByText(ui("freeze_resolution_done"))).toBeTruthy();
    openDialog();
    expect(screen.queryByText(ui("freeze_resolution_done"))).toBeNull();
    expect((screen.getByLabelText(ui("resolve_justification")) as HTMLTextAreaElement).value).toBe(""); // y la justificacion no se arrastra
  });

  it("otro error del servidor (409 conflict_state) se muestra en el dialogo y deja la justificacion", async () => {
    renderApp({ role: "cumplimiento", mfa: true, path: PATH, routes: { [GET]: freezeRecord(), [RESOLVE]: () => problem(409, "conflict_state") } });
    await screen.findByText(ui("freeze_summary_model", { id: "mv-congelado" }));
    openDialog();
    write("Revisado");
    fireEvent.click(await screen.findByRole("button", { name: ui("resolve_submit") }));
    expect((await screen.findByRole("alert")).textContent).toContain("El elemento cambió de estado");
    expect((screen.getByLabelText(ui("resolve_justification")) as HTMLTextAreaElement).value).toBe("Revisado");
  });

  it("sin MFA reciente: el boton dice «Verificar y confirmar», abre la ventana en ese clic y, al terminar la verificacion, envia con la misma justificacion", async () => {
    const world = stepUpWorld();
    const view = renderApp({ role: "cumplimiento", mfa: false, path: PATH, stepUp: world.env, routes: { [GET]: freezeRecord(), [RESOLVE]: { status: 204 } } });
    await screen.findByText(ui("freeze_summary_model", { id: "mv-congelado" }));
    openDialog();
    write("Justificacion unica");
    const button = await screen.findByRole("button", { name: ui("verify_and_confirm") });
    fireEvent.click(button);
    expect(world.popups).toHaveLength(1); // la ventana se abrio en el clic
    expect(view.world.count(RESOLVE)).toBe(0); // y la accion todavia no se envio
    world.backend.resolveRequest();
    await waitFor(() => expect(world.backend.requests).toHaveLength(0));
    world.post();
    world.backend.resolveExchange("ok");
    await waitFor(() => expect(view.world.count(RESOLVE)).toBe(1));
    expect(view.world.calls.find((c) => c.method === "POST")?.body).toEqual({ action: "reactivar", justification: "Justificacion unica" });
  });

  it("403 mfa_required inesperado: sale StepUpDialog; «Verificar identidad» abre la ventana y el reintento unico lleva la MISMA justificacion y da 200", async () => {
    const world = stepUpWorld();
    let attempts = 0;
    const view = renderApp({
      role: "cumplimiento",
      mfa: true,
      path: PATH,
      stepUp: world.env,
      routes: { [GET]: freezeRecord(), [RESOLVE]: () => (++attempts === 1 ? problem(403, "mfa_required") : { status: 204 }) },
    });
    await screen.findByText(ui("freeze_summary_model", { id: "mv-congelado" }));
    openDialog();
    write("La misma justificacion");
    fireEvent.click(await screen.findByRole("button", { name: ui("resolve_submit") }));
    const stepUp = await screen.findByRole("dialog", { name: ui("stepup_dialog_title") });
    expect(world.popups).toHaveLength(0); // la ventana NO se abre sola: hace falta un clic nuevo
    fireEvent.click(within(stepUp).getByRole("button", { name: ui("verify_identity") }));
    expect(world.popups).toHaveLength(1);
    world.backend.resolveRequest();
    await flushReal();
    world.post();
    world.backend.resolveExchange("ok");
    await waitFor(() => expect(view.world.count(RESOLVE)).toBe(2));
    const bodies = view.world.calls.filter((c) => c.method === "POST").map((c) => c.body);
    expect(bodies).toEqual([bodies[0], bodies[0]]); // el reintento lleva exactamente el cuerpo original
    expect(bodies[0]).toEqual({ action: "reactivar", justification: "La misma justificacion" });
    expect(await screen.findByText(ui("freeze_resolution_done"))).toBeTruthy();
  });

  it("un segundo 403 mfa_required tras verificar es un error de la accion: no hay un tercer envio", async () => {
    const world = stepUpWorld();
    const view = renderApp({ role: "cumplimiento", mfa: true, path: PATH, stepUp: world.env, routes: { [GET]: freezeRecord(), [RESOLVE]: () => problem(403, "mfa_required") } });
    await screen.findByText(ui("freeze_summary_model", { id: "mv-congelado" }));
    openDialog();
    write("Justificacion");
    fireEvent.click(await screen.findByRole("button", { name: ui("resolve_submit") }));
    fireEvent.click(await screen.findByRole("button", { name: ui("verify_identity") }));
    world.backend.resolveRequest();
    await flushReal();
    world.post();
    world.backend.resolveExchange("ok");
    await waitFor(() => expect(view.world.count(RESOLVE)).toBe(2));
    await flushReal();
    expect(view.world.count(RESOLVE)).toBe(2);
    expect(await screen.findByText(ui("stepup_retry_failed"))).toBeTruthy();
  });
});

const flushReal = (): Promise<void> => new Promise((resolve) => setTimeout(resolve, 30));
