// `App` completa (los proveedores reales, el enrutador y las rutas por rol) con un cableado de dobles para las pruebas de vistas (U10-T04):
// un `fetch` falso que enruta por `METHOD /ruta` (con `{id}`), cuenta las llamadas y devuelve JSON; una sesion de `analista`, `cro`... con o
// sin MFA reciente; y el entorno del step-up de `stepup-world`. Las pruebas miran lo que ve la persona y las solicitudes que salieron.
import { QueryClient } from "@tanstack/react-query";
import { act, cleanup, configure, render } from "@testing-library/react";
import type { User } from "oidc-client-ts";
import { afterEach, vi } from "vitest";
import { App } from "../../src/App";
import { type ApiClient, createApi } from "../../src/api/client";
import { createQueryClient } from "../../src/api/queryClient";
import { createTokenStore } from "../../src/auth/AuthProvider";
import type { InactivityEnv } from "../../src/inactivity/InactivityProvider";
import { Reporter } from "../../src/reporter/reporter";
import type { Role } from "../../src/views/shared/routes";
import type { StepUpEnv } from "../../src/stepup/StepUpProvider";
import type { Wiring } from "../../src/wiring";
import { LOADERS } from "../../src/views/shared/loaders";
import { Bus } from "./bus";
import { CALLBACK, FakeBackend, ManualTimers, OWN } from "./stepup-world";

afterEach(cleanup);

// Las vistas son fragmentos (`React.lazy`): se cargan UNA vez al importar este modulo, para que ningun caso espere un `import()` bajo la carga de
// la cobertura (la suite completa corre con 30 procesos y la instrumentacion); y las esperas de las consultas dan margen por la misma razon.
await Promise.all(Object.values(LOADERS).map((load) => load?.()));
configure({ asyncUtilTimeout: 5000 });

export interface Call {
  readonly method: string;
  readonly path: string;
  readonly search: URLSearchParams;
  readonly body: unknown;
}

export type Reply = Response | { readonly status: number; readonly body?: unknown };
export type Handler = (call: Call) => Reply | Promise<Reply>;

export function json(status: number, body?: unknown, type = "application/json"): Response {
  return body === undefined ? new Response(null, { status }) : new Response(JSON.stringify(body), { status, headers: { "content-type": type } });
}

/** Un `Problem` de U0 (`application/problem+json`). */
export function problem(status: number, code: string, reason?: string, extra: Record<string, unknown> = {}): Response {
  return json(
    status,
    { type: `urn:vectra:problem:${code}`, title: code, status, code, correlation_id: "0".repeat(32), ...(reason === undefined ? {} : { reason }), ...extra },
    "application/problem+json",
  );
}

