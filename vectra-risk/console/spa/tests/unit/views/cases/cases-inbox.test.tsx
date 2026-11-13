// @vitest-environment jsdom
// BR-U10-10, 11; US-107: `CasesInbox` dentro de `App`: filtros en la URL, «Ir al caso», refresco de 15 s y que el refresco NO reinicia el contador
// de inactividad (la linea del Paso 11 que necesita la bandeja real).
import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { CASE_STATES } from "@vectra/contracts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { label, ui } from "../../../../src/i18n";
import { browserInactivityEnv } from "../../../../src/inactivity/InactivityProvider";
import { Bus } from "../../../support/bus";
import { CASE_ID, OTHER_CASE_ID, detail, page, summary } from "../../../support/fixtures";
import { flush, renderApp } from "../../../support/views-world";

const LIST = "GET /api/console/cases";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const items = [
  summary({ case_id: CASE_ID, applicant_display: "Ana M. G.", state: "listo", outcome: "favorable", score: "0.7312" }),
  summary({ case_id: OTHER_CASE_ID, applicant_display: "Jorge P.", state: "vencido" }),
];

describe("CasesInbox", () => {
  it("por omision pide todos los estados menos `vencido`, de 20 en 20, y muestra solo `applicant_display`", async () => {
    const { world } = renderApp({ role: "analista", path: "/casos", routes: { [LIST]: page(items) } });
    expect(await screen.findByRole("table")).toBeTruthy();
    const call = world.calls.find((c) => c.path === "/api/console/cases");
    expect(call?.search.getAll("state")).toEqual(CASE_STATES.filter((state) => state !== "vencido"));
    expect(call?.search.get("page_size")).toBe("20");
    expect(screen.getByText("Ana M. G.")).toBeTruthy();
    expect(within(screen.getByRole("table")).getByText(label("CASE_STATES", "listo"))).toBeTruthy(); // el estado con texto
    expect(screen.getByText("0,7312")).toBeTruthy();
    expect(window.location.search).toBe(""); // sin filtros, la URL queda limpia
  });

  it("con el filtro explicito aparece `vencido`: el estado va en la URL y en la solicitud", async () => {
    const { world } = renderApp({ role: "cro", path: "/casos", routes: { [LIST]: page(items) } });
    await screen.findByRole("table");
    fireEvent.click(screen.getByRole("checkbox", { name: label("CASE_STATES", "vencido") }));
    await waitFor(() => expect(world.calls.filter((c) => c.path === "/api/console/cases")).toHaveLength(2));
    expect(world.calls.at(-1)?.search.getAll("state")).toContain("vencido");
    expect(new URLSearchParams(window.location.search).getAll("state")).toContain("vencido");
    // volver a los de por omision limpia la URL
    fireEvent.click(screen.getByRole("checkbox", { name: label("CASE_STATES", "vencido") }));
    await waitFor(() => expect(window.location.search).toBe(""));
  });

  it("canal, fechas y «modelo congelado» van a la URL y a la solicitud (fechas del dia de Bogota); «Quitar filtros» los limpia", async () => {
    const { world } = renderApp({ role: "analista", path: "/casos", routes: { [LIST]: page(items) } });
    await screen.findByRole("table");
    fireEvent.change(screen.getByLabelText(ui("filter_channel")), { target: { value: "web" } });
    fireEvent.change(screen.getByLabelText(ui("filter_created_from")), { target: { value: "2026-11-01" } });
    fireEvent.change(screen.getByLabelText(ui("filter_created_to")), { target: { value: "2026-11-12" } });
    fireEvent.click(screen.getByRole("checkbox", { name: ui("filter_frozen") }));
    await waitFor(() => expect(world.calls.at(-1)?.search.get("model_frozen_after_recommendation")).toBe("true"));
    const last = world.calls.at(-1)?.search;
    expect(last?.get("channel")).toBe("web");
    expect(last?.get("created_from")).toBe("2026-11-01T00:00:00-05:00");
    expect(last?.get("created_to")).toBe("2026-11-12T23:59:59-05:00");
    expect(window.location.search).toBe("?channel=web&from=2026-11-01&to=2026-11-12&frozen=1");
    fireEvent.change(screen.getByLabelText(ui("filter_channel")), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText(ui("filter_created_from")), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText(ui("filter_created_to")), { target: { value: "" } });
    await waitFor(() => expect(window.location.search).toBe("?frozen=1"));
    fireEvent.click(screen.getByRole("button", { name: ui("filter_clear") }));
    await waitFor(() => expect(window.location.search).toBe(""));
  });

  it("lo que haya en la URL se lee de forma estricta: un valor ajeno (un nombre) se ignora", async () => {
    const { world } = renderApp({ role: "analista", path: "/casos?channel=Ana%20Gomez&state=listo&state=nombre&from=Ana&page=-3&q=Ana", routes: { [LIST]: page(items) } });
    await screen.findByRole("table");
    const search = world.calls.find((c) => c.path === "/api/console/cases")?.search;
    expect(search?.getAll("state")).toEqual(["listo"]);
    expect(search?.get("channel")).toBeNull();
    expect(search?.get("created_from")).toBeNull();
    expect(search?.get("page")).toBe("1");
    expect(search?.has("q")).toBe(false);
  });

  it("paginacion: «Pagina siguiente» solo si hay mas; pagina anterior desde la 2", async () => {
    const full = Array.from({ length: 20 }, (_, i) => summary({ case_id: `00000000-0000-0000-0000-0000000001${String(i).padStart(2, "0")}` }));
    const { world } = renderApp({ role: "analista", path: "/casos", routes: { [LIST]: { items: full, page: 1, total: 45, next_seq_after: null } } });
    await screen.findByRole("table");
    expect(screen.getByRole("button", { name: ui("page_previous") }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: ui("page_next") }));
    await waitFor(() => expect(world.calls.at(-1)?.search.get("page")).toBe("2"));
    expect(window.location.search).toBe("?page=2");
    expect(screen.getByText(ui("page_current", { page: "2" }))).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: ui("page_previous") }));
    await waitFor(() => expect(window.location.search).toBe(""));
  });

  it("sin total, la pagina completa sigue ofreciendo la siguiente; una vacia dice que no hay casos", async () => {
    const full = Array.from({ length: 20 }, (_, i) => summary({ case_id: `00000000-0000-0000-0000-0000000002${String(i).padStart(2, "0")}` }));
    renderApp({ role: "analista", path: "/casos", routes: { [LIST]: { items: full, page: 1, total: null, next_seq_after: null } } });
    await screen.findByRole("table");
    expect(screen.getByRole("button", { name: ui("page_next") }).hasAttribute("disabled")).toBe(false);
    cleanup();
    renderApp({ role: "analista", path: "/casos", routes: { [LIST]: page([]) } });
    expect(await screen.findByText(ui("inbox_empty"))).toBeTruthy();
  });

  it("un error de la API se muestra con el texto del catalogo, no con el detalle del servidor", async () => {
    renderApp({ role: "analista", path: "/casos", routes: { [LIST]: () => ({ status: 503, body: { code: "dependency_unavailable", detail: "stack: secreto", correlation_id: "1".repeat(32) } }) } });
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Un servicio necesario no está disponible");
    expect(alert.textContent).not.toContain("secreto");
  });
});

