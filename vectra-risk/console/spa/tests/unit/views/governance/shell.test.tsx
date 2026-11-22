// @vitest-environment jsdom
// BR-U10-12; US-602: `Layout`, `RoleMenu` y las rutas por rol dentro de `App`: el inicio de cada rol, «sin acceso» y el marcador **sin llamar al BFF**
// (la prueba cuenta cero solicitudes), y un fragmento de vista que no carga se reporta como `chunk_load_failed` (BR-U10-22).
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { ui } from "../../../../src/i18n";
import { lazyView } from "../../../../src/views/shared/lazyView";
import { activeMenuPath } from "../../../../src/views/shared/RoleMenu";
import { ROUTES, type Role, routesFor, screenTitle } from "../../../../src/views/shared/routes";
import { renderApp } from "../../../support/views-world";
import { Suspense } from "react";

afterEach(cleanup);

const ROLES: Role[] = ["analista", "ingeniero_riesgo", "cro", "cumplimiento"];

describe("el menu y el inicio por rol", () => {
  it.each(ROLES)("%s: `/` lleva a su inicio y el menu muestra exactamente sus vistas con enlace", async (role) => {
    const { world } = renderApp({ role, path: "/", routes: { "GET /api/console/cases": { items: [], page: 1, total: 0 }, "GET /api/console/models": { items: [], page: 1, total: 0 }, "GET /api/console/freezes": [] } });
    const menu = await screen.findByRole("navigation", { name: ui("nav_label") });
    const expected = routesFor(role).filter((route) => route.inMenu).map((route) => ui(route.title));
    expect(within(menu).getAllByRole("link").map((link) => link.textContent)).toEqual(expected);
    await screen.findByRole("heading", { level: 2 });
    expect(window.location.pathname).toBe({ analista: "/casos", ingeniero_riesgo: "/modelos", cro: "/casos", cumplimiento: "/congelamientos" }[role]);
    expect(world.calls.length).toBeGreaterThan(0); // y su inicio pide a la API lo suyo
  });

  it("/callback (el retorno del login) tambien lleva al inicio", async () => {
    renderApp({ role: "cro", path: "/callback", routes: { "GET /api/console/cases": { items: [], page: 1, total: 0 } } });
    await screen.findByRole("heading", { name: ui("view_cases") });
    expect(window.location.pathname).toBe("/casos");
  });
});

describe("pasada de usabilidad: el titulo del documento, «Saltar al contenido» y el cambio de pantalla", () => {
  const EMPTY = { "GET /api/console/cases": { items: [], page: 1, total: 0 }, "GET /api/console/models": { items: [], page: 1, total: 0 }, "GET /api/console/freezes": [] };
  const titled = (key: Parameters<typeof ui>[0]): string => ui("document_title_view", { view: ui(key) });

  it("screenTitle: la pantalla de la ruta si el rol llega, «Sin acceso» si no, «no encontrada» si no existe y nada en las que redirigen", () => {
    expect(screenTitle("/casos", "analista")).toBe("view_cases");
    expect(screenTitle("/casos/nuevo", "analista")).toBe("view_manual_application"); // la estatica antes que `/casos/:caseId`
    expect(screenTitle("/casos/3fa85f64-5717-4562-b3fc-2c963f66afa6", "cro")).toBe("view_case_detail");
    expect(screenTitle("/casos", "ingeniero_riesgo")).toBe("no_access_title");
    expect(screenTitle("/no-existe", "cro")).toBe("not_found_title");
    expect(screenTitle("/", "cro")).toBeNull();
    expect(screenTitle("/callback", "cro")).toBeNull();
  });

  it("el titulo del documento dice la pantalla y cambia con la ruta; al navegar el foco pasa al contenido y se anuncia la pantalla", async () => {
    renderApp({ role: "cumplimiento", path: "/congelamientos", routes: EMPTY });
    await screen.findByRole("heading", { name: ui("view_freezes") });
    expect(document.title).toBe(titled("view_freezes"));
    const main = screen.getByRole("main");
    expect(document.activeElement).not.toBe(main); // en la primera pantalla no se mueve el foco
    expect(document.querySelector("[aria-live='polite'].visually-hidden")?.textContent).toBe("");
    fireEvent.click(within(screen.getByRole("navigation", { name: ui("nav_label") })).getByRole("link", { name: ui("view_models") }));
    await screen.findByRole("heading", { name: ui("view_models") });
    expect(document.title).toBe(titled("view_models"));
    expect(document.activeElement).toBe(main);
    expect(document.querySelector("[aria-live='polite'].visually-hidden")?.textContent).toBe(ui("route_announcement", { view: ui("view_models") }));
    fireEvent.click(within(screen.getByRole("navigation", { name: ui("nav_label") })).getByRole("link", { name: ui("view_policies") }));
    await screen.findByText(ui("not_available_body"));
    expect(document.title).toBe(titled("view_policies"));
  });

  it("una ruta de otro rol titula «Sin acceso» y una que no existe, «Pantalla no encontrada»", async () => {
    renderApp({ role: "ingeniero_riesgo", path: "/casos", routes: EMPTY });
    await screen.findByRole("heading", { name: ui("no_access_title") });
    expect(document.title).toBe(titled("no_access_title"));
    cleanup();
    expect(document.title).toBe(ui("document_title")); // sin la consola montada vuelve el titulo general
    renderApp({ role: "cro", path: "/no-existe", routes: EMPTY });
    await screen.findByRole("heading", { name: ui("not_found_title") });
    expect(document.title).toBe(titled("not_found_title"));
  });

  it("«Saltar al contenido» es el primer enlace de la pagina y lleva el foco al contenido sin tocar la URL", async () => {
    renderApp({ role: "analista", path: "/casos?state=listo", routes: EMPTY });
    await screen.findByRole("heading", { name: ui("view_cases") });
    const skip = screen.getAllByRole("link")[0] as HTMLElement;
    expect(skip.textContent).toBe(ui("skip_to_content"));
    expect(skip.getAttribute("href")).toBe("#contenido");
    const main = screen.getByRole("main");
    expect(main.id).toBe("contenido");
    fireEvent.click(skip);
    expect(document.activeElement).toBe(main);
    expect(`${window.location.pathname}${window.location.search}${window.location.hash}`).toBe("/casos?state=listo");
  });
});

