// @vitest-environment jsdom
// BR-U10-07, 08, 10, 11; US-102, 104, 106, 109, 110, 501: `CaseDetail` dentro de `App` (proveedores y enrutador reales) con un `fetch` falso.
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { label, notice, ui } from "../../../../src/i18n";
import { CASE_ID, detail, recommendation } from "../../../support/fixtures";
import { flush, problem, renderApp } from "../../../support/views-world";

const PATH = `/casos/${CASE_ID}`;
const GET_CASE = "GET /api/console/cases/{id}";
const VIEWS = "POST /api/console/cases/{id}/explanation-views";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("CaseDetail: lo que muestra", () => {
  it("el caso listo: el estado con texto, el puntaje y la confianza formateados con Intl (sin Number), la solicitud y el panel cerrado", async () => {
    renderApp({ role: "analista", path: PATH, routes: { [GET_CASE]: detail() } });
    expect(await screen.findByRole("heading", { name: ui("recommendation_title") })).toBeTruthy();
    expect(screen.getByText(label("CASE_STATES", "listo"))).toBeTruthy(); // texto, no solo color
    expect(screen.getByText(ui("recommendation_score", { score: "0,7312" }))).toBeTruthy();
    expect(screen.getByText(ui("recommendation_confidence", { confidence: "0,8800" }))).toBeTruthy();
    expect(screen.getByText(ui("recommendation_outcome", { outcome: label("OUTCOMES", "favorable") }))).toBeTruthy();
    expect(screen.getByRole("heading", { name: ui("application_title") })).toBeTruthy();
    expect(screen.queryByText(ui("explanation_narrative"))).toBeNull(); // sin abrir, no hay narrativa
    expect(screen.queryByText(/sexo|estrato/i)).toBeNull(); // la solicitud sin etiquetas de monitoreo
  });

  it("free_text con <script> se muestra como texto y no agrega ningun script al DOM (US-109)", async () => {
    const text = "<script>alert(1)</script>";
    const { container } = renderApp({
      role: "analista",
      path: PATH,
      routes: { [GET_CASE]: detail({ application: { ...detail().application, free_text: text } }) },
    });
    expect((await screen.findByText(text)).textContent).toBe(text);
    expect(container.querySelectorAll("script")).toHaveLength(0);
    expect(document.querySelectorAll("script")).toHaveLength(0);
  });

  it("credit_status: no_integrado, no_disponible y los demas dicen su texto (BR-U10-07)", async () => {
    renderApp({ role: "cro", path: PATH, routes: { [GET_CASE]: detail({ credit_status: "no_integrado" }) } });
    expect(await screen.findByText(notice("credit_not_integrated"))).toBeTruthy();
    cleanup();
    renderApp({ role: "cro", path: PATH, routes: { [GET_CASE]: detail({ credit_status: "no_disponible" }) } });
    expect(await screen.findByText(notice("credit_unavailable"))).toBeTruthy();
    cleanup();
    renderApp({ role: "cro", path: PATH, routes: { [GET_CASE]: detail({ credit_status: "desembolsado" }) } });
    expect(await screen.findByText(label("CREDIT_STATUSES", "desembolsado"))).toBeTruthy();
  });

  it("baja confianza, revision_requerida, modelo congelado tras la recomendacion y caso anonimizado: cada marca con su texto (US-106)", async () => {
    renderApp({
      role: "cro",
      path: PATH,
      routes: {
        [GET_CASE]: detail({
          outcome: "revision_requerida",
          recommendation: recommendation({ outcome: "revision_requerida", reasons: ["baja_confianza"] }),
          model_frozen_after_recommendation: true,
          anonymized: true,
        }),
      },
    });
    expect(await screen.findByText(notice("low_confidence"))).toBeTruthy();
    expect(screen.getByText(notice("revision_requerida"))).toBeTruthy();
    expect(screen.getByText(notice("model_frozen_after_recommendation"))).toBeTruthy();
    expect(screen.getByText(notice("case_anonymized"))).toBeTruthy();
    expect(screen.getByText(label("REASON_CODES", "baja_confianza"))).toBeTruthy();
  });

  it("un caso sin recomendacion (el BFF omite los campos nulos) dice que no hay recomendacion y no rompe", async () => {
    const { recommendation: _r, decision: _d, credit_status: _c, ...sinNulos } = detail({ state: "no_disponible", outcome: null, score: null });
    renderApp({ role: "cro", path: PATH, routes: { [GET_CASE]: sinNulos } });
    expect(await screen.findByText(ui("case_unavailable"))).toBeTruthy();
    expect(screen.getByText(label("CASE_STATES", "no_disponible"))).toBeTruthy();
  });

  it("un caso decidido muestra la decision registrada y ya no el formulario", async () => {
    renderApp({
      role: "analista",
      path: PATH,
      routes: {
        [GET_CASE]: detail({
          state: "decidido",
          decision: { decision: "se_aparta", final_outcome: "desfavorable", used_factors: ["loan_to_value"], justification: "Porque aplica", decided_at: "2026-11-12T15:00:00Z", decided_by: "user-1" },
        }),
      },
    });
    expect(await screen.findByRole("heading", { name: ui("decision_recorded_title") })).toBeTruthy();
    expect(screen.getByText("Porque aplica", { exact: false })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: ui("decision_form_title") })).toBeNull();
  });

  it("un identificador que no es un UUID no llama al BFF; un 404 muestra el mensaje del catalogo con el codigo de soporte", async () => {
    const bad = renderApp({ role: "analista", path: "/casos/no-es-un-uuid", routes: {} });
    expect((await screen.findByRole("alert")).textContent).toBe(ui("go_to_case_invalid"));
    expect(bad.world.calls).toEqual([]);
    cleanup();
    renderApp({ role: "analista", path: PATH, routes: { [GET_CASE]: () => problem(404, "not_found") } });
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("No se encontró lo que buscas.");
    expect(alert.textContent).toContain("0".repeat(32)); // el correlation_id para soporte
  });
});