describe("«Ir al caso»", () => {
  it("un UUID abre el detalle (en minusculas); otra cosa avisa y no navega", async () => {
    renderApp({ role: "analista", path: "/casos", routes: { [LIST]: page(items), "GET /api/console/cases/{id}": detail() } });
    await screen.findByRole("table");
    const input = screen.getByLabelText(ui("go_to_case_label"));
    fireEvent.change(input, { target: { value: "Ana Gomez" } });
    fireEvent.click(screen.getByRole("button", { name: ui("go_to_case_button") }));
    expect(screen.getByRole("alert").textContent).toBe(ui("go_to_case_invalid"));
    expect(window.location.pathname).toBe("/casos");
    fireEvent.change(input, { target: { value: ` ${CASE_ID.toUpperCase()} ` } });
    expect(screen.queryByText(ui("go_to_case_invalid"))).toBeNull(); // al escribir de nuevo, el aviso se va
    fireEvent.click(screen.getByRole("button", { name: ui("go_to_case_button") }));
    expect(await screen.findByRole("heading", { name: ui("recommendation_title") })).toBeTruthy();
    expect(window.location.pathname).toBe(`/casos/${CASE_ID}`);
  });

  it("cada fila lleva al detalle de su caso", async () => {
    renderApp({ role: "cro", path: "/casos", routes: { [LIST]: page(items), "GET /api/console/cases/{id}": detail() } });
    await screen.findByRole("table");
    fireEvent.click(within(screen.getByRole("table")).getByRole("link", { name: ui("open_case", { applicant: "Ana M. G." }) }));
    expect(await screen.findByRole("heading", { name: ui("recommendation_title") })).toBeTruthy();
  });
});

describe("refresco de 15 s", () => {
  it("la bandeja se vuelve a pedir cada 15 s", async () => {
    await import("../../../../src/views/cases/CasesInbox");
    vi.useFakeTimers();
    const { world } = renderApp({ role: "analista", path: "/casos", routes: { [LIST]: page(items) } });
    await flush();
    await flush(10);
    expect(world.count(LIST)).toBe(1);
    await flush(15_000);
    expect(world.count(LIST)).toBe(2);
    await flush(30_000);
    expect(world.count(LIST)).toBe(4);
  });

  it("con la pestana oculta no se vuelve a pedir (TanStack Query lo detiene)", async () => {
    await import("../../../../src/views/cases/CasesInbox");
    vi.useFakeTimers();
    const { world } = renderApp({ role: "analista", path: "/casos", routes: { [LIST]: page(items) } });
    await flush();
    await flush(10);
    const visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    const before = world.count(LIST);
    await flush(60_000);
    expect(world.count(LIST)).toBe(before);
    visibility.mockRestore();
  });

  it("el refresco NO reinicia el contador de inactividad: a los 25 min sin tocar nada sale el aviso, tras decenas de refrescos", async () => {
    await import("../../../../src/views/cases/CasesInbox");
    vi.useFakeTimers();
    const bus = new Bus();
    const { world } = renderApp({
      role: "analista",
      path: "/casos",
      routes: { [LIST]: page(items) },
      inactivity: { ...browserInactivityEnv, now: () => Date.now(), setTimeout: (h, ms) => setTimeout(h, ms), clearTimeout: (h) => { clearTimeout(h as ReturnType<typeof setTimeout>); }, createChannel: () => bus.channel() },
    });
    await flush();
    await flush(10);
    await flush(24 * 60_000); // 24 minutos: unos 96 refrescos de la bandeja
    expect(world.count(LIST)).toBeGreaterThan(90);
    expect(screen.queryByRole("alertdialog")).toBeNull();
    await flush(61_000); // 25 min + 1 s desde el ultimo evento de la persona
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    expect(screen.getByText(ui("idle_title"))).toBeTruthy();
  });
});
