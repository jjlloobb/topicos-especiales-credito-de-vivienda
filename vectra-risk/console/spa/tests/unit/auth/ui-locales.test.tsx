// @vitest-environment jsdom
// Enmienda del 2026-11-21: cada peticion de autorizacion de la SPA (login silencioso `prompt=none`, login interactivo y step-up) lleva el
// parametro estandar de OIDC `ui_locales` con el idioma activo de la consola (`es` o `en`, un conjunto cerrado), para que el login del emisor
// salga en el mismo idioma. Nada mas del flujo cambia: PKCE, `state`, `redirect_uri`, `prompt`, `max_age` y `acr_values` siguen igual.
// Se prueba en dos capas: lo que `AuthProvider` y el backend del step-up piden a la libreria, y la URL de autorizacion que `oidc-client-ts`
// de verdad construye (`UserManager` y `OidcClient` reales, sin red: los metadatos del emisor son estaticos).
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { InMemoryWebStorage, OidcClient, WebStorageStateStore } from "oidc-client-ts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { type AuthManager, AuthProvider, type SigninArgs, useAuth } from "../../../src/auth/AuthProvider";
import { createTokenStore } from "../../../src/auth/AuthProvider";
import { issuerMetadata } from "../../../src/auth/issuer-metadata";
import { createLoginStateStorage } from "../../../src/auth/loginStateStorage";
import { createUserManager, SCOPE } from "../../../src/auth/manager";
import type { AppConfig } from "../../../src/config/load";
import { chooseLanguage, initLanguage, LANGUAGES } from "../../../src/i18n/language";
import { createOidcBackend, FILTER_PROTOCOL_CLAIMS } from "../../../src/stepup/oidc";

const ORIGIN = "https://console.test";
const CONFIG: AppConfig = {
  oidc: { authority: `${ORIGIN}/auth/realms/vectra`, client_id: "vectra-console" },
  redirect_uri: `${ORIGIN}/callback`,
  stepup_redirect_uri: `${ORIGIN}/stepup-callback`,
  grafana: { bias_dashboard_uid: "bias" },
};

afterEach(() => {
  cleanup();
  initLanguage(); // vuelve a espanol
  sessionStorage.clear();
});

function Login() {
  const auth = useAuth();
  return (
    <button type="button" onClick={auth.login}>
      entrar
    </button>
  );
}

/** Monta `AuthProvider` sin sesion en memoria y devuelve los argumentos de cada `signinRedirect`. */
function mountAnonymous(callbackError = false) {
  const calls: SigninArgs[] = [];
  const manager: AuthManager = {
    getUser: async () => null,
    signinRedirect: async (args) => {
      calls.push(args);
    },
    signinCallback: async () => Promise.reject(Object.assign(new Error("login_required"), { error: "login_required", state: { mode: "silent" } })),
    signoutRedirect: async () => undefined,
    events: { addUserLoaded: () => undefined, removeUserLoaded: () => undefined },
  };
  const page = { callbackUrl: () => (callbackError ? `${ORIGIN}/callback?error=login_required&state=s` : null), clean: () => undefined, target: () => null };
  render(
    <AuthProvider manager={manager} loadSession={vi.fn()} tokens={createTokenStore()} page={page}>
      <Login />
    </AuthProvider>,
  );
  return calls;
}

describe("AuthProvider pide ui_locales con el idioma activo", () => {
  it.each(LANGUAGES)("login silencioso (prompt=none) en %s", async (language) => {
    chooseLanguage(language);
    const calls = mountAnonymous();
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]).toEqual({ prompt: "none", state: { mode: "silent" }, nonce: expect.stringMatching(/^[0-9a-f-]{36}$/), ui_locales: language });
  });

  it("login interactivo: el idioma del momento del clic, y cambia al cambiar el idioma", async () => {
    const calls = mountAnonymous(true); // el `prompt=none` ya volvio sin sesion: queda el boton
    const button = await screen.findByRole("button", { name: "entrar" });
    fireEvent.click(button);
    chooseLanguage("en");
    fireEvent.click(button);
    chooseLanguage("es");
    fireEvent.click(button);
    expect(calls.map((call) => call.ui_locales)).toEqual(["es", "en", "es"]);
    for (const call of calls) {
      expect(call).toEqual({ state: { mode: "interactive" }, nonce: expect.stringMatching(/^[0-9a-f-]{36}$/), ui_locales: call.ui_locales });
      expect(call).not.toHaveProperty("prompt");
    }
  });
});

/** Un navegador de redireccion de prueba para el `UserManager` real: guarda la URL a la que iria. */
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

