// @vitest-environment jsdom
// BR-U10-12; US-602: `Layout`, `RoleMenu` y las rutas por rol dentro de `App`: el inicio de cada rol, «sin acceso» y el marcador **sin llamar al BFF**
// (la prueba cuenta cero solicitudes), y un fragmento de vista que no carga se reporta como `chunk_load_failed` (BR-U10-22).
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { ui } from "../../../../src/i18n";
import { lazyView } from "../../../../src/views/shared/lazyView";
import { ROUTES, type Role, routesFor } from "../../../../src/views/shared/routes";
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