describe("H-12: tras el login la SPA vuelve a la ruta pedida", () => {
  const CASES = { "GET /api/console/cases": { items: [], page: 1, total: 0 } };
  const ORIGIN = window.location.origin;

  it("la bandeja con filtro y pagina: la URL y la solicitud conservan el filtro", async () => {
    const { world } = renderApp({ role: "analista", returnTo: "/casos?state=no_disponible&page=2", routes: CASES });
    await screen.findByRole("heading", { name: ui("view_cases") });
    expect(`${window.location.pathname}${window.location.search}`).toBe("/casos?state=no_disponible&page=2");
    const call = world.calls.find((c) => c.path === "/api/console/cases");
    expect(call?.search.getAll("state")).toEqual(["no_disponible"]);
    expect(call?.search.get("page")).toBe("2");
  });

  it.each([
    ["analista", "/casos/3fa85f64-5717-4562-b3fc-2c963f66afa6", "view_case_detail"],
    ["cumplimiento", "/congelamientos/freeze-mv-1", "freeze_context_title"],
    ["ingeniero_riesgo", "/modelos/mv-activo", "view_model_detail"],
  ] as const)("%s vuelve al detalle %s", async (role, path, title) => {
    renderApp({ role, returnTo: path, routes: {} });
    await screen.findByRole("heading", { name: ui(title) });
    expect(window.location.pathname).toBe(path);
  });

  it.each([
    ["analista", "/modelos/mv-activo", "/casos"], // una ruta de otro rol: al inicio del rol
    ["cro", "/congelamientos/freeze-mv-1", "/casos"],
    ["cumplimiento", "/casos?state=listo", "/congelamientos"],
    ["analista", "//evil.example/casos", "/casos"],
    ["analista", "https://evil.example/casos", "/casos"],
    ["analista", "/\\evil.example", "/casos"],
    ["analista", "/callback?code=c&state=s", "/casos"],
    ["analista", "/stepup-callback", "/casos"],
    ["analista", "/no/existe", "/casos"],
    ["ingeniero_riesgo", undefined, "/modelos"],
  ] as const)("%s con el destino %s termina en %s (el inicio de su rol)", async (role, returnTo, home) => {
    renderApp({ role, returnTo, routes: { ...CASES, "GET /api/console/models": { items: [], page: 1, total: 0 }, "GET /api/console/freezes": [] } });
    await screen.findByRole("heading", { level: 2 });
    await waitFor(() => expect(window.location.pathname).toBe(home));
    expect(window.location.search).toBe("");
    expect(window.location.origin).toBe(ORIGIN); // nunca sale del origen
  });

  it("el destino es de un solo uso: volver despues a `/` lleva al inicio del rol, no otra vez al destino", async () => {
    renderApp({ role: "analista", returnTo: "/casos?state=no_disponible", routes: CASES });
    await screen.findByRole("heading", { name: ui("view_cases") });
    expect(window.location.search).toBe("?state=no_disponible");
    act(() => {
      window.history.pushState({}, "", "/");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await waitFor(() => expect(`${window.location.pathname}${window.location.search}`).toBe("/casos"));
  });
});

describe("la seccion activa del menu", () => {
  const current = (): (string | null)[][] =>
    within(screen.getByRole("navigation", { name: ui("nav_label") }))
      .getAllByRole("link")
      .filter((link) => link.hasAttribute("aria-current"))
      .map((link) => [link.textContent, link.getAttribute("aria-current")]);

  it("en la lista marca su entrada como la pagina; dentro de un detalle marca la seccion; nunca mas de una", async () => {
    renderApp({ role: "analista", path: "/casos", routes: { "GET /api/console/cases": { items: [], page: 1, total: 0 } } });
    await screen.findByRole("heading", { name: ui("view_cases") });
    expect(current()).toEqual([[ui("view_cases"), "page"]]);
    cleanup();
    renderApp({ role: "analista", path: "/casos/3fa85f64-5717-4562-b3fc-2c963f66afa6", routes: {} });
    await screen.findByRole("heading", { name: ui("view_case_detail") });
    expect(current()).toEqual([[ui("view_cases"), "true"]]);
    cleanup();
    renderApp({ role: "analista", path: "/casos/nuevo", routes: {} }); // la ruta mas larga gana: «Alta manual», no la bandeja
    await screen.findByRole("heading", { name: ui("view_manual_application"), level: 2 });
    expect(current()).toEqual([[ui("view_manual_application"), "page"]]);
    cleanup();
    renderApp({ role: "cumplimiento", path: "/congelamientos/freeze-mv-1", routes: {} });
    await screen.findByRole("heading", { name: ui("freeze_context_title") });
    expect(current()).toEqual([[ui("view_freezes"), "true"]]);
  });

  it("una direccion que no es de ninguna seccion no marca nada", async () => {
    renderApp({ role: "analista", path: "/no/existe", routes: {} });
    await screen.findByRole("heading", { name: ui("not_found_title") });
    expect(current()).toEqual([]);
    expect(activeMenuPath(["/casos", "/casos/nuevo", "/modelos"], "/")).toBeNull();
    expect(activeMenuPath(["/casos", "/casos/nuevo", "/modelos"], "/casosx")).toBeNull(); // prefijo de segmento completo, no de texto
    expect(activeMenuPath(["/casos", "/casos/nuevo", "/modelos"], "/casos/nuevo")).toBe("/casos/nuevo");
  });
});

describe("«sin acceso», el marcador y la ruta desconocida: cero solicitudes al BFF", () => {
  it.each([
    ["ingeniero_riesgo", "/casos"],
    ["ingeniero_riesgo", "/casos/3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    ["cro", "/congelamientos/freeze-mv-1"],
    ["cumplimiento", "/casos"],
    ["analista", "/modelos"],
    ["analista", "/congelamientos"],
    ["cumplimiento", "/fallos"],
  ] as const)("%s en %s: «sin acceso»", async (role, path) => {
    const { world } = renderApp({ role, path, routes: {} });
    expect(await screen.findByRole("heading", { name: ui("no_access_title") })).toBeTruthy();
    expect(screen.getByText(ui("no_access_body"))).toBeTruthy();
    expect(world.calls).toEqual([]);
  });

  it.each(ROUTES.filter((route) => !route.entry).map((route) => [route.view, route] as const))("%s: el marcador, con su titulo, sin llamar al BFF", async (_view, route) => {
    const role = route.roles[0] as Role;
    const { world } = renderApp({ role, path: route.path, routes: {} });
    expect(await screen.findByRole("heading", { name: ui(route.title), level: 2 })).toBeTruthy();
    expect(screen.getByText(ui("not_available_body"))).toBeTruthy();
    expect(world.calls).toEqual([]);
  });

  it("una direccion que no es ninguna ruta dice que no existe y no llama al BFF", async () => {
    const { world } = renderApp({ role: "analista", path: "/no/existe", routes: {} });
    expect(await screen.findByRole("heading", { name: ui("not_found_title") })).toBeTruthy();
    expect(world.calls).toEqual([]);
  });
});

describe("lazyView: un fragmento que no carga", () => {
  it("se reporta (`onFailure`) y el error sube al ErrorBoundary", async () => {
    const onFailure = vi.fn();
    const Broken = lazyView(() => Promise.reject(new Error("ChunkLoadError")), onFailure);
    const quiet = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { ErrorBoundary } = await import("../../../../src/reporter/ErrorBoundary");
    const caught = vi.fn();
    render(
      <ErrorBoundary onError={caught}>
        <MemoryRouter>
          <Suspense fallback={null}>
            <Broken />
          </Suspense>
        </MemoryRouter>
      </ErrorBoundary>,
    );
    expect((await screen.findByRole("alert")).textContent).toContain(ui("error_boundary_title"));
    expect(onFailure).toHaveBeenCalledTimes(1);
    expect(caught).toHaveBeenCalled();
    quiet.mockRestore();
  });

  it("en `App`, un fragmento que no carga llega al reporter como chunk_load_failed", async () => {
    const { LOADERS } = await import("../../../../src/views/shared/loaders");
    const original = LOADERS.Models;
    LOADERS.Models = () => Promise.reject(new Error("ChunkLoadError"));
    const quiet = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { reports, wiring } = renderApp({ role: "ingeniero_riesgo", path: "/modelos", routes: {} });
    wiring.tokens.set("t"); // el reporter solo envia con token
    expect((await screen.findByRole("alert")).textContent).toContain(ui("error_boundary_title"));
    expect(reports).toContain("chunk_load_failed");
    LOADERS.Models = original;
    quiet.mockRestore();
  });
});
