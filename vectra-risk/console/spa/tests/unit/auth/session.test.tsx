// @vitest-environment jsdom
// BR-U10-05 con el `UserManager` REAL de `oidc-client-ts` y el login por REDIRECCION (decision del usuario, 2026-11-12) contra un
// servidor falso: login con PKCE, callback, refresco rotativo, `prompt=none` y logout. En cada paso: `localStorage` vacio, ninguna cookie
// y, en `sessionStorage`, como mucho la clave del flujo en curso (sin ningun token), que desaparece al terminar el callback, con exito
// o con error. Los tokens y el usuario viven en memoria: un `UserManager` nuevo (una recarga) no los ve. La navegacion de jsdom no
// existe: el navegador falso de redireccion captura la URL del emisor y el callback se entrega con `signinCallback(url)`.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createLoginStateStorage } from "../../../src/auth/loginStateStorage";
import { createUserManager } from "../../../src/auth/manager";
import type { AppConfig } from "../../../src/config/load";

const ORIGIN = window.location.origin;
const AUTHORITY = `${ORIGIN}/auth/realms/vectra`;
const CONFIG: AppConfig = {
  oidc: { authority: AUTHORITY, client_id: "vectra-console" },
  redirect_uri: `${ORIGIN}/callback`,
  stepup_redirect_uri: `${ORIGIN}/stepup-callback`,
  grafana: { bias_dashboard_uid: "bias" },
};

const b64 = (value: unknown): string => btoa(JSON.stringify(value)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
const jwt = (claims: Record<string, unknown>): string => `${b64({ alg: "RS256", kid: "k1" })}.${b64(claims)}.firma`;

interface Server {
  tokenCalls: URLSearchParams[];
  refreshIssued: string[];
  /** El `nonce` de la ultima solicitud de autorizacion: el ID token lo devuelve, como un emisor real. */
  nonce: string | null;
}

function fakeServer(): Server {
  const server: Server = { tokenCalls: [], refreshIssued: [], nonce: null };
  let counter = 0;
  const authTime = Math.floor(Date.now() / 1000); // como en un IdP: `auth_time` es de la sesion y no cambia con cada token
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input instanceof Request ? input.url : input);
      const json = (data: unknown) => new Response(JSON.stringify(data), { headers: { "content-type": "application/json" } });
      if (url.endsWith("/.well-known/openid-configuration")) {
        return json({
          issuer: AUTHORITY,
          authorization_endpoint: `${AUTHORITY}/protocol/openid-connect/auth`,
          token_endpoint: `${AUTHORITY}/protocol/openid-connect/token`,
          end_session_endpoint: `${AUTHORITY}/protocol/openid-connect/logout`,
          jwks_uri: `${AUTHORITY}/protocol/openid-connect/certs`,
        });
      }
      const body = new URLSearchParams(String(init?.body));
      server.tokenCalls.push(body);
      counter += 1;
      const now = Math.floor(Date.now() / 1000);
      const refresh = `refresh-${counter}`;
      server.refreshIssued.push(refresh);
      return json({
        access_token: `access-${counter}`,
        token_type: "Bearer",
        expires_in: 300,
        refresh_token: refresh,
        scope: "openid",
        id_token: jwt({
          iss: AUTHORITY,
          sub: "analista",
          aud: "vectra-console",
          exp: now + 300,
          iat: now,
          auth_time: authTime,
          acr: "pwd",
          ...(server.nonce === null ? {} : { nonce: server.nonce }),
        }),
      });
    }),
  );
  return server;
}

const flowKeys = (): string[] => Object.keys(sessionStorage);
const stored = (): string => JSON.stringify(Object.entries(sessionStorage));
const snapshot = () => ({ local: localStorage.length, cookie: document.cookie, href: window.location.href });

