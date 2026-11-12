// @vitest-environment jsdom
// BR-U10-05 de punta a punta con el `UserManager` REAL de `oidc-client-ts` (login con PKCE, refresco rotativo, login silencioso y
// logout) contra un servidor falso: `localStorage`, `sessionStorage` y `document.cookie` no cambian en ningun paso, y la URL no
// recibe `code` ni `state`. El `window.open` y el iframe de jsdom no navegan: la prueba entrega el `postMessage` del callback.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
}

function fakeServer(): Server {
  const server: Server = { tokenCalls: [], refreshIssued: [] };
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
        id_token: jwt({ iss: AUTHORITY, sub: "analista", aud: "vectra-console", exp: now + 300, iat: now, auth_time: authTime, acr: "pwd" }),
      });
    }),
  );
  return server;
}

const snapshot = () => ({ local: localStorage.length, session: sessionStorage.length, cookie: document.cookie, href: window.location.href });

/** Entrega el `postMessage` que haria `/callback` en la ventana hija (el protocolo de `oidc-client-ts`). */
function deliverCallback(authorizeUrl: string): void {
  const url = new URL(authorizeUrl);
  const callback = `${url.searchParams.get("redirect_uri")}?code=codigo&state=${url.searchParams.get("state")}`;
  window.dispatchEvent(new MessageEvent("message", { data: { source: "oidc-client", url: callback, keepOpen: false }, origin: ORIGIN }));
}

beforeEach(() => {
  vi.useRealTimers();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("el ciclo de la sesion en memoria", () => {
  it("login (PKCE), refresco rotativo, login silencioso y logout: nada de almacenamiento y la URL limpia", async () => {
    const server = fakeServer();
    const before = snapshot();
    const popup = { closed: false, close: vi.fn(), focus: vi.fn(), location: { replace: vi.fn() } };
    const open = vi.spyOn(window, "open").mockReturnValue(popup as unknown as Window);
    const navigated: string[] = [];
    const redirect = {
      prepare: async () => ({
        navigate: async (params: { url: string }) => {
          navigated.push(params.url);
          return await new Promise<never>(() => undefined);
        },
        close: () => undefined,
      }),
      callback: async () => undefined,
    };
    // El iframe del login silencioso: jsdom no navega, asi que el navegador falso devuelve la respuesta del callback para ese `state`.
    const silentUrls: string[] = [];
    const iframe = {
      prepare: async () => ({
        navigate: async (params: { url: string }) => {
          silentUrls.push(params.url);
          const url = new URL(params.url);
          return { url: `${url.searchParams.get("redirect_uri")}?code=codigo&state=${url.searchParams.get("state")}` };
        },
        close: () => undefined,
      }),
      callback: async () => undefined,
    };
    const manager = createUserManager(CONFIG, ORIGIN, [redirect as never, undefined, iframe as never]);
    const loaded: string[] = [];
    manager.events.addUserLoaded((user) => {
      loaded.push(user.access_token);
    });

    // 1. login: la ventana se abre de forma sincrona dentro de la llamada (el clic) y el flujo es codigo + PKCE S256
    expect(await manager.getUser()).toBeNull();
    const login = manager.signinPopup();
    expect(open).toHaveBeenCalledTimes(1);
    await vi.waitFor(() => expect(popup.location.replace).toHaveBeenCalled());
    const authorize = new URL(popup.location.replace.mock.calls[0]?.[0] as string);
    expect(authorize.pathname).toBe("/auth/realms/vectra/protocol/openid-connect/auth");
    expect(authorize.searchParams.get("response_type")).toBe("code");
    expect(authorize.searchParams.get("code_challenge_method")).toBe("S256");
    expect(authorize.searchParams.get("redirect_uri")).toBe(CONFIG.redirect_uri);
    expect(authorize.searchParams.get("code_challenge")).toMatch(/^[\w-]{43}$/);
    deliverCallback(authorize.toString());
    const user = await login;
    expect(user.access_token).toBe("access-1");
    expect(server.tokenCalls[0]?.get("grant_type")).toBe("authorization_code");
    expect(server.tokenCalls[0]?.get("code_verifier")).toMatch(/^[\w-]{43,128}$/); // el verificador estaba en memoria
    expect(user.profile["acr"]).toBe("pwd"); // `acr` y `auth_time` llegan al perfil (FILTER_PROTOCOL_CLAIMS)
    expect(user.profile["auth_time"]).toBeTypeOf("number");
    expect(snapshot()).toEqual(before);

    // 2. refresco: con el refresh token, que rota
    const refreshed = await manager.signinSilent();
    expect(server.tokenCalls[1]?.get("grant_type")).toBe("refresh_token");
    expect(server.tokenCalls[1]?.get("refresh_token")).toBe("refresh-1");
    expect(refreshed?.access_token).toBe("access-2");
    expect(refreshed?.refresh_token).toBe("refresh-2"); // rotado
    expect(snapshot()).toEqual(before);

    // 3. recarga / pestana nueva: otro UserManager sin nada en memoria -> prompt=none (iframe)
    const reloaded = createUserManager(CONFIG, ORIGIN, [redirect as never, undefined, iframe as never]);
    expect(await reloaded.getUser()).toBeNull();
    const silentUser = await reloaded.signinSilent();
    const silent = new URL(silentUrls[0] as string);
    expect(silent.searchParams.get("prompt")).toBe("none");
    expect(silent.searchParams.get("code_challenge_method")).toBe("S256");
    expect(silent.searchParams.get("redirect_uri")).toBe(CONFIG.redirect_uri);
    expect(server.tokenCalls[2]?.get("grant_type")).toBe("authorization_code");
    expect(silentUser?.access_token).toBe("access-3");
    expect(snapshot()).toEqual(before);

    // 4. logout: borra la memoria y va al `end_session_endpoint`
    void manager.signoutRedirect();
    await vi.waitFor(() => expect(navigated).toHaveLength(1));
    const logout = new URL(navigated[0] as string);
    expect(logout.pathname).toBe("/auth/realms/vectra/protocol/openid-connect/logout");
    expect(logout.searchParams.get("id_token_hint")).toBeTruthy();
    expect(logout.searchParams.get("post_logout_redirect_uri")).toBe(`${ORIGIN}/`);
    expect(await manager.getUser()).toBeNull();
    expect(snapshot()).toEqual(before);
    expect(window.location.search).toBe(""); // sin `code` ni `state` en la URL
    expect(loaded).toEqual(["access-1", "access-2"]);
    manager.stopSilentRenew();
    reloaded.stopSilentRenew();
  });
});