describe("la URL de autorizacion que construye oidc-client-ts lleva ui_locales y nada mas cambia", () => {
  it.each(LANGUAGES)("login silencioso e interactivo del UserManager real, en %s", async (language) => {
    chooseLanguage(language);
    const { urls, navigator } = redirectNavigator();
    const manager = createUserManager(CONFIG, ORIGIN, createLoginStateStorage(window), [navigator]);
    const args: SigninArgs[] = [];
    const recording: AuthManager = {
      getUser: () => manager.getUser(),
      signinRedirect: async (given) => {
        args.push(given);
        void manager.signinRedirect(given); // nunca resuelve: el navegador se iria de la pagina
      },
      signinCallback: async () => Promise.reject(Object.assign(new Error("login_required"), { error: "login_required", state: { mode: "silent" } })),
      signoutRedirect: async () => undefined,
      events: { addUserLoaded: () => undefined, removeUserLoaded: () => undefined },
    };
    render(
      <AuthProvider manager={recording} loadSession={vi.fn()} tokens={createTokenStore()} page={{ callbackUrl: () => null, clean: () => undefined, target: () => null }}>
        <Login />
      </AuthProvider>,
    );
    await vi.waitFor(() => expect(urls).toHaveLength(1));
    fireEvent.click(screen.getByRole("button", { name: "entrar" }));
    await vi.waitFor(() => expect(urls).toHaveLength(2));
    const [silent, interactive] = urls.map((url) => new URL(url)) as [URL, URL];
    for (const url of [silent, interactive]) {
      expect(url.pathname).toBe("/auth/realms/vectra/protocol/openid-connect/auth");
      expect(url.searchParams.getAll("ui_locales")).toEqual([language]);
      expect(url.searchParams.get("client_id")).toBe("vectra-console");
      expect(url.searchParams.get("redirect_uri")).toBe(CONFIG.redirect_uri);
      expect(url.searchParams.get("response_type")).toBe("code");
      expect(url.searchParams.get("scope")).toBe(SCOPE);
      expect(url.searchParams.get("code_challenge_method")).toBe("S256");
      expect(url.searchParams.get("code_challenge")).toMatch(/^[\w-]{43}$/);
      expect(url.searchParams.get("state")).toMatch(/^[0-9a-f]{32}$/);
      expect(url.searchParams.get("nonce")).toMatch(/^[0-9a-f-]{36}$/);
      expect(url.searchParams.has("kc_locale")).toBe(false);
    }
    expect(silent.searchParams.get("prompt")).toBe("none");
    expect(interactive.searchParams.get("prompt")).toBeNull();
    // exactamente los parametros de siempre mas `ui_locales`
    const names = (url: URL): string[] => [...url.searchParams.keys()].sort();
    const common = ["client_id", "code_challenge", "code_challenge_method", "nonce", "redirect_uri", "response_type", "scope", "state", "ui_locales"];
    expect(names(interactive)).toEqual(common);
    expect(names(silent)).toEqual([...common, "prompt"].sort());
  });

  it.each(LANGUAGES)("step-up con el OidcClient real, en %s: prompt=login, max_age=0 y acr_values=mfa siguen; se anade ui_locales", async (language) => {
    chooseLanguage(language);
    const store = new WebStorageStateStore({ store: new InMemoryWebStorage() });
    const client = new OidcClient({
      authority: CONFIG.oidc.authority,
      metadata: issuerMetadata(CONFIG.oidc.authority),
      client_id: CONFIG.oidc.client_id,
      redirect_uri: CONFIG.stepup_redirect_uri,
      response_type: "code",
      scope: SCOPE,
      filterProtocolClaims: FILTER_PROTOCOL_CLAIMS,
      stateStore: store,
    });
    const backend = createOidcBackend(client, store, CONFIG.stepup_redirect_uri, () => undefined);
    const url = new URL((await backend.createRequest()).url);
    expect(url.searchParams.getAll("ui_locales")).toEqual([language]);
    expect(url.searchParams.get("prompt")).toBe("login");
    expect(url.searchParams.get("max_age")).toBe("0");
    expect(url.searchParams.get("acr_values")).toBe("mfa");
    expect(url.searchParams.get("redirect_uri")).toBe(CONFIG.stepup_redirect_uri);
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect([...url.searchParams.keys()].sort()).toEqual(
      ["acr_values", "client_id", "code_challenge", "code_challenge_method", "max_age", "nonce", "prompt", "redirect_uri", "response_type", "scope", "state", "ui_locales"].sort(),
    );
    // y sigue al idioma: la siguiente peticion, ya en el otro
    const other = language === "es" ? "en" : "es";
    chooseLanguage(other);
    expect(new URL((await backend.createRequest()).url).searchParams.get("ui_locales")).toBe(other);
    expect(sessionStorage.length).toBe(0); // el step-up sigue sin tocar el almacenamiento
  });
});