/** Un navegador de redireccion falso: captura la URL del emisor (jsdom no navega) y, como el real, nunca vuelve. */
function redirectNavigator() {
  const urls: string[] = [];
  const navigator = {
    prepare: async () => ({
      navigate: async (params: { url: string }) => {
        urls.push(params.url);
        return await new Promise<never>(() => undefined);
      },
      close: () => undefined,
    }),
    callback: async () => undefined,
  };
  return { urls, navigator: navigator as never };
}

/** Lo que haria el emisor al volver: `/callback?code=...&state=...` o `?error=...&state=...`. */
function emitterReturn(authorizeUrl: string, result: "code" | { error: string }): string {
  const url = new URL(authorizeUrl);
  const query = result === "code" ? "code=codigo" : `error=${result.error}`;
  return `${url.searchParams.get("redirect_uri")}?${query}&state=${url.searchParams.get("state")}`;
}

/** Una carga de pagina: el `UserManager` es nuevo (memoria vacia) y el `sessionStorage` es el del navegador. */
function pageLoad(server: Server) {
  const { urls, navigator } = redirectNavigator();
  const manager = createUserManager(CONFIG, ORIGIN, createLoginStateStorage(window), [navigator]);
  return { manager, urls, server };
}

beforeEach(() => {
  vi.useRealTimers();
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("el ciclo de la sesion en memoria, con login por redireccion", () => {
  it("login (PKCE) -> callback -> refresco rotativo -> logout: tokens solo en memoria; en sessionStorage solo la clave del flujo en curso", async () => {
    const server = fakeServer();
    const before = snapshot();

    // 1. clic en «Iniciar sesion»: redireccion al emisor; el estado transitorio queda en sessionStorage, y solo ese
    const first = pageLoad(server);
    expect(await first.manager.getUser()).toBeNull();
    void first.manager.signinRedirect({ state: { mode: "interactive" }, nonce: "n-login" });
    await vi.waitFor(() => expect(first.urls).toHaveLength(1));
    const authorize = new URL(first.urls[0] as string);
    expect(authorize.pathname).toBe("/auth/realms/vectra/protocol/openid-connect/auth");
    expect(authorize.searchParams.get("response_type")).toBe("code");
    expect(authorize.searchParams.get("code_challenge_method")).toBe("S256");
    expect(authorize.searchParams.get("redirect_uri")).toBe(CONFIG.redirect_uri);
    expect(authorize.searchParams.get("code_challenge")).toMatch(/^[\w-]{43}$/);
    expect(authorize.searchParams.get("nonce")).toBe("n-login");
    expect(authorize.searchParams.get("prompt")).toBeNull();
    server.nonce = "n-login";
    expect(flowKeys()).toEqual([`oidc.${authorize.searchParams.get("state")}`]); // UNA clave por flujo
    expect(stored()).toContain("code_verifier"); // el verificador PKCE esta ahi: es lo que sobrevive a la redireccion
    expect(snapshot()).toEqual(before);

    // 2. la redireccion completa recarga la pagina: la memoria se pierde, el sessionStorage no. `/callback` canjea en esa misma pagina
    const second = pageLoad(server);
    const loaded: string[] = [];
    second.manager.events.addUserLoaded((user) => {
      loaded.push(user.access_token);
    });
    expect(await second.manager.getUser()).toBeNull(); // sin tokens en el almacenamiento: nada que restaurar
    const user = await second.manager.signinCallback(emitterReturn(authorize.toString(), "code"));
    expect(user?.access_token).toBe("access-1");
    expect(loaded).toEqual(["access-1"]); // `userLoaded` una sola vez: `get_me` se pide una vez
    expect(server.tokenCalls[0]?.get("grant_type")).toBe("authorization_code");
    expect(server.tokenCalls[0]?.get("code_verifier")).toMatch(/^[\w-]{43,128}$/);
    expect(user?.profile["acr"]).toBe("pwd"); // `acr` y `auth_time` llegan al perfil (FILTER_PROTOCOL_CLAIMS)
    expect(user?.profile["auth_time"]).toBeTypeOf("number");
    expect(flowKeys()).toEqual([]); // la clave del flujo se borro al terminar el callback
    expect(stored()).not.toMatch(/access-1|refresh-1|id_token|refresh_token/);
    expect((await second.manager.getUser())?.access_token).toBe("access-1"); // en memoria
    expect(snapshot()).toEqual(before);

    // 3. refresco: con el refresh token (sin iframe), que rota
    const refreshed = await second.manager.signinSilent();
    expect(server.tokenCalls[1]?.get("grant_type")).toBe("refresh_token");
    expect(server.tokenCalls[1]?.get("refresh_token")).toBe("refresh-1");
    expect(refreshed?.access_token).toBe("access-2");
    expect(refreshed?.refresh_token).toBe("refresh-2");
    expect(flowKeys()).toEqual([]);
    expect(snapshot()).toEqual(before);

    // 4. otra recarga: un `UserManager` nuevo no ve nada (los tokens nunca salieron de la memoria)
    expect(await pageLoad(server).manager.getUser()).toBeNull();

    // 5. logout: va al `end_session_endpoint` con `id_token_hint` y borra la memoria
    void second.manager.signoutRedirect();
    await vi.waitFor(() => expect(second.urls).toHaveLength(1));
    const logout = new URL(second.urls[0] as string);
    expect(logout.pathname).toBe("/auth/realms/vectra/protocol/openid-connect/logout");
    expect(logout.searchParams.get("id_token_hint")).toBeTruthy();
    expect(logout.searchParams.get("post_logout_redirect_uri")).toBe(`${ORIGIN}/`);
    expect(await second.manager.getUser()).toBeNull();
    expect(flowKeys()).toEqual([]);
    expect(snapshot()).toEqual(before);
    second.manager.stopSilentRenew();
  });

  it("recarga: prompt=none por redireccion; sin sesion el emisor devuelve login_required, el callback falla con el modo del flujo y la clave se borra", async () => {
    const server = fakeServer();
    const first = pageLoad(server);
    void first.manager.signinRedirect({ prompt: "none", state: { mode: "silent" }, nonce: "n-silent" });
    await vi.waitFor(() => expect(first.urls).toHaveLength(1));
    const url = new URL(first.urls[0] as string);
    expect(url.searchParams.get("prompt")).toBe("none");
    expect(url.searchParams.get("redirect_uri")).toBe(CONFIG.redirect_uri);
    expect(flowKeys()).toHaveLength(1);

    const second = pageLoad(server);
    const error = await second.manager.signinCallback(emitterReturn(url.toString(), { error: "login_required" })).catch((e: unknown) => e);
    expect(error).toMatchObject({ error: "login_required", state: { mode: "silent" } });
    expect(flowKeys()).toEqual([]); // se borra tambien con error
    expect(server.tokenCalls).toHaveLength(0);
    expect(snapshot().local).toBe(0);
  });

  it("prompt=none con sesion en el emisor: entra sin interaccion y deja el almacenamiento limpio", async () => {
    const server = fakeServer();
    const first = pageLoad(server);
    void first.manager.signinRedirect({ prompt: "none", state: { mode: "silent" }, nonce: "n2" });
    await vi.waitFor(() => expect(first.urls).toHaveLength(1));
    server.nonce = "n2";
    const user = await pageLoad(server).manager.signinCallback(emitterReturn(first.urls[0] as string, "code"));
    expect(user?.access_token).toBe("access-1");
    expect(flowKeys()).toEqual([]);
  });

  it("sin iframe ni ventana emergente: silent_redirect_uri y popup_redirect_uri vacios, y sin refresh token el refresco falla en vez de abrir un iframe", async () => {
    const server = fakeServer();
    const { manager } = pageLoad(server);
    expect(manager.settings.silent_redirect_uri).toBe("");
    expect(manager.settings.popup_redirect_uri).toBe("");
    await expect(manager.signinPopup()).rejects.toThrow("No popup_redirect_uri configured");
    await expect(manager.signinSilent()).rejects.toThrow("No silent_redirect_uri configured");
    manager.stopSilentRenew();
  });
});
