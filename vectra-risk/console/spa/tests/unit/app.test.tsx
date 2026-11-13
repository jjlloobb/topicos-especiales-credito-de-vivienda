// @vitest-environment jsdom
// BR-U10-05, 06, 20, 22: la entrada (`entry.ts`), el cableado real (`wiring.ts`) y `App` con un cableado de dobles.
import { QueryClient } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { SigninResponse, User, UserManager } from "oidc-client-ts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../src/App";
import { createApi } from "../../src/api/client";
import type { AuthManager } from "../../src/auth/AuthProvider";
import { createTokenStore } from "../../src/auth/AuthProvider";
import type { AppConfig } from "../../src/config/load";
import { entryKind } from "../../src/entry";
import { ui } from "../../src/i18n";
import { Reporter } from "../../src/reporter/reporter";
import { acceptStepUp, createWiring, type Wiring } from "../../src/wiring";
import { Bus } from "../support/bus";
import { OWN, CALLBACK, FakeBackend, ManualTimers } from "../support/stepup-world";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("entryKind: /stepup-callback se detecta antes de montar React; /callback es la propia SPA", () => {
  it.each([
    ["/stepup-callback", "stepup-callback"],
    ["/callback", "app"],
    ["/", "app"],
    ["/casos", "app"],
    ["/callback/otra", "app"],
  ])("%s -> %s", (path, kind) => {
    expect(entryKind(path)).toBe(kind);
  });
});

const CONFIG: AppConfig = {
  oidc: { authority: `${OWN}/auth/realms/vectra`, client_id: "vectra-console" },
  redirect_uri: `${OWN}/callback`,
  stepup_redirect_uri: CALLBACK,
  grafana: { bias_dashboard_uid: "bias" },
};