function matcher(key: string): { method: string; pattern: RegExp } {
  const [method = "", path = ""] = key.split(" ");
  const source = path
    .split(/(\{[a-z_]+\})/)
    .map((part) => (part.startsWith("{") ? "([^/]+)" : part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
    .join("");
  return { method, pattern: new RegExp(`^${source}$`) };
}

export interface World {
  readonly calls: Call[];
  readonly handlers: Map<string, Handler>;
  /** Cuantas veces salio una solicitud `METHOD /ruta` (con `{id}` casando cualquier segmento). */
  count(key: string): number;
  on(key: string, handler: Handler | unknown): void;
}

export function createWorld(routes: Record<string, Handler | unknown> = {}): World {
  const handlers = new Map<string, Handler>();
  const calls: Call[] = [];
  const asHandler = (value: Handler | unknown): Handler =>
    typeof value === "function" ? (value as Handler) : () => ({ status: 200, body: value });
  for (const [key, value] of Object.entries(routes)) handlers.set(key, asHandler(value));
  return {
    calls,
    handlers,
    count: (key) => {
      const { method, pattern } = matcher(key);
      return calls.filter((call) => call.method === method && pattern.test(call.path)).length;
    },
    on: (key, handler) => {
      handlers.set(key, asHandler(handler));
    },
  };
}

function fakeFetch(world: World): typeof fetch {
  return (async (input: Request) => {
    const url = new URL(input.url);
    const text = input.method === "GET" || input.method === "HEAD" ? "" : await input.clone().text();
    const call: Call = { method: input.method, path: url.pathname, search: url.searchParams, body: text === "" ? undefined : JSON.parse(text) };
    world.calls.push(call);
    for (const [key, handler] of world.handlers) {
      const { method, pattern } = matcher(key);
      if (method === call.method && pattern.test(call.path)) {
        const reply = await handler(call);
        return reply instanceof Response ? reply : json(reply.status, reply.body);
      }
    }
    return problem(404, "not_found");
  }) as unknown as typeof fetch;
}

/** Entorno del step-up con las ventanas, el backend y los temporizadores de prueba (como `stepup-ui.test.tsx`). */
export function stepUpWorld() {
  const backend = new FakeBackend();
  const timers = new ManualTimers();
  const popups: { closed: boolean; close(): void; location: { replace(url: string): void } }[] = [];
  const listeners = new Set<(event: MessageEvent) => void>();
  const env: StepUpEnv = {
    ownOrigin: OWN,
    stepupRedirectUri: CALLBACK,
    backend,
    openWindow: () => {
      const popup = { closed: false, close() { this.closed = true; }, location: { replace: () => undefined } };
      popups.push(popup);
      return popup;
    },
    timers,
    reportFailure: () => undefined,
    now: () => Date.now(),
    messageTarget: {
      addEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => {
        listeners.add(listener as (event: MessageEvent) => void);
      },
      removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => {
        listeners.delete(listener as (event: MessageEvent) => void);
      },
    },
  };
  const post = (over: Partial<{ origin: string; source: unknown; data: unknown }> = {}): void => {
    for (const listener of listeners) listener({ origin: OWN, source: popups[0], data: { code: "c", state: "state-1" }, ...over } as MessageEvent);
  };
  return { env, backend, timers, popups, post };
}

export interface Options {
  readonly role?: Role;
  /** `true`: la sesion trae MFA reciente (no pide «Verificar y confirmar»). */
  readonly mfa?: boolean;
  readonly path?: string;
  readonly routes?: Record<string, Handler | unknown>;
  readonly stepUp?: StepUpEnv;
  readonly inactivity?: InactivityEnv;
  readonly queryClient?: QueryClient;
}

export function renderApp(options: Options = {}) {
  const world = createWorld(options.routes);
  const tokens = createTokenStore();
  const reports: string[] = [];
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
  const api: ApiClient = createApi({ baseUrl: OWN, getToken: () => tokens.get(), fetchImpl: fakeFetch(world) });
  const authTime = new Date(Date.now() - (options.mfa === true ? 60_000 : 3_600_000)).toISOString();
  const wiring: Wiring = {
    manager: {
      getUser: async () => ({ access_token: "t" }) as User,
      signinRedirect: async () => undefined,
      signinCallback: async () => undefined,
      signoutRedirect: async () => undefined,
      events: { addUserLoaded: () => undefined, removeUserLoaded: () => undefined },
    },
    authPage: { callbackUrl: () => null, clean: () => undefined },
    tokens,
    queryClient: options.queryClient ?? createQueryClient(),
    api,
    loadSession: async () => ({ role: options.role ?? "analista", mfa: options.mfa === true, auth_time: authTime, locale: "es-CO" as const }),
    reporter,
    stepUpEnv: options.stepUp ?? stepUpWorld().env,
    inactivityEnv: options.inactivity ?? {
      now: () => Date.now(),
      setTimeout: (handler: () => void, ms: number) => setTimeout(handler, ms),
      clearTimeout: (handle: unknown) => {
        clearTimeout(handle as ReturnType<typeof setTimeout>);
      },
      createChannel: () => bus.channel(),
      target: document,
    },
  };
  window.history.pushState({}, "", options.path ?? "/casos");
  const view = render(<App wiring={wiring} />);
  return { world, wiring, reports, bus, ...view };
}

/** Deja correr las promesas y los temporizadores falsos `ms` milisegundos (con `vi.useFakeTimers()`), dentro de `act`. */
export async function flush(ms = 0): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