describe("CaseDetail: refresco (BR-U10-10)", () => {
  async function renderSyncing(always = true) {
    await import("../../../../src/views/cases/CaseDetail"); // el `import()` de la vista ya resuelto: no depende de temporizadores
    vi.useFakeTimers();
    let state: "en_sincronizacion" | "listo" = "en_sincronizacion";
    const view = renderApp({
      role: "analista",
      path: PATH,
      routes: { [GET_CASE]: () => ({ status: 200, body: detail({ state: always ? "en_sincronizacion" : state, recommendation: null, outcome: null, score: null }) }) },
    });
    await flush();
    await flush(10);
    return { ...view, setState: (next: typeof state) => (state = next) };
  }

  it("en_sincronizacion se vuelve a pedir cada 3 s y se detiene a los 2 min, diciendolo", async () => {
    const { world } = await renderSyncing();
    expect(world.count(GET_CASE)).toBe(1);
    expect(screen.getByText(ui("case_refreshing"))).toBeTruthy();
    await flush(3000);
    expect(world.count(GET_CASE)).toBe(2);
    await flush(57_000); // 60 s: una solicitud cada 3 s
    expect(world.count(GET_CASE)).toBe(21);
    await flush(65_000); // 125 s: paso el maximo de 2 min
    const stopped = world.count(GET_CASE);
    expect(stopped).toBeGreaterThanOrEqual(40);
    expect(stopped).toBeLessThanOrEqual(42);
    await flush(60_000);
    expect(world.count(GET_CASE)).toBe(stopped); // ya no pide
    expect(screen.getByText(ui("case_refresh_stopped"))).toBeTruthy();
  });

  it("en_evaluacion tambien; un estado final (listo) detiene el refresco en cuanto cambia", async () => {
    await import("../../../../src/views/cases/CaseDetail");
    vi.useFakeTimers();
    let state: "en_evaluacion" | "listo" = "en_evaluacion";
    const { world } = renderApp({ role: "cro", path: PATH, routes: { [GET_CASE]: () => ({ status: 200, body: detail({ state }) }) } });
    await flush();
    await flush(3000);
    expect(world.count(GET_CASE)).toBe(2);
    state = "listo";
    await flush(3000);
    const atChange = world.count(GET_CASE);
    await flush(30_000);
    expect(world.count(GET_CASE)).toBe(atChange);
  });

  it("un caso listo no se vuelve a pedir solo", async () => {
    await import("../../../../src/views/cases/CaseDetail");
    vi.useFakeTimers();
    const { world } = renderApp({ role: "cro", path: PATH, routes: { [GET_CASE]: detail() } });
    await flush();
    await flush(30_000);
    expect(world.count(GET_CASE)).toBe(1);
  });
});

describe("ExplanationPanel (BR-U10-08; US-501)", () => {
  it("abrir el detalle no llama a record_explanation_view; abrir el panel llama UNA vez (aunque se cierre y se abra otra vez)", async () => {
    const { world } = renderApp({ role: "analista", path: PATH, routes: { [GET_CASE]: detail(), [VIEWS]: { status: 204 } } });
    const toggle = await screen.findByRole("button", { name: ui("explanation_button") });
    expect(world.count(VIEWS)).toBe(0);
    fireEvent.click(toggle);
    expect(await screen.findByText(ui("explanation_narrative"))).toBeTruthy();
    await waitFor(() => expect(world.count(VIEWS)).toBe(1));
    fireEvent.click(toggle);
    expect(screen.queryByText(ui("explanation_narrative"))).toBeNull();
    fireEvent.click(toggle);
    expect(screen.getByText(ui("explanation_narrative"))).toBeTruthy();
    expect(world.count(VIEWS)).toBe(1);
  });

  it("el CRO abre el panel y no sale ninguna llamada (BR-U8-19)", async () => {
    const { world } = renderApp({ role: "cro", path: PATH, routes: { [GET_CASE]: detail(), [VIEWS]: { status: 204 } } });
    fireEvent.click(await screen.findByRole("button", { name: ui("explanation_button") }));
    expect(await screen.findByText(ui("explanation_narrative"))).toBeTruthy();
    expect(within(screen.getByRole("main")).getByText(/installment_to_income/)).toBeTruthy();
    await flushReal();
    expect(world.count(VIEWS)).toBe(0);
  });

  it("si la llamada falla, el panel se muestra igual y se avisa", async () => {
    renderApp({ role: "analista", path: PATH, routes: { [GET_CASE]: detail(), [VIEWS]: () => problem(503, "dependency_unavailable") } });
    fireEvent.click(await screen.findByRole("button", { name: ui("explanation_button") }));
    expect(await screen.findByText(ui("explanation_narrative"))).toBeTruthy();
    expect(await screen.findByText(ui("explanation_record_failed"))).toBeTruthy();
  });
});

/** Un respiro real para que, si hubiera una llamada, ya hubiera salido. */
const flushReal = (): Promise<void> => new Promise((resolve) => setTimeout(resolve, 30));