describe("createWiring", () => {
  it("arma el UserManager, la API, el reporter y los entornos de stepup e inactivity con el origen y las rutas de config.json", () => {
    const win = { location: { origin: OWN, pathname: "/casos/123" }, sessionStorage: window.sessionStorage, open: vi.fn(() => null) } as unknown as Window;
    const wiring = createWiring(CONFIG, win);
    expect(wiring.stepUpEnv.ownOrigin).toBe(OWN);
    expect(wiring.stepUpEnv.stepupRedirectUri).toBe(CALLBACK);
    expect(wiring.stepUpEnv.messageTarget).toBe(win);
    expect(wiring.stepUpEnv.openWindow()).toBeNull();
    expect(win.open).toHaveBeenCalledWith("", "vectra-stepup");
    expect(wiring.stepUpEnv.now()).toBeTypeOf("number");
    expect(wiring.queryClient.getDefaultOptions().queries?.retry).toBe(false);
    expect(wiring.tokens.get()).toBeNull();
    expect(wiring.inactivityEnv.target).toBe(document);
  });

  it("loadSession pide get_me con el token dado; el reporter reporta con la plantilla de la ruta, no con la URL", async () => {
    const win = { location: { origin: OWN, pathname: "/casos/123" }, sessionStorage: window.sessionStorage, open: vi.fn() } as unknown as Window;
    const calls: { url: string; init?: RequestInit | undefined }[] = [];
    vi.stubGlobal("fetch", async (input: string | Request, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input;
      calls.push({ url, init: input instanceof Request ? { headers: input.headers } : init });
      if (url.endsWith("/api/console/me")) {
        return new Response(JSON.stringify({ role: "cro", mfa: false, auth_time: "2026-11-12T15:00:00Z", locale: "es-CO" }), {
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(null, { status: 204 });
    });
    const wiring = createWiring(CONFIG, win);
    expect(await wiring.loadSession("tok")).toMatchObject({ role: "cro" });
    expect((calls[0]?.init?.headers as Headers).get("authorization")).toBe("Bearer tok");
    wiring.tokens.set("tok");
    wiring.stepUpEnv.reportFailure();
    const report = calls.find((c) => c.url.endsWith("/client-errors"));
    expect(report).toBeDefined();
    // U10-T04 (P-7): la plantilla sale de la tabla de rutas del enrutador, nunca de la URL (`/casos/123` -> `/casos/:caseId`).
    expect(JSON.parse(report?.init?.body as string)).toMatchObject({ error_code: "stepup_failed", route_template: "/casos/:caseId" });
    vi.unstubAllGlobals();
  });

  it("los tokens del step-up se guardan en el UserManager y se avisa `userLoaded` (para pedir get_me otra vez)", async () => {
    const win = { location: { origin: OWN, pathname: "/" }, sessionStorage: window.sessionStorage, open: vi.fn() } as unknown as Window;
    const wiring = createWiring(CONFIG, win);
    const loaded: string[] = [];
    wiring.manager.events.addUserLoaded((user) => loaded.push(user.access_token));
    const manager = wiring.manager as UserManager;
    const response = {
      access_token: "nuevo",
      token_type: "Bearer",
      expires_at: Math.floor(Date.now() / 1000) + 300,
      profile: { sub: "s", iss: CONFIG.oidc.authority, aud: "vectra-console", exp: 1, iat: 1, acr: "mfa" },
    } as unknown as SigninResponse;
    await acceptStepUp(manager, response);
    expect(loaded).toEqual(["nuevo"]);
    expect((await manager.getUser())?.profile["acr"]).toBe("mfa");
    manager.stopSilentRenew();
  });
});

/** Lo que el emisor devuelve a `/callback` tras un `prompt=none` sin sesion (la forma de `ErrorResponse` de `oidc-client-ts`). */
const LOGIN_REQUIRED = Object.assign(new Error("login_required"), { error: "login_required", state: { mode: "silent" } });

function fakeWiring(
  over: { user?: User | null; redirect?: () => Promise<void> } = {},
): Wiring & { signedOut: number; reports: string[]; redirects: { prompt?: string; mode: string }[] } {
  const redirects: { prompt?: string; mode: string }[] = [];
  const events = new Set<(user: User) => void>();
  const tokens = createTokenStore();
  const reports: string[] = [];
  const manager: AuthManager = {
    getUser: async () => over.user ?? null,
    signinRedirect: async (args) => {
      redirects.push({ ...(args.prompt === undefined ? {} : { prompt: args.prompt }), mode: args.state.mode });
      await over.redirect?.();
    },
    signinCallback: async () => Promise.reject(LOGIN_REQUIRED),
    signoutRedirect: async () => undefined,
    events: { addUserLoaded: (cb) => events.add(cb), removeUserLoaded: (cb) => events.delete(cb) },
  };
  const reporter = new Reporter({
    endpoint: "/x",
    getToken: () => tokens.get(),
    routeTemplate: () => "/",
    appVersion: "0.1.0",
    fetchImpl: (async (_url: string, init: RequestInit) => {
      reports.push((JSON.parse(init.body as string) as { error_code: string }).error_code);
      return new Response(null, { status: 204 });
    }) as unknown as typeof fetch,
  });
  const bus = new Bus();
  const backend = new FakeBackend();
  const wiring = {
    manager,
    // La recarga ya volvio de `prompt=none` sin sesion: el callback trae `login_required` y se muestra el login interactivo.
    authPage: { callbackUrl: () => (over.user ? null : `${OWN}/callback?error=login_required&state=s`), clean: () => undefined },
    tokens,
    queryClient: new QueryClient(),
    // Las vistas piden a la API: aqui, una bandeja vacia.
    api: createApi({
      baseUrl: OWN,
      getToken: () => tokens.get(),
      fetchImpl: (async () =>
        new Response(JSON.stringify({ items: [], page: 1, total: 0 }), { headers: { "content-type": "application/json" } })) as unknown as typeof fetch,
    }),
    loadSession: async () => ({ role: "analista" as const, mfa: false, auth_time: "2026-11-12T15:00:00Z", locale: "es-CO" as const }),
    reporter,
    stepUpEnv: {
      ownOrigin: OWN,
      stepupRedirectUri: CALLBACK,
      backend,
      openWindow: () => null,
      timers: new ManualTimers(),
      reportFailure: () => undefined,
      now: () => Date.now(),
      messageTarget: window,
    },
    inactivityEnv: {
      now: () => Date.now(),
      setTimeout: (h: () => void, ms: number) => setTimeout(h, ms),
      clearTimeout: (handle: unknown) => {
        clearTimeout(handle as ReturnType<typeof setTimeout>);
      },
      createChannel: () => bus.channel(),
      target: document,
    },
    signedOut: 0,
    reports,
    redirects,
  };
  return wiring;
}

describe("App", () => {
  it("sin sesion muestra el login; el clic redirige con signinRedirect en modo interactivo", async () => {
    const wiring = fakeWiring();
    render(<App wiring={wiring} />);
    expect(screen.getByText(ui("loading_session"))).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: ui("login_button") }));
    expect(wiring.redirects).toEqual([{ mode: "interactive" }]);
    expect(screen.queryByRole("alert")).toBeNull(); // el login_required del prompt=none no es un fallo
  });

  it("un login fallido muestra el aviso del catalogo", async () => {
    render(<App wiring={fakeWiring({ redirect: async () => Promise.reject(new Error("emisor caido")) })} />);
    fireEvent.click(await screen.findByRole("button", { name: ui("login_button") }));
    expect((await screen.findByRole("alert")).textContent).toBe(ui("login_failed"));
  });

  it("con sesion muestra el rol; cerrar sesion vuelve al login", async () => {
    render(<App wiring={fakeWiring({ user: { access_token: "t" } as User })} />);
    expect(await screen.findByText(ui("session_role", { role: "Analista" }))).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: ui("logout_button") }));
    expect(await screen.findByRole("button", { name: ui("login_button") })).toBeTruthy();
  });

  it("un error de renderizado se reporta como render_error y la pantalla muestra el catalogo", async () => {
    const wiring = fakeWiring();
    wiring.tokens.set("t"); // el reporter solo envia con token
    const quiet = vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(<App wiring={{ ...wiring, queryClient: undefined as never }} />);
    expect(screen.getByRole("alert").textContent).toContain(ui("error_boundary_title"));
    expect(wiring.reports).toEqual(["render_error"]);
    quiet.mockRestore();
  });

  it("engancha los reportes del navegador mientras esta montada", async () => {
    const wiring = fakeWiring({ user: { access_token: "t" } as User });
    const { unmount } = render(<App wiring={wiring} />);
    await screen.findByRole("button", { name: ui("logout_button") });
    window.dispatchEvent(new Event("securitypolicyviolation"));
    expect(wiring.reports).toContain("csp_violation");
    unmount();
    window.dispatchEvent(new Event("securitypolicyviolation"));
    expect(wiring.reports.filter((code) => code === "csp_violation")).toHaveLength(1);
  });
});
